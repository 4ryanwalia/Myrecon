package com.aryan.myrecon.data

import com.aryan.myrecon.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * MyRecon backend client.
 *
 * OkHttp rather than Retrofit: only one call shape is needed (POST JSON), and
 * the streaming endpoints have to be read line-by-line off a raw source, which
 * Retrofit's converter layer gets in the way of.
 */
object ReconApi {

    val json = Json {
        ignoreUnknownKeys = true   // the backend adds fields; old builds must not break
        isLenient = true
        explicitNulls = false
        coerceInputValues = true   // null where a default exists → use the default
    }

    private val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()

    private val client = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        // A cold Render free-tier instance can take ~50s to wake, and a deep
        // sweep runs ~20s on top. Read timeout is generous for that reason;
        // the UI shows streaming progress so the wait is visible, not blank.
        .readTimeout(180, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    private fun request(path: String, body: String): Request =
        Request.Builder()
            .url(BuildConfig.API_BASE + path)
            .post(body.toRequestBody(JSON_MEDIA))
            .header("Accept", "application/json")
            .build()

    /** POST a JSON body and decode the response. */
    private suspend inline fun <reified T> post(path: String, body: String): T =
        withContext(Dispatchers.IO) {
            client.newCall(request(path, body)).execute().use { resp ->
                val text = resp.body?.string().orEmpty()
                if (!resp.isSuccessful) {
                    throw ApiException(friendlyError(resp.code, text))
                }
                json.decodeFromString<T>(text)
            }
        }

    /**
     * Read an NDJSON stream as a Flow of events.
     *
     * Emitting per line rather than buffering is the whole point: the caller
     * renders progress as it arrives. Collected on IO; the flow closes when the
     * response ends or the collector is cancelled.
     */
    private fun stream(path: String, body: String): Flow<StreamEvent> = callbackFlow {
        val call = client.newCall(request(path, body))
        try {
            call.execute().use { resp ->
                if (!resp.isSuccessful) {
                    throw ApiException(friendlyError(resp.code, resp.body?.string().orEmpty()))
                }
                val source = resp.body?.source() ?: throw ApiException("Empty response from the server.")
                while (!source.exhausted()) {
                    val line = source.readUtf8Line() ?: break
                    if (line.isBlank()) continue
                    // A malformed line should not kill an otherwise good scan.
                    val event = runCatching { json.decodeFromString<StreamEvent>(line) }.getOrNull()
                    if (event != null) trySend(event)
                }
            }
            close()
        } catch (e: Throwable) {
            close(e)
        }
        awaitClose { call.cancel() }
    }.flowOn(Dispatchers.IO)

    // ── Endpoints ────────────────────────────────────────────────

    suspend fun username(handle: String, deep: Boolean = false): UsernameResult =
        post("/api/username", """{"username":${handle.q()},"deep":$deep}""")

    fun usernameStream(handle: String, deep: Boolean = false): Flow<StreamEvent> =
        stream("/api/username/stream", """{"username":${handle.q()},"deep":$deep}""")

    suspend fun email(address: String): EmailResult =
        post("/api/email", """{"email":${address.q()}}""")

    suspend fun domain(domain: String): DomainResult =
        post("/api/domain", """{"domain":${domain.q()}}""")

    suspend fun dns(domain: String): DnsResult =
        post("/api/dns", """{"domain":${domain.q()}}""")

    suspend fun ip(address: String): IpResult =
        post("/api/ip", """{"ip":${address.q()}}""")

    fun investigateStream(handle: String, deep: Boolean = false): Flow<StreamEvent> =
        stream("/api/investigate/stream", """{"query":${handle.q()},"deep":$deep}""")

    /**
     * Profile detail for one platform, fetched through the server.
     *
     * The sweep runs on-device on purpose, and for almost everything that is
     * the better address to ask from. Instagram is the exception: it decides
     * by IP and by how much that IP has asked lately, and a phone it has
     * started refusing cannot talk its way back in. The server is usually a
     * different address, and its enricher has fallbacks the on-device probe
     * does not — measured the same minute, it returned a full profile for a
     * handle the local check could only get 401 for.
     *
     * Strictly additive: used to fill in an avatar the sweep could not get,
     * never to decide whether an account exists.
     */
    suspend fun enrich(platform: String, handle: String): EnrichResult =
        post("/api/enrich", """{"platform":${platform.q()},"username":${handle.q()}}""")

    // ── Helpers ──────────────────────────────────────────────────

    /** JSON-quote a string so a target containing quotes cannot break the body. */
    private fun String.q(): String = json.encodeToString(kotlinx.serialization.serializer(), this)

    /**
     * Turn an HTTP failure into something a person can act on.
     * The backend sends {"error": "..."} for validation problems — prefer that
     * message over a status code, since it explains what to change.
     */
    private fun friendlyError(code: Int, body: String): String {
        val serverMessage = runCatching {
            json.parseToJsonElement(body).let { el ->
                (el as? kotlinx.serialization.json.JsonObject)
                    ?.get("error")?.let { (it as? kotlinx.serialization.json.JsonPrimitive)?.content }
            }
        }.getOrNull()
        if (!serverMessage.isNullOrBlank()) return serverMessage
        return when (code) {
            422 -> "That input isn't valid for this lookup."
            429 -> "Too many lookups just now — wait a moment and try again."
            in 500..599 -> "The MyRecon service is having trouble. Try again shortly."
            else -> "Request failed (HTTP $code)."
        }
    }
}

class ApiException(message: String) : IOException(message)
