from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas import ChatPayload, ChatAgentRequest, ChatRequest
from app.memory_store import MemoryStore
import json, asyncio

router = APIRouter()
memory = MemoryStore()

def sse(event: dict) -> str:
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"

@router.post("/chat-agent")
async def chat_agent(req: ChatPayload):
    # Hợp nhất “phiên”:
    if isinstance(req, ChatAgentRequest):
        sid = (req.session_id or "default")
        prompt = req.prompt
    else:  # ChatRequest
        sid = f"{req.user_id}:{req.conversation_id}"
        prompt = req.prompt

    history = memory.get(sid)
    history.append({"role":"user","content": prompt})

    # ... tính answer thực tế ở đây ...
    answer = f"Đã nhận: “{prompt}”. (demo SSE & session_id)"

    history.append({"role":"assistant","content": answer})

    async def stream():
        yield sse({"type":"status_update","content":"Đang phân tích yêu cầu…"})
        yield sse({"type":"thinking_header","content":"Xác định mục tiêu"})
        await asyncio.sleep(0.03)
        yield sse({"type":"thinking_chunk","content":f"• Session: {sid}"})
        await asyncio.sleep(0.03)
        yield sse({"type":"thinking_done"})
        yield sse({"type":"final_answer","content": answer})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
