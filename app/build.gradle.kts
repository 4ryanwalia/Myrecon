plugins {
    // AGP 9 compiles Kotlin itself; adding kotlin-android here is an error.
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

android {
    // Source package. Deliberately different from applicationId below: this only
    // names the generated R and BuildConfig classes, so it can stay as it is
    // while the installed identity matches the Play Console entry.
    namespace = "com.aryan.myrecon"
    compileSdk {
        version = release(36) {
            minorApiLevel = 1
        }
    }

    defaultConfig {
        // Must match the Play Console listing character for character — a store
        // entry's package name is fixed when the app is created and cannot be
        // edited afterwards, so the app moves, not the listing. The capital M is
        // unconventional but legal; it is kept because the Console has it.
        applicationId = "com.Myrecon.osint"
        minSdk = 30
        targetSdk = 36
        versionCode = 2
        versionName = "1.1"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // The API host is a build config value rather than a hardcoded string,
        // mirroring how the web frontend takes it from an env var. Override per
        // build type instead of editing source.
        buildConfigField("String", "API_BASE", "\"https://myrecon.onrender.com\"")

        // Real AdMob IDs in every variant, debug included. Safety comes from
        // registering this developer's handset as a test device at runtime, not
        // from swapping the identifier per build type.
        manifestPlaceholders["admobAppId"] = "ca-app-pub-6109270472398539~8843971332"
        buildConfigField(
            "String",
            "AD_BANNER_UNIT",
            "\"ca-app-pub-6109270472398539/3567327992\"",
        )
        buildConfigField(
            "String",
            "AD_REWARDED_UNIT",
            "\"ca-app-pub-6109270472398539/2229481585\"",
        )
        // Ads on everywhere by default; the screenshots variant turns them off.
        buildConfigField("boolean", "SHOW_ADS", "true")
    }

    buildTypes {
        debug {
            buildConfigField("String", "API_BASE", "\"https://myrecon.onrender.com\"")
        }

        /**
         * Store-listing screenshots.
         *
         * Identical to debug except that no ad is requested or drawn. Play
         * discourages listing images dominated by advertising, and a banner
         * across the bottom of every screenshot makes the app look cheaper
         * than it is.
         *
         * It is a separate variant rather than a runtime toggle so there is no
         * chance of shipping a switch that disables monetisation in
         * production. Debug signing keeps it installable alongside normal
         * development.
         *
         *   gradlew installScreenshots
         */
        create("screenshots") {
            initWith(getByName("debug"))
            signingConfig = signingConfigs.getByName("debug")
            buildConfigField("boolean", "SHOW_ADS", "false")
            matchingFallbacks += listOf("debug")

            // Minified like release. An unminified build is ~97 MB, which is
            // more than a wireless-adb link reliably completes — the transfer
            // was dropping mid-install. This also means the screenshots are
            // taken against the same R8 output that ships, so anything
            // minification breaks shows up here rather than in production.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
        release {
            // R8 shrinks and obfuscates. Beyond the size win, it strips the
            // readable class and method names that make an APK trivial to
            // reverse, which is the first thing any assessment looks at.
            isMinifyEnabled = true
            isShrinkResources = true
            // Never ship a debuggable release: it exposes the app's data
            // directory over adb and permits a debugger to attach.
            isDebuggable = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlin {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_11)
        }
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation(libs.core.ktx)
    implementation(libs.lifecycle.runtime.ktx)
    implementation(libs.lifecycle.viewmodel.compose)
    implementation(libs.activity.compose)

    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    implementation(libs.compose.material.icons)
    debugImplementation(libs.compose.ui.tooling)

    implementation(libs.navigation.compose)

    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.coil.compose)

    // Reads EXIF without decoding pixels — needed for on-device image forensics.
    implementation(libs.exifinterface)

    // QR scanning: CameraX for the preview and frame stream, ML Kit for decode.
    // Both run entirely on-device.
    implementation(libs.camera.core)
    implementation(libs.camera.camera2)
    implementation(libs.camera.lifecycle)
    implementation(libs.camera.view)
    implementation(libs.mlkit.barcode)

    // Periodic breach checks and local persistence.
    implementation(libs.work.runtime)
    implementation(libs.datastore.preferences)

    // AdMob, plus Google's consent SDK for EEA/UK users.
    implementation(libs.play.services.ads)
    implementation(libs.user.messaging.platform)

    testImplementation(libs.junit)
    androidTestImplementation(libs.ext.junit)
    androidTestImplementation(libs.espresso.core)
    androidTestImplementation(platform(libs.compose.bom))
}
