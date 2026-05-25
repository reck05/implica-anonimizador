"""Procesador de PowerPoint (.pptx) con python-pptx.

Procesa: text frames en shapes, tablas, notas de speaker.
Preserva formato editando .text de cada run.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation

from ..replacer import replace_in_text


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


def _replace_in_text_frame(tf, mapping: dict[str, str]) -> int:
    total = 0
    for paragraph in tf.paragraphs:
        full = "".join(r.text for r in paragraph.runs)
        new, n = replace_in_text(full, mapping)
        if n == 0:
            continue
        total += n
        # Intento por run
        runs_changed = 0
        for run in paragraph.runs:
            run_new, run_n = replace_in_text(run.text, mapping)
            if run_n > 0:
                run.text = run_new
                runs_changed += run_n
        if runs_changed < n and paragraph.runs:
            paragraph.runs[0].text = new
            for r in paragraph.runs[1:]:
                r.text = ""
    return total


def extract_text(path: Path) -> list[str]:
    prs = Presentation(str(path))
    texts: list[str] = []
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
    prs = Presentation(str(src))
    for slide in prs.slides:
        for shape in slide.shapes:
            for tf in _iter_text_frames(shape):
                _replace_in_text_frame(tf, mapping)
        if slide.has_notes_slide:
            _replace_in_text_frame(slide.notes_slide.notes_text_frame, mapping)
    prs.save(str(dst))
