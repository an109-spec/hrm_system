class AppException(Exception):
    """Base exception cho toàn hệ thống"""
    status_code = 400
    message = "Application error"

    def __init__(self, message=None, status_code=None, payload=None):
        self.message = message if message is not None else self.message
        self.status_code = status_code if status_code is not None else self.status_code
        self.payload = payload # Thêm payload để gửi kèm chi tiết lỗi (ví dụ: lỗi ở field nào)
        super().__init__(self.message)

    def to_dict(self):
        """Hàm helper để chuyển lỗi thành Dictionary (trả về JSON cho API)"""
        rv = dict(self.payload or ())
        rv['message'] = self.message
        rv['status_code'] = self.status_code
        return rv

class ValidationError(AppException):
    status_code = 422
    message = "Dữ liệu không hợp lệ"

class UnauthorizedError(AppException):
    status_code = 401
    message = "Vui lòng đăng nhập"

    def __init__(self, message=None, locked_until=None):
        payload = {'locked_until': locked_until} if locked_until else None
        super().__init__(message=message, status_code=self.status_code, payload=payload)

class ForbiddenError(AppException):
    status_code = 403
    message = "Bạn không có quyền thực hiện hành động này"

class NotFoundError(AppException):
    status_code = 404
    message = "Không tìm thấy thông tin yêu cầu"

class ConflictError(AppException):
    status_code = 409
    message = "Dữ liệu đã tồn tại hoặc bị xung đột"

class TooManyRequestsError(AppException):
    status_code = 429
    message = "Thao tác quá nhanh, vui lòng đợi"