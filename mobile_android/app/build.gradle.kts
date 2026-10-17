plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

fun panelUrlFromConfig(): String {
    val f = rootProject.projectDir.parentFile.resolve("config/mobile_default_servers.txt")
    if (!f.isFile) {
        return "about:blank"
    }
    val line = f.readLines()
        .map { it.trim() }
        .firstOrNull { it.startsWith("http://") || it.startsWith("https://") }
        ?: "about:blank"
    return if (line.endsWith("/")) line else "$line/"
}

android {
    namespace = "com.goldenshield.control"
    compileSdk = 34

    buildFeatures {
        buildConfig = true
    }

    defaultConfig {
        applicationId = "com.goldenshield.control"
        minSdk = 24
        targetSdk = 34
        versionCode = 7
        versionName = "2.2.0-live-discovery"
        buildConfigField("String", "PANEL_URL", "\"${panelUrlFromConfig()}\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
}
