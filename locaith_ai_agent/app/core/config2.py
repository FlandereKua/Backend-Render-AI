# app/core/config.py
import os
from pathlib import Path

# --- load .env ở thư mục gốc dự án (cùng cấp run_with_ngrok.py) ---
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    ROOT_DIR = Path(__file__).resolve().parents[2]  # .../app/core/config.py -> project root
    ENV_PATH = ROOT_DIR / ".env"
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=False)
except Exception:
    # nếu chưa cài python-dotenv vẫn chạy bằng os.environ
    pass

# ==== API Keys ====
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

# ==== Models ====
MODEL_FLASH = os.getenv("MODEL_FLASH", "gemini-2.0-flash-exp")
MODEL_LIVE  = os.getenv("MODEL_LIVE",  "gemini-2.0-flash-lite")
SYSTEM_PROMPT_V7 = os.getenv(
    "SYSTEM_PROMPT_V7",
    "Bạn là trợ lý nghiên cứu Việt hoá, viết gọn, không dùng markdown, không đặt câu hỏi ngược."
)

# ==== Storage (file-based) ====
BASE_DIR   = Path(os.getenv("AGENT_DATA_DIR", "./data")).resolve()
USERS_FILE = BASE_DIR / "users.json"
BASE_DIR.mkdir(parents=True, exist_ok=True)

# ==== Ngrok ====
NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN", "")
NGROK_ADDR   = os.getenv("NGROK_ADDR", "http://127.0.0.1:8000")
NGROK_REGION = os.getenv("NGROK_REGION", "ap")   # ap/us/eu/jp/au/in/sa
NGROK_DOMAIN = os.getenv("NGROK_DOMAIN", "")
