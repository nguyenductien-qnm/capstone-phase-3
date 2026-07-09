# TF1-54 [AIE-Reliability] - Valkey Cart Offline Cleanup Script
# Script nay duoc chay qua CronJob vao 2h sang hang ngay de thuc hien Garbage Collection (GC)
# doi voi cac gio hang khong co hoat dong (idle) tren 30 ngay, tranh ro ri bo nho.

import os
import sys
import time
import logging
import redis

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("valkey-cleanup")

# Doc cau hinh tu bien moi truong
VALKEY_HOST = os.environ.get("VALKEY_HOST", "valkey-cart")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", 6379))
IDLE_THRESHOLD_SECONDS = int(os.environ.get("IDLE_THRESHOLD_SECONDS", 30 * 24 * 3600))  # Mặc định 30 ngày
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

def main():
    log.info(f"Bat dau quet don Valkey tai {VALKEY_HOST}:{VALKEY_PORT}")
    log.info(f"Nguong thoi gian idle: {IDLE_THRESHOLD_SECONDS} giay (~{IDLE_THRESHOLD_SECONDS // 86400} ngay)")
    if DRY_RUN:
        log.info("Che do DRY_RUN dang bat. Khong thuc hien xoa that.")

    try:
        # Ket noi toi Valkey/Redis
        r = redis.Redis(host=VALKEY_HOST, port=VALKEY_PORT, socket_timeout=5)
        
        cursor = 0
        total_scanned = 0
        total_deleted = 0
        
        while True:
            # Dung SCAN de khong lam block server dang chay (tranh thundering herd / high CPU)
            cursor, keys = r.scan(cursor=cursor, count=100)
            
            for key in keys:
                key_str = key.decode('utf-8')
                total_scanned += 1
                
                # Chi xu ly gio hang (bo qua cache review va cac key he thong khac co prefix reviews:)
                if key_str.startswith("reviews:"):
                    continue
                
                try:
                    # Lay thoi gian idle cua key (giay)
                    idle_time = r.object("idletime", key)
                    
                    if idle_time is not None and idle_time > IDLE_THRESHOLD_SECONDS:
                        log.info(f"Phat hien gio hang idle: {key_str} (Idle: {idle_time}s)")
                        if not DRY_RUN:
                            r.delete(key)
                            total_deleted += 1
                            log.info(f"Da xoa gio hang: {key_str}")
                except Exception as e:
                    log.error(f"Loi khi xu ly key {key_str}: {e}")
                    
            if cursor == 0:
                break
                
        log.info(f"Hoan thanh GC. Quet: {total_scanned} keys, Xoa: {total_deleted} gio hang idle.")
        
    except Exception as e:
        log.error(f"Loi ket noi hoac thuc thi tren Valkey: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
