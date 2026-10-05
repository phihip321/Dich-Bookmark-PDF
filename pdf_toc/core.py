"""Đọc và ghi mục lục (outline) trong file PDF bằng pypdf.

Ghi chú:
- Hàm write_pdf_with_toc() XÓA outline cũ trước khi thêm outline mới
  để tránh tình trạng PDF mới có cả bookmark tiếng Anh lẫn tiếng Việt.
"""

from dataclasses import dataclass, field
from typing import List

from pypdf import PdfReader, PdfWriter


@dataclass
class TocItem:
    level: int          # 0 = cấp 1, 1 = cấp 2, ...
    title: str
    page: int           # 1-based
    children: List["TocItem"] = field(default_factory=list)


# ============================================================
# ĐỌC PDF
# ============================================================
def pdf_page_count(pdf_path: str) -> int:
    """Số trang của PDF."""
    return len(PdfReader(pdf_path).pages)


def read_outline(pdf_path: str) -> List[TocItem]:
    """Đọc outline PDF -> list[TocItem] phẳng (theo đúng thứ tự trong file)."""
    reader = PdfReader(pdf_path)
    result: List[TocItem] = []

    def walk(items, level: int = 0):
        for item in items:
            if isinstance(item, list):
                walk(item, level + 1)
            else:
                try:
                    page = reader.get_destination_page_number(item) + 1
                except Exception:
                    page = 1
                result.append(TocItem(
                    level=level,
                    title=(item.title or "").strip(),
                    page=page,
                ))

    walk(reader.outline)
    return result


# ============================================================
# XÂY CÂY TỪ LIST PHẲNG
# ============================================================
def _build_tree(items: List[TocItem]) -> List[TocItem]:
    """Chuyển list phẳng -> cây theo level. Trả về list các node gốc."""
    roots: List[TocItem] = []
    stack: List[TocItem] = []

    for it in items:
        node = TocItem(level=it.level, title=it.title, page=it.page)
        while stack and stack[-1].level >= node.level:
            stack.pop()
        if stack:
            stack[-1].children.append(node)
        else:
            roots.append(node)
        stack.append(node)

    return roots


# ============================================================
# XÓA OUTLINE CŨ
# ============================================================
def _clear_outline(writer: PdfWriter) -> None:
    """Xóa outline cũ trong writer để tránh trùng với outline mới.

    pypdf lưu outline tại /Root/Outlines. Ngoài ra có thể có
    /Root/PageMode và /Root/PageLabels trỏ đến outline cũ.
    """
    try:
        root = writer._root_object
    except Exception:
        return

    for key in ("/Outlines", "/PageMode", "/PageLabels"):
        try:
            if key in root:
                del root[key]
        except Exception:
            pass


# ============================================================
# GHI PDF MỚI VỚI OUTLINE
# ============================================================
def write_pdf_with_toc(src_pdf: str, items: List[TocItem], out_pdf: str) -> int:
    """Ghi PDF mới với outline từ items.

    - Copy toàn bộ nội dung (trang, metadata, ảnh, …) từ PDF gốc.
    - XÓA outline cũ trước khi thêm outline mới.
    - Trả về số mục đã ghi.
    """
    reader = PdfReader(src_pdf)
    writer = PdfWriter()
    writer.append(reader)

    # ✅ Xóa outline cũ để không bị lẫn bookmark tiếng Anh
    _clear_outline(writer)

    total_pages = len(writer.pages)
    count = 0

    def add_nodes(nodes: List[TocItem], parent=None):
        nonlocal count
        for n in nodes:
            # Clamp số trang vào khoảng hợp lệ
            page = max(0, min(n.page - 1, total_pages - 1))
            ref = writer.add_outline_item(n.title, page, parent=parent)
            count += 1
            if n.children:
                add_nodes(n.children, parent=ref)

    add_nodes(_build_tree(items))

    with open(out_pdf, "wb") as f:
        writer.write(f)

    return count