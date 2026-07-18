# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/python:3.12-slim-bookworm AS build-venv

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY ./src/product-reviews/requirements.txt requirements.txt

RUN python -m venv venv && \
    venv/bin/pip install --no-cache-dir -r requirements.txt

RUN venv/bin/opentelemetry-bootstrap -a install

FROM docker.io/library/python:3.12-slim-bookworm

# Patch OS packages from the base image.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY --from=build-venv /venv/ /venv/

WORKDIR /app

COPY ./src/product-reviews/demo_pb2_grpc.py demo_pb2_grpc.py
COPY ./src/product-reviews/demo_pb2.py demo_pb2.py
COPY ./src/product-reviews/product_reviews_server.py product_reviews_server.py
COPY ./src/product-reviews/database.py database.py
COPY ./src/product-reviews/guardrails.py guardrails.py
COPY ./src/product-reviews/bedrock_client.py bedrock_client.py
COPY ./src/product-reviews/metrics.py metrics.py
# product_reviews_server imports ModelRouter — must ship in image (ModuleNotFoundError if missing)
COPY ./src/product-reviews/model_router.py model_router.py


RUN useradd -u 1000 -m app
USER 1000

EXPOSE ${PRODUCT_REVIEWS_PORT}
ENTRYPOINT [ "/venv/bin/opentelemetry-instrument", "/venv/bin/python", "product_reviews_server.py" ]
