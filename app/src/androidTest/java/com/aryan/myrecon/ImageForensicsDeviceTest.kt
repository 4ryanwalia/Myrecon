package com.aryan.myrecon

import android.content.ContentValues
import android.graphics.Bitmap
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.aryan.myrecon.data.CleanCopy
import com.aryan.myrecon.data.ImageForensics
import com.aryan.myrecon.data.ImageProvenance
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayOutputStream
import java.util.zip.CRC32

/**
 * The image pipeline end to end on a real device.
 *
 * The JVM tests cover the byte parsing; this covers everything the JVM cannot:
 * a genuine MediaStore uri, Android's own PNG encoder, the content resolver
 * round trip, and a clean copy actually landing in the gallery. Those are the
 * steps where a feature that passes every unit test still does nothing useful
 * on a handset.
 */
@RunWith(AndroidJUnit4::class)
class ImageForensicsDeviceTest {

    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val created = mutableListOf<Uri>()

    @After
    fun cleanUp() {
        created.forEach { runCatching { context.contentResolver.delete(it, null, null) } }
    }

    @Test
    fun a_generated_image_is_reported_as_declared_and_leaks_its_prompt() = runBlocking {
        val prompt = "an astronaut riding a horse, 8k\nSteps: 28, Sampler: Euler a, CFG scale: 7"
        val uri = publish("myrecon-test-ai.png", pngWithText("parameters", prompt))

        val report = ImageForensics.analyse(context, uri).getOrElse {
            fail("analysis failed: ${it.message}"); return@runBlocking
        }

        assertEquals(
            ImageProvenance.Origin.DeclaredAiGenerated,
            report.provenance.origin,
        )
        assertEquals(prompt, report.provenance.prompt)

        // The half that matters to the person sharing it: the prompt they typed
        // travels inside the file.
        assertTrue(
            "the embedded prompt should be reported as a leak",
            report.leaks.any { it.what.contains("prompt", ignoreCase = true) },
        )
        assertTrue("a clean copy should be offered", report.cleanCopy.supported)
    }

    @Test
    fun an_ordinary_png_is_not_called_generated() = runBlocking {
        val uri = publish("myrecon-test-plain.png", pngWithText(null, null))
        val report = ImageForensics.analyse(context, uri).getOrElse {
            fail("analysis failed: ${it.message}"); return@runBlocking
        }
        assertEquals(ImageProvenance.Origin.Undeclared, report.provenance.origin)
        assertNull(report.provenance.generator)
    }

    @Test
    fun saving_a_clean_copy_produces_a_readable_file_with_nothing_left_in_it() = runBlocking {
        val uri = publish(
            "myrecon-test-strip.png",
            pngWithText("parameters", "a lighthouse at dusk, Steps: 20"),
        )

        val saved = CleanCopy.save(context, uri).getOrElse {
            fail("save failed: ${it.message}"); return@runBlocking
        }
        created += saved.uri
        assertFalse("a PNG should be edited in place, not re-encoded", saved.recompressed)

        val bytes = context.contentResolver.openInputStream(saved.uri)!!.use { it.readBytes() }

        // Nothing identifying survived...
        val after = ImageProvenance.analyse(bytes)
        assertEquals(ImageProvenance.Origin.Undeclared, after.origin)
        assertTrue(after.textFields.isEmpty())

        // ...and it is still a decodable image of the same size. A stripper
        // that produces an unopenable file would pass every check above.
        val decoded = android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
        assertNotNull("the clean copy must still decode", decoded)
        assertEquals(WIDTH, decoded!!.width)
        assertEquals(HEIGHT, decoded.height)
    }

    // ── Fixtures ─────────────────────────────────────────────────

    /** Put an image into the gallery and hand back the uri the app would get. */
    private fun publish(name: String, bytes: ByteArray): Uri {
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, name)
            put(MediaStore.Images.Media.MIME_TYPE, "image/png")
            put(
                MediaStore.Images.Media.RELATIVE_PATH,
                "${Environment.DIRECTORY_PICTURES}/MyReconTest",
            )
        }
        val uri = context.contentResolver
            .insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)!!
        context.contentResolver.openOutputStream(uri)!!.use { it.write(bytes) }
        created += uri
        return uri
    }

    /**
     * A real PNG from Android's own encoder, optionally carrying a text chunk.
     *
     * Encoded on the device rather than embedded as a fixture so the parser
     * meets whatever Android actually produces — chunk order included.
     */
    private fun pngWithText(keyword: String?, text: String?): ByteArray {
        val bitmap = Bitmap.createBitmap(WIDTH, HEIGHT, Bitmap.Config.ARGB_8888)
        for (y in 0 until HEIGHT) for (x in 0 until WIDTH) {
            bitmap.setPixel(x, y, 0xFF000000.toInt() or (x * 3 shl 16) or (y * 7 shl 8) or x)
        }
        val base = ByteArrayOutputStream()
            .also { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
            .toByteArray()
        bitmap.recycle()
        if (keyword == null || text == null) return base

        val payload = keyword.toByteArray(Charsets.ISO_8859_1) + byteArrayOf(0) +
            text.toByteArray(Charsets.ISO_8859_1)
        val out = ByteArrayOutputStream()
        out.write(base, 0, 8)
        for ((type, data) in ImageProvenance.pngChunks(base)) {
            if (type == "IEND") writeChunk(out, "tEXt", payload)
            writeChunk(out, type, data)
        }
        return out.toByteArray()
    }

    private fun writeChunk(out: ByteArrayOutputStream, type: String, data: ByteArray) {
        val n = data.size
        out.write((n ushr 24) and 0xFF); out.write((n ushr 16) and 0xFF)
        out.write((n ushr 8) and 0xFF); out.write(n and 0xFF)
        val tb = type.toByteArray(Charsets.ISO_8859_1)
        out.write(tb); out.write(data)
        val crc = CRC32().apply { update(tb); update(data) }.value
        out.write(((crc ushr 24) and 0xFF).toInt()); out.write(((crc ushr 16) and 0xFF).toInt())
        out.write(((crc ushr 8) and 0xFF).toInt()); out.write((crc and 0xFF).toInt())
    }

    private companion object {
        const val WIDTH = 96
        const val HEIGHT = 72
    }
}
