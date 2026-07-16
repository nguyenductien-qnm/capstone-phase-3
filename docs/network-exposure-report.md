# Báo Cáo Phân Tích Giải Pháp: Bảo Mật Cổng Vận Hành
## Dự án: TechX Corp Platform - Capstone Phase 3
## Chủ đề: Giải quyết Directive #1 - Storefront công khai, cổng vận hành riêng tư

Báo cáo này phân tích các phương án (options) kỹ thuật để giải quyết yêu cầu từ Ban Hạ tầng & Bảo mật: **Chặn toàn bộ truy cập từ internet công cộng vào các công cụ vận hành (Grafana, Jaeger, ArgoCD)** nhưng **vẫn đảm bảo các thành viên trong team và Mentor có thể truy cập an toàn.**

---

## 1. Mục Tiêu & Ràng Buộc Kỹ Thuật

* **Mục tiêu:** 
  * Cổng Storefront (`http://<IP-hoặc-Domain>:8080/`): Luôn mở công khai, chạy ổn định.
  * Các cổng quản trị (`/grafana`, `/jaeger/ui`, `/argocd`): Chặn hoàn toàn từ Internet công cộng.
  * Chỉ những người có thẩm quyền (Team TF1, Mentor) có thể kết nối thông qua một đường truyền bảo mật (Tunnel / VPN / Mạng riêng).
* **Ràng buộc:** 
  * Không làm gián đoạn hệ thống storefront.
  * Nằm trong ngân sách hiện tại (~$300/tuần).
  * Hoàn thành trước **thứ Ba 13/07/2026**.

---

## 2. Phân Tích Các Giải Pháp Có Thể Triển Khai (Options)

### Option 1: AWS Systems Manager (SSM) Port-Forwarding (SSM Tunnel)
* **Cơ chế:** Cấu hình chặn các route Grafana/Jaeger tại Envoy Proxy (`frontend-proxy`). Lập trình viên sử dụng AWS CLI kết hợp plugin SSM Session Manager để tạo một đường ống chuyển tiếp cổng (Port-Forwarding) qua Worker Node EKS về máy cá nhân của mình.
* **Ưu điểm:**
  * **Cực kỳ bảo mật (Zero-Trust):** Không cần mở bất kỳ cổng inbound nào (kể cả cổng 22 SSH) trên máy chủ. Máy chủ có thể nằm hoàn toàn trong subnet riêng tư (Private Subnet).
  * **Không dùng Key `.pem`:** Xác thực hoàn toàn thông qua tài khoản AWS IAM cá nhân. Rất dễ tắt quyền truy cập khi có người rời dự án.
  * **Ghi vết tự động (Auditability):** Mọi hành động đăng nhập, gõ lệnh đều được AWS CloudTrail ghi lại chi tiết (ghi điểm cực tốt ở trụ cột Auditability).
  * **Chi phí:** Hoàn toàn miễn phí.
* **Nhược điểm:**
  * Lập trình viên và Mentor bắt buộc phải cài đặt **AWS CLI** và **Session Manager Plugin** trên máy tính cá nhân.
  * Yêu cầu phải cấp tài khoản AWS IAM (hoặc phân quyền tương ứng) cho Mentor để họ có thể chạy lệnh kết nối.

---

### Option 2: SSH Tunneling qua Bastion Host (Cầu nối EC2)
* **Cơ chế:** Tạo một máy ảo EC2 nhỏ (Bastion Host / Jumpbox) có IP công cộng nằm trong cùng VPC của EKS. Mở cổng `22` (SSH) trên máy ảo này. Lập trình viên dùng file Key Pair (`.pem`) thực hiện SSH Tunnel để chuyển tiếp các cổng Grafana/Jaeger về máy nội bộ.
* **Ưu điểm:**
  * Giải pháp truyền thống, quen thuộc với hầu hết các kỹ sư hệ thống.
  * Chỉ cần dùng các công cụ SSH tiêu chuẩn (như terminal của OS, Putty), không cần cài các plugin chuyên biệt của AWS.
* **Nhược điểm:**
  * **Rủi ro bảo mật:** Phải mở cổng `22` ra internet, tạo cơ hội cho kẻ xấu quét IP và dò mật khẩu.
  * **Quản lý khóa phức tạp:** Phải phân phát và quản lý file key `.pem`. Nếu file này bị lộ, toàn bộ hệ thống mạng nội bộ sẽ bị đe dọa.
  * **Cực kỳ phiền hà khi đổi IP:** Do lập trình viên làm việc tại nhà có IP thay đổi liên tục, nhóm CDO sẽ phải liên tục cập nhật Security Group để whitelist IP mới cho phép SSH.
  * **Tốn chi phí:** Phải trả tiền thuê thêm 1 con máy ảo EC2 chạy 24/7 làm Bastion Host.

---

### Option 3: Cloudflare Zero Trust Tunnel (cloudflared)
* **Cơ chế:** Cài đặt một con Agent (`cloudflared`) chạy dưới dạng một Pod trong cụm Kubernetes. Con agent này tự động kết nối ra ngoài tới hệ thống đám mây Cloudflare. Cấu hình định tuyến tên miền Grafana qua Cloudflare và thiết lập Cloudflare Access (bắt buộc đăng nhập bằng tài khoản Github/Google được chỉ định mới cho phép vào web).
* **Ưu điểm:**
  * **Trải nghiệm người dùng tuyệt vời:** Không cần cài đặt phần mềm gõ lệnh phức tạp dưới máy cá nhân. Mentor và team chỉ cần gõ địa chỉ web (ví dụ: `grafana.tf1-techx.com`), trình duyệt hiện bảng bắt đăng nhập Gmail/Github, đăng nhập đúng là vào thẳng giao diện web.
  * Độ bảo mật rất cao nhờ lớp xác thực danh tính tích hợp sẵn (Identity-Aware Proxy).
* **Nhược điểm:**
  * **Cấu hình rất phức tạp:** Đòi hỏi phải sở hữu một tên miền (Domain), thiết lập DNS, cài đặt Agent Helm Chart, cấu hình Zero Trust Dashboard trên Cloudflare.
  * Dễ xảy ra lỗi cấu hình mạng/định tuyến trong thời gian thi đấu ngắn ngủi (3 tuần), làm chậm tiến độ của các việc khác.

---

### Option 4: VPN (Tailscale hoặc AWS Client VPN)
* **Cơ chế:** Thiết lập một mạng ảo riêng tư (Virtual Private Network). 
  * *Nếu dùng Tailscale:* Cài Agent Tailscale làm subnet router trong cụm EKS. Mọi người cài app Tailscale trên máy để join vào chung mạng ảo.
  * *Nếu dùng AWS Client VPN:* Setup VPN Endpoint trên AWS để mọi người dùng OpenVPN kết nối vào.
* **Ưu điểm:**
  * Sau khi kết nối VPN, lập trình viên truy cập trực tiếp vào IP nội bộ của EKS giống như đang ngồi trực tiếp tại văn phòng. Rất mượt mà và tiện lợi.
* **Nhược điểm:**
  * AWS Client VPN cấu hình phức tạp và có **chi phí khá đắt** (ít nhất ~$30 - $50/tháng trở lên cho endpoint và phí duy trì kết nối), dễ làm thâm hụt ngân sách của TF.
  * Tailscale cấu hình đơn giản hơn nhưng vẫn yêu cầu cài đặt phần mềm Client và quản lý khóa thiết bị trên bảng điều khiển Tailscale.

---

## 3. Bảng So Sánh & Đánh Đổi (Trade-off Matrix)

| Tiêu chí so sánh | Option 1: SSM Tunnel | Option 2: SSH Bastion | Option 3: Cloudflare Tunnel | Option 4: VPN (Tailscale) |
|---|---|---|---|---|
| **Độ Bảo Mật (Security)** | **Cực Kỳ Cao (Zero Trust)** | Trung Bình (Lộ cổng 22, lộ Key) | Rất Cao (OAuth tích hợp) | Cao |
| **Chi Phí (Cost)** | **$0 (Miễn phí)** | Tốn phí thuê EC2 Bastion | $0 (Gói free của CF) | Tốn phí (AWS) hoặc $0 (Tailscale) |
| **Ghi Vết (Auditability)** | **Rất Tốt** (Log CloudTrail) | Kém | Tốt (Log Cloudflare Access) | Trung bình |
| **Độ Khó Cấu Hình** | **Dễ / Trung Bình** | Dễ | Rất Khó / Phức tạp | Trung bình |
| **Trải Nghiệm Mentor** | Phải cài CLI + AWS credentials | Chỉ cần file `.pem` và SSH | **Cực tốt** (Chỉ cần đăng nhập web) | Phải cài VPN Client |

---

## 4. Khuyến Nghị Lựa Chọn (Final Recommendation)

> [!IMPORTANT]
> **ĐỀ XUẤT CHỌN: OPTION 1 - AWS SSM PORT-FORWARDING (SSM TUNNEL)**
> Đây là phương án dung hòa tốt nhất giữa **Bảo mật (Security)**, **Chi phí (Cost)**, và **Độ khả thi trong thời gian ngắn (3 tuần)**.
>
> * **Tại sao chọn SSM Tunnel?**
>   1. Đóng hoàn toàn các cổng kết nối từ ngoài internet, đáp ứng hoàn hảo tiêu chí "Security Hardening" của Directive #1.
>   2. Tận dụng cơ chế phân quyền AWS IAM sẵn có của cụm AWS EKS, không phát sinh thêm chi phí hạ tầng.
>   3. Tự động ghi lại nhật ký kết nối trên CloudTrail, giúp team lấy trọn vẹn điểm ở trụ cột **Auditability**.
> * **Giải pháp cho trải nghiệm của Mentor:** Để Mentor dễ dàng chấm điểm, team sẽ chuẩn bị một tài khoản AWS IAM có quyền truy cập tối thiểu (Read-Only + SSM Session Manager) kèm theo một file script cấu hình tự động (shell script hoặc batch script). Mentor chỉ cần chạy file script này là tự động mở cổng Grafana/Jaeger/ArgoCD lên trình duyệt mà không cần nhớ các câu lệnh AWS CLI phức tạp.

---

## 5. Kế Hoạch Triển Khai Kỹ Thuật (SSM Tunnel)

### Bước 1: CDO Cấu hình hạ tầng EKS (AWS IAM)
1. Thêm IAM Policy `AmazonSSMManagedInstanceCore` vào IAM Role của EKS Worker Node (NodeInstanceRole). Lớp Agent SSM trên Worker Node sẽ tự động kích hoạt kết nối lên AWS Systems Manager.
2. Cấu hình Envoy Proxy (`frontend-proxy`) để loại bỏ các route trỏ tới `/grafana`, `/jaeger/ui`, `/argocd` từ cổng Public IP công cộng.

### Bước 2: Tạo IAM Policy cho Mentor & Team truy cập
Tạo một IAM Policy tối giản có tên là `SSMTunnelAccess` và gán cho các tài khoản của thành viên và Mentor:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:StartSession"
            ],
            "Resource": [
                "arn:aws:ec2:*:*:instance/i-*",
                "arn:aws:ssm:*:*:document/AWS-StartPortForwardingSessionToRemoteHost"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances"
            ],
            "Resource": "*"
        }
    ]
}
```

### Bước 3: Viết script tự động cho người dùng cuối (Local Script)
Tạo file script `connect-grafana.sh` (hoặc `.bat` cho Windows) để mọi người chỉ cần click đúp là kết nối được:
```bash
#!/bin/bash
# Script tự động kết nối Grafana nội bộ EKS qua AWS SSM
INSTANCE_ID="<INSTANCE_ID_WORKER_NODE>"
GRAFANA_IP="172.20.10.5" # IP nội bộ của service Grafana trong K8s

echo "Đang thiết lập kết nối an toàn tới Grafana..."
aws ssm start-session \
    --target $INSTANCE_ID \
    --document-name AWS-StartPortForwardingSessionToRemoteHost \
    --parameters "{\"portNumber\":[\"3000\"],\"localPortNumber\":[\"3000\"],\"host\":[\"$GRAFANA_IP\"]}"
```

---
*Tài liệu được soạn thảo bởi Châu Thành Trung - Team TF1.*
