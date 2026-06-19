from flask_jwt_extended import JWTManager
from flask import redirect, request, url_for, flash, jsonify

jwt = JWTManager()

def init_jwt(app):
    jwt.init_app(app)

    @jwt.unauthorized_loader
    def unauthorized_response(callback):
        # Thay vì redirect, trả về JSON để frontend xử lý
        return jsonify({
            "success": False,
            "message": "Phiên đăng nhập đã hết hạn hoặc bạn không có quyền truy cập.",
            "redirect": url_for('auth.login')
        }), 401

    @jwt.expired_token_loader
    def expired_token_response(jwt_header, jwt_payload):
        return jsonify({
            "success": False,
            "message": "Token đã hết hạn, vui lòng đăng nhập lại.",
            "redirect": url_for('auth.login')
        }), 401