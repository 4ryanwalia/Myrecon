package com.aryan.myrecon.data

import java.util.zip.Inflater

/**
 * What a file says about its own origin.
 *
 * "Is this AI?" is the question people bring to an image now, and there are two
 * ways to answer it. One is to guess from the pixels, which is a model's
 * opinion, needs a paid service, and is wrong often enough to be dangerous. The
 * other is to read what the file declares about itself — and generators,
 * cameras and editors all write that down, in formats that are open and
 * parseable with no key and no network.
 *
 * So this reads declarations, and only declarations. The distinction is carried
 * all the way into the wording the user sees:
 *
 *  • "this file declares it was AI-generated" is a fact about the file.
 *  • "no such marker" is *not* evidence the image is real. A screenshot, a
 *    re-save, or an upload through almost any social platform strips every
 *    marker here. Absence proves nothing, and the report must never imply it
 *    does.
 *
 * Pure Kotlin, no Android types, so the parsing is unit-testable on the JVM —
 * which matters, because every one of these formats is a byte layout that is
 * easy to get subtly wrong.
 */
object ImageProvenance {

    enum class Container { Jpeg, Png, WebP, Heif, Gif, Unknown }

    enum class Origin {
        /** The file states a generative model produced it. */
        DeclaredAiGenerated,

        /** The file states a model contributed to part of it. */
        DeclaredAiEdited,

        /** The file states a camera captured it. */
        DeclaredCapture,

        /** The file says nothing either way. Not the same as "real". */
        Undeclared,
    }

    /** One declaration, kept with where it was read from so it can be checked. */
    data class Marker(val source: String, val value: String)

    data class Report(
        val container: Container,
        val origin: Origin,
        /** "Midjourney", "Stable Diffusion" — named only when the file names it. */
        val generator: String?,
        /** The generation prompt, when the generator wrote one into the file. */
        val prompt: String?,
        /** A C2PA / Content Credentials manifest is attached. */
        val contentCredentials: Boolean,
        val markers: List<Marker>,
        /** Embedded text fields, which double as a leak surface. */
        val textFields: List<Pair<String, String>>,
        val xmpPresent: Boolean,
        /** Apps the file's own edit log names, when it keeps one. */
        val editHistory: List<String> = emptyList(),
        /** The file records being made from an earlier one. */
        val derivedFrom: Boolean = false,
        /** The app that created the file, as it names itself. */
        val creatorTool: String? = null,
    )

    // ── Entry point ──────────────────────────────────────────────

    fun analyse(bytes: ByteArray, exifSoftware: String? = null): Report {
        val container = containerOf(bytes)
        val markers = mutableListOf<Marker>()

        val text = when (container) {
            Container.Png -> pngTextFields(bytes)
            else -> emptyList()
        }
        val xmp = extractXmp(bytes)
        val c2pa = hasContentCredentials(bytes, container)

        if (c2pa) {
            markers += Marker(
                "Content Credentials",
                "The file carries a record of how it was made",
            )
        }

        // IPTC's own vocabulary for this, written into XMP. It is the closest
        // thing to a standard answer and the major generators emit it.
        var origin = Origin.Undeclared
        xmp?.let { x ->
            when {
                x.contains("compositeWithTrainedAlgorithmicMedia") -> {
                    origin = Origin.DeclaredAiEdited
                    markers += Marker(
                        "Hidden label",
                        "Part of this picture was made by an AI generator",
                    )
                }
                x.contains("trainedAlgorithmicMedia") -> {
                    origin = Origin.DeclaredAiGenerated
                    markers += Marker(
                        "Hidden label",
                        "The file is tagged as made by an AI image generator",
                    )
                }
                x.contains("algorithmicMedia") -> {
                    origin = Origin.DeclaredAiGenerated
                    markers += Marker(
                        "Hidden label",
                        "The file is tagged as made by software, not taken by a camera",
                    )
                }
                x.contains("digitalCapture") -> {
                    origin = Origin.DeclaredCapture
                    markers += Marker(
                        "Hidden label",
                        "The file is tagged as taken by a camera",
                    )
                }
            }
        }

        // Generator names, searched across every place one can be written.
        val haystack = buildString {
            exifSoftware?.let { append(it).append('\n') }
            xmp?.let { append(it).append('\n') }
            text.forEach { append(it.first).append(' ').append(it.second).append('\n') }
        }
        val generator = GENERATORS.firstOrNull { (needle, _) ->
            haystack.contains(needle, ignoreCase = true)
        }?.second

        if (generator != null) {
            markers += Marker("Made with", generator)
            if (origin == Origin.Undeclared) origin = Origin.DeclaredAiGenerated
        }

        // Tools that rebuild part of an existing photo rather than invent a new
        // one: a face smoothed, a background replaced, a blurry picture
        // "enhanced" into detail that was never captured. The file is a
        // photograph *and* partly invented, so it is neither of the two answers
        // people expect and both halves have to be said.
        val aiEditor = AI_EDITORS.firstOrNull { (needle, _) ->
            haystack.contains(needle, ignoreCase = true)
        }?.second
        if (aiEditor != null) {
            markers += Marker("Changed with", aiEditor)
            if (origin == Origin.Undeclared || origin == Origin.DeclaredCapture) {
                origin = Origin.DeclaredAiEdited
            }
        }

        // Automatic1111 writes the prompt into a `parameters` chunk verbatim.
        // Only that key is treated as evidence: `Description` is an ordinary
        // caption field on any PNG, so reading a prompt out of it would call
        // every captioned image AI-generated.
        val parameters = text.firstOrNull { it.first.equals("parameters", true) }?.second
        if (parameters != null) {
            origin = Origin.DeclaredAiGenerated
            markers += Marker(
                "Saved instructions",
                "The words used to create this picture are stored inside the file",
            )
        }
        val prompt = parameters
            ?: text.firstOrNull { it.first.equals("Description", true) && generator != null }?.second

        // ComfyUI stores its whole node graph. Too large to show, but its
        // presence is as conclusive as a prompt — provided it really is a graph
        // and not a `prompt` field someone wrote by hand, so the value has to
        // parse as an object before it counts.
        if (text.any {
                (it.first.equals("workflow", true) || it.first.equals("prompt", true)) &&
                    it.second.trimStart().startsWith("{")
            }
        ) {
            origin = Origin.DeclaredAiGenerated
            markers += Marker(
                "Saved instructions",
                "The full recipe used to create this picture is stored inside the file",
            )
        }

        val history = xmp?.let { editHistory(it) }.orEmpty()
        if (history.isNotEmpty()) {
            markers += Marker("Edit log", history.take(3).joinToString(", "))
        }

        return Report(
            container = container,
            origin = origin,
            generator = generator ?: aiEditor,
            prompt = prompt?.trim()?.take(1200)?.takeIf { it.isNotBlank() },
            contentCredentials = c2pa,
            markers = markers,
            textFields = text,
            xmpPresent = xmp != null,
            editHistory = history,
            derivedFrom = xmp?.contains("xmpMM:DerivedFrom") == true,
            creatorTool = xmp?.let { first(it, CREATOR_TOOL) }?.take(120),
        )
    }

    // ── The edit log Adobe leaves behind ─────────────────────────

    /**
     * Which applications the file's own history says have written to it.
     *
     * Adobe's tools, and anything else that implements the XMP media-management
     * schema, append an entry every time a file is saved: what was done and
     * which program did it. It is the closest thing to a chain of custody a
     * picture ever carries, and unlike a thumbnail or a compression trace it
     * says so in words.
     *
     * The catch is that the *first* entry is usually the file being created,
     * not edited. A camera app that writes a single "produced" event has not
     * edited anything, and reporting it as an edit history would put "this has
     * been altered" on untouched photos from the phones that do this. So an
     * entry only counts once some action other than creation appears.
     */
    fun editHistory(xmp: String): List<String> {
        if (!xmp.contains("xmpMM:History")) return emptyList()
        val actions = all(xmp, ACTION).map { it.lowercase() }
        val agents = all(xmp, SOFTWARE_AGENT)
            .map { it.trim() }
            .filter { it.isNotBlank() }
            .distinct()

        val edited = if (actions.isEmpty()) agents.size > 1 else {
            actions.any { it !in CREATION_ACTIONS }
        }
        return if (edited) agents.take(6) else emptyList()
    }

    /**
     * XMP writes the same property either as an attribute or as an element,
     * and which one you get depends on the serialiser rather than the schema.
     * Both spellings are matched, and whichever group participated is taken.
     */
    private fun all(xmp: String, pattern: Regex): List<String> =
        pattern.findAll(xmp).mapNotNull { m ->
            m.groupValues.drop(1).firstOrNull { it.isNotBlank() }
        }.toList()

    private fun first(xmp: String, pattern: Regex): String? =
        all(xmp, pattern).firstOrNull()?.trim()?.takeIf { it.isNotBlank() }

    // ── Container ────────────────────────────────────────────────

    fun containerOf(b: ByteArray): Container = when {
        b.size < 12 -> Container.Unknown
        b[0] == 0xFF.toByte() && b[1] == 0xD8.toByte() && b[2] == 0xFF.toByte() -> Container.Jpeg
        b.startsWith(PNG_MAGIC) -> Container.Png
        b.ascii(0, 4) == "RIFF" && b.ascii(8, 4) == "WEBP" -> Container.WebP
        b.ascii(4, 4) == "ftyp" -> Container.Heif
        b.ascii(0, 4) == "GIF8" -> Container.Gif
        else -> Container.Unknown
    }

    // ── C2PA / Content Credentials ───────────────────────────────

    /**
     * Presence only, never validity.
     *
     * A real C2PA check verifies a signature chain against a trust list, which
     * needs the certificates and the c2pa library. What can be said honestly
     * from the bytes alone is that a manifest is attached — so that is all this
     * claims, and the UI says "attached", not "verified".
     */
    fun hasContentCredentials(bytes: ByteArray, container: Container = containerOf(bytes)): Boolean =
        when (container) {
            // JUMBF rides in APP11 segments, which open with the "JP" marker.
            Container.Jpeg -> jpegSegments(bytes).any { (marker, data) ->
                marker == 0xEB && data.size > 8 && data.ascii(0, 2) == "JP" &&
                    (data.indexOf(C2PA_LABEL) >= 0 || data.indexOf(JUMB_BOX) >= 0)
            }
            // PNG carries it in a dedicated ancillary chunk.
            Container.Png -> pngChunks(bytes).any { it.first == "caBX" }
            // Everything else: the ISO box name is still a reliable needle.
            else -> bytes.indexOf(C2PA_LABEL) >= 0 && bytes.indexOf(JUMB_BOX) >= 0
        }

    // ── XMP ──────────────────────────────────────────────────────

    /**
     * Pull the XMP packet out by scanning, rather than through the container.
     *
     * JPEG keeps it in an APP1 segment, PNG in an iTXt chunk, HEIF in a box.
     * The packet is self-delimiting in all three, so one scan handles every
     * format including the ones with no parser here.
     */
    fun extractXmp(bytes: ByteArray): String? {
        val start = bytes.indexOf(XMP_OPEN).takeIf { it >= 0 } ?: return null
        val endTag = bytes.indexOf(XMP_CLOSE, start)
        val end = if (endTag >= 0) endTag + XMP_CLOSE.size else minOf(bytes.size, start + MAX_XMP)
        return String(bytes, start, end - start, Charsets.UTF_8).takeIf { it.isNotBlank() }
    }

    // ── JPEG ─────────────────────────────────────────────────────

    /**
     * Walk the marker segments, stopping at the start of scan.
     *
     * Everything after SOS is entropy-coded pixel data that can contain any
     * byte sequence at all, so continuing past it would find "markers" that are
     * really just compressed pixels.
     */
    fun jpegSegments(b: ByteArray): List<Pair<Int, ByteArray>> {
        if (containerOf(b) != Container.Jpeg) return emptyList()
        val out = mutableListOf<Pair<Int, ByteArray>>()
        var pos = 2
        while (pos + 4 <= b.size) {
            if (b[pos] != 0xFF.toByte()) break
            val marker = b[pos + 1].toInt() and 0xFF
            // Standalone markers carry no length word.
            if (marker == 0xD8 || marker == 0x01 || marker in 0xD0..0xD7) {
                pos += 2
                continue
            }
            if (marker == 0xDA || marker == 0xD9) break
            val len = ((b[pos + 2].toInt() and 0xFF) shl 8) or (b[pos + 3].toInt() and 0xFF)
            if (len < 2 || pos + 2 + len > b.size) break
            out += marker to b.copyOfRange(pos + 4, pos + 2 + len)
            pos += 2 + len
        }
        return out
    }

    // ── PNG ──────────────────────────────────────────────────────

    /** Chunk type and payload, in file order. */
    fun pngChunks(b: ByteArray): List<Pair<String, ByteArray>> {
        if (!b.startsWith(PNG_MAGIC)) return emptyList()
        val out = mutableListOf<Pair<String, ByteArray>>()
        var pos = PNG_MAGIC.size
        while (pos + 8 <= b.size) {
            val len = be32(b, pos)
            // A negative length means the file claims a chunk over 2 GB, which
            // is corruption or a crafted file. Either way, stop reading.
            if (len < 0 || pos + 12 + len > b.size) break
            val type = b.ascii(pos + 4, 4)
            out += type to b.copyOfRange(pos + 8, pos + 8 + len)
            pos += 12 + len
            if (type == "IEND") break
        }
        return out
    }

    /**
     * Every text field a PNG carries, across all three chunk types.
     *
     * This is where Stable Diffusion front-ends put the entire prompt, which
     * makes it both the clearest AI declaration available and — for anyone
     * sharing a generated image — a leak of exactly what they typed.
     */
    fun pngTextFields(b: ByteArray): List<Pair<String, String>> {
        val out = mutableListOf<Pair<String, String>>()
        for ((type, data) in pngChunks(b)) {
            when (type) {
                "tEXt" -> {
                    val split = data.indexOf(0)
                    if (split > 0) {
                        out += data.ascii(0, split) to
                            String(data, split + 1, data.size - split - 1, Charsets.ISO_8859_1)
                    }
                }
                "zTXt" -> {
                    val split = data.indexOf(0)
                    // keyword \0 compressionMethod deflate-stream
                    if (split > 0 && data.size > split + 2) {
                        inflate(data, split + 2)?.let {
                            out += data.ascii(0, split) to String(it, Charsets.ISO_8859_1)
                        }
                    }
                }
                "iTXt" -> {
                    val split = data.indexOf(0)
                    if (split > 0 && data.size > split + 3) {
                        val compressed = data[split + 1].toInt() == 1
                        // Two more null-terminated fields before the text:
                        // language tag, then the translated keyword.
                        var p = split + 3
                        var skipped = 0
                        while (p < data.size && skipped < 2) {
                            if (data[p].toInt() == 0) skipped++
                            p++
                        }
                        if (p < data.size) {
                            val value = if (compressed) {
                                inflate(data, p)?.toString(Charsets.UTF_8)
                            } else {
                                String(data, p, data.size - p, Charsets.UTF_8)
                            }
                            value?.let { out += data.ascii(0, split) to it }
                        }
                    }
                }
            }
        }
        return out.map { (k, v) -> k to v.trim().take(MAX_FIELD) }.filter { it.second.isNotBlank() }
    }

    private fun inflate(data: ByteArray, from: Int): ByteArray? = runCatching {
        val inflater = Inflater()
        inflater.setInput(data, from, data.size - from)
        val buffer = ByteArray(8192)
        val out = java.io.ByteArrayOutputStream()
        while (!inflater.finished() && out.size() < MAX_FIELD * 4) {
            val n = inflater.inflate(buffer)
            if (n == 0) break
            out.write(buffer, 0, n)
        }
        inflater.end()
        out.toByteArray().takeIf { it.isNotEmpty() }
    }.getOrNull()

    // ── Helpers ──────────────────────────────────────────────────

    private fun be32(b: ByteArray, at: Int): Int =
        ((b[at].toInt() and 0xFF) shl 24) or ((b[at + 1].toInt() and 0xFF) shl 16) or
            ((b[at + 2].toInt() and 0xFF) shl 8) or (b[at + 3].toInt() and 0xFF)

    private fun ByteArray.ascii(at: Int, len: Int): String =
        if (at < 0 || at + len > size) "" else String(this, at, len, Charsets.ISO_8859_1)

    private fun ByteArray.startsWith(prefix: ByteArray): Boolean {
        if (size < prefix.size) return false
        for (i in prefix.indices) if (this[i] != prefix[i]) return false
        return true
    }

    private fun ByteArray.indexOf(byte: Int): Int {
        for (i in indices) if (this[i].toInt() == byte) return i
        return -1
    }

    private fun ByteArray.indexOf(needle: ByteArray, from: Int = 0): Int {
        if (needle.isEmpty() || needle.size > size) return -1
        outer@ for (i in from..size - needle.size) {
            for (j in needle.indices) if (this[i + j] != needle[j]) continue@outer
            return i
        }
        return -1
    }

    private val PNG_MAGIC = byteArrayOf(
        0x89.toByte(), 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A
    )
    private val XMP_OPEN = "<x:xmpmeta".toByteArray(Charsets.ISO_8859_1)
    private val XMP_CLOSE = "</x:xmpmeta>".toByteArray(Charsets.ISO_8859_1)
    private val C2PA_LABEL = "c2pa".toByteArray(Charsets.ISO_8859_1)
    private val JUMB_BOX = "jumb".toByteArray(Charsets.ISO_8859_1)

    private const val MAX_XMP = 64 * 1024
    private const val MAX_FIELD = 4000

    private val ACTION = Regex(
        """stEvt:action\s*=\s*"([^"]{1,40})"|<stEvt:action>([^<]{1,40})</stEvt:action>"""
    )
    private val SOFTWARE_AGENT = Regex(
        """stEvt:softwareAgent\s*=\s*"([^"]{1,120})"|""" +
            """<stEvt:softwareAgent>([^<]{1,120})</stEvt:softwareAgent>"""
    )
    private val CREATOR_TOOL = Regex(
        """xmp:CreatorTool\s*=\s*"([^"]{1,160})"|<xmp:CreatorTool>([^<]{1,160})</xmp:CreatorTool>"""
    )

    /** Making the file, as opposed to changing one that already existed. */
    private val CREATION_ACTIONS = setOf("produced", "created")

    /**
     * Needles specific enough not to fire on ordinary text.
     *
     * "Firefly" alone would match a photograph of an insect, so the Adobe
     * product is matched on its full name. The cost of a wrong name here is a
     * user told their holiday photo was generated, which is exactly the failure
     * this whole module is built to avoid.
     */
    private val GENERATORS: List<Pair<String, String>> = listOf(
        "midjourney" to "Midjourney",
        "dall-e" to "DALL·E",
        "dall·e" to "DALL·E",
        "adobe firefly" to "Adobe Firefly",
        "stable diffusion" to "Stable Diffusion",
        "automatic1111" to "Stable Diffusion (AUTOMATIC1111)",
        "stable-diffusion-webui" to "Stable Diffusion (AUTOMATIC1111)",
        "comfyui" to "ComfyUI",
        "novelai" to "NovelAI",
        "black forest labs" to "FLUX (Black Forest Labs)",
        "leonardo.ai" to "Leonardo.Ai",
        "ideogram" to "Ideogram",
        // "imagen" is the ordinary Spanish word for "image", and "gemini" is a
        // star sign someone might caption a photo with. Both are matched only
        // as part of the string Google actually writes.
        "google imagen" to "Google Imagen",
        "made with google ai" to "Google AI",
        "gemini_generated" to "Google Gemini",
        "openai" to "OpenAI",
        "chatgpt" to "ChatGPT",
        "flux.1" to "FLUX",
        "recraft" to "Recraft",
        "playground.ai" to "Playground",
        "nightcafe" to "NightCafe",
        "dreamstudio" to "DreamStudio",
        "invokeai" to "InvokeAI",
        "fooocus" to "Fooocus",
        "seedream" to "Seedream",
        "getimg.ai" to "getimg.ai",
        "clipdrop" to "Clipdrop",
        "artbreeder" to "Artbreeder",
        "starryai" to "StarryAI",
        "craiyon" to "Craiyon",
        "bing image creator" to "Bing Image Creator",
    )

    /**
     * Tools that rewrite part of a real photograph.
     *
     * Separated from [GENERATORS] because the honest answer about their output
     * is neither "AI made this" nor "a camera took this" — a camera took it and
     * then a model replaced some of it, and a user deciding whether to trust a
     * face needs to be told the second half.
     *
     * The same specificity rule applies. "Remini" and "Lensa" are invented
     * words and safe; "enhance", "magic" and "portrait" appear in the name of
     * every second camera app and are not here.
     */
    private val AI_EDITORS: List<Pair<String, String>> = listOf(
        "generative fill" to "Photoshop Generative Fill",
        "generative expand" to "Photoshop Generative Expand",
        "neural filters" to "Photoshop Neural Filters",
        "magic editor" to "Google Magic Editor",
        "magic eraser" to "Google Magic Eraser",
        "galaxy ai" to "Samsung Galaxy AI",
        "generative edit" to "Samsung Generative Edit",
        "remini" to "Remini",
        "lensa" to "Lensa",
        "faceapp" to "FaceApp",
        "photoroom" to "PhotoRoom",
        "cleanup.pictures" to "Cleanup.pictures",
        "topaz gigapixel" to "Topaz Gigapixel",
        "topaz photo ai" to "Topaz Photo AI",
        "luminar neo" to "Luminar Neo",
        "facetune" to "Facetune",
    )
}
