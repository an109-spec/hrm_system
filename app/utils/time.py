from datetime import datetime, timedelta, timezone
import os

# Đường dẫn file để lưu độ chênh lệch thời gian giữa thực tế và demo
OFFSET_FILE = "time_offset.txt"

def get_offset():
    """Đọc số giây chênh lệch từ file"""
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE, "r") as f:
            try: return float(f.read().strip())
            except: return 0
    return 0

def set_offset(new_sim_time_dt):
    """Tính toán và lưu độ lệch mới khi bạn xoay đồng hồ demo"""
    real_now = datetime.now()
    # Lấy thời gian bạn muốn demo TRỪ ĐI thời gian thực của máy tính
    offset = (new_sim_time_dt - real_now).total_seconds()
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))

def reset_offset():
    """Xóa file offset để quay về thời gian thực"""
    if os.path.exists(OFFSET_FILE):
        os.remove(OFFSET_FILE)

def utcnow():
    """Thay thế hàm cũ: Giờ hệ thống = Giờ thực + Độ lệch demo"""
    offset = get_offset()
    sim_now = datetime.now() + timedelta(seconds=offset)
    return sim_now.replace(tzinfo=None) # Trả về naive để khớp DB của bạn