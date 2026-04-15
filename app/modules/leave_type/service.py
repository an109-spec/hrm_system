from flask import request, jsonify
from flask_login import login_required

from . import leave_type_bp
from .service import LeaveTypeService


# =========================
# GET ALL (dropdown UI)
# =========================
@leave_type_bp.route("/", methods=["GET"])
@login_required
def get_all():
    items = LeaveTypeService.get_all()

    return jsonify([
        {
            "id": i.id,
            "name": i.name,
            "is_paid": i.is_paid
        }
        for i in items
    ])


# =========================
# GET DETAIL
# =========================
@leave_type_bp.route("/<int:type_id>", methods=["GET"])
@login_required
def get_one(type_id):
    item = LeaveTypeService.get_by_id(type_id)

    if not item:
        return jsonify({"error": "Not found"}), 404

    return jsonify({
        "id": item.id,
        "name": item.name,
        "is_paid": item.is_paid
    })


# =========================
# CREATE
# =========================
@leave_type_bp.route("/", methods=["POST"])
@login_required
def create():
    data = request.json

    try:
        item = LeaveTypeService.create(
            name=data["name"],
            is_paid=data.get("is_paid", True)
        )

        return jsonify({
            "id": item.id,
            "message": "Created successfully"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# =========================
# UPDATE
# =========================
@leave_type_bp.route("/<int:type_id>", methods=["PUT"])
@login_required
def update(type_id):
    data = request.json

    try:
        item = LeaveTypeService.update(
            type_id=type_id,
            name=data.get("name"),
            is_paid=data.get("is_paid")
        )

        return jsonify({
            "id": item.id,
            "message": "Updated successfully"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# =========================
# DELETE
# =========================
@leave_type_bp.route("/<int:type_id>", methods=["DELETE"])
@login_required
def delete(type_id):
    try:
        LeaveTypeService.delete(type_id)

        return jsonify({
            "message": "Deleted successfully"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400