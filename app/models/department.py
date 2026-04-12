from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship

class Department(BaseModel):
    """
    Model quản lý thông tin các phòng ban trong tổ chức.
    Kế thừa từ BaseModel để có id, created_at, updated_at và is_deleted.
    """
    __tablename__ = 'departments'

    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    
    # Manager_id liên kết đến bảng Employees
    # Lưu ý: 'employees.id' là tên bảng trong DB, 'Employee' là tên class Model
    manager_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    
    # Trạng thái hoạt động
    status = db.Column(db.Boolean, default=True)

    # Relationships
    # Liên kết với trưởng phòng (người quản lý phòng ban)
    manager = relationship('Employee', foreign_keys=[manager_id], backref='managed_department')
    
    # Liên kết với danh sách nhân viên thuộc phòng ban này
    employees = relationship('Employee', foreign_keys='Employee.department_id', backref='department')

    def __repr__(self):
        return f"<Department {self.name}>"

    @property
    def employee_count(self):
        """Hàm helper để đếm nhanh số nhân viên trong phòng (không tính người đã xóa)"""
        return len([e for e in self.employees if not e.is_deleted])