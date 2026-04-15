from flask import request, jsonify
from werkzeug.utils import secure_filename

from . import upload_bp
from .service import UploadService


@upload_bp.route("", methods=["POST"])
def upload_file():
    file = request.files.get("file")

    if not file:
        return jsonify({"error": "No file provided"}), 400

    user_id = request.form.get("user_id")
    entity_type = request.form.get("entity_type")
    entity_id = request.form.get("entity_id")

    if not all([user_id, entity_type, entity_id]):
        return jsonify({"error": "Missing metadata"}), 400

    saved = UploadService.save_file(
        file=file,
        user_id=int(user_id),
        entity_type=entity_type,
        entity_id=int(entity_id)
    )

    return jsonify({
        "id": saved.id,
        "file_name": saved.file_name,
        "file_url": saved.file_url,
        "file_type": saved.file_type,
        "file_size": saved.file_size
    }), 201