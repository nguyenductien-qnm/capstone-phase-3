"""Shim — logic thật nằm ở pb/ml_guard_client.py (dùng chung với product-reviews).

Trong container, ml_guard_client.py được COPY vào cùng thư mục service nên import
trực tiếp; khi chạy từ repo, sys.path trỏ sang ../../pb.
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # ml_guard_pb2* nằm cạnh shim
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../pb')))

from ml_guard_client import *  # noqa: F401,F403
