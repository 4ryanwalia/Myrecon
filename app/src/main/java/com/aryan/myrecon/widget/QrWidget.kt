package com.aryan.myrecon.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import com.aryan.myrecon.MainActivity
import com.aryan.myrecon.R

/**
 * Home screen widget: one tap into the QR scanner.
 *
 * A widget cannot host a camera — RemoteViews has no preview surface — so this
 * is deliberately a button rather than a readout. What it removes is the gap
 * between standing in front of a code and having the phone pointed at it: cold
 * start, find the app, find the Scan tab. Those seconds are the whole reason
 * people reach for the camera app's built-in scanner instead, and that one
 * tells them nothing about where the link goes.
 *
 * It does no work at all. `onUpdate` builds a static RemoteViews and attaches a
 * single PendingIntent — no DataStore read, no network, no `goAsync()`, and
 * `updatePeriodMillis` is 0 so the system never wakes it. Widget rendering runs
 * inside the launcher's process, where anything slow shows up as home screen
 * jank that the user blames on their phone.
 *
 * The launch itself is where the perceived lag actually lives, and that is
 * handled on the other side: the intent names its destination so MainActivity
 * composes straight onto the Scan tab, and starts warming CameraX in parallel
 * with the first frame instead of after it.
 */
class QrWidget : AppWidgetProvider() {

    override fun onUpdate(
        context: Context,
        manager: AppWidgetManager,
        ids: IntArray,
    ) {
        val views = RemoteViews(context.packageName, R.layout.widget_qr).apply {
            // The whole card is the target. A 42dp icon is a miss on a home
            // screen; the full width of the widget is not.
            setOnClickPendingIntent(R.id.widget_qr_root, launchScanner(context))
        }
        ids.forEach { manager.updateAppWidget(it, views) }
    }

    private fun launchScanner(context: Context): PendingIntent {
        val intent = Intent(context, MainActivity::class.java).apply {
            action = Intent.ACTION_VIEW
            putExtra(MainActivity.EXTRA_TAB, MainActivity.TAB_SCAN)
            // CLEAR_TOP with SINGLE_TOP delivers onNewIntent to an activity that
            // is already running rather than stacking a second copy, so tapping
            // the widget while the app is open switches tabs instead of
            // rebuilding the whole thing.
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or
                Intent.FLAG_ACTIVITY_CLEAR_TOP or
                Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        return PendingIntent.getActivity(
            context,
            REQUEST_SCAN,
            intent,
            // UPDATE_CURRENT so the extra is refreshed rather than the stale
            // one from the first placement being replayed.
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
    }

    private companion object {
        const val REQUEST_SCAN = 0x51
    }
}
