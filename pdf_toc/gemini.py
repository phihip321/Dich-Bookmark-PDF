"""Gọi Gemini API để dịch tiêu đề mục lục.

Dùng SDK mới: google-genai (thay cho google-generativeai đã deprecated).
- 1 request duy nhất cho mỗi file PDF.
- Trả về JSON array, giữ nguyên thứ tự.
"""

import json
from typing import List

from google import genai
from google.genai import types


PROMPT_TMPL = "Dịch sang tiếng Việt, giữ nguyên thứ tự:\n{titles_json}"


class GeminiError(Exception):
    """Lỗi khi gọi Gemini API."""
    pass


# ============================================================
# PHÂN LOẠI LỖI
# ============================================================
def _classify_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "api key" in msg or "api_key" in msg or "401" in msg or "403" in msg:
        return "API key không hợp lệ hoặc chưa được cấp quyền."
    if "429" in msg or "quota" in msg or "rate" in msg:
        return "Đã vượt quota hoặc bị giới hạn tốc độ. Thử lại sau."
    if "timeout" in msg or "connection" in msg or "network" in msg:
        return "Lỗi kết nối mạng. Kiểm tra Internet và thử lại."
    if "not found" in msg or "404" in msg:
        return f"Model không tồn tại hoặc không được hỗ trợ: {exc}"
    return f"Lỗi Gemini: {exc}"


# ============================================================
# DỊCH TIÊU ĐỀ
# ============================================================
def translate_titles(api_key: str, model_name: str,
                     titles: List[str], temperature: float = 0.0) -> List[str]:
    """Gửi 1 request duy nhất, trả về list tiêu đề đã dịch.

    Args:
        api_key: Gemini API key
        model_name: Tên model (VD: gemini-2.5-flash)
        titles: List tiêu đề cần dịch
        temperature: 0 để output ổn định

    Returns:
        List tiêu đề tiếng Việt, cùng số lượng và thứ tự với input.

    Raises:
        GeminiError: Nếu có lỗi xảy ra
    """
    if not api_key:
        raise GeminiError("Chưa cấu hình API key.")
    if not titles:
        return []

    # Khởi tạo client (SDK mới)
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        raise GeminiError(f"Không khởi tạo được Gemini client: {e}") from e

    # Chuẩn bị prompt
    prompt = PROMPT_TMPL.format(
        titles_json=json.dumps(titles, ensure_ascii=False)
    )

    # Cấu hình generation
    config = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json",
        response_schema={
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
    )

    # Gọi API
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )
    except Exception as e:
        raise GeminiError(_classify_error(e)) from e

    # Lấy text
    text = (response.text or "").strip()
    if not text:
        raise GeminiError("Gemini trả về rỗng.")

    # Parse JSON
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise GeminiError(f"Không parse được JSON từ Gemini: {e}") from e

    if not isinstance(data, list):
        raise GeminiError("Gemini trả về không phải mảng.")

    if len(data) != len(titles):
        raise GeminiError(
            f"Gemini trả về {len(data)} mục, cần {len(titles)} mục."
        )

    return [str(x).strip() for x in data]


# ============================================================
# LIỆT KÊ MODEL KHẢ DỤNG
# ============================================================
def list_available_models(api_key: str) -> List[str]:
    """Liệt kê các model hỗ trợ generateContent.

    Dùng để hiển thị dropdown trong GUI.
    """
    if not api_key:
        return []

    try:
        client = genai.Client(api_key=api_key)
        models = []
        for m in client.models.list():
            # m.name có dạng "models/gemini-2.5-flash"
            name = m.name.replace("models/", "") if m.name else ""
            if name:
                models.append(name)
        return sorted(models)
    except Exception:
        return []