import grpc
import sys
sys.path.append('src/shopping-copilot')
sys.path.append('src/shopping-copilot/genproto/oteldemo')
import shopping_copilot_pb2 as pb
import shopping_copilot_pb2_grpc as pb_grpc

def test():
    print("Connecting to gRPC server...")
    channel = grpc.insecure_channel('localhost:3552')
    stub = pb_grpc.ShoppingCopilotServiceStub(channel)
    req = pb.ChatWithCopilotRequest(user_id="test_user", session_id="test_session", question="Tôi muốn tìm một ống nhòm loại roof cho người mới với giá dưới 500 USD")
    try:
        print("Sending first request...")
        resp = stub.ChatWithCopilot(req)
        print("Response 1:", resp.response)
        print("Cache status 1:", resp.cache_status)
        print("Source Fingerprint 1:", resp.source_fingerprint)
        print("Similarity 1:", resp.similarity)
        
        print("\nSending second request (should hit exact cache)...")
        resp2 = stub.ChatWithCopilot(req)
        print("Response 2:", resp2.response)
        print("Cache status 2:", resp2.cache_status)
    except Exception as e:
        print("Error:", e)

test()
