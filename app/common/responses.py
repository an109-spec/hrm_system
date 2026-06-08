from __future__ import annotations

from http import HTTPStatus
from typing import Any

from flask import jsonify


def swal_payload(
    icon: str,
    title: str,
    message: str = "",
    data: Any = None,
    *,
    success: bool | None = None,
    include_data: bool = False,
) -> dict[str, Any]:
    """Build a SweetAlert2-compatible payload without converting to JSON."""
    payload: dict[str, Any] = {
        "swal": {
            "icon": icon,
            "title": title,
            "text": message,
        }
    }
    if success is not None:
        payload["success"] = success
    if data is not None or include_data:
        payload["data"] = data if data is not None else {}
    return payload


def swal_response(
    icon: str,
    title: str,
    message: str = "",
    data: Any = None,
    *,
    status_code: int = HTTPStatus.OK,
    success: bool | None = None,
):
    """Return a Flask JSON response tuple using the shared SweetAlert2 shape."""
    return jsonify(
        swal_payload(
            icon=icon,
            title=title,
            message=message,
            data=data,
            success=success,
        )
    ), status_code


def swal_success(title: str = "Thành công", message: str = "", data: Any = None, status_code: int = HTTPStatus.OK):
    return swal_response("success", title, message, data, status_code=status_code, success=True)


def swal_error(title: str = "Lỗi", message: str = "Đã xảy ra lỗi, vui lòng thử lại.", status_code: int = HTTPStatus.BAD_REQUEST):
    return swal_response("error", title, message, status_code=status_code, success=False)


def swal_warning(title: str = "Cảnh báo", message: str = "", status_code: int = HTTPStatus.BAD_REQUEST):
    return swal_response("warning", title, message, status_code=status_code, success=False)


def swal_info(title: str = "Thông tin", message: str = "", data: Any = None, status_code: int = HTTPStatus.OK):
    return swal_response("info", title, message, data, status_code=status_code)


def payroll_success_payload(message: str, data: Any = None, title: str = "Thành công") -> dict[str, Any]:
    return swal_payload("success", title, message, data, include_data=True)


def payroll_error_payload(message: str, title: str = "Lỗi") -> dict[str, Any]:
    return swal_payload("error", title, message, None)


def payroll_warning_payload(message: str, data: Any = None, title: str = "Cảnh báo") -> dict[str, Any]:
    return swal_payload("warning", title, message, data, include_data=True)


def payroll_info_payload(message: str, data: Any = None, title: str = "Thông tin") -> dict[str, Any]:
    return swal_payload("info", title, message, data, include_data=True)


def flat_swal_response(icon: str, title: str, message: str = "", data: Any = None, *, status_code: int = HTTPStatus.OK):
    """Legacy flat response shape used by notification endpoints."""
    payload: dict[str, Any] = {"icon": icon, "title": title, "text": message}
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status_code


def flat_swal_success(title: str, message: str = "", data: Any = None, status_code: int = HTTPStatus.OK):
    return flat_swal_response("success", title, message, data, status_code=status_code)


def flat_swal_error(title: str, message: str = "", status_code: int = HTTPStatus.BAD_REQUEST):
    return flat_swal_response("error", title, message, status_code=status_code)


def flat_swal_info(title: str, message: str = "", data: Any = None, status_code: int = HTTPStatus.OK):
    return flat_swal_response("info", title, message, data, status_code=status_code)