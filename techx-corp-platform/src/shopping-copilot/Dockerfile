# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/python:3.12-alpine3.22 AS build-venv

RUN apk update && \
    apk add gcc g++ linux-headers

COPY ./src/shopping-copilot/requirements.txt requirements.txt

RUN python -m venv venv && \
    venv/bin/pip install --no-cache-dir -r requirements.txt

RUN venv/bin/opentelemetry-bootstrap -a install

FROM docker.io/library/python:3.12-alpine3.22

COPY --from=build-venv /venv/ /venv/

WORKDIR /app

COPY ./src/shopping-copilot/demo_pb2.py demo_pb2.py
COPY ./src/shopping-copilot/demo_pb2_grpc.py demo_pb2_grpc.py
COPY ./src/shopping-copilot/shopping_copilot_pb2.py shopping_copilot_pb2.py
COPY ./src/shopping-copilot/shopping_copilot_pb2_grpc.py shopping_copilot_pb2_grpc.py
COPY ./src/shopping-copilot/tools.py tools.py
COPY ./src/shopping-copilot/agent.py agent.py
COPY ./src/shopping-copilot/copilot_server.py copilot_server.py

EXPOSE ${SHOPPING_COPILOT_PORT}
ENTRYPOINT [ "/venv/bin/opentelemetry-instrument", "/venv/bin/python", "copilot_server.py" ]
