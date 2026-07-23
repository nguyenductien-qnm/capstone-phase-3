import requests, json, time
url = "https://ecommerce.nguyenductien.cloud/api/copilot"
payload = {
    "question": "Chào bạn, mình đang muốn mua ống nhòm hoặc kính thiên văn.",
    "user_id": "test-user-1",
    "session_id": "sess-2"
}
print("Sending to Copilot...")
t0 = time.time()
try:
    r = requests.post(url, json=payload, timeout=60)
    print(f"Status: {r.status_code}")
    print(f"Time: {time.time() - t0:.2f}s")
    print(r.text)
except Exception as e:
    print(f"Error: {e}")
