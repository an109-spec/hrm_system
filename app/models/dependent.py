from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship as orm_relationship


class Dependent(BaseModel):
    """
    Người phụ thuộc phục vụ tính thuế TNCN/payroll.
    """

    __tablename__ = "dependents"

    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True
    )

    full_name = db.Column(
        db.String(120),
        nullable=False
    )

    dob = db.Column(
        db.Date,
        nullable=False
    )

    relationship = db.Column(
        db.String(30),
        nullable=False
    )

    tax_code = db.Column(
        db.String(30),
        nullable=True
    )

    is_valid = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default="true"
    )

    note = db.Column(
        db.Text,
        nullable=True
    )

    # RELATIONSHIP
    employee = orm_relationship(
        "Employee",
        back_populates="dependents"
    )

    def __repr__(self):
        return f"<Dependent {self.full_name} - Emp:{self.employee_id}>"