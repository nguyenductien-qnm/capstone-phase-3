#!/bin/bash
# Generate Python gRPC stubs from the demo.proto definition.
# Prerequisites: pip install grpcio-tools

set -euo pipefail

python -m grpc_tools.protoc \
  -I techx-corp-platform/pb \
  --python_out=. \
  --grpc_python_out=. \
  techx-corp-platform/pb/demo.proto

echo 'Stubs generated: demo_pb2.py, demo_pb2_grpc.py'
