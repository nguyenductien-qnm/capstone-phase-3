# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM golang:1.25-bookworm@sha256:ea341baa9bd5ba6784f6d7161ace70544349a6242d54d34a0fbfd2c4d51c9d58 AS builder

WORKDIR /usr/src/app/

COPY ./src/checkout/go.mod go.mod
COPY ./src/checkout/go.sum go.sum

RUN go mod download

COPY ./src/checkout/genproto/oteldemo/ genproto/oteldemo/
COPY ./src/checkout/kafka/ kafka/
COPY ./src/checkout/money/ money/
COPY ./src/checkout/validator/ validator/
COPY ./src/checkout/main.go main.go
COPY ./src/checkout/kafka_publisher.go kafka_publisher.go

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags "-s -w" -o checkout .

FROM gcr.io/distroless/static-debian12:nonroot@sha256:f5b485ea962d9bd1186b2f6b3a061191539b905b82ec395de78cbfae51f20e35

WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/checkout/ ./

EXPOSE ${CHECKOUT_PORT}
ENTRYPOINT [ "./checkout" ]
