import requests
import time
import uuid

BASE = "https://ecommerce.nguyenductien.cloud/api/copilot"

def ask(q, uid, sid):
    t = time.time()
    try:
        r = requests.post(BASE, json={"question": q, "user_id": uid, "session_id": sid}, timeout=30)
        lat = round(time.time() - t, 2)
        if r.status_code != 200:
            return {"ERR": f"HTTP {r.status_code}"}, lat
        return r.json(), lat
    except Exception as e:
        return {"ERR": str(e)[:80]}, round(time.time() - t, 2)

uid_base = str(uuid.uuid4())[:8]

print(f"=== ĐÁNH GIÁ M23 TRÊN PRODUCTION (UID_BASE: {uid_base}) ===")

# 1. Exact Cache Test
print("\n1. Test Exact Cache (L1)")
uid1, sid1 = f"u1-{uid_base}", f"s1-{uid_base}"
q_exact = "Ống nhòm Roof Binoculars giá bao nhiêu?"
print("Lần 1 (Expect: miss)...")
d1, l1 = ask(q_exact, uid1, sid1)
print(f"-> {d1.get('cacheStatus')} | {l1}s")

print("Lần 2 (Expect: hit_exact)...")
d2, l2 = ask(q_exact, uid1, f"s2-{uid_base}")
print(f"-> {d2.get('cacheStatus')} | {l2}s")

# 2. Semantic Cache Test
print("\n2. Test Semantic Cache (L2)")
uid2, sid2 = f"u2-{uid_base}", f"s3-{uid_base}"
print("Câu hỏi gốc (Expect: miss)...")
d3, l3 = ask(q_exact, uid2, sid2)
print(f"-> {d3.get('cacheStatus')} | {l3}s")

print("Câu diễn đạt khác cùng ý (Expect: hit_semantic)...")
d4, l4 = ask("Cho mình hỏi giá của ống nhòm Roof Binoculars?", uid2, f"s4-{uid_base}")
print(f"-> {d4.get('cacheStatus')} | {l4}s")

print("Câu phủ định / thay đổi số (Expect: miss)...")
d5, l5 = ask("Kính thiên văn dưới 200 USD có gì?", uid2, f"s5-{uid_base}")
d6, l6 = ask("Kính thiên văn trên 200 USD có gì?", uid2, f"s6-{uid_base}")
print(f"-> Gốc: {d5.get('cacheStatus')} ({l5}s) | Sau: {d6.get('cacheStatus')} ({l6}s)")

# 3. Short-term memory
print("\n3. Test Short-term memory (3-turn context)")
uid3, sid3 = f"u3-{uid_base}", f"s7-{uid_base}"
ask("Cho mình xem các loại kính thiên văn", uid3, sid3)
ask("Cái đầu tiên giá bao nhiêu?", uid3, sid3)
d7, l7 = ask("Nó có phù hợp cho người mới không?", uid3, sid3)
print(f"-> Lượt 3 (Nó = Kính thiên văn đầu tiên): {d7.get('response')[:100]}...")

# 4. Long-term memory
print("\n4. Test Long-term memory (Cross-session)")
uid4 = f"u4-{uid_base}"
ask("Mình là người mới chơi thiên văn, ngân sách khoảng 150 USD", uid4, f"s8-{uid_base}")
d8, l8 = ask("Ở phiên trước mình nói trình độ của mình là gì?", uid4, f"s9-{uid_base}")
print(f"-> Lượt ở phiên mới: {d8.get('response')[:100]}...")

# 5. Cross-user isolation
print("\n5. Test Cross-user isolation (Hard Bar)")
d9, l9 = ask(q_exact, f"u5-{uid_base}", f"s10-{uid_base}")
print(f"-> User B hỏi cùng câu User A đã hỏi (Expect: miss): {d9.get('cacheStatus')} | {l9}s")

