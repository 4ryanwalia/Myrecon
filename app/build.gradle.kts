plugins {
    // AGP 9 compiles Kotlin itself; adding kotlin-android here is an error.
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.aryan.myrecon"
    compileSdk {
        version = release(36) {
            minorApiLevel = 1
        }
    }

    defaultConfig {
        applicationId = "com.aryan.myrecon"
        minSdk = 30
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // The API host is a build config value rather than a hardcoded string,
        // mirroring how the web frontend takes it from an env var. Override per
        // build type instead of editing source.
        buildConfigField("String", "API_BASE", "\"https://myrecon.onrender.com\"")
    }

    // AdMob identifiers.
    //
    // These are publisher IDs, not credentials — every published APK carries
    // them in plain sight and the SDK requires it. The reason they are split by
    // build type is policy, not secrecy: impressions or clicks a developer
    // generates against a live ad unit count as invalid traffic, and repeated
    // invalid traffic gets an AdMob account suspended. Debug therefore uses
    // Google's public test units, which serve real-looking ads that bill
    // nobody.
    val realAppId = "ca-app-pub-6109270472398539~8843971332"
    val realBanner = "ca-app-pub-6109270472398539/3567327992"
    val testAppId = "ca-app-pub-3940256099942544~3347511713"
    val testBanner = "ca-app-pub-3940256099942544/6300978111"

    buildTypes {
        debug {
            buildConfigField("String", "API_BASE", "\"https://myrecon.onrender.com\"")
            buildConfigField("String", "AD_BANNER_UNIT", "\"$testBanner\"")
            manifestPlaceholders["admobAppId"] = testAppId
        }
        release {
            buildConfigField("String", "AD_BANNER_UNIT", "\"$realBanner\"")
            manifestPlaceholders["admobAppId"] = realAppId

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
