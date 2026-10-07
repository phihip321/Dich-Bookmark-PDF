"""Gọi Gemini API để dịch tiêu đề mục lục.

Dùng SDK mới: google-genai (thay cho google-generativeai đã deprecated).
- Hỗ trợ dịch theo batch (an toàn cho mục lục dài).
- Retry tự động khi batch lỗi.
- Fallback: giữ nguyên tiêu đề gốc nếu batch thất bại hoàn toàn.
"""

import json
import time
from typing import Callable, List, Optional

from google import genai
from google.genai import types


PROMPT_TMPL = "Dịch sang tiếng Việt, giữ nguyên thứ tự:\n{titles_json}"

# ============================================================
# CẤU HÌNH
# ============================================================
DEFAULT_BATCH_SIZE = 200        # Số mục / 1 request (mặc định)
MIN_BATCH_SIZE = 50
MAX_BATCH_SIZE = 1000

DEFAULT_OUTPUT_LIMIT = 8192     # Nếu không lấy được từ API
SAFETY_FACTOR = 0.25            # Dùng 25% output limit để an toàn
TOKENS_PER_TITLE = 15           # Ước lượng token output cho 1 tiêu đề

MAX_RETRIES = 3                 # Số lần retry cho mỗi batch


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
    if "token" in msg and ("limit" in msg or "exceed" in msg):
        return "Vượt giới hạn token. Giảm batch size rồi thử lại."
    return f"Lỗi Gemini: {exc}"


# ============================================================
# DỊCH 1 BATCH
# ============================================================
def translate_titles(api_key: str, model_name: str,
                     titles: List[str], temperature: float = 0.0) -> List[str]:
    """Dịch 1 batch tiêu đề (không chia nhỏ).

    Raises:
        GeminiError: nếu có lỗi.
    """
    if not api_key:
        raise GeminiError("Chưa cấu hình API key.")
    if not titles:
        return []

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        raise GeminiError(f"Không khởi tạo được Gemini client: {e}") from e

    prompt = PROMPT_TMPL.format(
        titles_json=json.dumps(titles, ensure_ascii=False)
    )

    config = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json",
        response_schema={
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )
    except Exception as e:
        raise GeminiError(_classify_error(e)) from e

    text = (response.text or "").strip()
    if not text:
        raise GeminiError("Gemini trả về rỗng.")

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
# DỊCH NHIỀU BATCH
# ============================================================
def translate_titles_batched(
    api_key: str,
    model_name: str,
    titles: List[str],
    temperature: float = 0.0,
    batch_size: int = DEFAULT_BATCH_SIZE,
    progress_callback: Optional[Callable] = None,
) -> List[str]:
    """Dịch nhiều batch nhỏ, ghép kết quả.

    - Retry tối đa MAX_RETRIES lần nếu 1 batch lỗi.
    - Nếu vẫn lỗi → giữ nguyên tiêu đề gốc của batch đó (không mất dữ liệu).

    Args:
        batch_size: Số mục / 1 batch. Tự động clamp trong [MIN, MAX].
        progress_callback: fn(batch_num, n_batches, done, total) báo tiến độ.

    Returns:
        List tiêu đề đã dịch, cùng số lượng với input.
    """
    if not titles:
        return []

    total = len(titles)
    batch_size = max(MIN_BATCH_SIZE, min(batch_size, MAX_BATCH_SIZE))
    n_batches = (total + batch_size - 1) // batch_size

    result: List[str] = []

    for i in range(0, total, batch_size):
        batch = titles[i:i + batch_size]
        batch_num = i // batch_size + 1

        if progress_callback:
            try:
                progress_callback(batch_num, n_batches, i, len(batch), total)
            except Exception:
                pass

        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                translated = translate_titles(
                    api_key=api_key,
                    model_name=model_name,
                    titles=batch,
                    temperature=temperature,
                )
                result.extend(translated)
                success = True
                break
            except GeminiError as e:
                if attempt < MAX_RETRIES:
                    wait = 2 ** attempt      # 2s, 4s
                    print(f"⚠️ Batch {batch_num}/{n_batches} "
                          f"lỗi lần {attempt}: {e}")
                    print(f"   Chờ {wait}s rồi thử lại...")
                    time.sleep(wait)
                else:
                    print(f"❌ Batch {batch_num}/{n_batches} "
                          f"thất bại hoàn toàn. Giữ nguyên tiêu đề gốc.")
                    result.extend(batch)

        if not success:
            continue

    return result


# ============================================================
# DỊCH THEO LEVEL (lọc trước khi gửi)
# ============================================================
def translate_filtered(
    api_key: str,
    model_name: str,
    items: list,
    selected_levels: set,
    temperature: float = 0.0,
    batch_size: int = DEFAULT_BATCH_SIZE,
    progress_callback: Optional[Callable] = None,
) -> List[str]:
    """Dịch các mục có level nằm trong selected_levels.

    Args:
        items: List[TocItem] đầy đủ.
        selected_levels: set[int] — các level cần dịch.

    Returns:
        List[str] — bản dịch cho TẤT CẢ items
        (mục không chọn giữ nguyên tiêu đề gốc).
    """
    to_translate: List[str] = []
    to_translate_idx: List[int] = []

    for i, it in enumerate(items):
        if it.level in selected_levels:
            to_translate.append(it.title)
            to_translate_idx.append(i)

    if not to_translate:
        return [it.title for it in items]

    translated = translate_titles_batched(
        api_key=api_key,
        model_name=model_name,
        titles=to_translate,
        temperature=temperature,
        batch_size=batch_size,
        progress_callback=progress_callback,
    )

    result = [it.title for it in items]
    for idx, new_title in zip(to_translate_idx, translated):
        result[idx] = new_title
    return result


# ============================================================
# LIỆT KÊ MODEL + GIỚI HẠN
# ============================================================
def list_available_models(api_key: str) -> List[str]:
    """Liệt kê các model hỗ trợ generateContent."""
    if not api_key:
        return []
    try:
        client = genai.Client(api_key=api_key)
        models = []
        for m in client.models.list():
            methods = getattr(m, "supported_generation_methods", []) or []
            if "generateContent" in methods:
                name = (m.name or "").replace("models/", "")
                if name:
                    models.append(name)
        return sorted(models)
    except Exception:
        return []


def get_model_limits(api_key: str, model_name: str) -> dict:
    """Trả về giới hạn token của model.

    Returns:
        dict với keys 'input_token_limit', 'output_token_limit'
        hoặc {} nếu không lấy được.
    """
    if not api_key or not model_name:
        return {}
    try:
        client = genai.Client(api_key=api_key)
        for m in client.models.list():
            name = (m.name or "").replace("models/", "")
            if name == model_name:
                return {
                    "name": name,
                    "input_token_limit": getattr(m, "input_token_limit", None),
                    "output_token_limit": getattr(m, "output_token_limit", None),
                }
    except Exception:
        pass
    return {}


def auto_batch_size(output_token_limit: Optional[int]) -> int:
    """Tính batch size an toàn từ output token limit của model."""
    if not output_token_limit or output_token_limit <= 0:
        return DEFAULT_BATCH_SIZE

    safe = int(output_token_limit * SAFETY_FACTOR)
    batch = safe // TOKENS_PER_TITLE
    return max(MIN_BATCH_SIZE, min(batch, MAX_BATCH_SIZE))