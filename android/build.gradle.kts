// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
plugins {
    id("com.android.application") version "8.13.2" apply false
    id("org.jetbrains.kotlin.android") version "2.1.21" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.1.21" apply false
}

// Keep build output out of the (possibly cloud-synced) source folder.
val yumeBuildRoot: String? = System.getenv("YUME_BUILD_ROOT")
if (yumeBuildRoot != null) {
    allprojects {
        layout.buildDirectory.set(file("$yumeBuildRoot/out/${project.name}"))
    }
}
