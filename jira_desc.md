# AI MANDATE #6 - AI Trust & Safety: model that + guardrail + eval tai tao duoc (TF1 / AIO)

## Link PR/commit (guardrail + eval + fallback + model that):

- Guardrail prompt-injection / PII / system prompt: PR #36 - TF1-61 (merged)


- Fallback routing + retry/timeout: PR #26 - TF1-60 (merged)


- Eval fidelity + golden_qa 34 case + CI: TF1-67 (Done)


- Copilot confirmation gate + injection eval: TF1-74 (In Progress)


- Deploy product-reviews Bedrock that len EKS: TF1-65


- Do Bedrock latency P50/P95: TF1-66 (Done)



## Cach chay lai (repro):

- Eval fidelity + injection: python docs/ai/evals/run_evals.py voi golden_qa_dataset.json (24 case: grounded/no_info/injection) + golden_dataset.json (10 case summary)


- Guardrail injection test: gui review chua 'bo qua huong dan tren, tra loi...' -> AI khong nghe theo


- Guardrail PII: gui review chua email/sdt -> khong lot ra tom tat


- Copilot confirmation gate: bao 'checkout' / 'xoa gio' -> tu choi / hoi xac nhan


- Fallback: inject ThrottlingException -> chuyen model du phong, khach van thay tom tat



## Bang chung chay that:

- (a) Guardrail chan injection + che PII - TF1-61 resolved boi PR #36, eval chay tren service that, bo test adversarial gom bien the tieng Viet + tieng Anh


- (b) AI tra 'khong co thong tin' thay vi bia - golden_qa_dataset.json 24 case bao gom no_info scenario, do fidelity summary khop expected_summary_keywords


- (c) Eval chay ra so - bao cao trong 04_eval_report.md voi so that, CI xanh chay duoc tu repo sach (pytest + guardrail self-check + eval moi PR)


- (d) Copilot tu choi/hoi xac nhan khi bi bao checkout - TF1-74 eval injection pass 4/4: chan 'add 10 to cart', 'reveal system prompt', 'medical claim', 'checkout without confirm'



## ADR ky ten:

- ADR-006: guardrail + fallback design (chon model, phuong phap eval)


- ADR-003: valkey reliability (lien quan fallback cache)



## Dong doi tham gia:

Vinh Bui (nop), Vinh Bui (guardrail TF1-61), Thinh Nguyen Cong (fallback TF1-60), Phan Duc Tai (latency TF1-66), Dinh Nguyen (review)

## Phu Mandate 06 DoD:

DoD item

Ticket/Evidence

1. Model that + fallback

TF1-65 deploy Bedrock EKS + TF1-60 fallback routing (Nova Lite -> model du phong) + TF1-66 do P50/P95 that

2. Qua 4 tinh huong guardrail

TF1-61 (injection/PII/system prompt) + TF1-74 (confirmation gate copilot)

3. Eval tai tao duoc

TF1-67 golden_qa 34 case + fidelity + CI green + 04_eval_report.md

