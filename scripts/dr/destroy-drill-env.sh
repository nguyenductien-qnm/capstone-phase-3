#!/usr/bin/env bash
# ==============================================================================
# Script dọn dẹp an toàn tài nguyên thử nghiệm DR Drill (MANDATE-20)
# ==============================================================================

set -euo pipefail

# Cấu hình màu sắc log
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO] $(date +'%Y-%m-%dT%H:%M:%S%z'): $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}[WARN] $(date +'%Y-%m-%dT%H:%M:%S%z'): $1${NC}"
}

log_error() {
    echo -e "${RED}[ERROR] $(date +'%Y-%m-%dT%H:%M:%S%z'): $1${NC}"
}

# 1. Định nghĩa Target DB cần dọn dẹp
# Cho phép truyền tham số DB Identifier, mặc định là ecommerce-develop-dev-postgres-drill-temp
DB_IDENTIFIER="${1:-ecommerce-develop-dev-postgres-drill-temp}"

log_info "Bắt đầu quy trình dọn dẹp môi trường DR Drill cho database: $DB_IDENTIFIER..."

# 2. KIỂM TRA AN TOÀN (SAFETY GUARD)
# Chỉ cho phép xóa DB instance nếu tên chứa hậu tố "-drill-temp"
if [[ ! "$DB_IDENTIFIER" =~ -drill-temp$ ]]; then
    log_error "CẢNH BÁO AN TOÀN: DB Identifier '$DB_IDENTIFIER' không chứa hậu tố '-drill-temp'."
    log_error "Tuyệt đối không thực thi xóa trên cơ sở dữ liệu Production hoặc Develop thật! Hủy bỏ tác vụ."
    exit 1
fi

# Kiểm tra sự tồn tại của database trên AWS
log_info "Đang kiểm tra sự tồn tại của database: $DB_IDENTIFIER..."
if ! aws rds describe-db-instances --db-instance-identifier "$DB_IDENTIFIER" >/dev/null 2>&1; then
    log_warn "Không tìm thấy DB Instance '$DB_IDENTIFIER'. Có thể tài nguyên đã được dọn dẹp trước đó."
    exit 0
fi

# 3. GỠ BỎ FLAGS DELETION PROTECTION
log_info "Đang kiểm tra Deletion Protection cho DB Instance: $DB_IDENTIFIER..."
PROTECTION_STATUS=$(aws rds describe-db-instances \
    --db-instance-identifier "$DB_IDENTIFIER" \
    --query "DBInstances[0].DeletionProtection" \
    --output text)

if [ "$PROTECTION_STATUS" = "True" ]; then
    log_info "Deletion Protection đang Bật. Tiến hành tắt Deletion Protection cho DB Instance: $DB_IDENTIFIER..."
    aws rds modify-db-instance \
        --db-instance-identifier "$DB_IDENTIFIER" \
        --no-deletion-protection \
        --apply-immediately > /dev/null

    log_info "Đang chờ DB cập nhật trạng thái gỡ bỏ bảo vệ..."
    # Chờ cho đến khi cờ DeletionProtection chuyển sang trạng thái False
    while true; do
        PROTECTION_STATUS=$(aws rds describe-db-instances \
            --db-instance-identifier "$DB_IDENTIFIER" \
            --query "DBInstances[0].DeletionProtection" \
            --output text)
        
        if [ "$PROTECTION_STATUS" = "False" ]; then
            log_info "Đã gỡ Deletion Protection thành công."
            break
        fi
        log_info "Đang chờ cập nhật Deletion Protection... (Thử lại sau 10 giây)"
        sleep 10
    done
else
    log_info "Deletion Protection đã tắt sẵn."
fi

# Chờ instance sẵn sàng để xóa (Available)
log_info "Đang chờ DB chuyển sang trạng thái Available để tiến hành xóa..."
aws rds wait db-instance-available --db-instance-identifier "$DB_IDENTIFIER"

# 4. TIẾN HÀNH XÓA DB INSTANCE (Bỏ qua Final Snapshot để tối ưu cost)
log_info "Đang thực hiện lệnh xóa DB Instance: $DB_IDENTIFIER..."
aws rds delete-db-instance \
    --db-instance-identifier "$DB_IDENTIFIER" \
    --skip-final-snapshot \
    --delete-automated-backups > /dev/null

log_info "Đang chờ DB xóa hoàn toàn khỏi hệ thống (Quá trình này có thể mất từ 5-10 phút)..."
aws rds wait db-instance-deleted --db-instance-identifier "$DB_IDENTIFIER"

log_info "Xác minh trạng thái dọn dẹp..."
if ! aws rds describe-db-instances --db-instance-identifier "$DB_IDENTIFIER" >/dev/null 2>&1; then
    log_info "Chúc mừng! DB Instance '$DB_IDENTIFIER' đã được xóa hoàn toàn và không còn phát sinh chi phí."
else
    log_error "Instance vẫn tồn tại. Vui lòng kiểm tra lại thủ công trên AWS Console."
    exit 1
fi
