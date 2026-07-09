"""Procesador de Word (.docx) con python-docx.

Procesa: párrafos, tablas (recursivo), headers/footers, texto en runs.
Preserva el formato porque modifica el .text de cada run, no del párrafo entero.
"""
from __future__ import annotations

import glob
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from docx import Document
from docx.document import Document as _Document
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

from ..replacer import Replacer
from ._meta import extract_core_props, scrub_core_props

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


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


def _replace_in_paragraph(paragraph: Paragraph, replacer: Replacer) -> int:
    """Reemplaza en runs preservando formato.

    Si la entidad cruza varios runs, hace fallback a unificar runs del párrafo
    (pierde formato dentro del párrafo pero solo cuando es necesario).
    """
    full_text = paragraph.text
    new_text, n = replacer.apply(full_text)
    if n == 0:
        return 0

    # Intento 1: reemplazar dentro de cada run si encaja
    runs_changed = 0
    for run in paragraph.runs:
        run_new, run_n = replacer.apply(run.text)
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


def _extract_hidden_xml_texts(path: Path) -> list[str]:
    """Texto en partes que python-docx no expone: comentarios, notas al pie/fin,
    cuadros de texto y control de cambios (todo vive en <w:t> de varios XML)."""
    out: list[str] = []
    try:
        from lxml import etree
        with zipfile.ZipFile(str(path)) as z:
            names = z.namelist()
            wanted = [n for n in names if n.startswith("word/")
                      and (n in ("word/comments.xml", "word/footnotes.xml", "word/endnotes.xml")
                           or n.startswith("word/header") or n.startswith("word/footer"))]
            for n in wanted:
                try:
                    tree = etree.fromstring(z.read(n))
                    for t in tree.iter("{%s}t" % _W_NS):
                        if t.text and t.text.strip():
                            out.append(t.text)
                except Exception:
                    continue
    except Exception:
        pass
    return out


def extract_text(path: Path) -> list[str]:
    doc = Document(str(path))
    texts: list[str] = []
    texts.extend(extract_core_props(doc.core_properties, "core"))
    for p in _iter_paragraphs(doc):
        if p.text.strip():
            texts.append(p.text)
    for section in doc.sections:
        for hf in (section.header, section.footer):
            for p in hf.paragraphs:
                if p.text.strip():
                    texts.append(p.text)
    texts.extend(_extract_hidden_xml_texts(path))
    return texts


def _sweep_hidden_xml(path: Path, replacer: Replacer) -> None:
    """Reemplaza en TODOS los <w:t> de las partes que python-docx no toca
    (comentarios, notas, cuadros de texto, control de cambios) y en las URLs de
    hipervínculos (document.xml.rels). Trabaja a nivel ZIP/XML.

    Es idempotente sobre el cuerpo (ya reemplazado por python-docx) y DEFENSIVO:
    ante cualquier error deja el .docx tal cual lo dejó python-docx (no corrompe).
    """
    tmp = None
    try:
        from lxml import etree
        tmp = tempfile.mkdtemp()
        with zipfile.ZipFile(str(path)) as z:
            z.extractall(tmp)
        wdir = os.path.join(tmp, "word")
        if not os.path.isdir(wdir):
            return
        xml_files: list[str] = []
        for fn in ("document.xml", "comments.xml", "footnotes.xml", "endnotes.xml"):
            p = os.path.join(wdir, fn)
            if os.path.exists(p):
                xml_files.append(p)
        xml_files += glob.glob(os.path.join(wdir, "header*.xml"))
        xml_files += glob.glob(os.path.join(wdir, "footer*.xml"))
        for xf in xml_files:
            try:
                tree = etree.parse(xf)
                changed = False
                for t in tree.iter("{%s}t" % _W_NS):
                    if t.text:
                        new, n = replacer.apply(t.text)
                        if n > 0:
                            t.text = new
                            changed = True
                if changed:
                    tree.write(xf, xml_declaration=True, encoding="UTF-8", standalone=True)
            except Exception:
                continue
        # URLs de hipervínculos (query params con nombres)
        rels = os.path.join(wdir, "_rels", "document.xml.rels")
        if os.path.exists(rels):
            try:
                tree = etree.parse(rels)
                changed = False
                for rel in tree.iter("{%s}Relationship" % _REL_NS):
                    tgt = rel.get("Target")
                    if tgt:
                        new, n = replacer.apply(tgt)
                        if n > 0:
                            rel.set("Target", new)
                            changed = True
                if changed:
                    tree.write(rels, xml_declaration=True, encoding="UTF-8", standalone=True)
            except Exception:
                pass
        # Reempaquetar (arcnames con '/' — requisito de OOXML)
        tmp_zip = str(path) + ".tmp"
        with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _dirs, files in os.walk(tmp):
                for f in files:
                    fp = os.path.join(root, f)
                    arc = os.path.relpath(fp, tmp).replace(os.sep, "/")
                    z.write(fp, arc)
        shutil.move(tmp_zip, str(path))
    except Exception:
        # No corromper: si algo falla, el .docx de python-docx queda intacto.
        pass
    finally:
        if tmp:
            try:
                shutil.rmtree(tmp)
            except Exception:
                pass


def apply_replacements(src: Path, mapping: dict[str, str], dst: Path) -> None:
    replacer = Replacer(mapping)
    doc = Document(str(src))
    for p in _iter_paragraphs(doc):
        _replace_in_paragraph(p, replacer)
    for section in doc.sections:
        for hf in (section.header, section.footer):
            for p in hf.paragraphs:
                _replace_in_paragraph(p, replacer)
            for table in hf.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            _replace_in_paragraph(p, replacer)
    # Metadatos (autor/título/...): identidad → vacío, descriptivos → mapping
    scrub_core_props(doc.core_properties, replacer, "core")
    doc.save(str(dst))
    # Partes ocultas (comentarios, notas, cuadros de texto, control de cambios,
    # URLs de hipervínculos) que python-docx no expone.
    _sweep_hidden_xml(dst, replacer)
