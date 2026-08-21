
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile
import com.google.protobuf.gradle.*
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    kotlin("jvm") version "2.4.10"
    application
    id("java")
    id("idea")
    id("com.google.protobuf") version "0.10.0"
    id("com.gradleup.shadow") version "8.3.11"
}

group = "io.opentelemetry"
version = "1.0"


val grpcVersion = "1.83.1"
val protobufVersion = "4.36.0"
val nettyVersion = "4.2.17.Final"
val jacksonVersion = "2.22.2"


repositories {
    mavenCentral()
    gradlePluginPortal()
}



dependencies {
    // netty/jackson kéo vào transitively qua grpc-netty, kafka-clients và flagd;
    // BOM ép version đã vá cho cả nhánh transitive (Trivy gate CRITICAL,HIGH).
    implementation(platform("io.netty:netty-bom:${nettyVersion}"))
    implementation(platform("com.fasterxml.jackson:jackson-bom:${jacksonVersion}"))
    implementation("com.google.protobuf:protobuf-java:${protobufVersion}")
    testImplementation(kotlin("test"))
    implementation(kotlin("script-runtime"))
    implementation("org.apache.kafka:kafka-clients:4.3.1")
    implementation("com.google.api.grpc:proto-google-common-protos:2.74.0")
    implementation("io.grpc:grpc-protobuf:${grpcVersion}")
    implementation("io.grpc:grpc-stub:${grpcVersion}")
    implementation("io.grpc:grpc-netty:${grpcVersion}")
    implementation("io.grpc:grpc-services:${grpcVersion}")
    implementation("io.opentelemetry:opentelemetry-api:1.65.0")
    implementation("io.opentelemetry:opentelemetry-sdk:1.65.0")
    implementation("io.opentelemetry:opentelemetry-extension-annotations:1.18.0")
    implementation("org.apache.logging.log4j:log4j-core:2.26.1")
    implementation("org.slf4j:slf4j-api:2.0.18")
    implementation("com.google.protobuf:protobuf-kotlin:${protobufVersion}")
    implementation("dev.openfeature:sdk:1.22.0")
    implementation("dev.openfeature.contrib.providers:flagd:0.14.1")

    if (JavaVersion.current().isJava9Compatible) {
        // Workaround for @javax.annotation.Generated
        // see: https://github.com/grpc/grpc-java/issues/3633
        implementation("javax.annotation:javax.annotation-api:1.3.2")
    }
}

tasks {
    shadowJar {
        mergeServiceFiles()
    }
}

tasks.test {
    useJUnitPlatform()
}

kotlin {
  compilerOptions {
    jvmTarget.set(JvmTarget.JVM_17)
  }
}

protobuf {
    protoc {
        artifact = "com.google.protobuf:protoc:${protobufVersion}"
    }
    plugins {

        id("grpc") {
            artifact = "io.grpc:protoc-gen-grpc-java:${grpcVersion}"
        }
    }
    generateProtoTasks {
        ofSourceSet("main").forEach {
            it.plugins {
                // Apply the "grpc" plugin whose spec is defined above, without
                // options. Note the braces cannot be omitted, otherwise the
                // plugin will not be added. This is because of the implicit way
                // NamedDomainObjectContainer binds the methods.
                id("grpc") { }
            }
        }
    }
}

application {
    mainClass.set("frauddetection.MainKt")
}

tasks.jar {
    manifest.attributes["Main-Class"] = "frauddetection.MainKt"
}
