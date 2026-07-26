# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Find eligible builder and runner images on Docker Hub. We use Ubuntu/Debian
# instead of Alpine to avoid DNS resolution issues in production.
#
# https://hub.docker.com/r/hexpm/elixir/tags?name=ubuntu
# https://hub.docker.com/_/ubuntu/tags
#
# This file is based on these images:
#
#   - https://hub.docker.com/r/hexpm/elixir/tags - for the build image
#   - https://hub.docker.com/_/debian/tags?name=bookworm-20250610-slim - for the release image
#   - https://pkgs.org/ - resource for finding needed packages
#   - Ex: docker.io/hexpm/elixir:1.18.4-erlang-27.3.4-debian-bookworm-20250610-slim
#
ARG ELIXIR_VERSION=1.19.3
ARG OTP_VERSION=28.0.2
ARG DEBIAN_VERSION=bullseye-20251117-slim

# MANDATE-10 #4: pin theo DIGEST, không phải tag. Trước đây hai dòng này chỉ ghi tới
# tag (`docker.io/debian:${DEBIAN_VERSION}`) — nhìn qua tưởng đã cố định vì tag có ngày
# tháng, nhưng tag vẫn là con trỏ đẩy đè được, nên build hai thời điểm có thể ra hai nội
# dung khác nhau. Digest là băm của chính nội dung image nên không đổi được.
#
# Chỗ này lọt lưới lâu vì lệnh grep kiểm pin chỉ soi dòng `FROM`, mà `FROM ${RUNNER_IMAGE}`
# trông sạch — giá trị thật nằm ở đây. Job `pin-guard` trong platform-ci.yaml nay soi cả
# dòng ARG để không lặp lại.
#
# Giữ nguyên tag phía trước digest: tag cho người đọc biết đây là bản nào, digest cho
# Docker biết kéo đúng cái gì. Đổi version thì phải lấy digest mới:
#   docker buildx imagetools inspect <image>:<tag> | grep Digest
ARG BUILDER_IMAGE="docker.io/hexpm/elixir:${ELIXIR_VERSION}-erlang-${OTP_VERSION}-debian-${DEBIAN_VERSION}@sha256:78ae416dd0f9100dec7fbc58da76e2cdd0400b6eece5ddb5055390f3162c97cd"
ARG RUNNER_IMAGE="docker.io/debian:${DEBIAN_VERSION}@sha256:530a3348fc4b5734ffe1a137ddbcee6850154285251b53c3425c386ea8fac77b"

FROM ${BUILDER_IMAGE} AS builder

# install build dependencies
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential git \
  && rm -rf /var/lib/apt/lists/*

# prepare build dir
WORKDIR /app

# install hex + rebar
RUN mix local.hex --force \
  && mix local.rebar --force

# set build ENV
ENV MIX_ENV="prod"

# install mix dependencies
COPY ./src/flagd-ui/mix.exs ./src/flagd-ui/mix.lock ./
RUN mix deps.get --only $MIX_ENV
RUN mkdir config

# copy compile-time config files before we compile dependencies
# to ensure any relevant config change will trigger the dependencies
# to be re-compiled.
COPY ./src/flagd-ui/config/config.exs ./src/flagd-ui/config/${MIX_ENV}.exs ./src/flagd-ui/config/runtime.exs config/
RUN mix deps.compile

RUN mix assets.setup

COPY ./src/flagd-ui/priv priv

COPY ./src/flagd-ui/lib lib

COPY ./src/flagd-ui/assets assets

# compile assets
RUN mix assets.deploy

# Compile the release
RUN mix compile

COPY ./src/flagd-ui/rel rel
RUN mix release

# start a new build stage so that the final image will only contain
# the compiled release and other runtime necessities
FROM ${RUNNER_IMAGE} AS final

RUN apt-get update \
  && apt-get install -y --no-install-recommends libstdc++6 openssl libncurses5 locales ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Set the locale
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen \
  && locale-gen

ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

WORKDIR "/app"
RUN chown nobody /app

# set runner ENV
ENV MIX_ENV="prod"

# Only copy the final release from the build stage
COPY --from=builder --chown=nobody:root /app/_build/${MIX_ENV}/rel/flagd_ui ./

EXPOSE ${FLAGD_UI_PORT}

# If using an environment that doesn't automatically reap zombie processes, it is
# advised to add an init process such as tini via `apt-get install`
# above and adding an entrypoint. See https://github.com/krallin/tini for details
# ENTRYPOINT ["/tini", "--"]

CMD ["/app/bin/server"]
