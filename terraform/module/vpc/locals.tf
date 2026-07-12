locals {
  # Lấy danh sách các AZs duy nhất từ public subnets
  public_azs = distinct([for s in var.public_subnets : s.availability_zone])

  # Xác định NAT Gateway nào cần tạo
  # Nếu single_nat_gateway = true, chỉ tạo 1 NAT Gateway (chọn key đầu tiên làm gateway)
  # Nếu single_nat_gateway = false, tạo 1 NAT Gateway cho mỗi AZ có public subnet
  nat_gateways = var.enable_nat_gateway ? (
    var.single_nat_gateway ? {
      "single" = {
        subnet_key = keys(var.public_subnets)[0]
        az         = var.public_subnets[keys(var.public_subnets)[0]].availability_zone
      }
      } : {
      for az in local.public_azs : az => {
        # Chọn public subnet đầu tiên trong AZ này để đặt NAT Gateway
        subnet_key = [for k, v in var.public_subnets : k if v.availability_zone == az][0]
        az         = az
      }
    }
  ) : {}
}
