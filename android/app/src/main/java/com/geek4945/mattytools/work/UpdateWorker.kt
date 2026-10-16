package com.geek4945.mattytools.work

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.*
import com.geek4945.mattytools.MainActivity
import com.geek4945.mattytools.R
import com.geek4945.mattytools.ToolsApp
import com.geek4945.mattytools.data.UpdateResult
import java.util.concurrent.TimeUnit

/** Runs about once a month (WorkManager periodic work, network required). */
class UpdateWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result {
        val repo = (applicationContext as ToolsApp).repo
        return when (val r = repo.checkForUpdates()) {
            is UpdateResult.Updated -> {
                if (r.newCount > 0 && repo.notificationsEnabled()) notifyNew(applicationContext, r.newCount)
                Result.success()
            }
            is UpdateResult.UpToDate -> Result.success()
            // retry a few times with backoff, then wait for the next monthly run
            is UpdateResult.Failed -> if (runAttemptCount < 3) Result.retry() else Result.success()
        }
    }

    companion object {
        const val WORK_NAME = "monthly-catalog-update"
        const val CHANNEL = "catalog_updates"

        fun schedule(ctx: Context) {
            val req = PeriodicWorkRequestBuilder<UpdateWorker>(30, TimeUnit.DAYS, 3, TimeUnit.DAYS)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 1, TimeUnit.HOURS)
                .build()
            // KEEP: don't reset the 30 day timer every time the app opens
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(WORK_NAME, ExistingPeriodicWorkPolicy.KEEP, req)
        }

        fun ensureChannel(ctx: Context) {
            if (Build.VERSION.SDK_INT >= 26) {
                val nm = ctx.getSystemService(NotificationManager::class.java)
                nm.createNotificationChannel(NotificationChannel(CHANNEL, "New tools", NotificationManager.IMPORTANCE_DEFAULT)
                    .apply { description = "Monthly update check: new tools added to the directory" })
            }
        }

        fun notifyNew(ctx: Context, count: Int) {
            ensureChannel(ctx)
            if (Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
            val open = PendingIntent.getActivity(
                ctx, 0, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP).putExtra("show_new", true),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            val text = if (count == 1) "1 new tool added" else "$count new tools added"
            val n = NotificationCompat.Builder(ctx, CHANNEL)
                .setSmallIcon(android.R.drawable.ic_popup_sync)
                .setContentTitle(text).setContentText("Tap to see what's new in Matty Tools Directory")
                .setContentIntent(open).setAutoCancel(true).build()
            NotificationManagerCompat.from(ctx).notify(1001, n)
        }
    }
}
