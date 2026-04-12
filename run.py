import os 
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

from app import create_app
from app.extensions.socketio import socketio

# Khởi tạo ứng dụng từ Application Factory
app = create_app()

if __name__ == "__main__":
    # Lấy port và chế độ debug từ môi trường, mặc định là 5000 và True
    port_env = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "True").lower() == "true"
    
    print(f"--- 🚀 HRM System is starting on port: {port_env} ---")
    print(f"--- 🛠  Debug mode: {'ON' if debug_mode else 'OFF'} ---")

    # Sử dụng socketio.run để hỗ trợ các tính năng thời gian thực (thông báo, chat nội bộ)
    socketio.run(
        app,
        host="0.0.0.0",  # Bắt buộc để Docker có thể ánh xạ port ra ngoài
        port=port_env,
        debug=debug_mode, # Tự động reload khi sửa code
        allow_unsafe_werkzeug=True # Cần thiết khi chạy Socket.io với môi trường dev
    )