package com.aryan.myrecon.work

import android.Manifest
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.aryan.myrecon.MainActivity
import com.aryan.myrecon.R
import com.aryan.myrecon.data.ReconStore
import com.aryan.myrecon.data.UsernameSweep
import kotlinx.coroutines.flow.first
import java.util.concurrent.TimeUnit

/**
 * Re-runs the platform sweep for handles the user asked to watch, and says
 * something only when an account appears that was not there last time.
 *
 * This answers a question no breach feed can: not "was a company breached" but
 * "has something new turned up under your name". Someone registering an
 * account with your handle, or an old profile of yours resurfacing, produces
 * no breach and no notification anywhere else.
 *
 * Separate from [BreachWatchWorker] on purpose, and weekly rather than daily.
 * A sweep is a few hundred outbound requests; running that every day on
 * someone's mobile data to re-confirm the same answer would be rude, and it is
 * the kind of background behaviour that gets an app uninstalled or
 * battery-restricted. Weekly, unmetered, and not on a low battery.
 *
 * The first run for a handle is silent. It records what exists now as the
 * baseline — otherwise enabling the feature would immediately announce every
 * account the user already knew about, which is noise dressed as an alert.
 */
class HandleWatchWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val store = ReconStore(applicationContext)
        val handles = store.watchedHandles.first()
        if (handles.isEmpty()) return Result.success()

        val newFindings = mutableListOf<Pair<String, List<String>>>()

        // Capped per run. Someone watching six handles should not have the app
        // fire off seventeen hundred requests in one wake-up.
        handles.take(MAX_HANDLES_PER_RUN).forEach { handle ->
            val hits = runCatching { sweep(handle) }.getOrNull() ?: return@forEach
            val urls = hits.map { it.trimEnd('/') }.toSet()

            val baseline = store.seenProfiles(handle)
            if (baseline == null) {
                store.markProfilesSeen(handle, urls)
                return@forEach
            }

            val fresh = urls - baseline
            store.markProfilesSeen(handle, urls)
            if (fresh.isNotEmpty()) newFindings += handle to fresh.toList()
        }

        if (newFindings.isNotEmpty()) notifyNewAccounts(newFindings)
        return Result.success()
    }

    /** Confirmed profiles only. An unverified guess is not worth waking someone for. */
    private suspend fun sweep(handle: String): List<String> {
        var found = emptyList<String>()
        UsernameSweep.run(handle).collect { ev ->
            if (ev is UsernameSweep.Event.Finished) {
                found = ev.hits
                    .filter { it.exists && it.confidence != "unverified" }
                    .map { it.url }
            }
        }
        return found
    }

    private fun notifyNewAccounts(findings: List<Pair<String, List<String>>>) {
        val context = applicationContext
        if (!canNotify(context)) return
        BreachWatchWorker.ensureChannel(context)

        val total = findings.sumOf { it.second.size }
        val title = if (findings.size == 1) {
            val (handle, urls) = findings.first()
            if (urls.size == 1) "A new account appeared using @$handle"
            else "${urls.size} new accounts appeared using @$handle"
        } else {
            "$total new accounts appeared under handles you watch"
        }

        val lines = findings.flatMap { (handle, urls) ->
            urls.take(4).map { "@$handle — ${platformOf(it)}" }
        }

        val open = PendingIntent.getActivity(
            context,
            2,
            Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            },
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        val style = NotificationCompat.InboxStyle().setBigContentTitle(title)
        lines.take(5).forEach { style.addLine(it) }
        if (lines.size > 5) style.setSummaryText("and ${lines.size - 5} more")

        val notification = NotificationCompat.Builder(context, BreachWatchWorker.CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_recon)
            .setContentTitle(title)
            .setContentText(lines.firstOrNull().orEmpty())
            .setStyle(style)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setCategory(NotificationCompat.CATEGORY_STATUS)
            .setAutoCancel(true)
            .setContentIntent(open)
            .build()

        runCatching {
            NotificationManagerCompat.from(context).notify(NOTIFICATION_ID, notification)
        }
    }

    /** "instagram.com/x" reads better in a notification than the full URL. */
    private fun platformOf(url: String): String =
        runCatching {
            java.net.URI(url).host.orEmpty().removePrefix("www.").ifBlank { url }
        }.getOrDefault(url)

    private fun canNotify(context: Context): Boolean =
        android.os.Build.VERSION.SDK_INT < 33 ||
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED

    companion object {
        /** Its own id, so a handle finding never overwrites a breach alert. */
        const val NOTIFICATION_ID = 4203

        private const val MAX_HANDLES_PER_RUN = 3
        private const val WORK_NAME = "handle-watch"

        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<HandleWatchWorker>(7, TimeUnit.DAYS)
                .setConstraints(
                    Constraints.Builder()
                        // Unmetered because a sweep is hundreds of requests, and
                        // spending someone's mobile data on a background check
                        // they will not see is not a trade they agreed to.
                        .setRequiredNetworkType(NetworkType.UNMETERED)
                        .setRequiresBatteryNotLow(true)
                        .build()
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 1, TimeUnit.HOURS)
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request,
            )
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
        }
    }
}
