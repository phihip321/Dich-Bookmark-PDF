"""Lọc mục lục theo level."""

from typing import List, Set

from .core import TocItem


def get_all_levels(items: List[TocItem]) -> List[int]:
    """Danh sách level có trong mục lục, đã sắp xếp tăng dần."""
    if not items:
        return []
    return sorted(set(it.level for it in items))


def filter_by_levels(items: List[TocItem],
                     selected_levels: Set[int]) -> List[TocItem]:
    """Lọc các mục có level nằm trong selected_levels."""
    if not selected_levels:
        return []
    return [it for it in items if it.level in selected_levels]