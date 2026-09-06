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
import com.aryan.myrecon.data.AccountBreachCheck
import com.aryan.myrecon.data.BreachFeed
import com.aryan.myrecon.data.ReconStore
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import java.util.concurrent.TimeUnit

/**
 * Periodic check for newly published breaches. Two halves, with deliberately
 * different privacy costs.
 *
 * **The catalogue check** runs on-device against Have I Been Pwned's keyless
 * list. Nothing about the user is transmitted — the public list is downloaded
 * and compared locally, so there is no account, no signup, and no address
 * handed to anyone. Every competing breach-alert service requires exactly the
 * opposite. This half is always on once alerts are enabled.
 *
 * **The per-address check** answers the question the catalogue cannot: not
 * "did a breach happen" but "were you in it". That requires sending the
 * address to a lookup service, so it is gated behind its own consent flag
 * (`ReconStore.emailMonitoring`) that the catalogue switch does not grant. If
 * that flag is off, or no address is watched, nothing here transmits anything
 * and the behaviour is exactly as it was before the feature existed.
 *
 * Both halves only ever notify about something not reported before. First run
 * records the current state silently as a baseline; without that, a fresh
 * install would announce a thousand historical breaches — and a newly watched
 * address would open with a push about a 2018 dump — and be muted within the
 * minute.
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
        checkWatchedAddresses(store)
        return Result.success()
    }

    /**
     * The personal half: has anything new turned up for an address the user
     * asked us to watch.
     *
     * Runs only with explicit consent, because unlike the catalogue check this
     * one transmits the address. Silence here is never assumed to be good news
     * — a lookup that fails returns null and the address's history is left
     * untouched, so the finding still surfaces on the next run instead of being
     * marked as already seen.
     */
    private suspend fun checkWatchedAddresses(store: ReconStore) {
        if (!store.isEmailMonitoringOn()) return
        val watched = store.watchedEmails.first()
        if (watched.isEmpty()) return

        val findings = mutableListOf<Pair<String, List<AccountBreachCheck.Source>>>()
        var severe = false

        // Capped and paced: the public endpoint is rate-limited, and a burst
        // gets the whole run throttled rather than just the last address.
        for (email in watched.sorted().take(MAX_ADDRESSES_PER_RUN)) {
            val report = AccountBreachCheck.check(email) ?: continue

            if (!store.hasBaselineFor(email)) {
                // First look: record what is already known without alerting.
                store.markSourcesSeen(email, report.sources.map { it.name })
                continue
            }

            val seen = store.seenSourcesFor(email)
            val new = report.sources.filter { it.name !in seen }
            store.markSourcesSeen(email, report.sources.map { it.name })
            if (new.isNotEmpty()) {
                findings += email to new
                if (report.isSevere) severe = true
            }
            delay(REQUEST_SPACING_MS)
        }

        if (findings.isNotEmpty()) notifyAccounts(findings, severe)
    }

    /**
     * Alert for the user's own address, kept separate from the catalogue
     * notification in both id and channel priority. "A breach happened" and
     * "you are in it" are different messages and must not overwrite each other.
     */
    private fun notifyAccounts(
        findings: List<Pair<String, List<AccountBreachCheck.Source>>>,
        severe: Boolean,
    ) {
        val context = applicationContext
        if (!canNotify(context)) return
        ensureChannel(context)

        val addresses = findings.size
        val title = if (addresses == 1) {
            "Your address appeared in a new breach"
        } else {
            "$addresses of your addresses appeared in new breaches"
        }

        val lines = findings.flatMap { (email, sources) ->
            sources.take(4).map { "$email — ${it.label}" }
        }
        val body = lines.firstOrNull().orEmpty()

        val open = PendingIntent.getActivity(
            context,
            1,
            Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
                putExtra(EXTRA_OPEN_TAB, TAB_EMAIL)
            },
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        val style = NotificationCompat.InboxStyle().setBigContentTitle(title)
        lines.take(5).forEach { style.addLine(it) }
        if (lines.size > 5) style.setSummaryText("and ${lines.size - 5} more")

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_recon)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(style)
            // Being personally exposed outranks a general news item, and a
            // credential or identity-document leak outranks both.
            .setPriority(if (severe) NotificationCompat.PRIORITY_HIGH else NotificationCompat.PRIORITY_DEFAULT)
            .setCategory(NotificationCompat.CATEGORY_STATUS)
            .setAutoCancel(true)
            .setContentIntent(open)
            .build()

        runCatching {
            NotificationManagerCompat.from(context).notify(ACCOUNT_NOTIFICATION_ID, notification)
        }
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
        /** Separate id: a personal hit must not overwrite the news item. */
        const val ACCOUNT_NOTIFICATION_ID = 4202

        /** The public endpoint is rate-limited; a burst throttles the run. */
        private const val MAX_ADDRESSES_PER_RUN = 5
        private const val REQUEST_SPACING_MS = 1_500L
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
