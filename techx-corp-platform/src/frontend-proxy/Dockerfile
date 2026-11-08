# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM envoyproxy/envoy-contrib:v1.35-latest@sha256:5cbfbcb103a3486078727ae04afaf7108fce50cfeb2aa6bc3d87511805678cd3

# apt-get upgrade: vá CVE ở package hệ thống của base image (vd CVE-2026-45447
# libssl3). Base image tag không đổi nhưng repo ubuntu đã có bản vá.
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y gettext-base && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

USER envoy

WORKDIR /home/envoy

COPY ./src/frontend-proxy/envoy.tmpl.yaml envoy.tmpl.yaml

EXPOSE ${ENVOY_PORT}
EXPOSE ${ENVOY_ADMIN_PORT}
ENTRYPOINT ["/bin/sh", "-c", "envsubst < envoy.tmpl.yaml > envoy.yaml && envoy -c envoy.yaml;"]
