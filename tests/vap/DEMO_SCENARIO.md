# Kịch bản Video Demo — Mandate 05: Runtime Hardening

---

## Mở đầu

Chào mentor, trong video này mình sẽ demo phần bảo mật runtime cho cluster Kubernetes.

Ý tưởng đơn giản thôi — mình muốn đảm bảo không ai có thể deploy một container
nguy hiểm lên cluster, dù vô tình hay cố ý. Nguy hiểm ở đây là: chạy quyền root,
dùng image không rõ version, không khai báo giới hạn tài nguyên, hay giữ các đặc
quyền hệ thống không cần thiết.

Kubernetes có một tính năng native gọi là ValidatingAdmissionPolicy — mình dùng
cái đó để chặn, không cần cài thêm gì vào cluster cả.

---

## Phần 1 — Xác nhận policy đang chạy

Đầu tiên mình show 5 policy đang active trên cluster.

> Chạy: kubectl get validatingadmissionpolicy

Tất cả đang ở chế độ Deny — tức là vi phạm thì bị từ chối thẳng, không phải chỉ
cảnh báo.

---

## Phần 2 — Chạy bộ test

> Chạy: NS=techx-tf1 bash run-dry-run-tests.sh

Script này test 19 tình huống khác nhau. Mình không tạo pod thật — chỉ giả lập
request đến API Server để xem nó có chặn đúng không.

Cuối script hiện PASS=19 FAIL=0. Bây giờ mình giải thích từng nhóm.

---

## Phần 3 — Giải thích từng case

---

### Nhóm 1 — Chặn container chạy quyền root

**neg-01:** Dev set runAsUser: 0 — tức là chạy root. Cái này nguy hiểm vì nếu
container bị hack, kẻ tấn công có full quyền trên máy chủ. Bị chặn.

**neg-10:** Lần này root không đặt ở container mà đặt ở cấp pod, container không
set gì nên kế thừa xuống. Nhìn vào manifest tưởng ổn nhưng thực ra vẫn chạy root.
Policy phát hiện được và vẫn chặn.

**pos-02:** Ngược lại, đây là cách viết đúng — đặt runAsNonRoot: true ở pod-level.
Hầu hết service trên cluster đang dùng pattern này. Policy nhận ra và cho qua.

---

### Nhóm 2 — Cấm image không rõ version

**neg-02:** Image dùng tag "latest". Vấn đề là "latest" hôm nay và "latest" tuần sau
có thể là hai image hoàn toàn khác nhau — không ai kiểm soát được. Bị chặn.

**neg-06:** Lần này container chính dùng image đúng chuẩn, nhưng có một initContainer
ẩn bên trên dùng busybox:latest. Policy quét cả initContainer nên vẫn phát hiện được.

**neg-11:** Thử viết hoa thành "LATEST" để né. Không qua — policy normalize hết
về chữ thường trước khi kiểm tra.

**pos-04:** Cách pin image an toàn nhất là dùng digest @sha256 — hash cố định,
không ai thay được nội dung mà không đổi hash. Policy cho qua.

---

### Nhóm 3 — Bắt buộc khai báo giới hạn tài nguyên

**neg-03:** Container không khai báo resources gì cả. Không khai báo thì Kubernetes
không biết pod cần bao nhiêu RAM, CPU — có thể ăn hết tài nguyên node và kéo sập
các service khác đang chạy cùng. Bị chặn.

**neg-09:** Lần này có khai báo nhưng thiếu limits.memory. Đây là lỗi hay gặp
nhất — dev khai requests xong quên mất limits. Vẫn bị chặn vì phải đủ cả 4 field.

---

### Nhóm 4 — Khóa đặc quyền hệ thống

**neg-07:** Không set allowPrivilegeEscalation. Mặc định Kubernetes cho phép
escalation nếu bỏ trống — tức là process bên trong container có thể tự leo thang
quyền. Phải set false tường minh, bỏ trống là vi phạm.

**neg-08:** Không có capabilities block. Container mặc định được cấp sẵn một số
quyền hệ thống nguy hiểm. Phải drop ALL để thu hồi hết, chỉ add lại cái nào thực
sự cần. Không drop gì = giữ hết mặc định = vi phạm.

**neg-04:** Vi phạm cả hai cái trên cùng lúc, thêm SYS_ADMIN — quyền gần như
toàn quyền kernel. Bị chặn ngay.

**pos-03:** DaemonSet thu thập metrics — otel-collector — cần chạy với quyền đặc
biệt để đọc dữ liệu từ host. Đây là ngoại lệ đã đăng ký chính thức. Policy nhận
ra đúng image và cho qua.

---

### Nhóm 5 — Chặn ngay khi apply Deployment, không chờ tới Pod

**neg-12:** Đây là case quan trọng nhất. Nếu policy chỉ chặn Pod thì
"kubectl apply deployment.yaml" vẫn chạy được — chỉ đến khi Deployment cố tạo Pod
mới bị chặn, lúc đó rất khó debug. Policy mình match cả Deployment nên bị từ chối
ngay tại lệnh apply, trước khi bất cứ thứ gì được tạo ra.

**neg-13:** Tương tự với CronJob — bị chặn ngay lúc apply, không phải lúc job
chạy lần đầu.

**neg-05:** Pod vi phạm hết tất cả 5 luật cùng lúc — image latest, chạy root,
không khai resources, giữ đặc quyền. Bị chặn ngay, không cần check hết.

**pos-05, pos-06:** Deployment và CronJob viết đúng chuẩn thì vẫn deploy bình
thường. Không ảnh hưởng gì đến dev đang làm đúng.

---

## Tổng kết

19/19 test PASS trên cluster thật, namespace techx-tf1, chế độ Deny.

5 policy đang bảo vệ toàn cluster — Pod, Deployment, CronJob và các loại workload khác
đều bị kiểm tra ngay lúc apply. Dev viết đúng thì không bị ảnh hưởng. Dev viết sai
thì bị chặn và biết ngay lý do.

Chi phí triển khai thêm: 0 đồng, 0 pod phụ — chạy thẳng trong API Server có sẵn.
