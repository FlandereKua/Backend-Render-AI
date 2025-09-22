# main.py
import os
import re
import requests
import traceback
import urllib.parse
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import google.generativeai as genai

# ---------------- Load environment ----------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY must be set in environment variables")

# ---------------- Gemini setup ----------------
genai.configure(api_key=GOOGLE_API_KEY)

SYSTEM_PROMPT = """You are a helpful, concise assistant.
- Use provided real-time search context (if present) to answer up-to-date questions, and say when you used it.
- Otherwise, use your general knowledge.
"""

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=SYSTEM_PROMPT,
    generation_config={
        "temperature": 0.6,
        "top_p": 0.9,
        "max_output_tokens": 4000,
    },
)

# ---------------- FastAPI setup ----------------
app = FastAPI(title="Gemini FastAPI Webhook")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 🔒 Replace with your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Utilities ----------------
def remove_markdown(text: str) -> str:
    """Remove markdown formatting for cleaner output."""
    text = re.sub(r"\*{1,3}([^\*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"```[^\n]*\n(.*?)```", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^[\-\*\_]{3,}$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\*\-\+]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"^\d+\.\s+", "• ", text, flags=re.MULTILINE)
    return text.strip()

def needs_realtime_search(prompt: str) -> bool:
    """Heuristic to decide if real-time search is needed."""
    realtime_keywords = [
        "today","current","latest","recent","now","news","update","price",
        "weather","score","stock","crypto","bitcoin","election","breaking",
        "this week","this month","yesterday","tomorrow","forecast","trending","live"
    ]
    p = prompt.lower()
    if any(k in p for k in realtime_keywords):
        return True
    current_patterns = [
        r"what.*happening", r"who.*president", r"who.*prime minister",
        r"what.*price", r"how much.*cost", r"what.*weather"
    ]
    return any(re.search(pattern, p) for pattern in current_patterns)

def search_with_serper(query: str, api_key: str, search_type: str = "search"):
    """Perform a Google Serper API search."""
    url = f"https://google.serper.dev/{search_type}"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": 5}
    if search_type == "news":
        payload["tbs"] = "qdr:d"  # restrict to last 24h
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def format_search_context(search_results: dict, news_results: dict | None = None) -> str:
    """Format Serper results into context text for Gemini."""
    context = "REAL-TIME SEARCH RESULTS:\n\n"
    if search_results and "organic" in search_results:
        context += "WEB SEARCH RESULTS:\n"
        for i, result in enumerate(search_results["organic"][:3], 1):
            context += f"\n{i}. {result.get('title','No title')}\n"
            context += f"   Source: {result.get('link','No link')}\n"
            context += f"   Summary: {result.get('snippet','No snippet')}\n"
    if news_results and "news" in news_results:
        context += "\n\nLATEST NEWS:\n"
        for i, article in enumerate(news_results["news"][:3], 1):
            context += f"\n{i}. {article.get('title','No title')}\n"
            context += f"   Source: {article.get('source','Unknown')}\n"
            context += f"   Date: {article.get('date','No date')}\n"
            context += f"   Summary: {article.get('snippet','No summary')}\n"
    return context

# ---------------- Models ----------------
class AskRequest(BaseModel):
    question: str

# ---------------- Endpoints ----------------
@app.get("/")
def root():
    return {"status": "ok", "message": "Gemini FastAPI service running."}

@app.post("/ask_stream")
async def ask_stream(req: AskRequest):
    """
    Stream Gemini response line-by-line over SSE.
    Uses Serper when real-time search is needed.
    """
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Empty 'question' field")

    use_search = SERPER_API_KEY and needs_realtime_search(question)

    def event_stream():
        try:
            if use_search:
                web_results = search_with_serper(question, SERPER_API_KEY, "search")
                news_results = None
                if any(k in question.lower() for k in ["news", "latest", "breaking", "today"]):
                    news_results = search_with_serper(question, SERPER_API_KEY, "news")

                search_context = format_search_context(web_results, news_results)
                composed = (
                    "Based on the following real-time search results, "
                    "answer the user's question. Indicate you used current search data.\n\n"
                    f"{search_context}\n\n"
                    f"USER QUESTION: {question}"
                )
                stream = model.generate_content_stream(composed)
            else:
                stream = model.generate_content_stream(question)

            buffer = ""
            for chunk in stream:
                text = chunk.text or ""
                if text:
                    buffer += text
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        clean = remove_markdown(line).strip()
                        if clean:
                            yield f"data: {clean}\n\n"
            if buffer.strip():
                yield f"data: {remove_markdown(buffer).strip()}\n\n"

            yield "event: end\ndata: done\n\n"

        except Exception as e:
            print("ERROR in /ask_stream:", str(e))
            print(traceback.format_exc())
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

class ImageRequest(BaseModel):
    prompt: str

@app.post("/ask_image")
def ask_image(req: ImageRequest):
    """
    Generate an AI image from the given prompt using Pollinations API
    and return it as a PNG stream.
    """
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Empty 'prompt' field")

    try:
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?nologo=true&width=1024&height=576"

        # Pollinations sometimes takes a few seconds to render the image
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()

        return StreamingResponse(r.iter_content(chunk_size=8192), media_type="image/png")

    except Exception as e:
        print("ERROR in /ask_image:", str(e))
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")
