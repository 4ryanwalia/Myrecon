package com.aryan.myrecon

import android.graphics.Bitmap
import android.graphics.Canvas
import android.util.TypedValue
import android.view.View
import android.widget.FrameLayout
import android.widget.RemoteViews
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.aryan.myrecon.widget.QrWidget
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Proves the QR widget actually inflates as RemoteViews, and draws it.
 *
 * A widget is rendered inside the launcher's process, where an unsupported view
 * class or a missing resource does not throw where anyone can see it — it turns
 * into "Problem loading widget" on the home screen with nothing in the app's
 * log. `RemoteViews.apply` reproduces that inflation path exactly, so this test
 * fails in CI rather than on a user's home screen.
 *
 * It also writes the rendered result to a PNG, because the other half of the
 * requirement is that it looks right at the size a launcher gives it.
 */
@RunWith(AndroidJUnit4::class)
class QrWidgetRenderTest {

    @Test
    fun widget_inflates_and_draws() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext

        // The same call the launcher makes. Anything RemoteViews rejects —
        // a ConstraintLayout, a custom view, an attribute it does not support —
        // throws here.
        val views = RemoteViews(context.packageName, R.layout.widget_qr)
        val rendered: View = views.apply(context, FrameLayout(context))
        assertNotNull(rendered)

        // A realistic placement: three cells wide, one tall.
        val width = dp(context, 260f)
        val height = dp(context, 72f)
        rendered.measure(
            View.MeasureSpec.makeMeasureSpec(width, View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec(height, View.MeasureSpec.EXACTLY),
        )
        rendered.layout(0, 0, width, height)

        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        rendered.draw(Canvas(bitmap))

        // A widget that laid out to nothing is the other silent failure: it
        // renders as an empty rectangle rather than an error.
        assertTrue("widget measured to nothing", rendered.measuredHeight > 0)
        val title = rendered.findViewById<android.widget.TextView>(R.id.widget_qr_title)
        assertTrue("title did not lay out", title.width > 0 && title.height > 0)

        // Written through MediaStore into Downloads: this device blocks shell
        // access to both Android/data and run-as, so it is the only place the
        // render can be collected from afterwards.
        val values = android.content.ContentValues().apply {
            put(android.provider.MediaStore.Downloads.DISPLAY_NAME, "widget_qr_render.png")
            put(android.provider.MediaStore.Downloads.MIME_TYPE, "image/png")
        }
        val uri = context.contentResolver.insert(
            android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI, values
        )
        assertNotNull("could not create the output file", uri)
        context.contentResolver.openOutputStream(uri!!)!!.use {
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)
        }
    }

    @Test
    fun update_touches_no_storage_and_no_network() {
        // The anti-lag contract, asserted rather than commented: onUpdate runs
        // on the launcher's main thread, so if it ever grows a DataStore read
        // or an HTTP call, StrictMode catches it here.
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val manager = android.appwidget.AppWidgetManager.getInstance(context)

        val policy = android.os.StrictMode.getThreadPolicy()
        android.os.StrictMode.setThreadPolicy(
            android.os.StrictMode.ThreadPolicy.Builder()
                .detectDiskReads().detectDiskWrites().detectNetwork()
                .penaltyDeath()
                .build()
        )
        try {
            // No placed widget ids, so this is the render path without the
            // manager round trip — which is exactly the work being measured.
            QrWidget().onUpdate(context, manager, intArrayOf())
        } finally {
            android.os.StrictMode.setThreadPolicy(policy)
        }
    }

    private fun dp(context: android.content.Context, value: Float): Int =
        TypedValue.applyDimension(
            TypedValue.COMPLEX_UNIT_DIP, value, context.resources.displayMetrics
        ).toInt()
}
