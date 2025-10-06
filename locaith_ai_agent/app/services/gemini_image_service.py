import time
import base64
from pathlib import Path
from typing import List, Union
from PIL import Image
import google.generativeai as genai
from google.generativeai.protos import Part
import requests
import urllib.parse
import asyncio

# Tên model được định nghĩa ở đây
MODEL_NANO_BANANA = "gemini-2.5-flash-image-preview"

def get_base64_from_response(resp) -> str:
    """Trích xuất dữ liệu ảnh từ response và chuyển thành Base64."""
    for cand in getattr(resp, "candidates", []) or []:
        for part in getattr(cand, "content", {}).parts or []:
            if getattr(part, "inline_data", None):
                data = part.inline_data
                if data and data.data:
                    return base64.b64encode(data.data).decode('utf-8')
    
    debug_texts = [part.text for cand in getattr(resp, "candidates", []) for part in getattr(cand, "content", {}).parts if getattr(part, "text", None)]
    if debug_texts:
        raise RuntimeError("Nano Banana không trả về ảnh. Phản hồi của model:\n" + "\n".join(debug_texts))
    raise RuntimeError("Nano Banana không trả về ảnh.")

async def nano_generate_image(prompt: str) -> str:
    """Tạo ảnh từ văn bản và trả về chuỗi Base64."""
    if not prompt or not prompt.strip():
        raise ValueError("Prompt để tạo ảnh không được để trống.")

    # Sử dụng cách khởi tạo model tiêu chuẩn
    model = genai.GenerativeModel(MODEL_NANO_BANANA)
    enhanced_prompt = f"{prompt}, high quality, sharp focus, detailed, cinematic lighting"
    
    # Sử dụng phiên bản bất đồng bộ (async)
    resp = await model.generate_content_async(contents=[enhanced_prompt])
    return get_base64_from_response(resp)

async def nano_edit_image(image_bytes_list: List[bytes], instruction: str) -> str:
    """Chỉnh sửa ảnh từ (các) ảnh đầu vào và hướng dẫn, trả về chuỗi Base64."""
    if not image_bytes_list:
        raise ValueError("Phải cung cấp ít nhất một ảnh đầu vào.")
    if not instruction or not instruction.strip():
        raise ValueError("Hướng dẫn chỉnh sửa không được để trống.")

    # Sử dụng cách khởi tạo model tiêu chuẩn
    model = genai.GenerativeModel(MODEL_NANO_BANANA)

    # Giả định mime_type là png, có thể cải tiến để tự nhận diện sau
    image_parts = [Part(inline_data={'mime_type': 'image/png', 'data': img_bytes}) for img_bytes in image_bytes_list]
    
    contents = [instruction] + image_parts

    # Sử dụng phiên bản bất đồng bộ (async)
    resp = await model.generate_content_async(contents=contents)
    return get_base64_from_response(resp)