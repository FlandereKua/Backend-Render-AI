import google.generativeai as genai
from google.generativeai.protos import Part
from google.generativeai.types import StopCandidateException
import re
import asyncio
import json
from pathlib import Path
from PIL import Image
from app.core.config import GEMINI_API_KEY, MODEL_PRO, MODEL_FLASH, SYSTEM_PROMPT_V7
from app.models.schemas import ThinkingChunk, ThinkingDone, FinalAnswer, ErrorMessage, StatusUpdate
from app.services.tool_executor import available_tools, tool_status_messages
from app.db import history_manager

genai.configure(api_key=GEMINI_API_KEY)

def sanitize_and_format_for_html(text: str) -> str:
    cleaned_text = text.replace('**', '').replace('###', '').replace('##', '').replace('#', '')
    formatted_text = re.sub(r'`([^`]+)`', r'<code>\1</code>', cleaned_text)
    return formatted_text

async def process_user_request(
    prompt: str,
    session_id: str,
    image_bytes: bytes | None = None,
    file_content: str | None = None,
    filename: str | None = None,
    mime_type: str | None = None
):
    retrieved_history = history_manager.get_history(session_id, limit=10)
    user_message = prompt
    if filename:
        user_message += f"\n(File đính kèm: {filename})"
    history_manager.add_message(session_id, "user", user_message)

    decision = ""
    if file_content or image_bytes:
        decision = "complex_reasoning"
    else:
        router_model = genai.GenerativeModel(MODEL_FLASH)
        router_prompt = f"""
        Analyze the user's prompt and classify it into one of two categories:
        1. 'simple_answer': For general knowledge questions, greetings, or topics that do not require real-time information.
        2. 'complex_reasoning': For questions about recent events, specific products, companies, or anything that requires up-to-date information or deep analysis.
        User Prompt: "{prompt}"
        Respond with ONLY 'simple_answer' or 'complex_reasoning'.
        """
        try:
            router_response = await router_model.generate_content_async(router_prompt)
            decision = router_response.text.strip()
        except Exception:
            decision = "complex_reasoning"

    final_model_answer = ""
    try:
        if decision == 'simple_answer':
            simple_model = genai.GenerativeModel(MODEL_FLASH)
            chat_session = simple_model.start_chat(history=retrieved_history)
            
            if not retrieved_history:
                persona_prefix = """
                Bạn là Locaith AI, một trợ lý ảo thân thiện và chuyên nghiệp từ Locaith Solution Tech.
                Nhiệm vụ của bạn là:
                1. Trả lời câu hỏi của người dùng một cách rõ ràng, giải thích từng bước nếu cần.
                2. Sau khi trả lời xong, hãy đề xuất 2-3 câu hỏi tiếp theo mà người dùng có thể quan tâm, dựa trên ngữ cảnh cuộc hội thoại.
                """
                simple_prompt = f"{persona_prefix}\n\nCâu hỏi của người dùng: \"{prompt}\""
            else:
                persona_prefix = """
                Tiếp tục cuộc hội thoại với vai trò là Locaith AI.
                Nhiệm vụ của bạn là:
                1. Trả lời câu hỏi của người dùng một cách rõ ràng, dựa trên ngữ cảnh đã có.
                2. Sau khi trả lời xong, hãy đề xuất 2-3 câu hỏi tiếp theo mà người dùng có thể quan tâm.
                """
                simple_prompt = f"{persona_prefix}\n\nCâu hỏi tiếp theo của người dùng: \"{prompt}\""

            response = await chat_session.send_message_async(simple_prompt)
            final_model_answer = response.text
            final_answer_obj = FinalAnswer(content=final_model_answer)
            yield f"data: {final_answer_obj.model_dump_json()}\n\n"
        
        else:
            full_thinking_process = []
            
            if image_bytes and mime_type:
                yield f"data: {StatusUpdate(content='👁️ Đang phân tích hình ảnh bằng `gemini-2.5-pro`...').model_dump_json()}\n\n"
                
                vision_model = genai.GenerativeModel(MODEL_PRO)
                
                image_part = Part(inline_data={'mime_type': mime_type, 'data': image_bytes})
                
                prompt_part = f"""
                Với vai trò là một trợ lý AI chuyên nghiệp, hãy thực hiện một bài phân tích chi tiết về hình ảnh được cung cấp để trả lời yêu cầu của người dùng.
                QUAN TRỌNG: Toàn bộ bài phân tích chi tiết của bạn PHẢI được đặt trong cặp thẻ `<thinking>` và `</thinking>`.
                Yêu cầu của người dùng: "{prompt}"
                """

                response = await vision_model.generate_content_async([prompt_part, image_part], stream=True)
                
                async for chunk in response:
                    if chunk.text:
                        sanitized_content = sanitize_and_format_for_html(chunk.text)
                        yield f"data: {ThinkingChunk(content=sanitized_content).model_dump_json()}\n\n"
                        full_thinking_process.append(sanitized_content)

            else:
                model_pro = genai.GenerativeModel(MODEL_PRO)
                chat_session = model_pro.start_chat(history=retrieved_history)
                
                prompt_for_thinking = f"{SYSTEM_PROMPT_V7}\n\n## USER REQUEST ##\n{prompt}"
                if file_content:
                    prompt_for_thinking += f"\n\n## ATTACHED FILE CONTENT: `{filename}` ##\n---\n{file_content}\n---"
                
                response_stream = await chat_session.send_message_async(prompt_for_thinking, stream=True)
                
                current_chunk_buffer = ""
                async for chunk in response_stream:
                    if not chunk.text: continue
                    
                    sanitized_content = chunk.text.replace('**', '').replace('###', '').replace('##', '').replace('#', '')
                    yield f"data: {ThinkingChunk(content=sanitized_content).model_dump_json()}\n\n"
                    current_chunk_buffer += sanitized_content
                
                full_thinking_process.append(current_chunk_buffer)
                final_thinking_text_pass1 = current_chunk_buffer
                
                tool_call_match = re.search(r'\[CallTool: (\w+)\(query="((?:[^"\\]|\\.)*)"\)\]', final_thinking_text_pass1)

                if tool_call_match:
                    tool_name = tool_call_match.group(1)
                    tool_query = tool_call_match.group(2)
                    
                    if tool_name in available_tools:
                        status_message = tool_status_messages.get(tool_name, f"⚙️ Đang thực thi công cụ {tool_name}...")
                        yield f"data: {StatusUpdate(content=status_message).model_dump_json()}\n\n"

                        tool_function = available_tools[tool_name]
                        tool_result = await tool_function(tool_query)
                        
                        observation_prompt = f"Observation: {tool_result}"
                        full_thinking_process.append(f"\n[Observation from {tool_name}: Received structured data]\n{tool_result}\n")
                        
                        follow_up_stream = await chat_session.send_message_async(observation_prompt, stream=True)
                        async for follow_up_chunk in follow_up_stream:
                            if follow_up_chunk.text:
                                sanitized_content_after_tool = follow_up_chunk.text.replace('**', '').replace('###', '').replace('##', '').replace('#', '')
                                yield f"data: {ThinkingChunk(content=sanitized_content_after_tool).model_dump_json()}\n\n"
                                full_thinking_process.append(sanitized_content_after_tool)
            
            yield f"data: {ThinkingDone().model_dump_json()}\n\n"
            
            synthesizer_model = genai.GenerativeModel(MODEL_FLASH)
            final_thinking_text = "".join(full_thinking_process)
            
            prompt_for_synthesis = ""
            observation_match = re.search(r"\[Observation from \w+: Received structured data\]\n(\{.*\}|\[.*\])", final_thinking_text, re.DOTALL)
            
            if observation_match:
                observation_data_raw = observation_match.group(1).strip()
                prompt_for_synthesis = f"""
                Nhiệm vụ của bạn là một chuyên gia trình bày dữ liệu. Dựa vào dữ liệu JSON thô sau, hãy định dạng thành danh sách rõ ràng cho người dùng, tuân thủ các quy tắc đã biết.
                Dữ liệu JSON thô: --- {observation_data_raw} ---
                Soạn thảo câu trả lời cuối cùng:
                """
            else:
                raw_answer = final_thinking_text.split("</thinking>")[-1].strip()
                if not raw_answer: 
                    raw_answer = final_thinking_text
                
                if image_bytes:
                     prompt_for_synthesis = f"""
                    Nhiệm vụ của bạn là một chuyên gia giao tiếp. Dựa trên luồng phân tích hình ảnh chi tiết sau đây, hãy viết một câu trả lời tổng hợp, thân thiện và chuyên nghiệp cho người dùng.
                    Không lặp lại tất cả chi tiết, chỉ cần tóm tắt các điểm chính một cách dễ hiểu và đưa ra các gợi ý tiếp theo.
                    Nội dung phân tích thô: --- {raw_answer} ---
                    Soạn thảo câu trả lời cuối cùng cho người dùng:
                    """
                else:
                    prompt_for_synthesis = f"""
                    Nhiệm vụ của bạn là một chuyên gia biên tập. Dựa trên nội dung hội thoại thô sau, hãy biên tập lại nó thành câu trả lời cuối cùng, hoàn chỉnh và chuyên nghiệp.
                    Giữ nguyên ý chính, cải thiện văn phong và đảm bảo có gợi ý câu hỏi tiếp theo.
                    Nội dung thô cần biên tập: --- {raw_answer} ---
                    Soạn thảo câu trả lời cuối cùng đã được hoàn thiện:
                    """
            
            synthesis_response = await synthesizer_model.generate_content_async(prompt_for_synthesis)
            final_model_answer = synthesis_response.text
            final_answer_obj = FinalAnswer(content=final_model_answer)
            yield f"data: {final_answer_obj.model_dump_json()}\n\n"

    except StopCandidateException as e:
        error_message = ErrorMessage(content="Yêu cầu của bạn có thể chứa nội dung không phù hợp hoặc nhạy cảm. Vui lòng thử lại với một câu hỏi khác.")
        yield f"data: {error_message.model_dump_json()}\n\n"
    except Exception as e:
        error_message = ErrorMessage(content=f"Đã xảy ra một lỗi nội bộ: {str(e)}")
        yield f"data: {error_message.model_dump_json()}\n\n"

    if final_model_answer:
        history_manager.add_message(session_id, "model", final_model_answer)