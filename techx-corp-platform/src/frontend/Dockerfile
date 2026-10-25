# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/node:22-slim@sha256:de170b39439eb0e5a3444ad7d60b015614a381e10fecae2e30ec9e735122f38d AS builder

WORKDIR /app

COPY ./src/frontend/package.json package.json
COPY ./src/frontend/package-lock.json package-lock.json

RUN npm ci

COPY ./src/frontend/components/ components/
COPY ./src/frontend/gateways/ gateways/
COPY ./src/frontend/hooks/ hooks/
COPY ./src/frontend/lib/ lib/
COPY ./src/frontend/pages/ pages/
COPY ./src/frontend/protos/ protos/
COPY ./src/frontend/providers/ providers/
COPY ./src/frontend/services/ services/
COPY ./src/frontend/styles/ styles/
COPY ./src/frontend/types/ types/

COPY ./src/frontend/utils/enums/ utils/enums/
COPY ./src/frontend/utils/telemetry/ utils/telemetry/
COPY ./src/frontend/utils/imageLoader.js utils/imageLoader.js
COPY ./src/frontend/utils/Request.ts utils/Request.ts
COPY ./src/frontend/utils/mockData.ts utils/mockData.ts
# M17-R1: CircuitBreaker.ts (dùng bởi Ad/Recommendations gateway)
COPY ./src/frontend/utils/resilience/ utils/resilience/

COPY ./src/frontend/next.config.js next.config.js
COPY ./src/frontend/postcss.config.mjs postcss.config.mjs
COPY ./src/frontend/tsconfig.json tsconfig.json

RUN npm run build

# -----------------------------------------------------------------------------

FROM docker.io/library/node:22-slim@sha256:de170b39439eb0e5a3444ad7d60b015614a381e10fecae2e30ec9e735122f38d AS deps

WORKDIR /app

COPY ./src/frontend/package.json package.json
COPY ./src/frontend/package-lock.json package-lock.json

RUN NODE_ENV=production npm ci

# -----------------------------------------------------------------------------

FROM gcr.io/distroless/nodejs22-debian13:nonroot@sha256:10747a1323be68f206aed893599d43e6697ad67257e7c42703553f99fbce3d33

WORKDIR /app

COPY --from=builder /app/.next/standalone/ ./
COPY --from=builder /app/.next/static/ .next/static/

COPY --from=deps /app/node_modules/ node_modules/

COPY ./src/frontend/public/ public/

COPY ./src/frontend/utils/telemetry/Instrumentation.js Instrumentation.js

EXPOSE ${FRONTEND_PORT}

CMD ["--require=./Instrumentation.js", "server.js"]
