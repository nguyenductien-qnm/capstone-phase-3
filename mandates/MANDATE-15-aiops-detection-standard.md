# [DIRECTIVE #15] Phát hiện sự cố phải đáng tin - phân biệt "bận" với "hỏng", chứng minh bằng ca kiểm

**Từ:** Ban Vận hành (SRE) & AI - TechX Corp
**Hiệu lực:** ngay khi nhận · hoàn tất & nộp trước **thứ Bảy 25/07/2026**
**Áp dụng:** nhóm AIO của mọi Task Force

---

## Bối cảnh
Đây là phát hiện **sự cố sức khỏe service** - bất thường trên telemetry ứng dụng (latency, lỗi, bão hòa…), khác với phát hiện hành động audit/bảo mật. Hệ như vậy chỉ có ích khi nó **bắt đúng sự cố thật, không kêu oan lúc hệ chỉ đang bận, không bị nhiễu che**, và **chạy liên tục** chứ không phải một script bấm tay. Từ đợt này, năng lực đó phải **đo được và chịu được một bộ kịch bản do BTC bơm vào lúc chấm**.

## Yêu cầu
Đo trên **bộ sự cố có nhãn**, tái tạo từ `repro`; **logic chấm phải mở để mentor soi**. Cách làm tự chọn; đã đạt thì chỉ cần chứng minh.
1. **Bắt đúng** - phát hiện sự cố thật; báo precision/recall/lead-time trên bộ có nhãn (bộ nhỏ, per-case).
2. **Không bị che (masking)** - một spike đơn/nhiễu trong cửa sổ không làm bỏ sót một sự cố thật khác.
3. **Không kêu oan khi bận** - cảnh báo dựa trên **độ lệch khỏi mức bình thường của chính service**, không mốc tuyệt đối.
4. **Chạy liên tục + có trên trunk** - detector là workload thường trực trong cụm (không chạy-một-lần-rồi-thoát), merged vào nhánh chính.
5. **Tự sinh tóm tắt sự cố** - khi vượt ngưỡng thì tạo incident summary và đẩy ra kênh thật.
6. **Đo MTTD before/after** - chứng minh phát hiện nhanh hơn so với mốc trước đó.

## Ràng buộc
- Đo phải nhẹ; trong ngân sách; không đụng / vô hiệu hóa flagd.
- Không hạ chuẩn để qua bài.

## Phải nộp (artifact)
Nộp qua **1 Jira ticket** `AI MANDATE #15` (xem `AI_MANDATE_EVIDENCE.md`):
- **Trước hạn:**
  - link PR/commit (đã merge trunk);
  - **cửa replay nhận kịch bản từ ngoài** (endpoint/lệnh chạy trên bộ sự cố đưa vào);
  - bằng chứng detector **chạy liên tục** trong cụm;
  - **bộ sự cố có nhãn** commit trong repo;
  - **MTTD before/after**;
  - `repro`.
- **Đến ngày chấm:** BTC bơm **bộ kịch bản ẩn** - 1 sự cố thật, 1 ca **masking** (spike nhiễu + một sự cố nhẹ), 1 cửa sổ **tải cao nhưng healthy**. Đội chạy, **chụp output detector + incident summary** từng ca dán ticket.
- **ADR ký tên**: baseline/ngưỡng, tóm tắt sinh thế nào.

**Đạt khi (bộ ẩn):** sự cố thật → **kêu ≤ 1 chu kỳ** kèm summary + severity đúng; ca masking → **vẫn bắt** sự cố nhẹ; tải-cao-healthy → **không kêu**.

## Được nhìn ở đâu
Trụ **AI** (AIOps): phát hiện có ích + chạy thật. Chạm **Reliability** + **Operational Excellence** (giảm MTTD, chống mệt cảnh báo).

> Điểm nằm ở chỗ detector đủ tinh để **không kêu oan khi service chỉ đang bận** và không bị nhiễu che - chứng minh bằng bộ kịch bản ẩn, không phải demo một lần.

---

## English

# [DIRECTIVE #15] Incident detection must be trustworthy — tell "busy" from "broken", proven by test cases

**From:** Operations (SRE) & AI — TechX Corp
**Effective:** immediately · complete & submit by **Sat 25/07/2026**
**Applies to:** the AIO team of every Task Force

### Context
This is **service-health** detection — anomalies in application telemetry (latency, errors, saturation…), distinct from detecting audit/security actions. Such a detector is only useful when it **catches real incidents, doesn't cry wolf when the system is merely busy, isn't masked by noise**, and **runs continuously** rather than as a hand-run script. From now, that capability must be **measurable and survive a scenario set the organizers inject at grading**.

### Requirements
Measured on a **labeled incident set**, reproducible from `repro`; **scoring logic must be open**. Method is your choice; if you already meet it, just prove it.
1. **Correct detection** — catch real incidents; report precision/recall/lead-time on the labeled set (small, per-case).
2. **Not masked** — a single spike/noise in the window must not make it miss a genuine separate incident.
3. **No false alarm when busy** — alert on **deviation from that service's own normal**, not an absolute threshold.
4. **Runs continuously + on trunk** — the detector is a standing in-cluster workload (not run-once-and-exit), merged to the main branch.
5. **Auto incident summary** — on breach, generate an incident summary and ship it to a real channel.
6. **MTTD before/after** — prove faster detection versus the prior baseline.

### Constraints
- Measurement stays lightweight; within budget; do not touch / disable flagd.
- No lowering the bar to pass.

### Deliverables (artifact)
Submit via **1 Jira ticket** `AI MANDATE #15` (see `AI_MANDATE_EVIDENCE.md`):
- **Before the deadline:**
  - PR/commit link (merged to trunk);
  - a **replay entry accepting external scenarios** (endpoint/command running on a supplied incident set);
  - evidence the detector **runs continuously** in-cluster;
  - the **labeled incident set** committed in the repo;
  - **MTTD before/after**;
  - `repro`.
- **On grading day:** the organizers inject a **hidden scenario set** — one real incident, one **masking** case (noise spike + a subtle incident), one **high-load-but-healthy** window. You run them and **capture the detector output + incident summary** per case into the ticket.
- **Signed ADR**: baseline/threshold, how the summary is generated.

**Met when (hidden set):** the real incident → **fires within ≤ 1 cycle** with a summary + correct severity; the masking case → **still catches** the subtle incident; high-load-healthy → **does not fire**.

### Where it shows up
The **AI** pillar (AIOps): useful detection that actually runs. Touches **Reliability** + **Operational Excellence** (lower MTTD, fight alert fatigue).

> The point is a detector sharp enough to **not cry wolf when a service is just busy** and not be masked by noise — proven by a hidden scenario set, not a one-off demo.
