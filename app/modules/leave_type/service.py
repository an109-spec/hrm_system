from app.models import LeaveType
from app.extensions.db import db


class LeaveTypeService:

    @staticmethod
    def get_all():
        return LeaveType.query.all()

    @staticmethod
    def get_by_id(type_id):
        return LeaveType.query.get(type_id)

    @staticmethod
    def create(name, is_paid=True):
        item = LeaveType(
            name=name,
            is_paid=is_paid
        )
        db.session.add(item)
        db.session.commit()
        return item

    @staticmethod
    def update(type_id, name=None, is_paid=None):
        item = LeaveType.query.get(type_id)
        if not item:
            raise Exception("Not found")

        if name is not None:
            item.name = name
        if is_paid is not None:
            item.is_paid = is_paid

        db.session.commit()
        return item

    @staticmethod
    def delete(type_id):
        item = LeaveType.query.get(type_id)
        if not item:
            raise Exception("Not found")

        db.session.delete(item)
        db.session.commit()