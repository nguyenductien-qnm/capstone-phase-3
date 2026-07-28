resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.project_name}-${var.environment}-vpc"
    Environment = var.environment
    Project     = var.project_name
  }
}

# CKV2_AWS_12: AWS luôn tạo sẵn một default security group cho mỗi VPC, và mặc định nó
# cho phép mọi traffic giữa các resource cùng gắn nó. Không resource nào của mình dùng SG
# này, nhưng nó vẫn tồn tại — ai lỡ tạo ENI mà quên chỉ định SG thì rơi đúng vào đây.
# Khai resource này KHÔNG tạo SG mới: Terraform nhận adopt SG có sẵn rồi xoá sạch rule.
# Để trống ingress/egress nghĩa là chặn hết cả hai chiều.
resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name        = "${var.project_name}-${var.environment}-default-sg-locked"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name        = "${var.project_name}-${var.environment}-igw"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Public Subnets
resource "aws_subnet" "public" {
  for_each = var.public_subnets

  vpc_id                  = aws_vpc.this.id
  cidr_block              = each.value.cidr_block
  availability_zone       = each.value.availability_zone
  map_public_ip_on_launch = true

  tags = merge(
    {
      Name                     = "${var.project_name}-${var.environment}-public-${each.key}"
      Environment              = var.environment
      Project                  = var.project_name
      "kubernetes.io/role/elb" = "1"
    },
    var.public_subnet_tags
  )
}

# Private App Subnets
resource "aws_subnet" "private_app" {
  for_each = var.private_app_subnets

  vpc_id            = aws_vpc.this.id
  cidr_block        = each.value.cidr_block
  availability_zone = each.value.availability_zone

  tags = merge(
    {
      Name                              = "${var.project_name}-${var.environment}-private-app-${each.key}"
      Environment                       = var.environment
      Project                           = var.project_name
      "kubernetes.io/role/internal-elb" = "1"
    },
    var.private_subnet_tags,
    var.private_app_subnet_tags
  )
}

# Private Node Subnets (Karpenter) — dải /20 rộng để prefix delegation luôn xin
# được khối /28 liền mạch. Tách khỏi private_app có chủ đích:
#   - app /24 cũ ở lại phục vụ MNG, ALB/ENI hiện hữu (subnet_ids của MNG là hardcode,
#     không theo tag) — không đụng gì tới chúng;
#   - KHÔNG gắn kubernetes.io/role/internal-elb ở đây: ALB controller auto-discovery
#     yêu cầu mỗi AZ chỉ một subnet mang tag đó, app subnet đang giữ vai trò này.
resource "aws_subnet" "private_node" {
  for_each = var.private_node_subnets

  vpc_id            = aws_vpc.this.id
  cidr_block        = each.value.cidr_block
  availability_zone = each.value.availability_zone

  tags = merge(
    {
      Name        = "${var.project_name}-${var.environment}-private-node-${each.key}"
      Environment = var.environment
      Project     = var.project_name
    },
    var.private_subnet_tags,
    var.private_node_subnet_tags
  )
}

# Private Data Subnets
resource "aws_subnet" "private_data" {
  for_each = var.private_data_subnets

  vpc_id            = aws_vpc.this.id
  cidr_block        = each.value.cidr_block
  availability_zone = each.value.availability_zone

  tags = merge(
    {
      Name        = "${var.project_name}-${var.environment}-private-data-${each.key}"
      Environment = var.environment
      Project     = var.project_name
    },
    var.private_subnet_tags
  )
}

# Private MQ Subnets
resource "aws_subnet" "private_mq" {
  for_each = var.private_mq_subnets

  vpc_id            = aws_vpc.this.id
  cidr_block        = each.value.cidr_block
  availability_zone = each.value.availability_zone

  tags = merge(
    {
      Name        = "${var.project_name}-${var.environment}-private-mq-${each.key}"
      Environment = var.environment
      Project     = var.project_name
    },
    var.private_subnet_tags
  )
}

# NAT Gateways
resource "aws_eip" "nat" {
  for_each = local.nat_gateways
  domain   = "vpc"

  tags = {
    Name        = "${var.project_name}-${var.environment}-nat-eip-${each.key}"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_nat_gateway" "this" {
  for_each = local.nat_gateways

  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = aws_subnet.public[each.value.subnet_key].id

  tags = {
    Name        = "${var.project_name}-${var.environment}-nat-gw-${each.key}"
    Environment = var.environment
    Project     = var.project_name
  }

  depends_on = [aws_internet_gateway.this]
}

# Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name        = "${var.project_name}-${var.environment}-public-rt"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table" "private" {
  for_each = var.enable_nat_gateway ? (
    var.single_nat_gateway ? { "single" = {} } : { for az in local.public_azs : az => {} }
  ) : {}

  vpc_id = aws_vpc.this.id

  tags = {
    Name        = var.single_nat_gateway ? "${var.project_name}-${var.environment}-private-rt" : "${var.project_name}-${var.environment}-private-rt-${each.key}"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_route" "private_nat" {
  for_each = aws_route_table.private

  route_table_id         = each.value.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[each.key].id
}

resource "aws_route_table" "private_isolated" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name        = "${var.project_name}-${var.environment}-private-isolated-rt"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Route Table Associations
resource "aws_route_table_association" "public" {
  for_each = var.public_subnets

  subnet_id      = aws_subnet.public[each.key].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private_app" {
  for_each = var.private_app_subnets

  subnet_id = aws_subnet.private_app[each.key].id
  route_table_id = var.enable_nat_gateway ? (
    var.single_nat_gateway ? aws_route_table.private["single"].id : aws_route_table.private[each.value.availability_zone].id
  ) : aws_route_table.private_isolated.id
}

resource "aws_route_table_association" "private_node" {
  for_each = var.private_node_subnets

  # Invariant (giống private_app/private_mq bên dưới): khi single_nat_gateway=false,
  # route table private được key theo AZ của PUBLIC subnet — mỗi AZ có node subnet
  # phải có public subnet tương ứng, nếu không plan fail vì thiếu key.
  subnet_id = aws_subnet.private_node[each.key].id
  route_table_id = var.enable_nat_gateway ? (
    var.single_nat_gateway ? aws_route_table.private["single"].id : aws_route_table.private[each.value.availability_zone].id
  ) : aws_route_table.private_isolated.id
}

resource "aws_route_table_association" "private_mq" {
  for_each = var.private_mq_subnets

  subnet_id = aws_subnet.private_mq[each.key].id
  route_table_id = var.enable_nat_gateway ? (
    var.single_nat_gateway ? aws_route_table.private["single"].id : aws_route_table.private[each.value.availability_zone].id
  ) : aws_route_table.private_isolated.id
}

resource "aws_route_table_association" "private_data" {
  for_each = var.private_data_subnets

  subnet_id      = aws_subnet.private_data[each.key].id
  route_table_id = aws_route_table.private_isolated.id
}
