# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/ruby:4.0.5-alpine3.22@sha256:fae3127404cb61d6897d7eed08e65ec7ccc96ba0542dc7c44712efa9b2ef78f0 AS builder

WORKDIR /email_server

COPY ./src/email/Gemfile Gemfile
COPY ./src/email/Gemfile.lock Gemfile.lock

# zlib-dev: header để build native ext của gem zlib (pin vá CVE-2026-27820).
RUN apk update && \
    apk add --no-cache make gcc g++ musl-dev gcompat zlib-dev && \
    bundle config set --local path 'vendor/bundle' && \
    bundle install

FROM docker.io/library/ruby:4.0.5-alpine3.22@sha256:fae3127404cb61d6897d7eed08e65ec7ccc96ba0542dc7c44712efa9b2ef78f0

# Patch OS packages from the base image.
RUN apk upgrade --no-cache

WORKDIR /email_server

ENV BUNDLE_PATH="vendor/bundle"

COPY --from=builder /email_server/vendor/bundle /email_server/vendor/bundle

COPY ./src/email/views/ views/

COPY ./src/email/.ruby-version .ruby-version
COPY ./src/email/Gemfile Gemfile
COPY ./src/email/Gemfile.lock Gemfile.lock
COPY ./src/email/email_server.rb email_server.rb

EXPOSE ${EMAIL_PORT}
ENTRYPOINT ["bundle", "exec", "ruby", "email_server.rb"]
