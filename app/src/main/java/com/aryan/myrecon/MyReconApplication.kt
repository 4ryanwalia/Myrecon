package com.aryan.myrecon

import android.app.Application
import com.aryan.myrecon.ads.Ads
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

    /**
     * Start the ad SDK here, not from a composable.
     *
     * It used to be kicked off by the banner, which meant every ad request in
     * the app raced initialisation and any request that lost was discarded —
     * fine on a fast emulator, silently broken on a handset. Starting it at
     * process creation gives the SDK the whole cold start to get ready, and
     * every ad path suspends on Ads.awaitReady() before requesting anyway.
     */
    override fun onCreate() {
        super.onCreate()
        Ads.start(this)
    }

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
                        val request = chain.request()
                        val host = request.url.host.lowercase()
                        val headers = request.newBuilder()
                            .header("User-Agent", "Mozilla/5.0 (Linux; Android 14) Mobile Safari/537.36")
                            .header("Accept", "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8")
                            .header("Accept-Language", "en-US,en;q=0.9")

                        // Instagram image URLs are served from its CDN rather
                        // than instagram.com. That CDN can reject direct
                        // image requests without the originating site, even
                        // though the profile API supplied a valid URL.
                        if (host.endsWith("cdninstagram.com") || host.endsWith("fbcdn.net")) {
                            headers.header("Referer", "https://www.instagram.com/")
                        }
                        chain.proceed(
                            headers.build()
                        )
                    }
                    .build()
            }
            .memoryCachePolicy(CachePolicy.ENABLED)
            .diskCachePolicy(CachePolicy.ENABLED)
            .crossfade(180)
            .build()
}
