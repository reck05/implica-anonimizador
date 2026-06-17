"""Procesador de PowerPoint (.pptx) con python-pptx.

Procesa: text frames en shapes, tablas, notas de speaker, hipervínculos y
metadatos del documento (autor/título/etc.).
Preserva formato editando .text de cada run.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation

from ..replacer import Replacer
from ._meta import extract_core_props, scrub_core_props


def _iter_text_frames(shape):
    """Yield text_frames recursivos (groups, tables, etc.)."""
    if shape.has_text_frame:
        yield shape.text_frame
    if shape.has_table:
        for row in shape.table.rows:
            for cell in row.cells:
                yield cell.text_frame
    if shape.shape_type == 6:  # GROUP
        for sub in shape.shapes:
            yield from _iter_text_frames(sub)


def _replace_in_text_frame(tf, replacer: Replacer) -> int:
    total = 0
    for paragraph in tf.paragraphs:
        full = "".join(r.text for r in paragraph.runs)
        new, n = replacer.apply(full)
        if n == 0:
            # Aun sin cambios en el texto visible, puede haber un hipervínculo
            # con un nombre en la URL.
            _replace_run_hyperlinks(paragraph, replacer)
            continue
        total += n
        # Intento por run
        runs_changed = 0
        for run in paragraph.runs:
            run_new, run_n = replacer.apply(run.text)
            if run_n > 0:
                run.text = run_new
                runs_changed += run_n
            _replace_run_hyperlinks_single(run, replacer)
        if runs_changed < n and paragraph.runs:
            paragraph.runs[0].text = new
            for r in paragraph.runs[1:]:
                r.text = ""
    return total


def _replace_run_hyperlinks_single(run, replacer: Replacer) -> None:
    """Reemplaza en la URL del hipervínculo de un run (p.ej. ?cliente=GlobalMenta)."""
    try:
        hl = run.hyperlink
        if hl is not None and hl.address:
            new_addr, n = replacer.apply(hl.address)
            if n > 0:
                hl.address = new_addr
    except Exception:
        pass


def _replace_run_hyperlinks(paragraph, replacer: Replacer) -> None:
    for run in paragraph.runs:
        _replace_run_hyperlinks_single(run, replacer)


def extract_text(path: Path) -> list[str]:
    prs = Presentation(str(path))
    texts: list[str] = []
    texts.extend(extract_core_props(prs.core_properties, "core"))
    for slide in prs.slides:
        for shape in slide.shapes:
            for tf in _iter_text_frames(shape):
                for p in tf.paragraphs:
                    line = "".join(r.text for r in p.runs)
                    if line.strip():
                        texts.append(line)
        if slide.has_notes_slide:
            notes_tf = slide.notes_slide.notes_text_frame
            for p in notes_tf.paragraphs:
                line = "".join(r.text for r in p.runs)
                if line.strip():
                    texts.append(line)
    return texts


def apply_replacements(src: Path, mapping: dict[str, str], dst: Path) -> None:
    replacer = Replacer(mapping)
    prs = Presentation(str(src))
    for slide in prs.slides:
        for shape in slide.shapes:
            for tf in _iter_text_frames(shape):
                _replace_in_text_frame(tf, replacer)
        if slide.has_notes_slide:
            _replace_in_text_frame(slide.notes_slide.notes_text_frame, replacer)
    scrub_core_props(prs.core_properties, replacer, "core")
    prs.save(str(dst))
