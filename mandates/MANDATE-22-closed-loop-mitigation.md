# [DIRECTIVE #22] Hệ phải tự dập được sự cố một cách an toàn

**Từ:** Ban Vận hành (SRE) & AI - TechX Corp
**Hiệu lực:** ngay khi nhận · hoàn tất & nộp trước **thứ Bảy 25/07/2026**
**Áp dụng:** nhóm AIO của mọi Task Force

---

## Bối cảnh
Sự cố nổ nửa đêm mà chờ người dậy xử thì khách đã chịu trận cả tiếng. Một hệ vận hành trưởng thành không dừng ở phát hiện: với sự cố đã biết cách xử, hệ phải **tự dập** rồi tự kiểm lại. Nhưng một hành động tự động sai còn tệ hơn không làm gì - nên tự động hoá phải đi kèm phanh: an toàn trước khi act, verify sau khi act, lùi khi sai.

## Yêu cầu
1. **An toàn trước khi act** - trước mỗi hành động tự động phải qua safety check: dry-run, giới hạn phạm vi tác động (blast-radius), cooldown chống lặp.
2. **Tự dập được sự cố** - phát hiện xong tự quyết định và thực thi hành động giảm thiểu, không cần người bấm.
3. **Verify sau khi act** - đo bằng telemetry thật xem đã đỡ chưa, không suy từ giả định.
4. **Rollback khi verify fail** - hành động không đỡ (hoặc bị ép sai) phải tự lùi/escalate, không để lại hậu quả.
5. **Audit log truy được** - mọi hành động tự động ghi lại đủ để tái dựng: ai/cái gì kích hoạt, làm gì, kết quả verify, có lùi không.

"Cách làm tự chọn; đã đạt thì chỉ cần chứng minh."

## Định nghĩa Hoàn thành (DoD - hạn 25/07)
Không cần phủ mọi loại sự cố. Đạt khi:
1. **Chọn ≥ 1 loại sự cố cụ thể** (vd một fault bơm qua flagd) mà hệ **tự dập được end-to-end**: detect → safety check (dry-run/blast-radius) → act → verify bằng telemetry thật.
2. **Nhánh rollback chạy được** - ép một hành động sai (hoặc verify fail) → hệ **tự lùi/escalate**, thấy được trong log.
3. **Audit log** cho lần tự dập đó: trigger → action → kết quả verify → có lùi không.
> Mở rộng nhiều loại sự cố + MTTR before/after = điểm cao hơn; 1 loại chạy e2e an toàn + 1 lần rollback là **sàn đạt**.

## Ràng buộc
- **Phải do AIOps của đội điều khiển:** hành động dập kích hoạt **từ detector của các bạn** (nối tiếp #7), có quyết định + verify + rollback + audit của chính đội. **k8s tự restart pod / HPA sẵn có KHÔNG được tính** là closed-loop.
- Giữ SLO/ngân sách; không đụng / vô hiệu hóa flagd; không hạ chuẩn để qua bài.

## Phải nộp (artifact)
Nộp qua **1 Jira ticket** `AI MANDATE #22` (xem `AI_MANDATE_EVIDENCE.md`):
- **Trước hạn:** link PR/commit + **cửa replay nhận kịch bản từ ngoài** + audit log + số MTTR/before-after của chính đội + `repro`.
- **Đến ngày chấm:** BTC bơm **kịch bản ẩn** (một sự cố thật; và một ca ép hành động sai để xem có rollback không). Đội chạy, **chụp: hệ tự dập + verify + rollback** dán ticket.
- **ADR ký tên**.

**Đạt khi:** sự cố → hệ tự dập an toàn (qua safety check) + verify; ép sai → **rollback**; không tự dập bừa ngoài phạm vi cho phép.

## Được nhìn ở đâu
Trụ **AI** (AIOps). Chạm **Reliability** + **Operational Excellence**.

> Điểm nằm ở chỗ hệ tự dập được một cách an toàn - có phanh, verify, lùi được - chứ không phải một script bấm bừa lên production.

---

## English

# [DIRECTIVE #22] The system must safely auto-mitigate incidents

**From:** Operations (SRE) & AI Board - TechX Corp
**Effective:** immediately on receipt · complete & submit before **Saturday 25/07/2026**
**Applies to:** the AIO team of every Task Force

---

## Context
An incident that fires at midnight and waits for a human to wake up costs the customer an hour of pain. A mature operations system does not stop at detection: for incidents whose fix is known, the system must **auto-mitigate** and then check itself. But a wrong automated action is worse than doing nothing - so automation must ship with brakes: safe before acting, verify after acting, roll back on failure.

## Requirements
1. **Safe before acting** - every automated action must pass a safety check first: dry-run, blast-radius limit, cooldown to prevent repeats.
2. **Auto-mitigate incidents** - on detection, the system decides and executes the mitigating action on its own, no human button press.
3. **Verify after acting** - measure with real telemetry whether the incident actually eased; do not infer from assumptions.
4. **Rollback on verify failure** - an action that does not help (or is deliberately forced wrong) must auto-revert/escalate, leaving no fallout.
5. **Auditable log** - every automated action is logged in enough detail to reconstruct: what triggered it, what it did, the verify result, whether it rolled back.

"Method is your choice; if the property holds, just prove it."

## Definition of Done (DoD - due 25/07)
No need to cover every incident type. Done when:
1. **Pick ≥ 1 concrete incident type** (e.g. one fault injected via flagd) the system **auto-mitigates end-to-end**: detect → safety check (dry-run/blast-radius) → act → verify with real telemetry.
2. **A working rollback branch** - force one wrong action (or a verify failure) → the system **auto-reverts/escalates**, visible in the log.
3. **Audit log** for that mitigation: trigger → action → verify result → whether it rolled back.
> Covering more incident types + MTTR before/after = higher score; one type running e2e safely + one rollback is the **floor**.

## Constraints
- **Must be driven by your AIOps:** the mitigating action is triggered **by your own detector** (building on #7), with your team's own decision + verify + rollback + audit. **k8s native pod-restart / HPA does NOT count** as closed-loop.
- Hold SLO/budget; do not touch or disable flagd; do not lower the bar to pass.

## Deliverables (artifact)
Submit via **one Jira ticket** `AI MANDATE #22` (see `AI_MANDATE_EVIDENCE.md`):
- **Before the deadline:** PR/commit link + **a replay entry that accepts external scenarios** + audit log + your own MTTR/before-after numbers + `repro`.
- **On grading day:** the organizers (BTC) inject a **hidden scenario** (one real incident; and one case that forces a wrong action to check for rollback). The team runs it and **captures: auto-mitigation + verify + rollback**, pasted into the ticket.
- **A signed ADR**.

**Pass when:** incident → system auto-mitigates safely (through the safety check) + verifies; forced wrong → **rollback**; no reckless mitigation outside the allowed scope.

## Where it shows up
The **AI** pillar (AIOps). Touches **Reliability** + **Operational Excellence**.

> The score is in whether the system auto-mitigates safely - with brakes, verify, and rollback - not a script blindly hammering production.
