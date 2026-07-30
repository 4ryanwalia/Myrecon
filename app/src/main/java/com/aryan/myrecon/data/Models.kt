package com.aryan.myrecon.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

/**
 * Wire models for the MyRecon API.
 *
 * Every field is optional with a default. The backend degrades gracefully when
 * a source is unreachable — it returns a partial document rather than an error
 * — so a strict model would turn a usable partial result into a crash. Missing
 * data is a normal outcome here, not an exception.
 */

// ── Username ─────────────────────────────────────────────────────

@Serializable
data class UsernameResult(
    val status: String = "ok",
    val query: UsernameQuery = UsernameQuery(),
    val summary: UsernameSummary = UsernameSummary(),
    val results: UsernameBuckets = UsernameBuckets(),
    @SerialName("identity_clusters") val identityClusters: List<JsonElement> = emptyList(),
)

@Serializable
data class UsernameQuery(val username: String = "", val deep: Boolean = false)

@Serializable
data class UsernameSummary(
    val total: Int = 0,
    val profiles: Int = 0,
    val documents: Int = 0,
    val mentions: Int = 0,
    val clusters: Int = 0,
)

@Serializable
data class UsernameBuckets(
    val profiles: List<Profile> = emptyList(),
    val documents: List<Profile> = emptyList(),
    val mentions: List<Profile> = emptyList(),
)

@Serializable
data class Profile(
    val url: String = "",
    val title: String = "",
    val platform: String = "",
    val category: String = "",
    val confidence: String? = null,
    val exists: Boolean = false,
    val bio: String? = null,
    @SerialName("profile_pic_url") val profilePicUrl: String? = null,
    @SerialName("avatar_url") val avatarUrl: String? = null,
    @SerialName("display_name") val displayName: String? = null,
    val followers: Int? = null,
    val verified: Boolean? = null,
) {
    val avatar: String? get() = profilePicUrl ?: avatarUrl
}

// ── Email ────────────────────────────────────────────────────────

@Serializable
data class EmailResult(
    val query: EmailQuery = EmailQuery(),
    val analysis: EmailAnalysis = EmailAnalysis(),
    val summary: EmailSummary = EmailSummary(),
    val breaches: Breaches = Breaches(),
    val darkweb: DarkWeb = DarkWeb(),
    val gravatar: Gravatar = Gravatar(),
    val github: GitHubAccount? = null,
)

@Serializable
data class EmailQuery(val email: String = "")

@Serializable
data class EmailAnalysis(
    val provider: String = "",
    @SerialName("provider_type") val providerType: String = "",
    val deliverable: Boolean = false,
    val disposable: Boolean = false,
    val format: String = "",
    @SerialName("plus_addressing") val plusAddressing: Boolean = false,
    @SerialName("mx_hosts") val mxHosts: List<String> = emptyList(),
)

@Serializable
data class EmailSummary(
    val breached: Boolean = false,
    @SerialName("breach_count") val breachCount: Int = 0,
    @SerialName("records_found") val recordsFound: Long = 0,
    @SerialName("records_exposed") val recordsExposed: Long = 0,
    @SerialName("risk_label") val riskLabel: String = "",
    @SerialName("risk_score") val riskScore: Int = 0,
    @SerialName("linked_accounts") val linkedAccounts: List<String> = emptyList(),
    val deliverable: Boolean = false,
    val disposable: Boolean = false,
)

@Serializable
data class Breaches(
    val breached: Boolean = false,
    val count: Int = 0,
    val fields: List<String> = emptyList(),
)

@Serializable
data class DarkWeb(
    val breached: Boolean = false,
    val count: Int = 0,
    @SerialName("risk_label") val riskLabel: String = "",
    @SerialName("risk_score") val riskScore: Int = 0,
    @SerialName("records_exposed") val recordsExposed: Long = 0,
    val breaches: List<BreachDetail> = emptyList(),
    val timeline: List<TimelinePoint> = emptyList(),
    @SerialName("exposed_data") val exposedData: List<ExposedData> = emptyList(),
    val pastes: Int = 0,
    val error: String? = null,
)

@Serializable
data class BreachDetail(
    val name: String = "",
    val domain: String = "",
    val date: String = "",
    val records: Long = 0,
    val industry: String = "",
    val verified: Boolean = false,
    @SerialName("password_risk") val passwordRisk: String = "",
    val logo: String = "",
    val exposed: List<String> = emptyList(),
    val details: String = "",
)

@Serializable
data class TimelinePoint(val year: Int = 0, val count: Int = 0)

@Serializable
data class ExposedData(val name: String = "", val category: String = "", val count: Int = 0)

@Serializable
data class Gravatar(
    val exists: Boolean = false,
    @SerialName("display_name") val displayName: String? = null,
    @SerialName("profile_url") val profileUrl: String? = null,
    val bio: String? = null,
    @SerialName("avatar_url") val avatarUrl: String? = null,
)

@Serializable
data class GitHubAccount(
    val username: String = "",
    val url: String = "",
    @SerialName("avatar_url") val avatarUrl: String = "",
)

// ── Network (domain / dns / ip) ──────────────────────────────────

@Serializable
data class DomainResult(
    val found: Boolean = false,
    val query: DomainQuery = DomainQuery(),
    val whois: Whois = Whois(),
    val dns: JsonElement? = null,
    @SerialName("primary_ip") val primaryIp: String? = null,
    val error: String? = null,
)

@Serializable
data class DomainQuery(val domain: String = "")

@Serializable
data class Whois(
    val registrar: String? = null,
    val created: String? = null,
    val expires: String? = null,
    val updated: String? = null,
    val status: List<String> = emptyList(),
    val nameservers: List<String> = emptyList(),
)

@Serializable
data class DnsResult(
    val query: DomainQuery = DomainQuery(),
    val records: Map<String, List<DnsRecord>> = emptyMap(),
    val summary: DnsSummary = DnsSummary(),
)

@Serializable
data class DnsRecord(val value: String = "", val ttl: Int? = null)

@Serializable
data class DnsSummary(@SerialName("total_records") val totalRecords: Int = 0)

@Serializable
data class IpResult(
    val found: Boolean = false,
    val query: IpQuery = IpQuery(),
    val geo: Geo = Geo(),
    val network: Network = Network(),
    @SerialName("reverse_dns") val reverseDns: String? = null,
    val error: String? = null,
)

@Serializable
data class IpQuery(val ip: String = "")

@Serializable
data class Geo(
    val city: String? = null,
    val region: String? = null,
    val country: String? = null,
    val lat: Double? = null,
    val lon: Double? = null,
    val timezone: String? = null,
)

@Serializable
data class Network(
    val asn: String? = null,
    val org: String? = null,
    val isp: String? = null,
    val hosting: Boolean? = null,
)

// ── Investigation graph (deep search) ────────────────────────────

@Serializable
data class InvestigationResult(
    val status: String = "ok",
    val handle: String = "",
    val graph: Graph = Graph(),
    val assessment: Assessment = Assessment(),
)

@Serializable
data class Graph(
    val nodes: List<GraphNode> = emptyList(),
    val edges: List<GraphEdge> = emptyList(),
    val clusters: List<Cluster> = emptyList(),
    val summary: GraphSummary = GraphSummary(),
)

@Serializable
data class GraphNode(
    val id: String = "",
    val type: String = "",
    val value: String = "",
    val label: String = "",
    val attrs: NodeAttrs = NodeAttrs(),
    val confidence: Confidence = Confidence(),
)

@Serializable
data class NodeAttrs(
    val platform: String? = null,
    val url: String? = null,
    val avatar: String? = null,
    val bio: String? = null,
    val title: String? = null,
)

@Serializable
data class GraphEdge(
    val id: String = "",
    val source: String = "",
    val target: String = "",
    val type: String = "",
    val confidence: Confidence = Confidence(),
)

@Serializable
data class Cluster(
    val id: String = "",
    val size: Int = 0,
    val label: String = "",
    val members: List<String> = emptyList(),
    val types: List<String> = emptyList(),
    val confidence: Confidence = Confidence(),
)

@Serializable
data class Confidence(
    val score: Int = 0,
    val band: String = "low",
    val factors: List<Factor> = emptyList(),
    @SerialName("source_count") val sourceCount: Int = 0,
)

@Serializable
data class Factor(val name: String = "", val weight: Int = 0)

@Serializable
data class GraphSummary(
    val entities: Int = 0,
    val relationships: Int = 0,
    val clusters: Int = 0,
)

@Serializable
data class Assessment(
    val text: String = "",
    val confidence: Confidence = Confidence(),
    @SerialName("generated_by") val generatedBy: String = "",
    val notes: List<String> = emptyList(),
)

// ── Streaming events ─────────────────────────────────────────────

/** One NDJSON line from a streaming endpoint. */
@Serializable
data class StreamEvent(
    val type: String = "",
    val phase: String? = null,
    val detail: String? = null,
    val percent: Double? = null,
    val error: String? = null,
    val data: JsonElement? = null,
)
