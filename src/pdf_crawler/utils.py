from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Iterable, Optional

from pypdf import PdfReader

LOGGER = logging.getLogger("pdf_crawler")


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def slugify(value: str, allow_unicode: bool = False) -> str:
    value = str(value)
    if allow_unicode:
        value = re.sub(r"[\s/]+", "_", value, flags=re.UNICODE)
        value = re.sub(r"[^\w.-]", "", value, flags=re.UNICODE)
        return value.strip("-_.")
    value = re.sub(r"[\s/]+", "-", value)
    value = re.sub(r"[^\w.-]", "", value)
    return value.strip("-_.")


def safe_filename(base: str, existing: Iterable[str], default: str = "document", allow_unicode: bool = False) -> str:
    base = slugify(base, allow_unicode=allow_unicode) if base else slugify(default, allow_unicode=allow_unicode)
    candidate = base
    index = 1
    existing_set = set(existing)
    while candidate in existing_set:
        index += 1
        candidate = f"{base}-{index}"
    return candidate


def extract_pdf_title(path: Path) -> Optional[str]:
    try:
        reader = PdfReader(str(path))
        info = reader.metadata
        if info and info.title:
            return slugify(info.title, allow_unicode=True)
    except Exception as exc:  # pragma: no cover - best effort only
        LOGGER.debug("Failed to read PDF metadata for %s: %s", path, exc)
    return None


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.getLogger("playwright").setLevel(logging.WARNING)


def env_default(name: str, fallback: Optional[str] = None) -> Optional[str]:
    return os.environ.get(name, fallback)
