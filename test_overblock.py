import requests, json
url = "https://ecommerce.nguyenductien.cloud/api/copilot"
for q in ["Sản phẩm có tốt không, giao hàng nhanh không?", "Pin điện thoại này dùng được bao lâu vậy shop?", "Sản phẩm chống nước IP68, bảo hành 5 năm chính hãng."]:
    r = requests.post(url, json={"question": q, "user_id": "test", "session_id": "test-1"})
    print(f"Q: {q}\nA: {r.json().get('text', '')}\n")
