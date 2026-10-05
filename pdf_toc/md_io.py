"""Xuất/nhập Markdown có cấu trúc + JSON để gửi Gemini."""

import json
import os
import re
from datetime import datetime
from typing import List

from .core import TocItem


# Mỗi dòng:  <indent>- <level>|Page <page>|<title>
LINE_RE = re.compile(r"^(\s*)-\s*(\d+)\|Page\s*(\d+)\|(.*)$")


HEADER_TMPL = """---
pdf: {pdf_name}
pages: {pages}
count: {count}
exported: {time}
---

# Table of Contents

> **Hướng dẫn:** Chỉ dịch phần **tiêu đề** (sau dấu `|` cuối cùng).
> **KHÔNG** sửa số cấp ở đầu dòng, **KHÔNG** sửa `Page N`, **KHÔNG** đổi thụt đầu dòng.

"""


# ---------------- XUẤT MD ----------------
def export_markdown(pdf_path: str, items: List[TocItem],
                    md_path: str, page_count: int = 0) -> int:
    lines = [HEADER_TMPL.format(
        pdf_name=os.path.basename(pdf_path),
        pages=page_count,
        count=len(items),
        time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )]
    for it in items:
        indent = "  " * it.level
        lines.append(f"{indent}- {it.level}|Page {it.page}|{it.title}")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return len(items)


# ---------------- ĐỌC MD ----------------
def load_markdown(md_path: str) -> List[TocItem]:
    items: List[TocItem] = []
    with open(md_path, "r", encoding="utf-8") as f:
        for raw in f:
            m = LINE_RE.match(raw.rstrip("\n"))
            if not m:
                continue
            _indent, level, page, title = m.groups()
            items.append(TocItem(
                level=int(level),
                title=title.strip(),
                page=int(page),
            ))
    return items


# ---------------- XUẤT JSON CHO GEMINI ----------------
def export_titles_json(md_path: str, json_path: str) -> int:
    """Chỉ lấy title, ghi thành JSON array để gửi Gemini."""
    items = load_markdown(md_path)
    titles = [it.title for it in items]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(titles, f, ensure_ascii=False)
    return len(titles)


# ---------------- GHÉP BẢN DỊCH ----------------
def merge_translated(md_path: str, translated_json_path: str,
                     out_md_path: str) -> int:
    """Ghép mảng title dịch vào cấu trúc gốc -> md tiếng Việt."""
    items = load_markdown(md_path)

    with open(translated_json_path, "r", encoding="utf-8") as f:
        translated = json.load(f)

    if not isinstance(translated, list):
        raise ValueError("File bản dịch không phải JSON array.")
    if len(translated) != len(items):
        raise ValueError(
            f"Số lượng không khớp: gốc {len(items)} mục, "
            f"bản dịch {len(translated)} mục."
        )

    lines = [HEADER_TMPL.format(
        pdf_name="translated",
        pages="",
        count=len(items),
        time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )]
    for it, new_title in zip(items, translated):
        indent = "  " * it.level
        lines.append(f"{indent}- {it.level}|Page {it.page}|{str(new_title).strip()}")

    with open(out_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return len(items)