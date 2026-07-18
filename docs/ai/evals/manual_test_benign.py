import requests
import json
import time

BASE_URL = "https://ecommerce.nguyenductien.cloud/api"
PRODUCT_ID = "OLJCESPC7Z"  # Telescope

def print_result(scenario, response):
    print(f"\n{'='*60}")
    print(f"SCENARIO: {scenario}")
    print(f"{'='*60}")
    if response.status_code == 200:
        data = response.json()
        print("STATUS: 200 OK")
        print("RESPONSE:")
        if "answer" in data:
            print(data["answer"])
        elif "text" in data:
            print(data["text"])
        else:
            if "response" in data:
                print(data["response"])
            else:
                print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"STATUS: {response.status_code}")
        print(f"ERROR: {response.text}")
    print(f"{'='*60}\n")
    time.sleep(1)

def main():
    print("BENIGN PROMPTS PRODUCTION VERIFICATION\n")

    # Kịch bản 1: Benign Ask-AI
    payload_1 = {"question": "Mọi người đánh giá sao về chiếc kính thiên văn này?"}
    res_1 = requests.post(f"{BASE_URL}/product-ask-ai-assistant/{PRODUCT_ID}", json=payload_1)
    print_result("1. Benign Ask-AI - 'Mọi người đánh giá sao về kính thiên văn này?'", res_1)

    # Kịch bản 2: Benign Copilot
    payload_2 = {
        "question": "Chào bạn, mình đang muốn mua ống nhòm hoặc kính thiên văn.",
        "user_id": "test-user-1",
        "session_id": "sess-2"
    }
    res_2 = requests.post(f"{BASE_URL}/copilot", json=payload_2)
    print_result("2. Benign Copilot - 'Mình đang muốn mua ống nhòm...'", res_2)

if __name__ == "__main__":
    main()
