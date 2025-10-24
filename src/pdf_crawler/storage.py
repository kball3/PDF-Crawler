from __future__ import annotations

import logging
from pathlib import Path
import requests

from .models import PDFDocument
from .utils import ensure_directory, extract_pdf_title, safe_filename

LOGGER = logging.getLogger("pdf_crawler.storage")


class PDFStorage:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        ensure_directory(self.base_dir)

    def _domain_directory(self, url: str) -> Path:
        domain = url.split("//", 1)[-1].split("/", 1)[0]
        path = self.base_dir / domain
        ensure_directory(path)
        return path

    def save_pdf(self, url: str, source_page: str) -> Path:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        filename_hint = url.rsplit("/", 1)[-1].replace(".pdf", "")
        domain_dir = self._domain_directory(source_page)
        existing_names = {f.stem for f in domain_dir.glob("*.pdf")}
        name = safe_filename(filename_hint or "document", existing_names)
        target = domain_dir / f"{name}.pdf"
        with target.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=8192):
                fh.write(chunk)
        return target

    def build_document(self, *, url: str, source_page: str, context: str | None) -> PDFDocument:
        saved_path = self.save_pdf(url, source_page)
        size = saved_path.stat().st_size
        title = extract_pdf_title(saved_path)
        if title:
            existing_names = {f.stem for f in saved_path.parent.glob("*.pdf")}
            proposed_name = safe_filename(title, existing=existing_names, allow_unicode=True)
            proposed = saved_path.with_name(f"{proposed_name}.pdf")
            if proposed != saved_path and not proposed.exists():
                saved_path.rename(proposed)
                saved_path = proposed
        document = PDFDocument(
            source_page=source_page,
            url=url,
            filename=saved_path,
            title=title,
            context=context,
            size_bytes=size,
        )
        return document
