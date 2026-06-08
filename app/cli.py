import click
from flask.cli import with_appcontext
from app.extensions import db

@click.command("init-db")
@click.option("--drop", is_flag=True, help="Xóa bảng cũ trước khi tạo mới.")
@with_appcontext
def init_db_command(drop: bool) -> None:
    """Khởi tạo các bảng Database từ Models."""
    from app import models
    if drop:
        db.drop_all()
        click.echo("--- Đã xóa các bảng cũ. ---")
    db.create_all()
    click.echo("--- Đã khởi tạo cấu trúc Database thành công! ---")

@click.command("seed-db")
@with_appcontext
def seed_db_command() -> None:
    """Tạo dữ liệu mẫu cho HRM (Phòng ban, Nhân viên mẫu)."""
    from app.models.user import User
    from app.models.department import Department # Giả sử Duy An có bảng này
    
    # Thêm phòng ban mẫu
    dev_dept = Department(name="Phòng Kỹ thuật")
    hr_dept = Department(name="Phòng Nhân sự")
    db.session.add_all([dev_dept, hr_dept])
    
    # Thêm Admin mẫu
    admin = User(full_name="Duy An Admin", email="admin@hrm.com", role="admin")
    admin.set_password("admin123")
    db.session.add(admin)
    
    db.session.commit()
    click.echo("--- Đã nạp dữ liệu mẫu thành công! ---")


@click.command("ensure-default-admin")
@with_appcontext
def ensure_default_admin_command() -> None:
    """Tạo tài khoản admin mặc định nếu bảng users đã tồn tại và chưa có admin."""
    from sqlalchemy import inspect
    from werkzeug.security import generate_password_hash

    from app.models import User

    inspector = inspect(db.engine)
    if not inspector.has_table("users"):
        click.echo("--- Bỏ qua: bảng users chưa tồn tại. Hãy chạy flask init-db hoặc migration trước. ---")
        return

    exists = User.query.filter_by(username="admin").first()
    if exists:
        click.echo("--- Tài khoản Admin mặc định đã tồn tại. ---")
        return

    admin = User(
        username="admin",
        email="admin@hrm.local",
        password_hash=generate_password_hash("admin123"),
    )
    db.session.add(admin)
    db.session.commit()
    click.echo("--- Đã tạo tài khoản Admin mặc định thành công! ---")

def register_cli(app) -> None:
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_db_command) # Đăng ký thêm lệnh seed
    app.cli.add_command(ensure_default_admin_command)