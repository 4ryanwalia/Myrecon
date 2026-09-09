package com.aryan.myrecon.data

import android.content.ContentValues
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Write a copy of an image with everything identifying removed.
 *
 * Saved into Pictures rather than Downloads so it lands in the gallery, which
 * is where a share sheet is opened from. A privacy tool that leaves its output
 * somewhere the user has to go hunting for gets used once.
 */
object CleanCopy {

    data class Saved(
        val uri: Uri,
        val displayName: String,
        val removed: List<String>,
        val bytesSaved: Int,
        /** True when the container had to be re-encoded rather than edited. */
        val recompressed: Boolean,
    )

    suspend fun save(context: Context, source: Uri): Result<Saved> =
        withContext(Dispatchers.IO) {
            runCatching {
                val bytes = context.contentResolver.openInputStream(source)?.use { it.readBytes() }
                    ?: error("The image could not be re-opened.")

                val stripped = MetadataStrip.strip(bytes)
                val (payload, mime, extension, removed, recompressed) = if (stripped != null) {
                    val jpeg = ImageProvenance.containerOf(bytes) ==
                        ImageProvenance.Container.Jpeg
                    Payload(
                        stripped.bytes,
                        if (jpeg) "image/jpeg" else "image/png",
                        if (jpeg) "jpg" else "png",
                        stripped.removed,
                        false,
                    )
                } else {
                    // HEIC and WebP have no lossless path here, and refusing
                    // outright would leave every iPhone photo unprotected. A
                    // re-encode drops all metadata by construction; the cost is
                    // one JPEG generation, which is stated rather than hidden.
                    val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                        ?: error("This format cannot be cleaned on device.")
                    val out = java.io.ByteArrayOutputStream()
                    try {
                        bitmap.compress(Bitmap.CompressFormat.JPEG, 95, out)
                    } finally {
                        bitmap.recycle()
                    }
                    Payload(
                        out.toByteArray(),
                        "image/jpeg",
                        "jpg",
                        listOf("All metadata (the image was re-encoded)"),
                        true,
                    )
                }

                val name = "myrecon-clean-${System.currentTimeMillis()}.$extension"
                val values = ContentValues().apply {
                    put(MediaStore.Images.Media.DISPLAY_NAME, name)
                    put(MediaStore.Images.Media.MIME_TYPE, mime)
                    put(
                        MediaStore.Images.Media.RELATIVE_PATH,
                        "${Environment.DIRECTORY_PICTURES}/MyRecon",
                    )
                    // Kept out of the gallery until the bytes are written, so a
                    // failure halfway cannot leave a truncated image on show.
                    put(MediaStore.Images.Media.IS_PENDING, 1)
                }

                val resolver = context.contentResolver
                val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
                    ?: error("The gallery would not accept a new file.")

                runCatching {
                    resolver.openOutputStream(uri)?.use { it.write(payload) }
                        ?: error("The file could not be written.")
                }.onFailure {
                    resolver.delete(uri, null, null)
                    throw it
                }

                resolver.update(
                    uri,
                    ContentValues().apply { put(MediaStore.Images.Media.IS_PENDING, 0) },
                    null,
                    null,
                )

                Saved(
                    uri = uri,
                    displayName = name,
                    removed = removed,
                    bytesSaved = bytes.size - payload.size,
                    recompressed = recompressed,
                )
            }
        }

    private data class Payload(
        val bytes: ByteArray,
        val mime: String,
        val extension: String,
        val removed: List<String>,
        val recompressed: Boolean,
    )
}
