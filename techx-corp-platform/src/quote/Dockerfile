# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM ghcr.io/mlocati/php-extension-installer:2.13.2@sha256:4fd45396c16685266d32bf147a24ecd5e81029d3820295895bf4a90131190ac9 AS installer

FROM docker.io/library/composer:2.11.1@sha256:8de2184c6de224f4689e8f80ed5f5edaf0030b6b8b7839a22a2bcb6722ac87d0 AS vendor

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
