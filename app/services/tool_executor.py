import requests
import json
import re
import google.generativeai as genai
import urllib.parse
import base64
from app.core.config import SERPER_API_KEY, MODEL_LIVE, MODEL_FLASH

async def serper_search(query: str) -> str:
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "num": 10})
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        search_results = response.json().get("organic", [])
        if not search_results:
            return "No relevant information found from web search."
        found_entities = {}
        mst_pattern = re.compile(r"(\d{10,13})")
        for item in search_results:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            full_text = f"{title} {snippet}"
            mst_match = mst_pattern.search(full_text)
            if mst_match:
                mst = mst_match.group(1)
                if mst not in found_entities:
                    found_entities[mst] = {
                        "tax_code": mst, "name": title.split(" - ")[0],
                        "representative": "Không rõ", "address": "Không rõ",
                        "source": item.get("link", "")}
                if "đại diện" in snippet.lower():
                    rep_match = re.search(r"(?:Đại diện|đại diện pháp luật): (.+?)(?:-|$)", snippet, re.IGNORECASE)
                    if rep_match: found_entities[mst]["representative"] = rep_match.group(1).strip()
                if "địa chỉ" in snippet.lower():
                    addr_match = re.search(r"Địa chỉ: (.+?)(?:-|$)", snippet, re.IGNORECASE)
                    if addr_match: found_entities[mst]["address"] = addr_match.group(1).strip()
        if not found_entities:
            return json.dumps([{"title": r.get("title"), "snippet": r.get("snippet")} for r in search_results[:5]], ensure_ascii=False, indent=2)
        return json.dumps(list(found_entities.values()), ensure_ascii=False, indent=2)
    except requests.exceptions.RequestException as e:
        return f"Error during Serper search: {str(e)}"

async def gemini_live_search(query: str) -> str:
    try:
        model = genai.GenerativeModel(MODEL_LIVE)
        response = await model.generate_content_async(query)
        return response.text
    except Exception as e:
        return f"Error during Gemini Live query: {str(e)}"

async def translate_to_english(text: str) -> str:
    try:
        model = genai.GenerativeModel(MODEL_FLASH)
        response = await model.generate_content_async(
            f"Translate the following text to English for an image generation AI. Respond with ONLY the translated English text, nothing else.\n\nText: \"{text}\""
        )
        return response.text.strip()
    except Exception as e:
        print(f"Lỗi khi dịch thuật: {e}")
        return text

async def generate_image(query: str) -> str:
    english_prompt = await translate_to_english(query)
    
    try:
        safe_prompt = english_prompt[:250]
        encoded_prompt = urllib.parse.quote(safe_prompt)
        api_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?nologo=true&width=1024&height=576"
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(api_url, timeout=90, allow_redirects=True, headers=headers)
        response.raise_for_status()

        if 'image' in response.headers.get('Content-Type', '').lower():
            base64_image = base64.b64encode(response.content).decode('utf-8')
            return base64_image
        else:
            return "[Lỗi: API tạo ảnh không trả về định dạng hình ảnh hợp lệ]"
            
    except requests.exceptions.RequestException as e:
        return f"[Lỗi khi gọi API tạo ảnh: {e}]"
    except Exception as e:
        return f"[Lỗi không xác định trong quá trình tạo ảnh: {e}]"

available_tools = {
    "serper_search": serper_search,
    "generate_image": generate_image,
}

tool_status_messages = {
    "serper_search": "🔍 Đang tìm kiếm thông tin trên web...",
    "generate_image": "🎨 Đang phác họa ý tưởng của bạn, quá trình này có thể mất một chút thời gian...",
}