from flask import request, jsonify
from . import complaint_bp

from .service import ComplaintService
from .dto import (
    CreateComplaintDTO,
    SendMessageDTO,
    UpdateComplaintStatusDTO
)

from app.common.exceptions import ValidationError


# ==============================
# CREATE COMPLAINT
# ==============================
@complaint_bp.route("/", methods=["POST"])
def create_complaint():
    try:
        data = request.get_json()

        if not data:
            raise ValidationError("Missing request body")

        required_fields = ["employee_id", "type", "title", "description"]
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing field: {field}")

        dto = CreateComplaintDTO(**data)
        complaint = ComplaintService.create_complaint(dto)

        return jsonify({
            "success": True,
            "data": complaint.to_dict()
        }), 201

    except ValidationError as e:
        return jsonify({"success": False, "message": str(e)}), 400

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==============================
# GET LIST COMPLAINTS
# ==============================
@complaint_bp.route("/", methods=["GET"])
def get_complaints():
    try:
        employee_id = request.args.get("employee_id", type=int)

        complaints = ComplaintService.get_complaints(employee_id)

        return jsonify({
            "success": True,
            "data": [c.to_dict() for c in complaints]
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==============================
# GET DETAIL
# ==============================
@complaint_bp.route("/<int:complaint_id>", methods=["GET"])
def get_detail(complaint_id):
    try:
        data = ComplaintService.get_detail(complaint_id)

        return jsonify({
            "success": True,
            "data": {
                "complaint": data["complaint"].to_dict(),
                "messages": [m.to_dict() for m in data["messages"]],
                "attachments": [a.to_dict() for a in data["attachments"]]
            }
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==============================
# SEND MESSAGE (CHAT)
# ==============================
@complaint_bp.route("/message", methods=["POST"])
def send_message():
    try:
        data = request.get_json()

        required_fields = ["complaint_id", "sender_id", "message"]
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing field: {field}")

        dto = SendMessageDTO(**data)
        message = ComplaintService.send_message(dto)

        return jsonify({
            "success": True,
            "data": message.to_dict()
        }), 201

    except ValidationError as e:
        return jsonify({"success": False, "message": str(e)}), 400

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==============================
# UPDATE STATUS (HR xử lý)
# ==============================
@complaint_bp.route("/status", methods=["PUT"])
def update_status():
    try:
        data = request.get_json()

        required_fields = ["complaint_id", "status", "handled_by"]
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing field: {field}")

        dto = UpdateComplaintStatusDTO(**data)
        complaint = ComplaintService.update_status(dto)

        return jsonify({
            "success": True,
            "data": complaint.to_dict()
        })

    except ValidationError as e:
        return jsonify({"success": False, "message": str(e)}), 400

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==============================
# UPLOAD FILE
# ==============================
@complaint_bp.route("/upload", methods=["POST"])
def upload_file():
    try:
        file = request.files.get("file")
        complaint_id = request.form.get("complaint_id", type=int)
        user_id = request.form.get("user_id", type=int)

        if not file:
            raise ValidationError("Missing file")

        if not complaint_id or not user_id:
            raise ValidationError("Missing complaint_id or user_id")

        # TODO: bạn có thể thay bằng upload S3 / Cloud
        file_url = f"/uploads/{file.filename}"

        uploaded = ComplaintService.attach_file(
            user_id=user_id,
            complaint_id=complaint_id,
            file_url=file_url,
            file_name=file.filename,
            file_type="image"
        )

        return jsonify({
            "success": True,
            "data": uploaded.to_dict()
        }), 201

    except ValidationError as e:
        return jsonify({"success": False, "message": str(e)}), 400

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500