from app.constants import STATUS_BADGE_CONFIG
# ✅ Thay vì import ENUM_LABELS, ta import các class đang có sẵn trong file constants của ông
from app.constants.employee import WorkingStatus, EmploymentType, GenderType

# ✅ Tự định nghĩa ENUM_LABELS cục bộ ngay tại đây để phục vụ hàm labelize_enum
ENUM_LABELS = {
    "working_status": WorkingStatus.LABELS,
    "employment_type": EmploymentType.LABELS,
    "gender": GenderType.LABELS
}

def get_status_badge(status: str) -> dict:
    """Trả về dictionary chứa class CSS và Icon cho Badge"""
    status_key = (status or "").strip().lower()
    
    default = {
        "icon": "bi-info-circle", 
        "label": status_key.replace("_", " ").capitalize() if status_key else "Không xác định", 
        "class": "bg-light text-dark"
    }
    
    return STATUS_BADGE_CONFIG.get(status_key, default)

def format_minutes_to_string(total_minutes: int) -> str:
    """Chuyển 75 thành '1 giờ 15 phút'"""
    if not total_minutes or total_minutes <= 0: 
        return "0 phút"
        
    hours, minutes = divmod(total_minutes, 60)
    parts = []
    if hours > 0: parts.append(f"{hours} giờ")
    if minutes > 0: parts.append(f"{minutes} phút")
    
    return " ".join(parts)

def labelize_enum(value: str | None, category: str = None) -> str:
    """
    Chuyển đổi key của Enum thành nhãn tiếng Việt dễ đọc.
    Ví dụ: 'working' -> 'Đang làm việc'
    """
    if not value:
        return "Chưa cập nhật"
    
    val_str = str(value).strip()

    # 1. Nếu có chỉ định rõ category (Ví dụ: category='working_status')
    if category and category in ENUM_LABELS:
        return ENUM_LABELS[category].get(val_str, val_str)
    
    # 2. Nếu không chỉ định, tìm kiếm thông minh trong tất cả các nhóm
    for group in ENUM_LABELS.values():
        if val_str in group:
            return group[val_str]
            
    # 3. Cuối cùng nếu không thấy thì định dạng đẹp lại cái key
    return val_str.replace("_", " ").capitalize()