from __future__ import annotations

from http import HTTPStatus

from app.common.exceptions import AppException
from app.common.responses import swal_error, swal_warning


def app_exception_response(error: AppException):
    """Convert an AppException into the shared SweetAlert2 response format."""
    if error.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
        return swal_warning("Dữ liệu không hợp lệ", str(error), HTTPStatus.UNPROCESSABLE_ENTITY)
    return swal_error("Lỗi", str(error), error.status_code)


def internal_error_response(error: Exception):
    """Return a consistent response for unexpected errors."""
    return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {error}", HTTPStatus.INTERNAL_SERVER_ERROR)
