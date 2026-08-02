allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    project.evaluationDependsOn(":app")
}

subprojects {
    val configureAndroid = {
        val ext = project.extensions.findByName("android")
        if (ext != null) {
            try {
                ext.javaClass.getMethod("setCompileSdk", java.lang.Integer.TYPE).invoke(ext, 36)
            } catch (_: Exception) {
                try {
                    ext.javaClass.getMethod("compileSdkVersion", java.lang.Integer.TYPE).invoke(ext, 36)
                } catch (_: Exception) {}
            }
        }
    }
    if (project.state.executed) {
        configureAndroid()
    } else {
        project.afterEvaluate {
            configureAndroid()
        }
    }
}



tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}

