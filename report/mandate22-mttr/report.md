# TF1-106 — MTTR before/after cho vòng tự dập của đội

**Ngày đo:** 2026-07-27 · **Người đo:** Thanh Pham Huu Tien (phamthanh.forwork@gmail.com)
**Cụm:** `ecommerce-dev-eks` / namespace `techx-tf1` · **Kịch bản:** OOM
**Mandate:** #22 (closed-loop auto-mitigate)

---

## Kết quả

| | MTTR | Đường phục hồi |
|---|---|---|
| **Before** | **310.3s** | kubelet tự restart, CrashLoopBackOff |
| **After** | **67.2s** | remediation xoá pod, backoff reset |
| | **giảm 4.6 lần** | |

> ⚠️ **Con số 4.6× chỉ đúng cho MỘT lần.** Đọc mục "Vì sao không được báo cáo 4.6× trần
> trụi" trước khi trích. MTTR **trung bình thực tế ≈ 302s**, gần như không cải thiện.

---

## 1. Vì sao phải đo theo góc CrashLoopBackOff

**Kubernetes đã tự restart pod OOMKilled rồi.** Nên "before" không phải "nằm chết", và nếu
chỉ đo lần OOM đầu tiên thì before/after gần bằng nhau — con số sẽ vô nghĩa.

Giá trị thật của vòng tự dập nằm ở chỗ khác: kubelet lùi theo cấp số nhân khi pod OOM lặp
lại (**10s → 20s → 40s → 80s → 160s → 300s**, trần 300s), còn remediation **xoá pod** nên
Deployment tạo pod mới và **backoff về 0**.

Đó là điều kubelet không tự thoát ra được, và là thứ duy nhất vòng tự dập làm được mà
kubelet không làm.

## 2. Bối cảnh đo — pod mồi, blast radius bằng không

Không ép OOM một service thật:

| Cách | Vì sao không dùng |
|---|---|
| flagd `emailMemoryLeak` | flagd trên EKS đồng bộ từ server BTC, **không bơm được** (`report/mandate15-eks/report.md` §2) |
| Hạ memory limit service thật | ArgoCD `selfHeal` revert, **và** ảnh hưởng người khác |

Thay bằng deployment dùng một lần `mttr-canary` (`mttr-canary.yaml`, đã xoá sau khi đo):
không phục vụ traffic nào nên **blast radius bằng không**, nhưng mang đúng nhãn
`opentelemetry.io/name` mà `find_oom_pods()` chọn (`k8s_status.py:41`) — nên đường đi qua
detector và remediation **y hệt pod thật**.

**Hạn chế phải nói rõ:** đây là pod mồi, không phải service production. Con số phản ánh
đúng độ trễ của *vòng tự dập*, không phải độ phức tạp phục hồi của một service thật có
dependency và warm-up.

Ba lần thử mới dựng được pod mồi chạy đúng, đều là ràng buộc thật của cụm:

| Lần | Hỏng | Nguyên nhân |
|---|---|---|
| 1 | Admission denied | Cụm có `ValidatingAdmissionPolicy` bắt `allowPrivilegeEscalation: false` |
| 2 | `StartError` | 64Mi quá thấp cho cả `runc init` — *"memory limit too low?"* |
| 3 | `StartError` | `emptyDir medium: Memory` làm rối kế toán bộ nhớ → bỏ tmpfs, cấp phát thẳng trong tiến trình |

## 3. Before — 310.3s

Đo bằng `measure_mttr.py before`, hai chu kỳ độc lập:

| Chu kỳ | MTTR |
|---|---|
| 1 (sau restart thứ 10) | 311.8s |
| 2 (sau restart thứ 11) | 308.8s |
| **Trung bình** | **310.3s** |

Phương sai 3s. Khớp trần backoff 300s + ~10s khởi động container.

**Kiểm chéo bằng lý thuyết.** Chuỗi backoff cho 11 lần restart:

```
10 + 20 + 40 + 80 + 160 + 300×6 = 2110s
+ 25s × 11 (pod chạy trước mỗi lần OOM) = 275s
= 2385s = 39.8 phút
```

Pod thực tế sống **39.3 phút** với 11 restart. Lệch **0.5 phút**.

`kubectl get events` xác nhận trực tiếp: `Warning BackOff — Back-off restarting failed
container memhog`.

Dữ liệu: `mttr-before.json`

## 4. After — 67.2s

```
OOM cuối       : 20:51:46
pod mới tạo    : 20:52:47      ← 61.0s   detector poll + remediation poll
pod mới Ready  : 20:52:53      ←  6.2s   khởi động container
────────────────────────────────────────
MTTR (after)   : 67.2s
```

**61.0s khớp đúng hai chu kỳ poll nối tiếp**: detector 30s + remediation ~31s. Không có
độ trễ ẩn nào — remediation phản ứng ngay khi được phép.

Dữ liệu: `mttr-after.json`

### Ba lần đo trước đó không dùng được, ghi lại để không ai lặp lại

| Lần | Hành động lúc | Bị chi phối bởi |
|---|---|---|
| 1 | **1 giây** sau khi `DRY_RUN=false` lên cụm | dry-run, không phải độ trễ phát hiện |
| 2 | **9 giây** sau khi cửa sổ blast-radius mở | quota |
| 3 | **3 giây** sau khi restart reset quota | quota |

Cả ba lần remediation phản ứng gần như tức thì khi được phép — nhưng *"được phép lúc nào"*
mới là thứ chi phối con số. Chỉ lần thứ tư, khi quota đã sẵn **trước** khi OOM xảy ra, mới
đo được độ trễ thật.

Cũng phát hiện: alert `oom-detected` cách nhau đúng ~10.5 phút — đó là **cooldown 600s của
alerter**, không phải nhịp OOM thật (pod OOM mỗi ~2 phút).

## 5. Vì sao KHÔNG được báo cáo 4.6× trần trụi

`blast_radius: max_actions 1 / 3600s / scope=namespace`.

Pod mồi OOM mỗi ~2 phút, nên vòng tự dập cứu được **1 trong ~30 lần**:

```
MTTR trung bình = (1 × 67.2 + 29 × 310.3) / 30 ≈ 302s
```

So với 310.3s — **cải thiện 2.7%**, không phải 4.6 lần.

Và với **một OOM đơn lẻ** thì ngược lại hoàn toàn: kubelet restart lần đầu chỉ mất **~10s**,
còn vòng tự dập cần **67.2s** — **chậm hơn 6.7 lần**.

| Loại sự cố | kubelet | vòng tự dập | Ai thắng |
|---|---|---|---|
| OOM đơn lẻ | ~10s | 67.2s | **kubelet** (6.7×) |
| OOM lặp, tính riêng lần được cứu | 310.3s | 67.2s | **vòng tự dập** (4.6×) |
| OOM lặp, tính trung bình thực tế | 310.3s | ~302s | hoà (2.7%) |

**Kết luận đúng:** vòng tự dập **phá được CrashLoopBackOff** — thứ kubelet không tự thoát
ra — và con số đó có thật. Nhưng với tham số `blast_radius` hiện tại nó **không cải thiện
MTTR trung bình**.

**Kiến nghị của ticket này là xem lại tham số `blast_radius`**, không phải khoe 4.6×.
`max_actions: 1 / 3600s` quá chặt cho một pod đang crashloop. Hướng đáng cân nhắc: tách
hạn mức theo *service* thay vì theo *namespace*, hoặc cho phép nhiều hành động hơn trên
cùng một service khi các lần đó là cùng một sự cố kéo dài.

## 6. Hai lỗ hổng cổng an toàn phát hiện trong lúc đo

Mandate #22 đòi *"kiểm tra an toàn: dry-run / blast-radius"*. Đo thật thì **hai trong ba
cổng không làm đúng việc**.

### 6.1 `blast_radius` không sống qua restart

```python
class BlastRadiusGuard:
    def __init__(self, ...):
        self._history = {}          # trong BỘ NHỚ
```

Lịch sử hành động nằm trong RAM tiến trình → **pod restart là quota reset ngay**.

**Đã chứng minh bằng thực nghiệm:** dùng chính lỗ hổng này để reset quota giữa chừng khi đo
(`kubectl rollout restart deploy/aiops-remediation` → hành động tiếp theo diễn ra sau
**3 giây**).

Hệ quả: một pod remediation crashloop được cấp lại quota đầy sau mỗi lần khởi động — giới
hạn *"1 hành động/giờ"* trên giấy thành *"1 hành động mỗi lần restart"* trên thực tế.

### 6.2 `error_budget_check` thất bại mở

Query của policy dùng `http_response_status_code=~"5.."`. Đo trên cụm: nhãn đó **rỗng toàn
cụm**, query trả **0 chuỗi**.

```python
for value, _labels in series:      # khong chay lan nao
    if value > max_ratio: return False
return True                         # -> luon cho qua
```

Một cổng an toàn **không bảo vệ gì cả**. Cùng lớp lỗi với rule kafka câm và 5 scenario chấm
sai: một thứ trông như đang bảo vệ nhưng thực ra không.

**Cả hai đều nghiêm trọng hơn con số MTTR**, vì mandate đòi cổng an toàn *hoạt động*.
Chưa sửa — nên tách ticket riêng.

## 7. Tái tạo

```sh
kubectl -n techx-tf1 apply -f report/mandate22-mttr/mttr-canary.yaml
python3 report/mandate22-mttr/measure_mttr.py before 13     # dry-run BAT
# ... bat dry-run tat, doi ArgoCD sync ...
python3 report/mandate22-mttr/measure_after.py              # dry-run TAT
kubectl -n techx-tf1 delete deploy mttr-canary
```

**Lưu ý khi chạy lại:** quota `blast_radius` phải **sẵn trước khi OOM xảy ra**, nếu không
con số đo được sẽ là thời gian chờ quota chứ không phải độ trễ phát hiện. Đó là sai lầm đã
làm hỏng ba lần đo đầu.

## 8. Trạng thái cụm sau khi đo

| | |
|---|---|
| `mttr-canary` | **đã xoá** |
| `REMEDIATION_DRY_RUN` | trả về `true` qua PR #460 |

PR #459 tắt dry-run để đo, PR #460 trả lại. Cụm không được để ở trạng thái `false` ngoài
cửa sổ đo.
