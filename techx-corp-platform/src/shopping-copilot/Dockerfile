# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/python:3.12-slim-trixie@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS build-venv

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY ./src/shopping-copilot/requirements.txt requirements.txt

RUN python -m venv venv && \
    venv/bin/pip install --no-cache-dir -r requirements.txt

RUN venv/bin/opentelemetry-bootstrap -a install

FROM docker.io/library/python:3.12-slim-trixie@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a

# Patch OS packages from the base image.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY --from=build-venv /venv/ /venv/

WORKDIR /app

COPY ./src/shopping-copilot/demo_pb2.py demo_pb2.py
COPY ./src/shopping-copilot/demo_pb2_grpc.py demo_pb2_grpc.py
COPY ./src/shopping-copilot/shopping_copilot_pb2.py shopping_copilot_pb2.py
COPY ./src/shopping-copilot/shopping_copilot_pb2_grpc.py shopping_copilot_pb2_grpc.py
COPY ./src/shopping-copilot/guardrails.py guardrails.py
COPY ./src/shopping-copilot/ml_guard_pb2.py ml_guard_pb2.py
COPY ./src/shopping-copilot/ml_guard_pb2_grpc.py ml_guard_pb2_grpc.py
COPY ./pb/ml_guard_client.py ml_guard_client.py
COPY ./pb/semantic_guard.py semantic_guard.py
COPY ./src/shopping-copilot/bedrock_client.py bedrock_client.py
COPY ./src/shopping-copilot/model_router.py model_router.py
COPY ./src/shopping-copilot/tools.py tools.py
COPY ./src/shopping-copilot/agent.py agent.py
# MANDATE-23: cache L2 + memory ngắn/dài hạn. Thiếu dòng này thì copilot_server.py
# crash ngay khi start (ModuleNotFoundError: No module named 'memory').
COPY ./src/shopping-copilot/memory.py memory.py
COPY ./src/shopping-copilot/llm_trace.py llm_trace.py
COPY ./src/shopping-copilot/copilot_server.py copilot_server.py
COPY ./pb/output_validator.py output_validator.py

# MANDATE-05: no container runs as root
RUN useradd -u 10001 -m copilot
USER copilot

EXPOSE ${SHOPPING_COPILOT_PORT}
ENTRYPOINT [ "/venv/bin/opentelemetry-instrument", "/venv/bin/python", "copilot_server.py" ]
