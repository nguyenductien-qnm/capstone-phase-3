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
      Name        = "${var.project_name}-${var.environment}-public-${each.key}"
      Environment = var.environment
      Project     = var.project_name
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
      Name        = "${var.project_name}-${var.environment}-private-app-${each.key}"
      Environment = var.environment
      Project     = var.project_name
    },
    var.private_subnet_tags
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
