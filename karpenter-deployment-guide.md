# Hướng Dẫn Triển Khai Karpenter Autoscaler Cho EKS

Tài liệu này hướng dẫn chi tiết các bước để cấu hình hạ tầng AWS (Terraform) và cài đặt Karpenter trên cụm EKS nhằm phục vụ tự động co giãn (autoscaling) tối ưu chi phí dưới tải lớn (Flash Sale).

---

## BƯỚC 1: Cấu Hình Hạ Tầng AWS (Terraform)

Karpenter cần các thẻ định danh (Discovery Tags) và các IAM Roles để có thể tự động cấp phát EC2 instance.

### A. Gắn Thẻ Định Danh (Discovery Tags) vào Subnet và Security Group
Karpenter dựa vào thẻ này để biết subnet nào được tạo Node và gán SG nào cho Node mới.

1. **Trong Module VPC (`terraform/modules/vpc/main.tf`):**
   Gắn tag vào các private subnets chạy ứng dụng:
   ```hcl
   resource "aws_subnet" "private_app" {
     # ... cấu hình subnet hiện tại ...

     tags = {
       Name                                                 = "${var.project_name}-${var.environment}-app-subnet-${each.key}"
       "kubernetes.io/role/internal-elb"                    = "1"
       "kubernetes.io/cluster/${var.project_name}-${var.environment}-cluster" = "shared"
       "karpenter.sh/discovery"                             = "${var.project_name}-${var.environment}-cluster" # [MỚI] Cho Karpenter nhận diện
     }
   }
   ```

2. **Trong Module EKS (`terraform/modules/eks/main.tf`):**
   Gắn tag cho EKS Security Group (để gán vào EC2 node mới):
   ```hcl
   resource "aws_security_group" "eks_nodes" {
     # ... cấu hình SG hiện tại ...

     tags = {
       Name                                      = "${var.project_name}-${var.environment}-node-sg"
       "karpenter.sh/discovery"                  = "${var.project_name}-${var.environment}-cluster" # [MỚI] Cho Karpenter nhận diện
     }
   }
   ```

### B. Tạo IAM Roles và Instance Profile
1. **Karpenter Node Role & Instance Profile:** Cho các EC2 instance do Karpenter tạo ra để đăng ký vào EKS Cluster.
   ```hcl
   # IAM Role cho EC2 Node
   resource "aws_iam_role" "karpenter_node" {
     name = "${var.project_name}-${var.environment}-karpenter-node-role"

     assume_role_policy = jsonencode({
       Version = "2012-10-17"
       Statement = [{
         Action    = "sts:AssumeRole"
         Effect    = "Allow"
         Principal = { Service = "ec2.amazonaws.com" }
       }]
     })
   }

   # Gán các policy cần thiết
   resource "aws_iam_role_policy_attachment" "karpenter_node_policies" {
     for_each = toset([
       "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
       "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
       "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPullOnly",
       "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
     ])
     role       = aws_iam_role.karpenter_node.name
     policy_arn = each.value
   }
   ```

2. **Karpenter Controller IAM Role (IRSA):** Cho phép Karpenter Controller (chạy dưới dạng Pod) gọi API EC2 tạo/xóa server.
   Sử dụng Module IAM EKS OIDC để tạo IRSA Role với Trust Policy ánh xạ tới ServiceAccount `karpenter` trong namespace `karpenter`.

3. **EKS Access Entry cho Node Role:**
   Cho phép các node do Karpenter tạo đăng ký thành công vào EKS Cluster (EKS 1.30 trở lên):
   ```hcl
   resource "aws_eks_access_entry" "karpenter_node" {
     cluster_name  = aws_eks_cluster.this.name
     principal_arn = aws_iam_role.karpenter_node.arn
     type          = "EC2_LINUX"
   }
   ```

---

## BƯỚC 2: Cài Đặt Karpenter Controller (Kubernetes)

Sau khi hạ tầng sẵn sàng, tiến hành cài đặt Karpenter qua Helm.

1. **Thêm Helm Repo & Cài Đặt:**
   ```bash
   helm repo add karpenter https://charts.karpenter.sh/
   helm repo update

   helm upgrade --install karpenter oci://public.ecr.aws/karpenter/karpenter \
     --namespace karpenter --create-namespace \
     --version "0.37.0" \
     --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=<ARN_ROLE_KARTPENTER_CONTROLLER> \
     --set settings.clusterName=ecommerce-dev-cluster \
     --set settings.interclusterQueueUrl=<SQS_QUEUE_URL_NẾU_CÓ> \
     --wait
   ```

---

## BƯỚC 3: Cấu Hình EC2NodeClass và NodePool (YAML)

Tạo file [karpenter-config.yaml](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/platform/karpenter-config.yaml) để khai báo các luật co giãn.

### A. Định nghĩa EC2NodeClass (Cấu hình EC2)
```yaml
apiVersion: karpenter.k8s.aws/v1beta1
kind: EC2NodeClass
metadata:
  name: default
spec:
  amiFamily: AL2 # Hoặc Bottlerocket
  role: ecommerce-dev-karpenter-node-role # IAM Role đã tạo ở Bước 1
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: ecommerce-dev-cluster
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: ecommerce-dev-cluster
  tags:
    Name: ecommerce-dev-karpenter-node
    Environment: dev
```

### B. Định nghĩa NodePool (Chính sách chọn Instance & Tiết kiệm cost)
Cấu hình tối ưu ưu tiên **Spot Instances** để tối ưu hóa ngân sách đợt Flash Sale.
```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      requirements:
        # Ưu tiên chạy node giá rẻ Spot, tự động fallback sang On-Demand nếu thiếu Spot
        - key: "karpenter.sh/capacity-type"
          operator: In
          values: ["spot", "on-demand"]
        # Chỉ định nghĩa các loại instance phù hợp túi tiền dev sandbox
        - key: "node.kubernetes.io/instance-type"
          operator: In
          values: ["t3.medium", "t3.large", "c6i.large"]
        - key: "kubernetes.io/arch"
          operator: In
          values: ["amd64"]
      nodeClassRef:
        name: default
  # Co lại (dọn dẹp node thừa) để tiết kiệm tiền ngay khi tải giảm
  disruption:
    consolidationPolicy: WhenUnderutilized
    expireAfter: 720h # Tự động xóa node sau 30 ngày
```

---

## BƯỚC 4: Chuẩn Bị Ứng Dụng Chạy Tải (Workload Optimization)

Để kiểm thử được luồng scale hoạt động tốt:

1. **Chuẩn hóa Request/Limit cho các Pod:**
   Karpenter chỉ biết tạo node mới khi phát hiện Pod bị `Pending` do thiếu tài nguyên `request`. Cần cấu hình cụ thể trong Helm [values.yaml](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/platform/charts/application/values.yaml):
   ```yaml
   checkout:
     resources:
       requests:
         cpu: 100m
         memory: 128Mi
       limits:
         memory: 256Mi # Nâng giới hạn RAM lên để tránh OOMKilled lúc tải cao
   ```

2. **Cấu hình HPA (Horizontal Pod Autoscaler):**
   Tạo HPA cho các service chịu tải trực tiếp như `checkout`, `product-catalog`:
   ```yaml
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   metadata:
     name: checkout-hpa
     namespace: default
   spec:
     scaleTargetRef:
       apiVersion: apps/v1
       kind: Deployment
       name: checkout
     minReplicas: 1
     maxReplicas: 10
     metrics:
       - type: Resource
         resource:
           name: cpu
           target:
             type: Utilization
             averageUtilization: 60
   ```

---

## BƯỚC 5: Kiểm Thử Co Giãn (Load Test Verification)

Tiến hành chạy Locust tăng dần số lượng CCU lên 200 để quan sát hành vi tự động scale:

1. Tải tăng $\rightarrow$ CPU của các pod tăng vượt quá 60% mức sử dụng trung bình.
2. HPA kích hoạt $\rightarrow$ Tạo thêm replicas mới (lên tới 10 pod).
3. EKS Node Group ban đầu (bootstrap) bị hết chỗ $\rightarrow$ Các pod mới sinh rơi vào trạng thái `Pending`.
4. Karpenter phát hiện Pod `Pending` $\rightarrow$ Tự động tính toán tổng tài nguyên và sinh thêm node EC2 (VD: cụm có thêm 1 node Spot `t3.medium`).
5. Khi kết thúc load test $\rightarrow$ Pod scale co xuống $\rightarrow$ Node trống $\rightarrow$ Karpenter kích hoạt `consolidation` và tự động tắt node trên AWS.
