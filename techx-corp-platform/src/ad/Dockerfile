# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM eclipse-temurin:21-jdk AS builder
ARG _JAVA_OPTIONS
WORKDIR /usr/src/app/

COPY ./src/ad/gradlew* ./src/ad/settings.gradle* ./src/ad/build.gradle ./
COPY ./src/ad/gradle ./gradle

RUN chmod +x ./gradlew
RUN ./gradlew
RUN ./gradlew downloadRepos

COPY ./src/ad/ ./
COPY ./pb/ ./proto
RUN chmod +x ./gradlew
RUN ./gradlew installDist -PprotoSourceDir=./proto

# -----------------------------------------------------------------------------

# :21-jre (ubuntu 26.04) nhét sẵn /usr/bin/pebble v1.32.0 — binary Go không thuộc
# app, không config nào ref tới, nhưng mang 5 CVE HIGH (x/net, stdlib) làm Trivy
# gate đỏ. Tag noble không có pebble và scan sạch 0 CVE; vẫn JRE 21, chỉ khác
# ubuntu 24.04 vs 26.04.
FROM eclipse-temurin:21-jre-noble

ARG OTEL_JAVA_AGENT_VERSION
ARG _JAVA_OPTIONS

WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/ ./
ADD --chmod=644 https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$OTEL_JAVA_AGENT_VERSION/opentelemetry-javaagent.jar /usr/src/app/opentelemetry-javaagent.jar
ENV JAVA_TOOL_OPTIONS=-javaagent:/usr/src/app/opentelemetry-javaagent.jar

EXPOSE ${AD_PORT}
ENTRYPOINT [ "./build/install/techx-corp-ad/bin/Ad" ]
