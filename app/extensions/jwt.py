from flask_jwt_extended import JWTManager
from flask import redirect, request, url_for, flash

jwt = JWTManager()

def init_jwt(app):
    jwt.init_app(app)

    # Nếu Token không hợp lệ hoặc thiếu, tự động redirect về trang login
    @jwt.unauthorized_loader
    def unauthorized_response(callback):
        # Đây chính là nơi in ra dòng "Please log in to access this page"
        # flash("Vui lòng đăng nhập để tiếp tục", "warning") 
        return redirect(url_for('auth.login', next=request.path))

    @jwt.expired_token_loader
    def expired_token_response(jwt_header, jwt_payload):
        return redirect(url_for('auth.login'))