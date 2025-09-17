# main.py
import os
import re
import requests
import traceback
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
- Be accurate and cite assumptions.
"""

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=SYSTEM_PROMPT,
    generation_config={
        "temperature": 0.6,
        "top_p": 0.9,
        "max_output_tokens": 1024,
    },
)

# Start chat session
chat = model.start_chat(history=[])

# ---------------- FastAPI setup ----------------
app = FastAPI(title="Gemini FastAPI Webhook")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # TODO: replace ["*"] with your frontend domain for security
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
    import re
    return any(re.search(pattern, p) for pattern in current_patterns)

def search_with_serper(query: str, api_key: str, search_type: str = "search"):
    url = f"https://google.serper.dev/{search_type}"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": 5}
    if search_type == "news":
        payload["tbs"] = "qdr:d"  # restrict to last 24h
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def format_search_context(search_results: dict, news_results: dict | None = None) -> str:
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

# ---------------- Request/Response Models ----------------
class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str
    used_search: bool

# ---------------- API Endpoints ----------------
@app.get("/")
def root():
    return {"status": "ok", "message": "Gemini FastAPI service running."}

@app.post("/ask", response_model=AskResponse)
def ask_question(req: AskRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Empty 'question' field")

    use_search = SERPER_API_KEY and needs_realtime_search(question)

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
            response = chat.send_message(composed)
        else:
            response = chat.send_message(question)

        resp_text = getattr(response, "text", None) or "No response"
        return AskResponse(answer=remove_markdown(resp_text), used_search=bool(use_search))

    except Exception as e:
        print("ERROR in /ask:", str(e))
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
