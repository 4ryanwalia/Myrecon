package com.aryan.myrecon.data

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Turns a result into something a person can send to someone else.
 *
 * Plain text, not a PDF or a rendered card. The people these reports get sent
 * to are a parent, a partner, a landlord or a police station, and every one of
 * those is reachable over WhatsApp or email — where text arrives readable on
 * any device, quotes cleanly in a reply, and needs no app to open.
 *
 * Every report carries the date and where the finding came from. A screenshot
 * of an app saying "dangerous" is worth very little to anyone who was not
 * there; the reasoning is the part that travels.
 */
object ReportText {

    private fun stamp(at: Long = System.currentTimeMillis()): String =
        SimpleDateFormat("d MMMM yyyy, HH:mm", Locale.getDefault()).format(Date(at))

    private fun header(title: String, subject: String, at: Long) = buildString {
        appendLine(title)
        appendLine("=".repeat(title.length))
        appendLine()
        appendLine(subject)
        appendLine("Checked on ${stamp(at)}")
        appendLine()
    }

    private fun footer() = buildString {
        appendLine()
        appendLine("---")
        appendLine("Checked with MyRecon, using public sources only.")
        appendLine("Results are evidence, not proof — see myrecon.xyz")
    }

    /** A username sweep: the report people most often want to forward. */
    fun forSweep(
        handle: String,
        profiles: List<SavedProfile>,
        at: Long = System.currentTimeMillis(),
    ): String = buildString {
        append(header("Accounts found for @$handle", "Searched: @$handle", at))

        if (profiles.isEmpty()) {
            appendLine("No accounts were found under this name.")
        } else {
            appendLine("${profiles.size} accounts carry this name:")
            appendLine()
            // Grouped by how sure we are, strongest first, because that is the
            // order the reader needs — a confident hit and a maybe should never
            // sit in one undifferentiated list.
            listOf(
                "high" to "Almost certainly this person",
                "medium" to "Likely",
                "low" to "Possible, unconfirmed",
            ).forEach { (band, title) ->
                val group = profiles.filter { it.confidence.equals(band, ignoreCase = true) }
                if (group.isEmpty()) return@forEach
                appendLine("$title (${group.size})")
                group.forEach { p ->
                    appendLine("  • ${p.platform} — ${p.url}")
                }
                appendLine()
            }
        }
        append(footer())
    }

    /** What a photo gives away, and what it says about its own origin. */
    fun forImage(
        name: String?,
        report: ImageForensics.Report,
        placeName: String?,
        at: Long = System.currentTimeMillis(),
    ): String = buildString {
        append(header("What this photo reveals", "Photo: ${name ?: "(no file name)"}", at))

        val origin = when (report.provenance.origin) {
            ImageProvenance.Origin.DeclaredAiGenerated -> "The file says it was made by AI"
            ImageProvenance.Origin.DeclaredAiEdited -> "The file says AI made part of it"
            ImageProvenance.Origin.DeclaredCapture -> "The file says a camera took it"
            ImageProvenance.Origin.Undeclared ->
                "The file does not say whether AI made it. That is not proof either way — " +
                    "the label is removed by screenshots and by most social media uploads."
        }
        appendLine("Was this made by AI?")
        appendLine("  $origin")
        report.provenance.generator?.let { appendLine("  Made with: $it") }
        appendLine()

        if (report.leaks.isNotEmpty()) {
            appendLine("What it gives away:")
            report.leaks.forEach { appendLine("  • ${it.what} — ${it.detail}") }
            appendLine()
        }

        val gps = report.exif.gps
        if (gps.present && gps.latitude != null && gps.longitude != null) {
            appendLine("Location stored in the photo:")
            appendLine("  %.6f, %.6f".format(gps.latitude, gps.longitude))
            placeName?.let { appendLine("  Near: $it") }
            appendLine("  Map: https://www.openstreetmap.org/?mlat=${gps.latitude}&mlon=${gps.longitude}#map=17/${gps.latitude}/${gps.longitude}")
            appendLine()
        }

        listOfNotNull(
            report.exif.make?.let { "Camera make: $it" },
            report.exif.model?.let { "Camera model: $it" },
            report.exif.capturedAt?.let { "Taken on: $it" },
            report.exif.serial?.let { "Camera serial: $it" },
        ).takeIf { it.isNotEmpty() }?.let {
            appendLine("The camera:")
            it.forEach { line -> appendLine("  $line") }
            appendLine()
        }

        if (report.signals.isNotEmpty()) {
            appendLine("What this tells you:")
            report.signals.forEach { appendLine("  • ${it.label} — ${it.detail}") }
            appendLine()
        }

        appendLine("File fingerprint (SHA-256):")
        appendLine("  ${report.file.sha256}")
        append(footer())
    }

    /** A scanned code, with the reasoning that produced the verdict. */
    fun forScan(report: LinkSafety.Report, at: Long = System.currentTimeMillis()): String =
        buildString {
            val verdict = when {
                report.kind == LinkSafety.Kind.Payment -> "This code sends money"
                report.verdict == LinkSafety.Verdict.Safe -> "Looks legitimate"
                report.verdict == LinkSafety.Verdict.Caution -> "Be careful"
                report.verdict == LinkSafety.Verdict.Dangerous -> "Do not open this"
                else -> "Could not verify"
            }
            append(header("QR code check: $verdict", "Scanned: ${report.scanned.take(200)}", at))

            report.destination?.let { d ->
                appendLine("Where it goes:")
                appendLine("  ${d.what}")
                d.title?.let { appendLine("  \"$it\"") }
                appendLine()
            }
            report.payee?.let { p ->
                appendLine("Payment details:")
                appendLine("  Paying: ${p.name ?: "not stated"}")
                appendLine("  To account: ${p.address}")
                appendLine(
                    "  Amount: " + (p.amount?.let { listOfNotNull(p.currency, it).joinToString(" ") }
                        ?: "you choose")
                )
                appendLine()
            }
            report.finalUrl?.let {
                appendLine("Final address:")
                appendLine("  $it")
                appendLine()
            }
            report.registered?.let {
                appendLine("Website registered on $it" + (report.ageDays?.let { d -> " ($d days ago)" } ?: ""))
                appendLine()
            }
            if (report.signals.isNotEmpty()) {
                appendLine("Why:")
                report.signals.forEach { appendLine("  • ${it.label} — ${it.detail}") }
            }
            append(footer())
        }

    /**
     * Anything else: a domain, a DNS record, an IP, an email check.
     *
     * These results differ too much in shape to format individually, so the
     * caller hands over the lines it wants preserved. Better a plain list than
     * six near-identical formatters that drift apart.
     */
    fun forLines(
        title: String,
        subject: String,
        sections: List<Pair<String, List<String>>>,
        at: Long = System.currentTimeMillis(),
    ): String = buildString {
        append(header(title, subject, at))
        sections.forEach { (heading, lines) ->
            if (lines.isEmpty()) return@forEach
            appendLine(heading)
            lines.forEach { appendLine("  $it") }
            appendLine()
        }
        append(footer())
    }
}
