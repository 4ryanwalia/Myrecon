package com.aryan.myrecon.work

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.*
import com.aryan.myrecon.MainActivity
import com.aryan.myrecon.R
import com.aryan.myrecon.data.BreachFeed
import com.aryan.myrecon.data.ReconStore
import java.util.concurrent.TimeUnit

/**
 * Periodic check for newly published breaches.
 *
 * Runs on-device against Have I Been Pwned's keyless catalogue. Nothing about
 * the user is transmitted — the app downloads the public list and compares it
 * locally, so there is no account, no signup, and no address handed to anyone.
 * Every competing breach-alert service requires exactly the opposite.
 *
 * The notification only ever fires for a breach the app has not reported
 * before. On first run the whole catalogue is recorded silently as a baseline;
 * without that, a fresh install would announce a thousand historical breaches
 * and be muted within the minute.
 */
class BreachWatchWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val store = ReconStore(applicationContext)

        val all = runCatching { BreachFeed.fetchAll() }.getOrElse {
            // Offline or rate-limited is a retry, not a failure — the periodic
            // schedule would otherwise skip an entire interval.
            return Result.retry()
        }
        if (all.isEmpty()) return Result.retry()

        val firstRun = !store.hasBaseline()
        if (firstRun) {
            store.markSeen(all.map { it.name })
            store.recordCheck()
            return Result.success()
        }

        val fresh = BreachFeed.newSince(all, store.seenBreaches())
        store.markSeen(all.map { it.name })
        store.recordCheck()

        if (fresh.isNotEmpty()) notify(fresh)
        return Result.success()
    }

    private fun notify(fresh: List<BreachFeed.Breach>) {
        val context = applicationContext
        if (!canNotify(context)) return

        ensureChannel(context)

        // Severe first: a breach leaking passwords or bank details is the one
        // worth waking someone for.
        val lead = fresh.sortedByDescending { it.isSevere }.first()
        val extra = fresh.size - 1

        val title = if (extra > 0) {
            "${lead.displayTitle} + $extra more breach${if (extra == 1) "" else "es"}"
        } else {
            "New breach: ${lead.displayTitle}"
        }

        val body = buildString {
            append(BreachFeed.headline(lead))
            append(" Check whether your details were included.")
        }

        val open = PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
                // Land on the email checker, which is the action the
                // notification is asking the user to take.
                putExtra(EXTRA_OPEN_TAB, TAB_EMAIL)
            },
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        val style = NotificationCompat.InboxStyle().setBigContentTitle(title)
        fresh.take(5).forEach { b ->
            style.addLine("${b.displayTitle} — ${BreachFeed.headline(b)}")
        }
        if (fresh.size > 5) style.setSummaryText("and ${fresh.size - 5} more")

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_recon)
            .setContentTitle(title)
            .setContentText(body)
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

    private fun canNotify(context: Context): Boolean =
        android.os.Build.VERSION.SDK_INT < 33 ||
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED

    companion object {
        const val CHANNEL_ID = "breach_alerts"
        const val NOTIFICATION_ID = 4201
        const val EXTRA_OPEN_TAB = "open_tab"
        const val TAB_EMAIL = "email"

        private const val WORK_NAME = "breach-watch"

        fun ensureChannel(context: Context) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Breach alerts",
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply {
                description = "Tells you when a new data breach is published, so you can " +
                    "check whether your details were in it."
            }
            context.getSystemService(NotificationManager::class.java)
                ?.createNotificationChannel(channel)
        }

        /**
         * Schedule the recurring check.
         *
         * Daily rather than hourly: breaches are published a few times a week,
         * so anything more frequent spends battery to learn nothing. KEEP means
         * re-launching the app does not reset the interval and re-trigger a
         * check on every cold start.
         */
        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<BreachWatchWorker>(1, TimeUnit.DAYS)
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .setRequiresBatteryNotLow(true)
                        .build()
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.MINUTES)
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request,
            )
        }

        /** Run once now — used after the user opts in, so they see it work. */
        fun runNow(context: Context) {
            WorkManager.getInstance(context).enqueue(
                OneTimeWorkRequestBuilder<BreachWatchWorker>()
                    .setConstraints(
                        Constraints.Builder()
                            .setRequiredNetworkType(NetworkType.CONNECTED)
                            .build()
                    )
                    .build()
            )
        }
    }
}
