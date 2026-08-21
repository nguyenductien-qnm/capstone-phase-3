# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM ghcr.io/mlocati/php-extension-installer:2.11.12@sha256:b6d3fa381b9ba5cf051117c1c601d6a523b590e534bf3d56eb4fbe352949c138 AS installer

FROM docker.io/library/composer:2.10.2@sha256:4d71c3c2109c61d5415544264b59ad4087e4c5b7244481723664138fd36d5040 AS vendor

WORKDIR /tmp/

COPY ./src/quote/composer.json composer.json

RUN composer install \
    --ignore-platform-reqs \
    --no-interaction \
    --no-plugins \
    --no-scripts \
    --no-dev \
    --prefer-dist

FROM docker.io/library/php:8.5-cli-alpine3.22@sha256:d4db4138a7adb7cb7b0152b5e12b121c473ea37195170a4c498058fd3b16e480

COPY --from=installer /usr/bin/install-php-extensions /usr/local/bin/

# Vá CVE ở package hệ thống của base image (vd CVE-2026-33630 c-ares).
# Base image tag không đổi nhưng repo alpine đã có bản vá -> upgrade lúc build.
RUN apk upgrade --no-cache

RUN install-php-extensions opcache pcntl protobuf opentelemetry

WORKDIR /var/www

USER www-data

COPY --from=vendor /tmp/vendor/ vendor/

COPY ./src/quote/app/ app/
COPY ./src/quote/public/ public/
COPY ./src/quote/src/ src/

EXPOSE ${QUOTE_PORT}

CMD ["php", "public/index.php"]
