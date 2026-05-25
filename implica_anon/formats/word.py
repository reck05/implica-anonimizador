"""Procesador de Word (.docx) con python-docx.

Procesa: párrafos, tablas (recursivo), headers/footers, texto en runs.
Preserva el formato porque modifica el .text de cada run, no del párrafo entero.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.document import Document as _Document
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

from ..replacer import replace_in_text


def _iter_paragraphs(parent) -> list[Paragraph]:
    """Itera párrafos en un Document/_Cell, incluyendo dentro de tablas anidadas."""
    if isinstance(parent, _Document):
        paragraphs = list(parent.paragraphs)
        tables = parent.tables
    elif isinstance(parent, _Cell):
        paragraphs = list(parent.paragraphs)
        tables = parent.tables
    else:
        return []

    for table in tables:
        for row in table.rows:
            for cell in row.cells:
                paragraphs.extend(_iter_paragraphs(cell))
    return paragraphs


def _replace_in_paragraph(paragraph: Paragraph, mapping: dict[str, str]) -> int:
    """Reemplaza en runs preservando formato.

    Si la entidad cruza varios runs, hace fallback a unificar runs del párrafo
    (pierde formato dentro del párrafo pero solo cuando es necesario).
    """
    full_text = paragraph.text
    new_text, n = replace_in_text(full_text, mapping)
    if n == 0:
        return 0

    # Intento 1: reemplazar dentro de cada run si encaja
    runs_changed = 0
    for run in paragraph.runs:
        run_new, run_n = replace_in_text(run.text, mapping)
        if run_n > 0:
            run.text = run_new
            runs_changed += run_n

    # Si los reemplazos por run no cubren el total, la entidad cruzaba runs.
    # Hacemos fallback: poner todo el texto en el primer run y vaciar los demás.
    if runs_changed < n:
        if paragraph.runs:
            paragraph.runs[0].text = new_text
            for r in paragraph.runs[1:]:
                r.text = ""
        else:
            paragraph.text = new_text

    return n


def extract_text(path: Path) -> list[str]:
    doc = Document(str(path))
    texts: list[str] = []
    for p in _iter_paragraphs(doc):
        if p.text.strip():
            texts.append(p.text)
    for section in doc.sections:
        for hf in (section.header, section.footer):
            for p in hf.paragraphs:
                if p.text.strip():
                    texts.append(p.text)
    return texts


def apply_replacements(src: Path, mapping: dict[str, str], dst: Path) -> None:
    doc = Document(str(src))
    for p in _iter_paragraphs(doc):
        _replace_in_paragraph(p, mapping)
    for section in doc.sections:
        for hf in (section.header, section.footer):
            for p in hf.paragraphs:
                _replace_in_paragraph(p, mapping)
            for table in hf.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            _replace_in_paragraph(p, mapping)
    doc.save(str(dst))
