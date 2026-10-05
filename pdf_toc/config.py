"""Quản lý cấu hình + API key, lưu vào .pdf-toc.json cạnh app/exe."""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


CONFIG_FILENAME = ".pdf-toc.json"

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "model": "gemini-2.0-flash",
    "temperature": 0,
    "last_saved": "",
    "last_open_dir": "",
}


def get_config_path() -> Path:
    """Trả về đường dẫn file config — cạnh exe (nếu frozen) hoặc cạnh app.py."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        # pdf_toc/config.py -> lên 2 cấp = thư mục gốc dự án
        base = Path(__file__).resolve().parent.parent
    return base / CONFIG_FILENAME


def load_config() -> dict:
    """Đọc file config. Nếu chưa có thì trả về config mặc định."""
    path = get_config_path()
    cfg = dict(DEFAULT_CONFIG)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
        except (json.JSONDecodeError, OSError):
            # File hỏng → dùng mặc định, không crash
            pass
    return cfg


def save_config(cfg: dict) -> None:
    """Ghi file config (indent=2, UTF-8)."""
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_api_key() -> Optional[str]:
    """Trả về key nếu có, ngược lại None."""
    key = load_config().get("gemini_api_key", "").strip()
    return key or None


def set_api_key(key: str, model: Optional[str] = None) -> None:
    """Cập nhật API key (và model nếu có) + timestamp, rồi lưu."""
    cfg = load_config()
    cfg["gemini_api_key"] = key.strip()
    if model:
        cfg["model"] = model
    cfg["last_saved"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_config(cfg)


def get_model() -> str:
    return load_config().get("model", DEFAULT_CONFIG["model"])


def get_temperature() -> float:
    try:
        return float(load_config().get("temperature", 0))
    except (TypeError, ValueError):
        return 0.0


def set_last_dir(directory: str) -> None:
    cfg = load_config()
    cfg["last_open_dir"] = directory
    save_config(cfg)


def get_last_dir() -> str:
    return load_config().get("last_open_dir", "")