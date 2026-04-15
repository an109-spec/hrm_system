import qrcode
from io import BytesIO
import base64


class QRService:

    @staticmethod
    def generate_qr(data: str) -> str:
        qr = qrcode.make(data)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")

        return base64.b64encode(buffer.getvalue()).decode()