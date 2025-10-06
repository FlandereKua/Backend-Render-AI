from pydantic import BaseModel, Field
from typing import Literal, Union, Optional, List, Dict

class ChatRequest(BaseModel):
    user_id: str = Field(..., description="ID người dùng (đăng nhập tạm)")
    conversation_id: str = Field(..., description="ID hội thoại hiện tại")
    prompt: str

class NewConversationRequest(BaseModel):
    user_id: str
    title: Optional[str] = None

class LoginRequest(BaseModel):
    username: str

class ThinkingHeader(BaseModel):
    type: Literal["thinking_header"] = "thinking_header"
    content: str

class ThinkingChunk(BaseModel):
    type: Literal["thinking_chunk"] = "thinking_chunk"
    content: str

class ThinkingDone(BaseModel):
    type: Literal["thinking_done"] = "thinking_done"

class StatusUpdate(BaseModel):
    type: Literal["status_update"] = "status_update"
    content: str

class FinalAnswer(BaseModel):
    type: Literal["final_answer"] = "final_answer"
    content: str

class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    content: str

StreamResponse = Union[ThinkingHeader, ThinkingChunk, ThinkingDone, StatusUpdate, FinalAnswer, ErrorMessage]
class ChatAgentRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None  # dùng cho test theo phiên, không cần user_id/conversation_id

# Cho /api/chat-agent nhận cả hai kiểu payload:
ChatPayload = Union[ChatAgentRequest, ChatRequest]