from app.models.base import db

class Role(db.Model):
    """
    Model phân quyền hệ thống.
    """
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False) # Admin, HR, Manager, Employee

    def __repr__(self):
        return f"<Role {self.name}>"