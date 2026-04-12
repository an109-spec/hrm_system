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

def register_cli(app) -> None:
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_db_command) # Đăng ký thêm lệnh seed