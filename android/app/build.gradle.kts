plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "net.yume.companion"
    compileSdk = 36

    defaultConfig {
        applicationId = "net.yume.companion"
        minSdk = 28
        targetSdk = 35
        versionCode = 2
        versionName = "1.1.0"
        ndk { abiFilters += listOf("arm64-v8a") }
    }

    // Own signing key for releases: the GitHub Action passes it via environment variables, nothing secret is in the repo.
    // Without them the release build is signed with the debug key (fine for your own phone).
    val releaseKeystore = System.getenv("YUME_KEYSTORE")
    signingConfigs {
        if (!releaseKeystore.isNullOrEmpty()) create("release") {
            storeFile = file(releaseKeystore)
            storePassword = System.getenv("YUME_KEYSTORE_PASSWORD")
            keyAlias = System.getenv("YUME_KEY_ALIAS") ?: "yume"
            keyPassword = System.getenv("YUME_KEY_PASSWORD") ?: System.getenv("YUME_KEYSTORE_PASSWORD")
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = if (!releaseKeystore.isNullOrEmpty()) signingConfigs.getByName("release") else signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    packaging {
        resources { excludes += setOf("/META-INF/{AL2.0,LGPL2.1}", "META-INF/DEPENDENCIES") }
        jniLibs { useLegacyPackaging = true }
    }
    lint { abortOnError = false; checkReleaseBuilds = false }
    testOptions { unitTests { isIncludeAndroidResources = true; isReturnDefaultValues = true } }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.06.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.1")
    implementation("androidx.lifecycle:lifecycle-service:2.9.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    // QR scanner
    implementation("androidx.camera:camera-core:1.4.2")
    implementation("androidx.camera:camera-camera2:1.4.2")
    implementation("androidx.camera:camera-lifecycle:1.4.2")
    implementation("androidx.camera:camera-view:1.4.2")
    implementation("com.google.mlkit:barcode-scanning:17.3.0")
    // offline wake word / speech recognition (no account, no key)
    implementation("net.java.dev.jna:jna:5.13.0@aar")
    implementation("com.alphacephei:vosk-android:0.3.47")
    // offline emergency LLM
    implementation("com.google.mediapipe:tasks-genai:0.10.24")
    // layout tests on the PC (no phone needed): renders the screens headless and saves screenshots
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.14.1")
    testImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
