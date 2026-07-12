# Shopping Copilot — PoC (Tuần 1)

Streamlit PoC cho 3 intent bắt buộc (search NL / reviews RAG / cart + confirmation gate).
Gom về đây từ root repo (review 12/07) — trước đó `demo_copilot_st.py`, `demo_pb2*.py`, `grpc_clients.py`, `generate_proto_stubs.sh`, `requirements-copilot.txt`, `database.db` nằm rải ở root.

- Contract tích hợp: `docs/ai/contracts/shopping-copilot-integration.md` (gRPC :50051)
- Chart `shopping-copilot` đang `enabled: false` cho tới khi có image thật (review J2)
- Eval: `docs/ai/evals/test_task_success.py` — LƯU Ý: hiện chấm trên mock agent, số accuracy chưa phải eval thật

Chạy: `pip install -r requirements-copilot.txt && streamlit run demo_copilot_st.py`
