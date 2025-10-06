import asyncio
import uvicorn
from pyngrok import ngrok
from app.core.config import NGROK_AUTHTOKEN


async def main():
    if not NGROK_AUTHTOKEN:
        print("❌ Lỗi: NGROK_AUTHTOKEN chưa được thiết lập trong tệp .env.")
        return

    # Thiết lập authtoken cho ngrok
    ngrok.set_auth_token(NGROK_AUTHTOKEN)

    # Tạo tunnel cho cổng 8000 (FastAPI chạy trên uvicorn)
    public_url = ngrok.connect(8000)
    print("✅ Locaith AI Agent đang chạy tại: http://127.0.0.1:8000")
    print(f"🌍 URL công khai (Ngrok): {public_url}")
    print("👉 URL này có thể dùng cho webhook trên Facebook, Zalo, v.v...")

    # Chạy uvicorn server (FastAPI)
    config = uvicorn.Config("main:app", host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def shutdown():
    ngrok.kill()  # đóng tất cả tunnel ngrok
    print("\n🛑 Đã đóng kết nối Ngrok.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        asyncio.run(shutdown())
