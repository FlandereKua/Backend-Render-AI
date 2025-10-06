from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest
from app.services import gemini_service
from app.services.file_parser import parse_file
import shutil
from pathlib import Path

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@router.post("/chat-agent", tags=["AI Agent"])
async def chat_agent_endpoint(request: ChatRequest):
    return StreamingResponse(
        gemini_service.process_user_request(prompt=request.prompt, session_id=request.session_id),
        media_type="text/event-stream"
    )

@router.post("/chat-with-file", tags=["AI Agent with File"])
async def chat_with_file_endpoint(
    session_id: str = Form(...),
    prompt: str = Form(...),
    file: UploadFile = File(...)
):
    if not file:
        raise HTTPException(status_code=400, detail="Không có file nào được tải lên.")
    if file.size > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Kích thước file vượt quá 100MB.")

    file_extension = Path(file.filename).suffix.lower()
    is_image = file_extension in ['.png', '.jpg', '.jpeg', '.webp', '.heic', '.heif']
    
    file_content = None
    image_bytes = None

    try:
        if is_image:
            # --- THAY ĐỔI: ĐỌC BYTES TRỰC TIẾP ---
            image_bytes = await file.read()
        else:
            # Lưu file tạm thời để các parser đọc
            file_path = UPLOAD_DIR / file.filename
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            file_content = parse_file(file_path)

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý file: {str(e)}")

    return StreamingResponse(
        gemini_service.process_user_request(
            prompt=prompt,
            session_id=session_id,
            image_bytes=image_bytes,
            file_content=file_content,
            filename=file.filename,
            mime_type=file.content_type
        ),
        media_type="text/event-stream"
    )