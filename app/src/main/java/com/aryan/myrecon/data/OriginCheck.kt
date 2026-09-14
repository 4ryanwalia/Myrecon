package com.aryan.myrecon.data

/**
 * Was this made by AI, and has it been edited?
 *
 * Those are the two questions people actually bring to a photo, and neither has
 * a single answer hiding in the file. [ImageProvenance] can answer the first
 * outright when a label survives, which is a minority of the time. The rest of
 * the time the answer has to be assembled out of things that are individually
 * weak — a filename, a picture size, the way it was compressed — and the whole
 * risk of doing that is manufacturing confidence out of coincidences.
 *
 * Three rules keep that from happening:
 *
 *  1. **Both directions are scored.** Evidence that a real camera took the
 *     picture is collected as carefully as evidence that a generator made it,
 *     and a verdict needs one side to clearly beat the other. A one-sided
 *     scorer finds what it is looking for in everything.
 *
 *  2. **Innocent explanations cancel clues rather than outweighing them.** A
 *     file called `Screenshot_20260914.png` has no metadata and a suspiciously
 *     round size because it is a screenshot, so those two clues are struck out
 *     entirely instead of being argued with. Same for anything that arrived
 *     through WhatsApp. These are the false positives this would otherwise
 *     produce all day, and they are common enough to be most of what users
 *     check.
 *
 *  3. **Every clue is shown with its reason.** The screen lists what was found
 *     and what it means, so a wrong conclusion is visibly wrong instead of
 *     being a verdict the user has to take on trust.
 *
 * Pure Kotlin: one function of its inputs, so the whole decision table is unit
 * testable without a device, which is the only practical way to know that
 * adding a clue did not quietly start accusing holiday photos.
 */
object OriginCheck {

    enum class Made {
        /** The file itself says a generator produced it. */
        DeclaredAi,

        /** The file itself says a generator was used on part of it. */
        DeclaredAiEdited,

        /** No label, but the evidence leans that way and nothing leans back. */
        LooksAi,

        /** Nothing useful either way. The honest answer for most files. */
        Unknown,

        /** No label, but this behaves like something a camera produced. */
        LooksCamera,

        /** The file itself says a camera captured it. */
        DeclaredCamera,
    }

    enum class Touched {
        /** The file names the app that changed it, or lists the edits. */
        Declared,

        /** The picture carries physical traces of having been altered. */
        Likely,

        /** Re-compressed since it was made, which every app and website does. */
        ReSaved,

        /** Camera traces intact and nothing indicating a later pass. */
        NoSign,

        Unknown,
    }

    /** One finding, with the reason it counts, in words a non-technical reader can use. */
    data class Clue(val text: String, val why: String)

    data class Verdict(
        val made: Made,
        val touched: Touched,
        val headline: String,
        val plain: String,
        val towardAi: List<Clue>,
        val towardCamera: List<Clue>,
        val edits: List<Clue>,
        /** Reasons a clue was struck out, so a user can see it was considered. */
        val explained: List<Clue>,
    )

    /**
     * Everything the decision is allowed to look at, flattened to plain values.
     *
     * Deliberately not a reference to [ImageForensics.Report]: keeping the input
     * primitive is what lets the whole table be exercised from a unit test by
     * writing down a situation, rather than by constructing a real image that
     * happens to produce one.
     */
    data class Evidence(
        val fileName: String? = null,
        val container: ImageProvenance.Container = ImageProvenance.Container.Unknown,
        val width: Int = 0,
        val height: Int = 0,
        val declared: ImageProvenance.Origin = ImageProvenance.Origin.Undeclared,
        val contentCredentials: Boolean = false,
        val generator: String? = null,
        val editHistory: List<String> = emptyList(),
        val derivedFrom: Boolean = false,
        val creatorTool: String? = null,
        val exifPresent: Boolean = false,
        val cameraMake: String? = null,
        val cameraModel: String? = null,
        val software: String? = null,
        val serial: String? = null,
        val hasGps: Boolean = false,
        /** How many of ISO, aperture, exposure and focal length are recorded. */
        val captureSettings: Int = 0,
        val capturedAt: String? = null,
        val modifiedAt: String? = null,
        val jpeg: JpegStructure.Report = JpegStructure.Report.NotJpeg,
        val thumbnail: ImageForensics.Match = ImageForensics.Match.NoThumbnail,
        val grid: BlockGrid.Result? = null,
    ) {
        val hasCameraIdentity: Boolean get() = cameraMake != null || cameraModel != null
        val megapixels: Double get() = width.toLong().toDouble() * height / 1e6
    }

    // ── The decision ─────────────────────────────────────────────

    fun of(e: Evidence): Verdict {
        val ai = mutableListOf<Clue>()
        val camera = mutableListOf<Clue>()
        val edits = mutableListOf<Clue>()
        val explained = mutableListOf<Clue>()
        var aiScore = 0
        var cameraScore = 0

        // ── Innocent explanations, established first ─────────────
        // These decide whether the weak clues below are even allowed to be
        // counted, so they have to be known before any of them are weighed.
        val name = e.fileName.orEmpty()
        val screenshot = SCREENSHOT_NAME.containsMatchIn(name)
        val messenger = MESSENGER_NAME.containsMatchIn(name)

        if (screenshot) {
            explained += Clue(
                "This is a screenshot",
                "The name your phone gave it says so. Screenshots never carry camera " +
                    "details, so the missing information below is expected and means nothing.",
            )
        }
        if (messenger) {
            explained += Clue(
                "It came through a messaging app",
                "The filename is the pattern WhatsApp uses. These apps squash every picture " +
                    "and throw away everything hidden inside it, so an empty file here is " +
                    "normal rather than suspicious.",
            )
        }

        // ── Toward a generator ───────────────────────────────────

        aiFromName(name)?.let { tool ->
            aiScore += 3
            ai += Clue(
                "The file is still called what $tool named it",
                "AI tools name the pictures they save in their own particular way, and this " +
                    "file still has that name. Nobody renamed it after it was downloaded.",
            )
        }

        if (!e.hasCameraIdentity) {
            val size = "${e.width}x${e.height}"
            when {
                size in DISTINCTIVE_SIZES -> {
                    aiScore += 2
                    ai += Clue(
                        "An unusual size that AI generators use",
                        "$size is one of the exact shapes image generators produce. Cameras " +
                            "and phone screens do not use it.",
                    )
                }
                size in COMMON_SIZES -> {
                    aiScore += 1
                    ai += Clue(
                        "A size AI generators commonly produce",
                        "$size is a standard generator output. Plenty of ordinary pictures " +
                            "are cropped to it too, so on its own this means little.",
                    )
                }
            }

            val blank = !e.exifPresent && !e.contentCredentials
            if (blank && e.container == ImageProvenance.Container.Png && e.megapixels >= 0.25) {
                if (screenshot) {
                    explained += Clue(
                        "Empty PNG, but explained",
                        "A picture file with nothing at all stored inside it can point to a " +
                            "generator, but a screenshot looks exactly the same, and this is one.",
                    )
                } else {
                    aiScore += 1
                    ai += Clue(
                        "Nothing at all is stored inside it",
                        "No camera, no date, no settings — not even the small traces most " +
                            "software leaves. Generators save pictures completely empty like this.",
                    )
                }
            }

            if (blank && e.jpeg.present && e.jpeg.tables == JpegStructure.Tables.Standard &&
                (e.jpeg.quality ?: 0) >= 90
            ) {
                if (messenger) {
                    explained += Clue(
                        "Squashed by software, but explained",
                        "It was compressed by an ordinary program rather than a camera — which " +
                            "is what the messaging app it arrived through does to everything.",
                    )
                } else {
                    aiScore += 1
                    ai += Clue(
                        "Saved by a program at very high quality",
                        "The way it was squashed is the setting image-generation software uses " +
                            "by default, and there are no camera details to go with it.",
                    )
                }
            }
        }
        // No else: on a file that names a camera the size and empty-file checks
        // are simply not run, and saying so on every holiday photo would be
        // noise about a test that was never going to fire.

        // ── Toward a real camera ─────────────────────────────────

        if (e.jpeg.makerNote) {
            cameraScore += 3
            camera += Clue(
                "The camera's own private block is still in here",
                "Every camera maker writes a chunk of its own data that only its cameras " +
                    "produce. Editing apps and websites throw it away rather than try to keep " +
                    "it, so finding it means the file has barely been touched.",
            )
        }
        if (e.captureSettings >= 3) {
            cameraScore += 2
            camera += Clue(
                "The shot settings were recorded",
                "Shutter speed, aperture and sensitivity are written at the moment the picture " +
                    "is taken. Generators have nothing to put there.",
            )
        }
        if (e.hasCameraIdentity) {
            cameraScore += 1
            camera += Clue(
                "It names the camera",
                listOfNotNull(e.cameraMake, e.cameraModel).joinToString(" ") +
                    " is recorded as what took it.",
            )
        }
        if (e.hasGps) {
            cameraScore += 1
            camera += Clue(
                "A place on the map is saved inside",
                "Coordinates get written by a device that was physically somewhere.",
            )
        }
        if (e.serial != null) {
            cameraScore += 1
            camera += Clue(
                "One specific camera's serial number",
                "This is the number of a single physical body, not a model.",
            )
        }
        // Photoshop is the one piece of ordinary software that also ships its
        // own tables, so this can be true of a file it wrote. That is left
        // alone rather than special-cased: a photograph edited in Photoshop is
        // still a photograph, which is the question this half is answering, and
        // the Adobe segment it leaves is picked up under editing below.
        if (e.jpeg.tables == JpegStructure.Tables.Custom) {
            cameraScore += 2
            camera += Clue(
                "Squashed the way a camera squashes",
                "Camera makers tune their own compression settings and no two use the same " +
                    "ones. Ordinary software uses the standard recipe out of the manual — and " +
                    "this file does not.",
            )
        }
        if (e.thumbnail == ImageForensics.Match.Consistent) {
            cameraScore += 1
            camera += Clue(
                "The camera's own preview still matches",
                "The tiny copy saved at the moment of the shot still looks like the picture.",
            )
        }

        // ── Has it been changed since ────────────────────────────

        var touched = Touched.Unknown

        if (e.editHistory.isNotEmpty()) {
            touched = Touched.Declared
            edits += Clue(
                "It lists the apps that changed it",
                "The file keeps its own edit log, and it names: " +
                    e.editHistory.take(4).joinToString(", ") + ".",
            )
        }
        if (e.derivedFrom) {
            touched = escalate(touched, Touched.Declared)
            edits += Clue(
                "It is a copy of another file",
                "The file records that it was made from an earlier picture, which is what " +
                    "editing software writes when you save a changed version.",
            )
        }
        (knownEditor(e.software) ?: knownEditor(e.creatorTool))?.let { app ->
            touched = escalate(touched, Touched.Declared)
            edits += Clue(
                "Last saved by $app",
                "The file names the program that wrote it, and that program is an editor, " +
                    "not a camera.",
            )
        }
        if (e.jpeg.photoshopBlock || e.jpeg.adobeSegment) {
            touched = escalate(touched, Touched.Declared)
            edits += Clue(
                "It has been through an Adobe app",
                "Photoshop and its relatives leave a block of their own inside the file. It " +
                    "is still here.",
            )
        }
        when (e.thumbnail) {
            ImageForensics.Match.Mismatch -> {
                touched = escalate(touched, Touched.Likely)
                edits += Clue(
                    "The camera's preview shows a different picture",
                    "Editing apps update the photo and forget the tiny preview saved beside " +
                        "it. When the two disagree, the photo is the one that changed.",
                )
            }
            ImageForensics.Match.Cropped -> {
                touched = escalate(touched, Touched.Likely)
                edits += Clue(
                    "The edges were trimmed off",
                    "The camera's preview is a different shape from the picture, so it was " +
                        "cropped after it was taken.",
                )
            }
            else -> Unit
        }

        e.grid?.let { g ->
            val lossless = e.container == ImageProvenance.Container.Png ||
                e.container == ImageProvenance.Container.WebP
            when {
                lossless && g.strength >= BlockGrid.CONVERTED -> {
                    touched = escalate(touched, Touched.Likely)
                    edits += Clue(
                        "It was a different kind of file before",
                        "Squashing a picture leaves a faint eight-pixel checkerboard in it. " +
                            "This file type does not create one, but the picture has one — so " +
                            "it was squashed earlier and saved again in this format.",
                    )
                }
                e.jpeg.present && !g.aligned && g.strength >= BlockGrid.PRESENT -> {
                    touched = escalate(touched, Touched.Likely)
                    edits += Clue(
                        "Cropped and then saved again",
                        "The faint grid left by squashing sits off-centre by " +
                            "${g.phaseX} across and ${g.phaseY} down. A picture saved once has " +
                            "it lined up with the corner, so this one was trimmed in between.",
                    )
                }
            }
        }

        if (e.jpeg.progressive) {
            touched = escalate(touched, Touched.ReSaved)
            edits += Clue(
                "Rewritten for the web",
                "It is stored in the layered form websites use so a picture appears blurry " +
                    "first and sharpens. Cameras never write this, so a program did.",
            )
        }
        if (e.hasCameraIdentity && e.jpeg.tables == JpegStructure.Tables.Standard) {
            touched = escalate(touched, Touched.ReSaved)
            edits += Clue(
                "Squashed again after the camera",
                "It still names a camera, but the compression is the standard one used by " +
                    "software. Something opened it and saved it again, carrying the camera " +
                    "details across.",
            )
        }
        if (e.capturedAt != null && e.modifiedAt != null && e.capturedAt != e.modifiedAt) {
            touched = escalate(touched, Touched.ReSaved)
            edits += Clue(
                "Saved after the day it was taken",
                "Taken ${e.capturedAt}, last written ${e.modifiedAt}.",
            )
        }

        if (touched == Touched.Unknown && e.jpeg.makerNote &&
            e.jpeg.tables == JpegStructure.Tables.Custom
        ) {
            touched = Touched.NoSign
            edits += Clue(
                "No sign it has been edited",
                "The camera's own data and its own compression are both still in place, and " +
                    "nothing in the file points to a later pass. A careful editor could hide " +
                    "its tracks, so this is reassuring rather than proof.",
            )
        }

        // ── Put it together ──────────────────────────────────────

        val made = when {
            e.declared == ImageProvenance.Origin.DeclaredAiGenerated -> Made.DeclaredAi
            e.declared == ImageProvenance.Origin.DeclaredAiEdited -> Made.DeclaredAiEdited
            e.declared == ImageProvenance.Origin.DeclaredCapture -> Made.DeclaredCamera
            aiScore >= 3 && aiScore > cameraScore -> Made.LooksAi
            cameraScore >= 4 && aiScore == 0 -> Made.LooksCamera
            else -> Made.Unknown
        }

        return Verdict(
            made = made,
            touched = touched,
            headline = headline(made, e.generator),
            plain = plain(made, aiScore, cameraScore),
            towardAi = ai,
            towardCamera = camera,
            edits = edits,
            explained = explained,
        )
    }

    /**
     * Keep the strongest finding about editing, whatever order they arrive in.
     *
     * [Touched] is declared strongest-first, so "strongest" is the lower
     * ordinal. Writing that as `minOf` reads backwards at every call site, and
     * reading it backwards is how a thumbnail mismatch ends up downgraded to
     * "re-saved" by a later, weaker check.
     */
    private fun escalate(current: Touched, next: Touched): Touched =
        if (next.ordinal < current.ordinal) next else current

    // ── Wording ──────────────────────────────────────────────────

    private fun headline(made: Made, generator: String?): String = when (made) {
        Made.DeclaredAi -> generator?.let { "Yes — $it made it" } ?: "Yes — the file says AI made it"
        Made.DeclaredAiEdited -> "Partly — AI was used on some of it"
        Made.LooksAi -> "Probably — several things point that way"
        Made.LooksCamera -> "Probably not — this behaves like a real photo"
        Made.DeclaredCamera -> "No — the file says a camera took it"
        Made.Unknown -> "There is no way to tell from this file"
    }

    private fun plain(made: Made, aiScore: Int, cameraScore: Int): String = when (made) {
        Made.DeclaredAi, Made.DeclaredAiEdited ->
            "This is a label the tool wrote inside the file, not a guess from looking at the " +
                "picture. Labels can be removed, but they are not added by accident."

        Made.DeclaredCamera ->
            "The file carries a tag saying it was captured by a camera. That tag can be " +
                "copied onto anything, so treat it as a claim rather than proof."

        Made.LooksAi ->
            "There is no label saying so. This is $aiScore separate things lining up, each " +
                "listed below with what it means, and nothing in the file pointing the other " +
                "way. Read them and judge for yourself."

        Made.LooksCamera ->
            "There is no label either way, but $cameraScore things a camera leaves behind are " +
                "still in this file, and generators cannot produce them. That is about as " +
                "close to a real photo as a file can get without saying so outright."

        Made.Unknown ->
            "AI tools usually hide a small label inside the picture saying they made it. This " +
                "one has no label, and nothing else in it leans either way.\n\n" +
                "That does not mean it is real. The label is wiped whenever a picture is " +
                "screenshotted, saved again, or posted on social media — so most genuine " +
                "photos you see online have no label either. Anyone claiming to tell you for " +
                "certain by looking at the picture is guessing."
    }

    // ── Names ────────────────────────────────────────────────────

    /**
     * The tool a filename betrays, if any.
     *
     * People download a generated picture and send it on without renaming it,
     * so the name the tool chose survives long after every label inside the
     * file is gone. Each pattern here is anchored the way the tool actually
     * writes it rather than matched loosely: "dream", "flux" and "designer" are
     * ordinary words that would match half the pictures on a phone.
     */
    fun aiFromName(fileName: String): String? {
        val n = fileName.trim()
        return NAME_PATTERNS.firstOrNull { it.first.containsMatchIn(n) }?.second
    }

    private fun knownEditor(value: String?): String? {
        val v = value?.trim().orEmpty()
        if (v.isBlank()) return null
        return EDITORS.firstOrNull { v.contains(it, ignoreCase = true) }
    }

    private val NAME_PATTERNS: List<Pair<Regex, String>> = listOf(
        Regex("""^Gemini_Generated_Image""", RegexOption.IGNORE_CASE) to "Google Gemini",
        Regex("""^ChatGPT Image """, RegexOption.IGNORE_CASE) to "ChatGPT",
        Regex("""^DALL[·\-]E """, RegexOption.IGNORE_CASE) to "DALL·E",
        Regex("""^ComfyUI_\d""") to "ComfyUI",
        // AUTOMATIC1111 writes a counter, then the seed it used.
        Regex("""^\d{5}-\d{6,}""") to "Stable Diffusion",
        Regex("""^Firefly[ _]""", RegexOption.IGNORE_CASE) to "Adobe Firefly",
        Regex("""midjourney""", RegexOption.IGNORE_CASE) to "Midjourney",
        Regex("""^Leonardo_""", RegexOption.IGNORE_CASE) to "Leonardo.Ai",
        Regex("""^grok[-_]image""", RegexOption.IGNORE_CASE) to "Grok",
        Regex("""^image[-_]fx[-_]""", RegexOption.IGNORE_CASE) to "Google ImageFX",
        Regex("""^ideogram""", RegexOption.IGNORE_CASE) to "Ideogram",
        Regex("""^nightcafe""", RegexOption.IGNORE_CASE) to "NightCafe",
        Regex("""^Playground[-_]Image""", RegexOption.IGNORE_CASE) to "Playground",
        Regex("""^meta[-_]ai[-_]""", RegexOption.IGNORE_CASE) to "Meta AI",
        Regex("""^stable[-_]diffusion""", RegexOption.IGNORE_CASE) to "Stable Diffusion",
    )

    /** Phone and camera naming, plus the two pipelines that explain an empty file. */
    private val SCREENSHOT_NAME = Regex("""screen[ _-]?shot""", RegexOption.IGNORE_CASE)

    /** WhatsApp's own naming: IMG-20260914-WA0007. */
    private val MESSENGER_NAME = Regex("""^(IMG|VID)-\d{8}-WA\d+""", RegexOption.IGNORE_CASE)

    /**
     * Exact output shapes, and nothing that merely looks like one.
     *
     * These are the sizes the diffusion models are trained to emit — the shapes
     * that fall out of their internal grid — and no camera sensor or phone
     * screen has them. The square sizes are kept separate because plenty of
     * profile pictures get cropped to 1024x1024 by hand.
     */
    private val DISTINCTIVE_SIZES = setOf(
        // Stable Diffusion XL's training buckets.
        "1152x896", "896x1152", "1216x832", "832x1216",
        "1344x768", "768x1344", "1536x640", "640x1536",
        // DALL·E 3.
        "1792x1024", "1024x1792",
        // Midjourney's wide and tall crops.
        "1456x816", "816x1456", "1232x928", "928x1232",
        // Stable Diffusion 1.5 portrait and landscape.
        "768x512", "512x768",
    )

    private val COMMON_SIZES = setOf("1024x1024", "512x512", "768x768", "1536x1536")

    /**
     * Editors, named the way they write themselves into a file.
     *
     * Matched as substrings, so each entry has to be distinctive on its own:
     * "Preview", "Photos" and "Paint" are all real applications and all
     * hopeless as needles.
     */
    private val EDITORS = listOf(
        "Adobe Photoshop", "Photoshop Express", "Lightroom", "Adobe Illustrator",
        "Adobe Express", "Affinity Photo", "Affinity Designer", "Capture One",
        "Luminar", "Pixelmator", "GIMP", "Krita", "Paint.NET", "Photopea",
        "Snapseed", "PicsArt", "Canva", "Fotor", "VSCO", "Facetune", "AirBrush",
        "BeautyPlus", "YouCam", "Meitu", "PhotoRoom", "Polarr", "Darktable",
        "RawTherapee", "ON1 Photo", "DxO PhotoLab", "Topaz",
    )
}
