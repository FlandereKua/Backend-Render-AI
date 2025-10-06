from pydantic import BaseModel
from typing import Literal, Union

class ChatRequest(BaseModel):
    prompt: str

class ThinkingChunk(BaseModel):
    type: Literal["thinking_chunk"] = "thinking_chunk"
    content: str  # bullet-friendly, no markdown symbols

class ThinkingDone(BaseModel):
    type: Literal["thinking_done"] = "thinking_done"

class StatusUpdate(BaseModel):
    type: Literal["status_update"] = "status_update"
    content: str  # short present-progress sentence

class FinalAnswer(BaseModel):
    type: Literal["final_answer"] = "final_answer"
    content: str  # final composed plain text (HTML-safe)

class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    content: str

StreamResponse = Union[ThinkingChunk, ThinkingDone, StatusUpdate, FinalAnswer, ErrorMessage]
