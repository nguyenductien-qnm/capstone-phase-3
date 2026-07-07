# 📖 Terraform Standard Rulebook & Best Practices

> **Dành cho AI Agents và Human Developers**
> Tài liệu này thiết lập các nguyên tắc cốt lõi khi phát triển mã nguồn Infrastructure as Code (IaC) sử dụng Terraform trong toàn bộ hệ thống Triage Hub. Bất kỳ dòng code nào được sinh ra bởi con người hay AI đều **PHẢI** tuân thủ nghiêm ngặt các quy tắc dưới đây.

---

## 🤖 Phần 0: Lệnh hệ thống cho AI Agent (System Prompt)

_Nếu bạn là một AI Code Assistant / Agent đang đọc file này, bạn được lập trình để tuân thủ các quy định sau:_

1. **KHÔNG** đề xuất sử dụng `count` trừ khi là cấu trúc bật/tắt (toggle). Luôn sử dụng `for_each`.
2. **KHÔNG** hardcode AWS Account ID, Region hay Partition. Phải dùng `data.aws_caller_identity`, `data.aws_region`, `data.aws_partition`.
3. **KHÔNG** đặt giá trị `default` cho các `variable` phụ thuộc vào môi trường (environment-specific).
4. **BẮT BUỘC** viết `validation` block cho các variable có tính chất enum hoặc theo định dạng cố định (như CIDR, Tên miền).
5. **BẮT BUỘC** tách logic phức tạp ra file `locals.tf` thay vì viết inline trực tiếp vào resource.
6. Khi cấu hình `ingress` hoặc `egress` cho Security Group, **PHẢI** yêu cầu thuộc tính `description` để giải thích lý do mở cổng. Không mở `0.0.0.0/0` ngoại trừ ALB hướng public.
7. **BẮT BUỘC** áp dụng `lifecycle { ignore_changes = [...] }` cho các tài nguyên có thể bị sửa đổi bởi Auto-Scaling hoặc tiến trình bên ngoài (ví dụ: `desired_count` của ECS, AMI của EC2/Launch Template).

---

## 🏗️ Phần 1: Kiến trúc & Quản lý State (Architecture & State)

### 1. Phân chia rõ ràng Module và Environment

Hệ thống sử dụng mô hình **Root Environment & Reusable Modules**:

- `modules/`: Chứa các module tái sử dụng được (không chứa thông tin môi trường cụ thể, không cấu hình provider backend).
- `environments/<env>/`: Là "Root Module" đại diện cho từng môi trường (dev, staging, prod). Gọi các module ở thư mục trên và truyền tham số cụ thể vào qua `terraform.tfvars`.

### 2. File State & Lock Database

- Mọi environment phải lưu trữ State từ xa (Remote State Backend) bằng S3 Bucket (có mã hóa KMS, phiên bản hóa - versioning) và khóa trạng thái (State Locking) bằng DynamoDB.
- KHÔNG sử dụng local state cho bất kỳ môi trường chia sẻ nào.
- Tránh dùng Terraform Workspace cho Dev/Staging/Prod. Tách riêng thư mục `environments/<env>` mang lại sự cô lập hoàn toàn về Code và State an toàn hơn rất nhiều.

### 3. Tiêu chuẩn 3 file cho một Module

Mọi module **bắt buộc** phải có ít nhất 3 tệp tin tiêu chuẩn:

- `main.tf`: Định nghĩa tài nguyên (Resources, Data sources).
- `variables.tf`: Định nghĩa input (Có mô tả rõ ràng, kèm validation).
- `outputs.tf`: Định nghĩa kết quả trả về để các module khác có thể kế thừa (Ví dụ: ID, ARN).

---

## 💻 Phần 2: Code Styling & Quy ước đặt tên (Naming Conventions)

### 1. Chuẩn mực đặt tên Resource

- Dùng `snake_case` cho tất cả các tên file, module, resource, variable và output.
- Chỉ đặt tên singleton resource là `"this"`. (Ví dụ: `aws_vpc.this`). KHÔNG đặt theo tên service (ví dụ: `aws_vpc.main_vpc` là sai, `aws_vpc.this` là đúng).
- Nếu có nhiều instance khác loại của cùng một resource, đặt tên mô tả mục đích (Ví dụ: `aws_subnet.public`, `aws_subnet.private`).

### 2. Định dạng mã nguồn (Formatting)

- Code bắt buộc phải được pass qua lệnh `terraform fmt -recursive`.
- Căn chỉnh dấu bằng (`=`) trong block để code dễ đọc.

---

## 🔄 Phần 3: Quản lý Resource (Resource Provisioning)

### 1. Sử dụng `for_each` thay cho `count`

Dùng `count` khiến Terraform định danh resource bằng _Index_ (0, 1, 2). Khi thêm/xóa phần tử ở giữa danh sách, toàn bộ resource phía sau sẽ bị destroy & recreate.
**Luôn sử dụng `for_each` (dựa trên key dạng chuỗi) cho các tập hợp (collections).**

```hcl
# ❌ BAD: Dùng count
resource "aws_subnet" "public" {
  count      = length(var.public_subnets)
  cidr_block = var.public_subnets[count.index]
}

# ✅ GOOD: Dùng for_each với map/object
resource "aws_subnet" "public" {
  for_each   = var.public_subnets
  cidr_block = each.value.cidr_block

  tags = {
    Name = "${var.project_name}-${each.key}"
  }
}
```

### 2. Tách logic phức tạp vào `locals`

Không sử dụng các hàm phức tạp (như map, filter) trực tiếp vào thuộc tính của resource. Khai báo chúng ở `locals` để code dễ đọc và dễ debug.

```hcl
# ❌ BAD: Viết logic filter inline
resource "aws_iam_role_policy_attachment" "vpc_execution" {
  for_each   = { for k, v in var.lambdas : k => v if v.vpc_subnet_ids != null }
  # ...
}

# ✅ GOOD: Tách riêng ra locals
locals {
  lambdas_in_vpc = {
    for k, v in var.lambdas : k => v if v.vpc_subnet_ids != null
  }
}

resource "aws_iam_role_policy_attachment" "vpc_execution" {
  for_each = local.lambdas_in_vpc
}
```

### 3. Vòng đời Tài Nguyên (Lifecycle Block)

Sử dụng `ignore_changes` cho các giá trị mà Terraform không nên ghi đè khi chạy lại plan/apply.

```hcl
resource "aws_ecs_service" "this" {
  lifecycle {
    ignore_changes = [desired_count, task_definition] # Tránh conflict với Application Auto Scaling hoặc CI/CD
  }
}
```

---

## 🔐 Phần 4: Input Variables & Validation

### 1. KHÔNG đặt `default` cho các biến phụ thuộc môi trường

Các tham số như CIDR, instance type, max/min size... khác nhau giữa Dev và Prod. Việc đặt `default` trong `variables.tf` sẽ khiến chúng ta lỡ tay tạo nhầm hạ tầng nếu quên khai báo trong `.tfvars`.
=> Hãy ép người vận hành BẮT BUỘC phải gán giá trị tại `terraform.tfvars`.

### 2. Bắt buộc có Validation Block

Mọi Input giới hạn giá trị hoặc định dạng phải được validation.

```hcl
# Ví dụ Validation CIDR và Enum
variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR"
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "Giá trị phải là một dải CIDR hợp lệ (vd: 10.0.0.0/16)."
  }
}

variable "environment" {
  type        = string
  description = "Tên môi trường triển khai"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Môi trường phải thuộc tập [dev, staging, prod]."
  }
}
```

### 3. Dùng Kiểu dữ liệu phức hợp (Typed Objects) thay cho List/String

Tránh dùng `list(string)` nếu các phần tử mang ý nghĩa khác biệt. Sử dụng `map(object({}))`.

---

## 🛡️ Phần 5: Bảo mật (Security & IAM)

### 1. Nguyên tắc Least Privilege & Tách Role

- KHÔNG gán policy `AdministratorAccess`.
- Phân biệt rõ `task_role_arn` (quyền cho ứng dụng gọi AWS API - VD: S3, DynamoDB) và `execution_role_arn` (quyền cho ECS Agent kéo Image từ ECR và ghi log CloudWatch). KHÔNG dùng chung 1 Role.

### 2. Không cấu hình Security Group mở toàn mạng (`0.0.0.0/0`)

Trừ khi ứng dụng trực tiếp hứng Public Traffic từ Internet qua Application Load Balancer.
Bất kỳ Ingress/Egress Rule nào cũng PHẢI có `description` ghi rõ lý do bảo mật.
Đặc biệt đối với SSH (port 22), hãy dùng **AWS Systems Manager (SSM) Session Manager** thay vì mở port 22 công khai.

```hcl
variable "ingress_rules" {
  type = list(object({
    from_port   = number
    to_port     = number
    protocol    = string
    cidr_blocks = list(string)
    description = string # BẮT BUỘC
  }))

  validation {
    condition = alltrue([for rule in var.ingress_rules : rule.description != null && rule.description != ""])
    error_message = "Toàn bộ Security Group Ingress Rules phải có description rõ ràng."
  }
}
```

### 3. Không lưu Hardcoded Secrets

Bất kỳ thông tin xác thực nào (Password, API Token) phải được tạo động qua tệp Terraform (như `random_password`) hoặc AWS Secrets Manager.

```hcl
# Báo lỗi nếu gõ mật khẩu thẳng vào code
resource "aws_db_instance" "this" {
  password = random_password.master.result
}
```

---

## 🌍 Phần 6: Data Sources & AWS Best Practices

### 1. Không bao giờ Hardcode ID, hãy dùng Data Sources

Tránh việc gõ cứng AMI ID (`ami-0c55b159cbfafe1f0`), thay vào đó sử dụng `data "aws_ami"`.
Tránh gõ cứng AWS Region (`us-east-1`), thay vào đó sử dụng `data.aws_region.current.name`.

### 2. Tận dụng `default_tags` tại Provider

Tránh rải rác tag thủ công. Bật tính năng `default_tags` của Terraform AWS Provider để đảm bảo mọi resource đều có các nhãn quản lý chuẩn xác.

```hcl
provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "CDO-09"
    }
  }
}
```

### 3. Loại bỏ Hardcoded Region, Account ID, Partition

Sử dụng các nguồn dữ liệu thay thế để module có thể chạy tốt trên GovCloud, China Region, hay chạy sang region khác mà không phải sửa lại code.

- Region: `data.aws_region.current.name`
- Partition: `data.aws_partition.current.partition`
- Account ID: `data.aws_caller_identity.current.account_id`

### 4. Bảo vệ các Stateful Resource

Các Database, S3 Bucket tại môi trường Prod cần bật `lifecycle { prevent_destroy = true }` để tránh việc vô tình chạy lệnh destroy làm bốc hơi toàn bộ dữ liệu. `force_destroy` của S3 chỉ nên áp dụng trên môi trường Dev/Test.

---

## ✅ Phần 7: Checklist CI/CD (Pre-Commit)

Để đảm bảo chất lượng, Developer hoặc AI Agent cần vượt qua:

- [ ] Code đã được định dạng (`terraform fmt -recursive`).
- [ ] Lệnh `terraform validate` chạy thành công.
- [ ] Modules mới đã bao gồm tệp `outputs.tf` cho các tài nguyên chính yếu (ARN, ID).
- [ ] Không có Warning nào liên quan tới Versioning hay Cú pháp hỏng.
- [ ] Mọi Input mới đều có `description` và `validation`.
- [ ] Kiểm tra tĩnh bảo mật (khuyến khích local dùng tfsec hoặc checkov).
- [ ] Module không dùng hardcode (`count`, `region`, `AMI IDs`, `0.0.0.0/0`).
