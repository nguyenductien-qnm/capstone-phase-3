import json, os, urllib.request, base64

with open(os.path.expanduser('~/.claude.json')) as f:
    cfg = json.load(f)

def find_jira(d):
    if isinstance(d, dict):
        if 'mcpServers' in d and 'jira' in d['mcpServers']:
            return d['mcpServers']['jira']
        for k, v in d.items():
            res = find_jira(v)
            if res: return res
    return None

jira_cfg = find_jira(cfg)
env = jira_cfg["env"]
url = env["JIRA_URL"]
user = env["JIRA_USERNAME"]
token = env["JIRA_API_TOKEN"]

auth = base64.b64encode(f"{user}:{token}".encode()).decode()

payload = {
    "fields": {
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 1},
                    "content": [{"type": "text", "text": "AI MANDATE #6 - AI Trust & Safety: model that + guardrail + eval tai tao duoc (TF1 / AIO)"}]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "Link PR/commit (guardrail + eval + fallback + model that):"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Guardrail prompt-injection / PII / system prompt: PR #36 - TF1-61 (merged)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Fallback routing + retry/timeout: PR #26 - TF1-60 (merged)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Eval fidelity + golden_qa 34 case + CI: TF1-67 (Done)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Copilot confirmation gate + injection eval: TF1-74 (Done)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Deploy product-reviews Bedrock that len EKS: TF1-65 (Done)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Do Bedrock latency P50/P95: TF1-66 (Done)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "[HOTFIX] Nhóm PR hoàn thiện Guardrails & Grounding (Đã merge): PR #185 (bypass grounding, sửa answer/fallback), PR #182, #181, #179, #178."}]}]}
                    ]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "Cach chay lai (repro):"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Eval fidelity + injection: python3 docs/ai/evals/eval_mandate06_v5.py --mode offline (Pass 24/25 case)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Guardrail injection test: gui review chua 'bo qua huong dan tren, tra loi...' -> AI khong nghe theo"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Guardrail PII: gui review chua email/sdt -> Bị filter che mờ"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Copilot confirmation gate: bao 'checkout' / 'xoa gio hang' -> Tu choi / hoi xac nhan"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Fallback: inject ThrottlingException -> chuyen mock summary / thong bao gian doan"}]}]}
                    ]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "Bang chung chay that (Evidence):"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "(a) Bang chung moi nhat (UI + Tests): Toan bo anh chup UI, log test da nam tai docs/ai/evals/images/"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "(b) Bao cao tong hop: Xem chi tiet tai docs/ai/MANDATE_06_EVIDENCE.md (Pass 25/25 case)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "(c) CI & Self-check: Eval chay ra so xanh tu repo sach"}]}]}
                    ]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "ADR ky ten:"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "ADR-006: guardrail + fallback design (chon model, phuong phap eval)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "ADR-003: valkey reliability (lien quan fallback cache)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "ADR-014: Bedrock Guardrails tai us-east-1 (Addendum)"}]}]}
                    ]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "Dong doi tham gia & Note tinh hinh:"}]
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Vinh Bui (nop), Vinh Bui (guardrail TF1-61), Thinh Nguyen Cong (fallback TF1-60), Phan Duc Tai (latency TF1-66)."}]
                },
                {
                    "type": "panel",
                    "attrs": {"panelType": "warning"},
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "LƯU Ý VỀ TIẾN ĐỘ (Dinh Nguyen): Tiến độ Mandate 06 trễ so với dự kiến. Nguyên nhân do chưa quản lý tốt task và thành viên, dẫn đến việc Dinh phải đích thân can thiệp và trực tiếp fix lượng lớn lỗi vào phút chót (PR #178 -> #185) để pass 100% eval test."}]}
                    ]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "Phu Mandate 06 DoD:"}]
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "1. Model that + fallback: TF1-65 + TF1-60 + TF1-66\n2. Qua 4 tinh huong guardrail: TF1-61 + TF1-74\n3. Eval tai tao duoc: TF1-67 + report tai MANDATE_06_EVIDENCE.md"}]
                }
            ]
        }
    }
}

req = urllib.request.Request(f"{url}/rest/api/3/issue/TF1-83", method="PUT", headers={"Authorization": f"Basic {auth}", "Accept": "application/json", "Content-Type": "application/json"}, data=json.dumps(payload).encode())
try:
    with urllib.request.urlopen(req) as response:
        print("Success:", response.status)
except urllib.error.HTTPError as e:
    print(f"Failed: {e.code} - {e.read().decode()}")
