'''
Các lệnh CLI tùy chỉnh cho ứng dụng Flask.

- flask init-db:      Khởi tạo (hoặc xóa và tạo lại) CSDL từ models.
- flask seed-db:      Tạo dữ liệu mẫu (seeding).
- flask ensure-default-admin: Đảm bảo có một tài khoản admin mặc định.
- flask reset-password: Đặt lại mật khẩu cho người dùng theo email.
- flask rename-role:    Đổi tên một vai trò (role).
- flask list-roles:     Liệt kê tất cả các vai trò trong CSDL.

Cách dùng:
1. Mở terminal, kích hoạt virtualenv: `source venv/bin/activate`
2. Chạy lệnh: `flask <tên-lệnh>`
'''
import click
from flask.cli import with_appcontext
from app.extensions import db

# ======================================================================================
# 1. NHÓM LỆNH QUẢN LÝ DATABASE
# ======================================================================================

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
    from app.models.department import Department
    from app.models.role import Role
    from app.constants import RoleName

    # Thêm vai trò mẫu
    if not Role.query.first():
        db.session.add_all([
            Role(name=RoleName.ADMIN),
            Role(name=RoleName.HR),
            Role(name=RoleName.MANAGER),
            Role(name=RoleName.EMPLOYEE)
        ])
        click.echo("--- Đã tạo các vai trò mẫu. ---")

    # Thêm phòng ban mẫu
    if not Department.query.first():
        dev_dept = Department(name="Phòng Kỹ thuật")
        hr_dept = Department(name="Phòng Nhân sự")
        db.session.add_all([dev_dept, hr_dept])
        click.echo("--- Đã tạo phòng ban mẫu. ---")

    # Thêm Admin mẫu
    if not User.query.filter(User.email=="admin@hrm.com").first():
        admin_role = Role.query.filter_by(name=RoleName.ADMIN).first()
        admin = User(full_name="Duy An Admin", email="admin@hrm.com", role_id=admin_role.id)
        admin.set_password("admin123")
        db.session.add(admin)
        click.echo("--- Đã tạo tài khoản Admin mẫu. ---")

    db.session.commit()
    click.echo("--- Đã nạp dữ liệu mẫu thành công! ---")


# ======================================================================================
# 2. NHÓM LỆNH QUẢN LÝ TÀI KHOẢN
# ======================================================================================

@click.command("ensure-default-admin")
@with_appcontext
def ensure_default_admin_command() -> None:
    """Tạo tài khoản admin mặc định nếu chưa có."""
    from sqlalchemy import inspect
    from app.models import User, Role
    from app.constants import RoleName

    if not Role.query.filter_by(name=RoleName.ADMIN).first():
        admin_role = Role(name=RoleName.ADMIN)
        db.session.add(admin_role)
        db.session.commit()
        click.echo(f"--- Vai trò '{RoleName.ADMIN}' chưa tồn tại, đã tự động tạo. ---")

    exists = User.query.join(Role).filter(Role.name == RoleName.ADMIN).first()
    if exists:
        click.echo("--- Đã có ít nhất một tài khoản Admin. Bỏ qua. ---")
        return

    admin_role = Role.query.filter_by(name=RoleName.ADMIN).first()
    admin = User(
        username="admin",
        email="admin@hrm.local",
        full_name="Default Admin",
        role_id=admin_role.id
    )
    admin.set_password("admin123")
    db.session.add(admin)
    db.session.commit()
    click.echo("--- Đã tạo tài khoản Admin mặc định thành công! (admin/admin123) ---")


@click.command("reset-password")
@click.option("--email", prompt="Nhập email của người dùng", help="Email của người dùng cần reset mật khẩu.")
@click.option("--new-password", prompt="Nhập mật khẩu mới", help="Mật khẩu mới.")
@with_appcontext
def reset_password_command(email: str, new_password: str) -> None:
    """Đặt lại mật khẩu của người dùng."""
    from app.models.user import User
    user = User.query.filter_by(email=email).first()
    if user:
        user.set_password(new_password)
        db.session.commit()
        click.echo(f"--- Mật khẩu cho người dùng {email} đã được đặt lại thành công! ---")
    else:
        click.echo(f"--- Không tìm thấy người dùng có email {email}. ---")


@click.command("rename-role")
@click.argument("old_name")
@click.argument("new_name")
@with_appcontext
def rename_role_command(old_name, new_name):
    """Đổi tên một vai trò."""
    from app.models.role import Role
    role = Role.query.filter_by(name=old_name).first()
    if role:
        role.name = new_name
        db.session.commit()
        click.echo(f"--- Vai trò \"{old_name}\" đã được đổi tên thành \"{new_name}\". ---")
    else:
        click.echo(f"--- Không tìm thấy vai trò \"{old_name}\". ---")


@click.command("list-roles")
@with_appcontext
def list_roles_command():
    """Liệt kê tất cả các vai trò trong CSDL."""
    from app.models.role import Role
    roles = Role.query.all()
    if not roles:
        click.echo("--- Không có vai trò nào trong cơ sở dữ liệu. ---")
        return
    click.echo("--- Các vai trò hiện có trong CSDL: ---")
    for role in roles:
        click.echo(f"- ID: {role.id}, Name: {role.name}")


# ======================================================================================
# ĐĂNG KÝ LỆNH VỚI FLASK APPLICATION
# ======================================================================================

def register_cli(app) -> None:
    """Đăng ký tất cả các lệnh Click vào ứng dụng Flask."""
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_db_command)
    app.cli.add_command(ensure_default_admin_command)
    app.cli.add_command(reset_password_command)
    app.cli.add_command(rename_role_command)
    app.cli.add_command(list_roles_command)
