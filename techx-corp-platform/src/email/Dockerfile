# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/ruby:3.4.7-alpine3.22 AS builder

COPY ./src/email/Gemfile Gemfile
COPY ./src/email/Gemfile.lock Gemfile.lock

# zlib-dev: header để build native ext của gem zlib (pin vá CVE-2026-27820).
RUN apk update && \
    apk add --no-cache make gcc musl-dev gcompat zlib-dev && \
    bundle install

FROM docker.io/library/ruby:3.4.7-alpine3.22

# Patch OS packages from the base image.
RUN apk upgrade --no-cache

COPY --from=builder /usr/local/bundle/ /usr/local/bundle/

WORKDIR /email_server

COPY ./src/email/views/ views/

COPY ./src/email/.ruby-version .ruby-version
COPY ./src/email/Gemfile Gemfile
COPY ./src/email/Gemfile.lock Gemfile.lock
COPY ./src/email/email_server.rb email_server.rb

EXPOSE ${EMAIL_PORT}
ENTRYPOINT ["bundle", "exec", "ruby", "email_server.rb"]
