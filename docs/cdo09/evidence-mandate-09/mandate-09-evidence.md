# Mandate 09 Evidence

**Phạm vi:** TBD1, TBD2, TBD3, TBD4.  
**Môi trường:** Production, `us-east-1`, namespace `techx-tf1`.  
> *Lưu ý về Naming:* Dù Runtime App đang chạy ở môi trường Production (namespace `techx-tf1`), RDS instance name vẫn mang prefix `ecommerce-dev-*` do quy ước đặt tên hạ tầng kế thừa (không phải chạy nhầm trên cluster Develop).  
**Thư mục ảnh:** `docs/cdo09/evidence-mandate-09/screenshots/`.

File này là evidence chính để nộp Mandate 09. Mỗi ảnh bên dưới có phần giải thích ngay sau ảnh để reviewer hiểu ảnh đang chứng minh điều gì, thay vì chỉ paste screenshot rời rạc.

## 1. Mandate 09 Chứng Minh Gì?

Mandate 09 chứng minh các thao tác database operation trên Production có thể diễn ra theo hướng zero-downtime: app vẫn có traffic, request không rớt hàng loạt, SLI/burn rate không xấu kéo dài, latency phục hồi, pod vẫn ready, và RDS quay lại trạng thái `available` sau thao tác.

| Task | Nội dung chứng minh | Evidence chính |
| --- | --- | --- |
| TBD1 | App chịu DB blip bằng retry/pool | Grafana during/after + terminal stable/done |
| TBD2 | Online schema migration expand-contract | Baseline curl + psql expand/backfill/verify + Grafana during/after |
| TBD3 | PostgreSQL major upgrade bằng RDS Blue/Green | Terminal before/success + Grafana during + AWS RDS after |
| TBD4 | Static parameter bằng Multi-AZ failover | Terminal preflight/attach/verify + Grafana during/after |

## 2. Evidence TBD1 - Retry/Pool Chịu DB Blip

*(Session Time: 2026-07-20 ~15:48–15:58)*

### 2.1 Grafana During Primary Failover

![TBD1 Grafana during primary failover and curl loop](screenshots/m09-tbd1-01-grafana-during-primary-failover.png)

Ảnh này chứng minh trong lúc failover primary, hệ thống vẫn có traffic thật trên dashboard SLO. Các panel SLI/burn/latency không cho thấy lỗi kéo dài, đồng thời terminal curl loop vẫn đang gọi `/api/products`, giúp chứng minh retry/pool của app hấp thụ được DB blip thay vì làm request rớt hàng loạt.

### 2.2 Terminal Stable State

> *Note:* Ảnh số `02` không có mặt trong bộ evidence do quá trình script chạy polling được gộp chung, chuyển thẳng sang trạng thái Stable ở bước `03` mà không dừng lại chụp ảnh.

![TBD1 terminal stable state](screenshots/m09-tbd1-03-terminal-stable-state.png)

Ảnh này chứng minh sau failover, hệ thống quay lại stable state: service/pod sẵn sàng và RDS trở lại trạng thái `available`. Đây là bằng chứng phục hồi sau thao tác DB blip.

### 2.3 Terminal DONE

![TBD1 terminal done](screenshots/m09-tbd1-04-terminal-done.png)

Ảnh này chứng minh script TBD1 chạy tới bước `DONE`, log đã được lưu, và cuối bài test không có dấu hiệu fail/crash-loop. Đây là checkpoint kết thúc bài test.

### 2.4 Grafana After

![TBD1 Grafana after](screenshots/m09-tbd1-05-grafana-after.png)

Ảnh này chứng minh sau thao tác DB blip, success rate và latency đã ổn định lại, pod phase bình thường, không có downtime kéo dài sau khi RDS phục hồi.

## 3. Evidence TBD2 - Online Schema Migration Expand-Contract

*(Session Time: 2026-07-20 ~16:13–16:17)*

### 3.1 Terminal Baseline Curl

![TBD2 terminal baseline curl](screenshots/m09-tbd2-01-terminal-baseline-curl.png)

Ảnh này chứng minh baseline trước migration đang khỏe: endpoint trả HTTP 200 và không có request lỗi trong smoke/curl summary. Đây là mốc trước khi thay đổi schema.

### 3.2 PSQL Expand Schema

![TBD2 psql expand](screenshots/m09-tbd2-02-psql-expand.png)

Ảnh này chứng minh bước expand schema đã chạy qua psql thành công, thêm cột `image_url` mà không làm gián đoạn app.

### 3.3 PSQL Verify Columns

![TBD2 psql verify columns](screenshots/m09-tbd2-03-psql-verify-columns.png)

Ảnh này chứng minh cả hai cột `picture` và `image_url` cùng tồn tại sau expand. Đây là đúng pattern expand-contract: thêm field mới trước, chưa drop field cũ.

### 3.4 PSQL Backfill Verify

![TBD2 psql backfill verify](screenshots/m09-tbd2-04-psql-backfill-verify.png)

Ảnh này chứng minh backfill dữ liệu đã hoàn tất, số record thiếu dữ liệu `image_url` bằng `0`. Điều này giúp app dual-read có dữ liệu đầy đủ để đọc từ cột mới.

### 3.5 Grafana During Migration

![TBD2 Grafana during migration](screenshots/m09-tbd2-05-grafana-during-migration.png)

Ảnh này chứng minh trong lúc expand/backfill vẫn có traffic, Browse/Cart/Checkout SLI không rớt kéo dài, burn rate không spike bất thường, và pod vẫn ổn định. Đây là bằng chứng migration diễn ra dưới load.

### 3.6 Terminal Dual-Read DONE

![TBD2 terminal dual read and done](screenshots/m09-tbd2-06-terminal-dual-read-done.png)

Ảnh này chứng minh app đọc được dữ liệu theo logic dual-read sau backfill, curl vẫn pass, và bài test kết thúc an toàn. Việc giữ cả `picture` và `image_url` giúp rollback/re-demo không bị mất đường lui.

### 3.7 Grafana After

![TBD2 Grafana after](screenshots/m09-tbd2-07-grafana-after.png)

Ảnh này chứng minh sau migration, success rate không bị drop, burn rate không spike, latency hồi phục và pod vẫn ready. Đây là bằng chứng hệ thống ổn định sau thay đổi schema.

## 4. Evidence TBD3 - PostgreSQL Major Upgrade Bằng RDS Blue/Green

*(Session Time: 2026-07-20 ~16:34–17:18)*

### 4.1 Terminal RDS Before

![TBD3 terminal RDS before](screenshots/m09-tbd3-01-terminal-rds-before.png)

Ảnh này chứng minh trạng thái trước upgrade: RDS primary được kiểm tra trước khi Blue/Green switchover. Đây là mốc before để đối chiếu với trạng thái engine/version sau khi upgrade.

### 4.2 Grafana Baseline

![TBD3 Grafana baseline](screenshots/m09-tbd3-02-grafana-baseline.png)

Ảnh này chứng minh hệ thống đang có traffic thật ổn định (baseline) trước khi bắt đầu tạo Blue/Green deployment.

### 4.3 Terminal Create Blue/Green

> *Note về Snapshot:* Trong log script có ghi nhận `SKIPPED-NO-SNAPSHOT`. Lý do là bài lab này chủ đích bỏ qua bước tạo snapshot thủ công để tiết kiệm thời gian (do bản chất Blue/Green đã cung cấp cụm Green an toàn để rollback nếu cần).

![TBD3 terminal create Blue/Green](screenshots/m09-tbd3-03-terminal-create-bg.png)

Ảnh này chứng minh lệnh gọi API tạo Blue/Green deployment đã được thực thi thành công, bắt đầu quá trình provisioning cụm Green.

### 4.4 Terminal Polling Green

![TBD3 terminal polling Green](screenshots/m09-tbd3-04-terminal-polling-bg.png)

Ảnh này chứng minh script đang polling trạng thái của Blue/Green deployment, chờ đợi cụm Green chuyển sang trạng thái AVAILABLE trước khi tiến hành switchover.

### 4.5 AWS Console Provisioning

![TBD3 AWS Console provisioning](screenshots/m09-tbd3-05-aws-console-provisioning.png)

Ảnh này chứng minh trên AWS Console cũng ghi nhận quá trình tạo cụm Green đang diễn ra, khớp với log polling ở terminal và đã ở bước chờ Switchover.

### 4.6 Grafana During Switchover

![TBD3 Grafana during switchover](screenshots/m09-tbd3-06-grafana-during-switchover.png)

Ảnh này chứng minh trong lúc lệnh `SWITCHOVER_IN_PROGRESS` đang chạy, hệ thống vẫn có traffic. Dashboard SLO dùng để kiểm tra SLI, burn rate, request volume, latency và pod phase trong cửa sổ chuyển đổi.

### 4.7 Terminal Verify Success

![TBD3 terminal verify success](screenshots/m09-tbd3-07-terminal-verify-success.png)

Ảnh này chứng minh sau khi switchover, script xác nhận DB chính đã lên phiên bản 17.10 và trạng thái `available`, lệnh `curl` liên tục trả về HTTP 200 mà không gặp lỗi.  
> *Note:* Trên màn hình terminal có báo proxy target cũ là `UNAVAILABLE`. Đây là trạng thái bình thường trong cửa sổ post-switchover khi AWS đang dọn dẹp topology (cleanup cụm Blue cũ). Lệnh curl 200 liên tục đã chứng minh kết nối từ App -> Proxy -> DB mới hoàn toàn thông suốt, không bị chặn.

### 4.8 AWS Console After Switchover

![TBD3 AWS Console after](screenshots/m09-tbd3-08-aws-console-after.png)

Ảnh này chứng minh trên AWS Console, RDS production sau switchover đang chạy PostgreSQL 17.10. Đây là bằng chứng độc lập ngoài terminal cho kết quả upgrade.

### 4.9 Terminal Success Banner

![TBD3 terminal success banner](screenshots/m09-tbd3-09-terminal-success-banner.png)

Ảnh này chứng minh quá trình nâng cấp thành công với hộp thông báo màu xanh `NANG VERSION THANH CONG` trên terminal.

### 4.10 Grafana After

![TBD3 Grafana after](screenshots/m09-tbd3-10-grafana-after.png)

Ảnh này chứng minh Dashboard SLO sau khi quá trình switchover hoàn tất. Hệ thống ổn định, traffic đều, SLO vẫn xanh, không có lỗi rớt request kéo dài.

## 5. Evidence TBD4 - Static Parameter + Multi-AZ Failover

*(Session Time: 2026-07-21 ~00:12–00:17)*

> [!NOTE]
> **Giải trình về Terraform State cho TBD4:**
> Trong bài test này, việc cập nhật parameter (`track_activity_query_size`) được thực hiện **trực tiếp qua AWS CLI/API** thay vì sửa code Terraform (`.tf`) và chạy `terraform apply`.
> Lý do: Trọng tâm của TBD4 là chứng minh hệ thống không bị downtime khi *force failover / reboot* để apply một static parameter. Nếu làm qua Terraform, thay đổi sẽ được lưu cứng vào State file. Điều này khiến việc dọn dẹp (rollback) sau buổi demo trở nên cồng kềnh hơn. Việc thao tác bằng CLI giúp ta có thể test nhanh khả năng failover, sau đó gọi cờ `-RollbackOnly` để reset lại parameter về mặc định mà hoàn toàn không làm bẩn (drift) Terraform State của môi trường Production.

### 5.1 Terminal Preflight Multi-AZ

![TBD4 terminal preflight MultiAZ](screenshots/m09-tbd4-01-terminal-preflight-multiaz.png)

Ảnh này chứng minh điều kiện trước khi đổi static parameter: RDS đang available, Multi-AZ được bật, engine/family phù hợp, và parameter group hiện tại được ghi nhận trước khi attach custom group.

### 5.2 Terminal Parameter Attach

![TBD4 terminal parameter attach](screenshots/m09-tbd4-02-terminal-param-attach.png)

Ảnh này chứng minh custom DB parameter group đã được tạo/gắn vào primary, static parameter đã được set để chờ reboot/failover. Đây là bằng chứng phần thay đổi cấu hình RDS đã được chuẩn bị đúng.

### 5.3 Grafana During Failover

![TBD4 Grafana during failover](screenshots/m09-tbd4-03-grafana-during-failover.png)

Ảnh này chứng minh trong lúc `reboot --force-failover` vẫn có traffic và dashboard SLO không ghi nhận lỗi kéo dài. Đây là ảnh quan trọng nhất để chứng minh static parameter được apply dưới load mà không tạo downtime rõ rệt.

### 5.4 Terminal Verify Curl

![TBD4 terminal verify curl](screenshots/m09-tbd4-04-terminal-verify-curl.png)

Ảnh này chứng minh sau failover, RDS quay lại trạng thái `available`, parameter group ổn định, và curl/smoke verify pass. Đây là bằng chứng hệ thống phục hồi sau thao tác reboot/failover.

### 5.5 Terminal SHOW Parameter

> *Note về Log:* Bước xác nhận SQL bằng lệnh `SHOW` này được thực hiện (chụp tay) ngay sau khi script tự động kết thúc. Do đó, trong file log text kết thúc ở trạng thái chờ (pending_sql_show), còn kết quả `8kB` thực tế được chứng minh qua bức ảnh này.

![TBD4 terminal show parameter](screenshots/m09-tbd4-05-terminal-show-parameter.png)

Ảnh này chứng minh static parameter đã thật sự có hiệu lực trong PostgreSQL thông qua câu lệnh `SHOW`. Đây là phần xác nhận kết quả bên trong database, không chỉ xác nhận ở AWS control plane.

### 5.6 Grafana After

![TBD4 Grafana after](screenshots/m09-tbd4-06-grafana-after.png)

Ảnh này chứng minh sau failover để apply static parameter, SLO quay lại ổn định, latency phục hồi, pod phase không có lỗi kéo dài. Đây là mốc after để kết luận thao tác đã hoàn tất và hệ thống ổn định.

## 6. Checklist Evidence Hiện Có

Bảng dưới đây đánh giá PASS/FAIL dựa trên điều kiện nghiệm thu tại mục 7. Tất cả các TBD đều đáp ứng đủ yêu cầu về Request Volume > 0, HTTP 200, và minh chứng được hệ thống hồi phục.

| Task | Đánh giá | Ảnh đã có | Nhận xét (Map tới Điều kiện PASS) |
| --- | :---: | ---: | --- |
| **TBD1** | **PASS** | 4 | Có Grafana during/after (Request > 0), terminal báo stable/done rõ ràng. |
| **TBD2** | **PASS** | 7 | Có baseline, script psql expand/backfill/verify thành công, Grafana không gián đoạn. Việc giữ dual-read (chưa drop) là để đảm bảo đường lùi an toàn. |
| **TBD3** | **PASS** | 10 | Trọn vẹn flow từ before, create B/G, switchover, đến lúc primary lên 17.10 và app curl HTTP 200. |
| **TBD4** | **PASS** | 6 | Có preflight, attach param, Grafana trong lúc failover, verify curl và lệnh SHOW chứng minh param 8192 đã ăn. |

## 7. Điều Kiện Không Ghi PASS

Không ghi PASS nếu thiếu một trong các bằng chứng sau:

```text
Không có ảnh Grafana với Request Volume > 0.
Không có terminal output chứng minh script đã chạy tới bước verify/pass.
Không có curl/result cho thấy bad=0 hoặc toàn HTTP 200.
Không có ảnh sau thao tác chứng minh hệ thống hồi phục/ổn định.
Dùng nhầm ảnh Develop để chứng minh Production.
Ảnh bị che secret/password hoặc connection string.
```

## 8. Log Files (Reference)

Bên cạnh ảnh chụp màn hình, các kịch bản chạy tự động (PowerShell scripts) cũng sinh ra file log text ghi nhận lại toàn bộ output ở terminal. Các file này được lưu trữ để làm bằng chứng bổ sung:

* **TBD1 (DB Blip Retry/Pool)**: [tbd1-drill-log.txt](logs/tbd1-drill-log.txt)
* **TBD2 (Online Schema Migration)**: [tbd2-test-log.txt](logs/tbd2-test-log.txt)
* **TBD3 (RDS Blue/Green 16 -> 17)**: [tbd3-bg-log.txt](logs/tbd3-bg-log.txt)
* **TBD4 (Static Parameter + Failover)**: [tbd4-param-log.txt](logs/tbd4-param-log.txt)

## 9. Tài Liệu Minh Chứng Môi Trường Develop (Develop Environment Evidence)

Dưới đây là các tài liệu ghi nhận kết quả baseline, kế hoạch chạy tải và kiểm chứng bảo mật trên môi trường Develop cho Mandate 09:

* **M9 Baseline & Load Window (Develop)**: [evidence-46.md](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/evidence/evidence-46.md) (hoặc [relative](evidence/evidence-46.md)) - Chi tiết kịch bản tải, baseline metric sạch lỗi (RPS 5.1, error rate 0%).
* **Xác nhận Security Guardrails (Develop)**: [evidence-44.md](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/evidence/evidence-44.md) (hoặc [relative](evidence/evidence-44.md)) - Đảm bảo database/cache endpoint nội bộ, dashboard Ops, và TLS/auth logic không bị nới lỏng.
* **Jaeger Trace & Storefront SLO**: [evidence-slo-02.md](file:///d:/GitHub/capstone-phase-3/docs/cdo09/evidence-mandate-09/evidence/evidence-slo-02.md) (hoặc [relative](evidence/evidence-slo-02.md)) - Phân tích latency của các dependency services qua Jaeger trace cho luồng storefront checkout.

