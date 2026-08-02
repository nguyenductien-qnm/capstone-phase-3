# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/node:22-slim@sha256:f32b81066cde10a75dbac96646099533316d94bac4150c55da1636e1f0ffdc46 AS builder

WORKDIR /usr/src/app/

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY ./src/payment/package.json package.json
COPY ./src/payment/package-lock.json package-lock.json

ENV CXXFLAGS="-std=c++20"
RUN NODE_ENV=production npm ci

# -----------------------------------------------------------------------------

FROM gcr.io/distroless/nodejs22-debian13:nonroot@sha256:a2723a2817c5b01b8e7b98d567bc8b5a6b0e713e25bfb0a82b6ade4b9db06f50

WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/node_modules/ node_modules/

COPY ./pb/demo.proto demo.proto

COPY ./src/payment/charge.js charge.js
COPY ./src/payment/consumer.js consumer.js
COPY ./src/payment/index.js index.js
COPY ./src/payment/logger.js logger.js
COPY ./src/payment/opentelemetry.js opentelemetry.js

EXPOSE ${PAYMENT_PORT}

CMD ["--require=./opentelemetry.js", "index.js"]
