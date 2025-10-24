from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PDFDocument:
    source_page: str
    url: str
    filename: Path
    title: Optional[str]
    context: Optional[str]
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
