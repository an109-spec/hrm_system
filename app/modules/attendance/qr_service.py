from importlib import import_module
from io import BytesIO
import base64


class QRService:

    @staticmethod
    def generate_qr(data: str) -> str:
        qrcode = import_module("qrcode")
        qr = qrcode.make(data)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")

        return base64.b64encode(buffer.getvalue()).decode()