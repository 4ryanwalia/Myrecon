package com.aryan.myrecon

import android.app.Application
import coil.ImageLoader
import coil.ImageLoaderFactory
import coil.disk.DiskCache
import coil.memory.MemoryCache
import coil.request.CachePolicy
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

/**
 * Configures the shared Coil image loader.
 *
 * A broad sweep can surface seventy accounts at once, each with an avatar
 * hosted on a different CDN. Coil's defaults would open all of them together,
 * which on mobile data is both slow and wasteful, so:
 *
 *  • the memory cache is capped as a share of available heap rather than a
 *    fixed byte count, so low-end devices are not pushed toward an OOM;
 *  • a disk cache means a repeated lookup for the same handle costs no data;
 *  • a dedicated OkHttp client keeps short timeouts, because a slow avatar must
 *    never hold up the list — the monogram fallback is already on screen.
 *
 * `allowHardware` stays on: these are small thumbnails that are never read back
 * into software bitmaps.
 */
class MyReconApplication : Application(), ImageLoaderFactory {

    override fun newImageLoader(): ImageLoader =
        ImageLoader.Builder(this)
            .memoryCache {
                MemoryCache.Builder(this)
                    .maxSizePercent(0.20)
                    .build()
            }
            .diskCache {
                DiskCache.Builder()
                    .directory(cacheDir.resolve("avatars"))
                    .maxSizeBytes(24L * 1024 * 1024)
                    .build()
            }
            .okHttpClient {
                OkHttpClient.Builder()
                    .connectTimeout(6, TimeUnit.SECONDS)
                    .readTimeout(10, TimeUnit.SECONDS)
                    // Many avatar CDNs reject requests without a browser-like
                    // agent, which reads as a broken image rather than a block.
                    .addInterceptor { chain ->
                        chain.proceed(
                            chain.request().newBuilder()
                                .header("User-Agent", "Mozilla/5.0 (Linux; Android 14) Mobile Safari/537.36")
                                .build()
                        )
                    }
                    .build()
            }
            .memoryCachePolicy(CachePolicy.ENABLED)
            .diskCachePolicy(CachePolicy.ENABLED)
            .crossfade(180)
            .build()
}
