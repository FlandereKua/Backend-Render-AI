from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat import router as chat_router
from app.db.history_manager import init_db

app = FastAPI(
    title="Locaith AI Agent",
    description="AI Agent powered by Gemini Multi-Model Architecture",
    version="1.0.0"
)

# Bật CORS cho toàn bộ domain (nếu muốn giới hạn thì sửa allow_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # hoặc ví dụ: ["https://yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],        # cho phép GET, POST, PUT, DELETE, OPTIONS
    allow_headers=["*"],        # cho phép tất cả headers
)

@app.on_event("startup")
def on_startup():
    init_db()

# Đăng ký router chính cho chat agent
app.include_router(chat_router, prefix="/api")

# Endpoint test nhanh
@app.get("/")
def read_root():
    return {"status": "Locaith AI Agent is running."}