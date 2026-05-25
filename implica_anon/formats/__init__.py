from pathlib import Path
from typing import Callable

from . import excel, word, pptx as pptx_mod, pdf

EXTRACTORS: dict[str, Callable[[Path], list[str]]] = {
    ".xlsx": excel.extract_text,
    ".xlsm": excel.extract_text,
    ".docx": word.extract_text,
    ".pptx": pptx_mod.extract_text,
    ".pdf": pdf.extract_text,
}

REPLACERS: dict[str, Callable[[Path, dict[str, str], Path], None]] = {
    ".xlsx": excel.apply_replacements,
    ".xlsm": excel.apply_replacements,
    ".docx": word.apply_replacements,
    ".pptx": pptx_mod.apply_replacements,
    ".pdf": pdf.apply_replacements,
}


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in EXTRACTORS


def extract_text(path: Path) -> list[str]:
    return EXTRACTORS[path.suffix.lower()](path)


def apply_replacements(src: Path, mapping: dict[str, str], dst: Path) -> None:
    REPLACERS[src.suffix.lower()](src, mapping, dst)
