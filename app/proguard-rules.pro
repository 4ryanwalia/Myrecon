# ── kotlinx.serialization ───────────────────────────────────────────
# The generated serializers are referenced reflectively, so R8 cannot see the
# link and would strip them. Without these rules the release build compiles
# cleanly and then fails at runtime on the first API response — the classic way
# minification breaks an app only after it ships.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**

-keepclassmembers class kotlinx.serialization.json.** {
    *** Companion;
}
-keepclasseswithmembers class kotlinx.serialization.json.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Every @Serializable model in this app, plus its generated $$serializer.
-keep,includedescriptorclasses class com.aryan.myrecon.**$$serializer { *; }
-keepclassmembers class com.aryan.myrecon.** {
    *** Companion;
}
-keepclasseswithmembers class com.aryan.myrecon.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# ── OkHttp / Okio ──────────────────────────────────────────────────
# Optional platform integrations OkHttp probes for reflectively.
-dontwarn okhttp3.internal.platform.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**

# ── ML Kit ─────────────────────────────────────────────────────────
# Model loading is reflective; obfuscating these breaks barcode scanning.
-keep class com.google.mlkit.** { *; }
-keep class com.google.android.gms.internal.mlkit_** { *; }

# ── WorkManager ────────────────────────────────────────────────────
# Workers are instantiated by name from the scheduler.
-keep class * extends androidx.work.Worker
-keep class * extends androidx.work.CoroutineWorker
-keepclassmembers class * extends androidx.work.ListenableWorker {
    public <init>(android.content.Context, androidx.work.WorkerParameters);
}

# ── Logging ────────────────────────────────────────────────────────
# Strip Log calls from the release binary. Nothing sensitive is logged today,
# but this makes that guarantee structural rather than a habit to maintain.
-assumenosideeffects class android.util.Log {
    public static *** v(...);
    public static *** d(...);
    public static *** i(...);
}
