package com.aryan.myrecon.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import com.aryan.myrecon.MainActivity
import com.aryan.myrecon.R
import com.aryan.myrecon.data.BreachArticles
import com.aryan.myrecon.data.ReconStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Home screen widget: what is still unhandled, and the latest breach.
 *
 * A widget is the only surface that keeps an app present without being opened,
 * which is exactly the problem a search-once tool has. It earns its space only
 * if the number on it moves, so it shows the two things here that do: how many
 * accounts from the last sweep still need a decision, and the most recent entry
 * in The Breach Files.
 *
 * Built with RemoteViews rather than Glance on purpose — Glance would add a
 * dependency and a Compose runtime to render four lines of text.
 */
class ExposureWidget : AppWidgetProvider() {

    override fun onUpdate(
        context: Context,
        manager: AppWidgetManager,
        ids: IntArray,
    ) {
        // Reading DataStore and the feed is suspending work, and a receiver is
        // dead the moment onUpdate returns. goAsync() keeps the process alive
        // for the round trip.
        val pending = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try {
                val views = render(context)
                ids.forEach { manager.updateAppWidget(it, views) }
            } finally {
                pending.finish()
            }
        }
    }

    private suspend fun render(context: Context): RemoteViews {
        val views = RemoteViews(context.packageName, R.layout.widget_exposure)
        val store = ReconStore(context.applicationContext)

        val scan = runCatching { store.lastScan() }.getOrNull()
        if (scan == null) {
            views.setTextViewText(R.id.widget_headline, "Run a scan to begin")
            views.setTextViewText(
                R.id.widget_detail,
                "Check a handle across the platform catalogue",
            )
        } else {
            val decisions = runCatching { store.cleanupFor(scan.handle).first() }
                .getOrDefault(emptyMap())
            val total = scan.profiles.size
            val handled = scan.profiles.count { p ->
                val state = decisions[p.url.trimEnd('/')]
                state != null && state != ReconStore.Cleanup.Todo
            }
            val left = (total - handled).coerceAtLeast(0)

            views.setTextViewText(
                R.id.widget_headline,
                when {
                    total == 0 -> "Nothing found for @${scan.handle}"
                    left == 0 -> "All $total handled"
                    else -> "$left of $total left to handle"
                },
            )
            views.setTextViewText(R.id.widget_detail, "@${scan.handle}")
        }

        // The feed is a nice-to-have on a widget: if the network is down the
        // rest of it is still correct, so a failure here must not blank it.
        val latest = runCatching { BreachArticles.load().breaches.firstOrNull() }.getOrNull()
        views.setTextViewText(
            R.id.widget_breach,
            latest?.let { "Latest breach · ${it.title}" }.orEmpty(),
        )

        views.setOnClickPendingIntent(
            R.id.widget_headline,
            PendingIntent.getActivity(
                context,
                0,
                Intent(context, MainActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
                },
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            ),
        )
        return views
    }

    companion object {
        /**
         * Redraw every placed widget.
         *
         * Called when the underlying numbers change — a scan finishing, an
         * account being marked — so the widget is current before the hourly
         * refresh comes round rather than up to an hour stale.
         */
        fun refresh(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(
                ComponentName(context, ExposureWidget::class.java)
            )
            if (ids.isEmpty()) return
            context.sendBroadcast(
                Intent(context, ExposureWidget::class.java).apply {
                    action = AppWidgetManager.ACTION_APPWIDGET_UPDATE
                    putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids)
                }
            )
        }
    }
}
