import grpc
import time
from src.shopping_copilot import demo_pb2, demo_pb2_grpc

channel = grpc.insecure_channel('localhost:3550') # wait, I don't know the local port for product-catalog
