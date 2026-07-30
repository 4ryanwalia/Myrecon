package com.aryan.myrecon.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import kotlin.math.log2
import kotlin.math.pow

/**
 * Password exposure check, k-anonymity style.
 *
 * The password is SHA-1'd on the device and only the first five hex characters
 * of the digest are sent. That prefix is shared by thousands of unrelated
 * passwords, so it identifies nothing; the server returns every suffix under it
 * and the match happens locally.
 *
 * The password therefore reaches neither MyRecon's backend nor Have I Been
 * Pwned. `Add-Padding` makes the response a constant-ish size so an observer
 * cannot infer anything from its length either.
 *
 * Deliberately talks to api.pwnedpasswords.com directly rather than proxying
 * through the MyRecon backend — routing it through our own server would mean
 * the prefix, and the fact that a check happened, touched infrastructure we
 * control. Going direct is the stronger privacy claim and it is free.
 */
object PwnedPasswords {

    private const val RANGE_URL = "https://api.pwnedpasswords.com/range/"

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    data class Result(
        val breachCount: Long,
        val strength: Strength,
    ) {
        val breached: Boolean get() = breachCount > 0
    }

    data class Strength(
        val bits: Int,
        val label: String,
        val crackTime: String,
        val poolSize: Int,
        val length: Int,
    )

    /** @return how many times the password appears in the corpus; 0 means no match. */
    suspend fun check(password: String): Result = withContext(Dispatchers.IO) {
        require(password.isNotEmpty()) { "Password is empty." }

        val digest = MessageDigest.getInstance("SHA-1")
            .digest(password.toByteArray(Charsets.UTF_8))
        val hash = digest.joinToString("") { "%02X".format(it) }
        val prefix = hash.substring(0, 5)
        val suffix = hash.substring(5)

        val request = Request.Builder()
            .url(RANGE_URL + prefix)
            .header("Add-Padding", "true")
            .header("User-Agent", "MyRecon-Android/1.0")
            .build()

        val count = client.newCall(request).execute().use { resp ->
            if (!resp.isSuccessful) {
                throw ApiException("Breach corpus unavailable (HTTP ${resp.code}).")
            }
            val body = resp.body?.source() ?: throw ApiException("Empty response.")
            var found = 0L
            while (!body.exhausted()) {
                val line = body.readUtf8Line() ?: break
                val sep = line.indexOf(':')
                if (sep <= 0) continue
                if (line.regionMatches(0, suffix, 0, sep, ignoreCase = true)) {
                    // Padded rows are real-looking entries with a count of 0,
                    // so a match here is genuine only when the count is > 0.
                    found = line.substring(sep + 1).trim().toLongOrNull() ?: 0L
                    break
                }
            }
            found
        }

        Result(breachCount = count, strength = strengthOf(password))
    }

    /**
     * Entropy from the character pool actually used.
     *
     * This measures brute-force resistance only. A breached password is weak at
     * any entropy, which is why the corpus result always outranks this in the
     * verdict shown to the user.
     */
    fun strengthOf(pw: String): Strength {
        val pool = (if (pw.any { it in 'a'..'z' }) 26 else 0) +
            (if (pw.any { it in 'A'..'Z' }) 26 else 0) +
            (if (pw.any { it in '0'..'9' }) 10 else 0) +
            (if (pw.any { !it.isLetterOrDigit() }) 33 else 0)

        val bits = if (pool == 0) 0.0 else pw.length * log2(pool.toDouble())
        // ~100 billion guesses/sec: a mid-range GPU rig against a fast hash.
        val seconds = 2.0.pow(bits - 1) / 1e11

        val label = when {
            bits >= 100 -> "Excellent"
            bits >= 75 -> "Strong"
            bits >= 60 -> "Reasonable"
            bits >= 40 -> "Weak"
            else -> "Very weak"
        }
        return Strength(
            bits = bits.toInt(),
            label = label,
            crackTime = humanDuration(seconds),
            poolSize = pool,
            length = pw.length,
        )
    }

    fun humanDuration(seconds: Double): String {
        if (seconds < 1) return "instantly"
        var v = seconds
        val units = listOf("second" to 60.0, "minute" to 60.0, "hour" to 24.0, "day" to 365.0)
        for ((name, step) in units) {
            if (v < step) {
                val n = v.toLong()
                return "$n ${name}${if (n == 1L) "" else "s"}"
            }
            v /= step
        }
        if (v >= 1_000_000) return "millions of years"
        val n = v.toLong()
        return "$n year${if (n == 1L) "" else "s"}"
    }
}
