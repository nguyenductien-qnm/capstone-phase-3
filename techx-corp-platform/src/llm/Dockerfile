# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/python:3.12-alpine3.22 AS build-venv

RUN apk update && \
    apk add gcc g++ linux-headers

COPY ./src/llm/requirements.txt requirements.txt

RUN python -m venv venv && \
    venv/bin/pip install --no-cache-dir -r requirements.txt

FROM docker.io/library/python:3.12-alpine3.22

# Vá CVE ở package hệ thống của base image (vd CVE-2026-45447 libssl3/libcrypto3).
# Base image tag không đổi nhưng repo alpine đã có bản vá -> upgrade lúc build.
RUN apk upgrade --no-cache

COPY --from=build-venv /venv/ /venv/

WORKDIR /app

COPY ./src/llm/app.py app.py
COPY ./src/llm/product-review-summaries/product-review-summaries.json product-review-summaries.json
COPY ./src/llm/product-review-summaries/inaccurate-product-review-summaries.json inaccurate-product-review-summaries.json

EXPOSE ${LLM_PORT}

# Base python alpine chạy root và không có UID 1000 sẵn -> kubelet chặn bởi
# runAsNonRoot:true. App chỉ đọc app.py + 2 file JSON (mode 644) nên không cần chown.
RUN adduser -D -u 1000 app
USER 1000

ENTRYPOINT [ "/venv/bin/python", "app.py" ]
