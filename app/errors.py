"""
app/errors.py
Đăng ký tất cả error handler cho Flask app.
"""
from flask import request, jsonify, redirect, url_for, flash

from app.common.exceptions import UnauthorizedError, ForbiddenError


def _is_api_request() -> bool:
    """True nếu request đến từ API (path bắt đầu /api/ hoặc Accept: json)."""
    return request.path.startswith("/api/") or \
           request.accept_mimetypes.best == "application/json"


def register_error_handlers(app):
    """Gắn toàn bộ error handler vào app."""

    @app.errorhandler(UnauthorizedError)
    def handle_unauthorized(e):
        if _is_api_request():
            return jsonify({
                "success": False,
                "icon":    "error",
                "title":   "Chưa xác thực",
                "text":    str(e) or "Vui lòng đăng nhập để tiếp tục.",
            }), 401
        flash("Vui lòng đăng nhập để tiếp tục.", "warning")
        return redirect(url_for("auth.login"))

    @app.errorhandler(ForbiddenError)
    def handle_forbidden(e):
        if _is_api_request():
            return jsonify({
                "success": False,
                "icon":    "error",
                "title":   "Không có quyền",
                "text":    str(e) or "Bạn không có quyền truy cập khu vực này.",
            }), 403
        flash("Bạn không có quyền truy cập khu vực này.", "danger")
        return redirect(url_for("auth.login"))