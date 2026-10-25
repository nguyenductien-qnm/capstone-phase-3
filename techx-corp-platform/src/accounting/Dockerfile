# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM --platform=${BUILDPLATFORM} mcr.microsoft.com/dotnet/sdk:8.0@sha256:738f72aff955d5c5690e06b6fc8ecd1b90ead564099a257ac528ff720b8da85f AS builder
ARG TARGETARCH
ARG BUILD_CONFIGURATION=Release
WORKDIR /src
COPY ["/src/accounting/", "Accounting/"]
COPY ["/pb/demo.proto", "Accounting/src/protos/demo.proto"]
RUN dotnet restore "./Accounting/Accounting.csproj" -r linux-$TARGETARCH
WORKDIR "/src/Accounting"

RUN dotnet build "./Accounting.csproj" -r linux-$TARGETARCH -c $BUILD_CONFIGURATION -o /app/build

# -----------------------------------------------------------------------------

FROM builder AS publish
ARG TARGETARCH
ARG BUILD_CONFIGURATION=Release
RUN dotnet publish "./Accounting.csproj" -r linux-$TARGETARCH -c $BUILD_CONFIGURATION -o /app/publish /p:UseAppHost=false

# -----------------------------------------------------------------------------

FROM mcr.microsoft.com/dotnet/aspnet:8.0@sha256:74a1d7c07211a7e8a2e35ff3c70ed8e4e1d6451a1ff7cf7bdf526f9eafa23023
# 'app' (UID 1654, có sẵn trong base .NET) là non-root, nhưng kubelet không
# resolve được USER dạng chữ để check runAsNonRoot:true -> CreateContainerConfigError.
# Ghi bằng số, GIỮ NGUYÊN 1654: các file dưới đây chown theo user 'app', đổi sang
# UID khác (vd 1000) sẽ mất quyền instrument.sh (ENTRYPOINT) và thư mục log.
USER 1654
WORKDIR /app
COPY --from=publish /app/publish .

USER root
RUN mkdir -p "/var/log/opentelemetry/dotnet"
RUN chown app "/var/log/opentelemetry/dotnet"
RUN chown app "/app/instrument.sh"
USER 1654
ENV OTEL_DOTNET_AUTO_TRACES_ADDITIONAL_SOURCES=Accounting.Consumer

ENTRYPOINT ["./instrument.sh", "dotnet", "Accounting.dll"]
