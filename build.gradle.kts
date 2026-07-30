// Top-level build file where you can add configuration options common to all sub-projects/modules.
plugins {
    // No kotlin-android plugin: AGP 9.0+ has built-in Kotlin support and
    // rejects it. The Compose and serialization compiler plugins are still
    // applied separately.
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
}