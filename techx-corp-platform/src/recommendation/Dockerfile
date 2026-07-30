# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM docker.io/library/python:3.12-alpine3.22@sha256:a190708a2dec1bd18b1decb539f8e8f5407abaa9bf39cacda583f7f8c11db322 AS build-venv

RUN apk update && \
    apk add gcc g++ linux-headers

COPY ./src/recommendation/requirements.txt requirements.txt

RUN python -m venv venv && \
    venv/bin/pip install --no-cache-dir --upgrade pip && \
    venv/bin/pip install --no-cache-dir -r requirements.txt


RUN venv/bin/opentelemetry-bootstrap -a install

# 30/07/2026 — GỠ pip KHỎI VENV TRƯỚC KHI COPY SANG ẢNH CHẠY.
#
# Trivy gate chặn build này với 2 HIGH, và cả hai KHÔNG nằm trong requirements.txt:
#   msgpack     GHSA-6v7p-g79w-8964  1.1.2  -> 1.2.1
#   setuptools  CVE-2025-47273       70.3.0 -> 78.1.1
# Chúng là thư viện pip VENDOR sẵn bên trong chính nó. Bằng chứng: pip/_vendor/vendor.txt
# của pip 26.2 ghi đúng hai dòng "msgpack==1.1.2" và "setuptools==70.3.0" — trùng khít
# số hiệu Trivy báo. Vì vendor không có .dist-info riêng nên Trivy gộp chúng vào target
# tên "Python" thay vì một đường dẫn file, đó là lý do bảng summary không có dòng nào
# tên msgpack/setuptools mà vẫn đếm 2 finding.
#
# VÌ SAO CHỈ service này vỡ, 19 service kia không: chỉ Dockerfile này có
# `pip install --upgrade pip`. Các service Python khác dùng pip 25.0.1 của base image,
# bản đó vendor msgpack/setuptools cũ hơn và hiện chưa có advisory (Trivy báo 0).
# Nói cách khác không phải app có lỗ, mà là tự nâng pip lên bản mới hơn base.
#
# VÌ SAO GỠ chứ không nâng hay ignore:
#   - Không nâng được: hai gói này pip ghim cứng trong vendor, `pip install -U msgpack`
#     không thay được bản pip đang dùng cho chính nó.
#   - Không nên ignore: pip là CÔNG CỤ BUILD, ảnh chạy không cần tới nó. Gỡ đi là xoá
#     hẳn đoạn code có lỗ, còn ignore chỉ bịt miệng scanner mà code vẫn nằm trong ảnh.
#   - Cả hai lỗ chỉ chạm được qua đường tải/cài gói của pip (msgpack: cache HTTP của
#     pip; setuptools: class PackageIndex khi tải từ index). Runtime không bao giờ chạy
#     đường đó — nhưng đó là lý do gỡ được an toàn, KHÔNG phải lý do để bỏ qua.
#
# PHẢI đứng SAU opentelemetry-bootstrap: bước đó gọi pip để cài instrumentation.
# `venv --without-pip` là cấu hình chính thức Python hỗ trợ, nên venv không có pip là
# hợp lệ. Đã kiểm ở máy: sau khi gỡ, `opentelemetry-instrument` vẫn chạy và import được
# grpc/psycopg2/pgvector/openfeature bình thường; pip cũng tự dọn luôn _vendor/vendor.txt
# tức đúng file Trivy đọc.
#
# LƯU Ý cho người sau: pip ở /usr/local của base image vẫn còn (hiện Trivy báo 0). Nếu
# sau này bản đó cũng có advisory thì gỡ thêm ở stage runtime, đừng quay lại ignore.
RUN venv/bin/pip uninstall -y pip

FROM docker.io/library/python:3.12-alpine3.22@sha256:a190708a2dec1bd18b1decb539f8e8f5407abaa9bf39cacda583f7f8c11db322

# Vá CVE ở package hệ thống của base image (vd CVE-2026-45447 libcrypto3).
# Base image tag không đổi nhưng repo alpine đã có bản vá -> upgrade lúc build.
RUN apk upgrade --no-cache

COPY --from=build-venv /venv/ /venv/

WORKDIR /app

COPY ./src/recommendation/demo_pb2_grpc.py demo_pb2_grpc.py
COPY ./src/recommendation/demo_pb2.py demo_pb2.py
COPY ./src/recommendation/logger.py logger.py
COPY ./src/recommendation/metrics.py metrics.py
COPY ./src/recommendation/recommendation_server.py recommendation_server.py

RUN adduser -D -u 1000 app
USER 1000

EXPOSE ${RECOMMENDATION_PORT}
ENTRYPOINT [ "/venv/bin/opentelemetry-instrument", "/venv/bin/python", "recommendation_server.py" ]
