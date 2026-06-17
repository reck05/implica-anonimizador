"""Procesador de Excel (.xlsx/.xlsm) con openpyxl.

Procesa: valores de celdas (string), nombres de hojas, comentarios, headers/footers.
NO procesa fórmulas (intencionalmente — son lógica, no datos sensibles).
"""
from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook

from ..replacer import Replacer, replace_in_text
from ..detectors import CIF_RE, NIF_RE, IBAN_RE
from ._meta import extract_core_props, scrub_core_props


def _is_structured_id(s: str) -> bool:
    """¿La celda es un CIF/NIF/IBAN? Son identificadores que SÍ hay que anonimizar,
    así que nunca deben filtrarse como 'artefacto'."""
    return bool(CIF_RE.fullmatch(s) or NIF_RE.fullmatch(s) or IBAN_RE.fullmatch(s.replace(" ", "")))


def _looks_like_formula_or_ref(text: str) -> bool:
    """True si el texto es una fórmula Excel, una referencia o un fragmento de fórmula
    roto por un salto de línea/separador."""
    if not text:
        return False
    s = text.strip()
    # Nunca descartar identificadores (CIF/NIF/IBAN): son datos a anonimizar.
    if _is_structured_id(s):
        return False
    if s.startswith("="):
        return True
    # Funciones Excel comunes (con paréntesis sin cerrar = fragmento roto)
    if re.search(r"\b(SUMIFS|SUMIF|SUM|VLOOKUP|HLOOKUP|INDEX|MATCH|IF|IFERROR|SUBSTITUTE|CONCAT|CONCATENATE|TEXT|ROUND|AVERAGE)\s*\(", s, re.IGNORECASE):
        return True
    # Referencias estilo "Hoja!$A:$A" o "Hoja!$A123"
    if re.search(r"!\$?[A-Z]+\$?\d*(:\$?[A-Z]+\$?\d*)?", s):
        return True
    # Operaciones aritméticas sobre referencias: AA34+BJ34, A10+BL15, M27+AV27, J6+AS6
    if re.fullmatch(r"\$?[A-Z]{1,3}\$?\d+\s*[+\-*/]\s*\$?[A-Z]{1,3}\$?\d+", s):
        return True
    # Sólo una referencia de celda: A10, AB141, AQ9992
    if re.fullmatch(r"\$?[A-Z]{1,3}\$?\d+", s):
        return True
    # Ratio: muchos paréntesis sin balancear o muchos signos +/$
    open_p = s.count("(")
    close_p = s.count(")")
    if abs(open_p - close_p) >= 2:
        return True
    return False


MAX_ROWS_PER_SHEET = 100_000  # protección contra Excels enormes
MAX_CELL_LENGTH = 5000  # texto muy largo en una celda = probablemente basura/fórmula
MAX_FRAGMENTS = 500_000  # protección de memoria global


def extract_text(path: Path) -> list[str]:
    """Extrae texto de un Excel robustamente.

    Estrategia:
    1. data_only=True para leer valores calculados, no fórmulas crudas.
    2. read_only=True para evitar cargar todo en RAM.
    3. Try/except por hoja: si una hoja falla, continuamos con las demás.
    4. Límites de seguridad para no agotar memoria.
    5. Filtra fórmulas, referencias y celdas anormalmente largas.
    """
    texts: list[str] = []
    try:
        wb = load_workbook(filename=str(path), data_only=True, read_only=True)
    except Exception as e:
        # Si falla data_only=True, intentamos sin él (lee fórmulas crudas, las filtramos)
        try:
            wb = load_workbook(filename=str(path), data_only=False, read_only=True)
        except Exception:
            raise RuntimeError(f"No se pudo abrir el Excel: {e}") from e

    try:
        # Metadatos del libro (autor/título/asunto...) — fuga silenciosa si no se ven.
        try:
            texts.extend(extract_core_props(wb.properties, "openpyxl"))
        except Exception:
            pass
        for ws in wb.worksheets:
            try:
                texts.append(ws.title)
                row_count = 0
                for row in ws.iter_rows(values_only=True):
                    row_count += 1
                    if row_count > MAX_ROWS_PER_SHEET:
                        break
                    if len(texts) > MAX_FRAGMENTS:
                        break
                    for cell in row:
                        if not isinstance(cell, str):
                            continue
                        s = cell.strip()
                        if not s or len(s) > MAX_CELL_LENGTH:
                            continue
                        if _looks_like_formula_or_ref(s):
                            continue
                        texts.append(s)
                if len(texts) > MAX_FRAGMENTS:
                    break
            except Exception:
                # Una hoja corrupta no debe tumbar la herramienta — saltar y seguir
                continue
    finally:
        try:
            wb.close()
        except Exception:
            pass
    return texts


def apply_replacements(src: Path, mapping: dict[str, str], dst: Path) -> None:
    # Compilar el patrón UNA vez y reutilizarlo en todas las celdas.
    replacer = Replacer(mapping)
    wb = load_workbook(filename=str(src), data_only=False)
    try:
        for ws in wb.worksheets:
            new_title, _ = replacer.apply(ws.title)
            if new_title != ws.title:
                # Excel limita a 31 chars el nombre de hoja
                ws.title = new_title[:31]

            for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str) and cell.value:
                        new_val, n = replacer.apply(cell.value)
                        if n > 0:
                            cell.value = new_val
                    # Hipervínculo de la celda (la URL puede llevar un nombre)
                    try:
                        hl = cell.hyperlink
                        if hl is not None and getattr(hl, "target", None):
                            new_t, nt = replacer.apply(hl.target)
                            if nt > 0:
                                hl.target = new_t
                    except Exception:
                        pass
                    # Comentario de la celda
                    try:
                        cmt = cell.comment
                        if cmt is not None and cmt.text:
                            new_c, nc = replacer.apply(cmt.text)
                            if nc > 0:
                                cmt.text = new_c
                    except Exception:
                        pass

            # Validaciones de datos (listas desplegables embebidas pueden llevar
            # nombres: "Mercadona,Carrefour,..."). Las referencias ($A$1:$A$9) se saltan.
            try:
                for dv in ws.data_validations.dataValidation:
                    for fattr in ("formula1", "formula2"):
                        f = getattr(dv, fattr, None)
                        if isinstance(f, str) and f.strip() and not f.strip().startswith("$"):
                            new_f, nf = replacer.apply(f)
                            if nf > 0:
                                setattr(dv, fattr, new_f)
            except Exception:
                pass

            # Títulos de gráficos
            try:
                for chart in getattr(ws, "_charts", []) or []:
                    _replace_in_chart_title(chart, replacer)
            except Exception:
                pass

            # Headers/footers
            for hf_attr in ("oddHeader", "oddFooter", "evenHeader", "evenFooter"):
                hf = getattr(ws.HeaderFooter, hf_attr, None)
                if hf is None:
                    continue
                for part in ("left", "center", "right"):
                    section = getattr(hf, part, None)
                    if section and getattr(section, "text", None):
                        new_text, n = replacer.apply(section.text)
                        if n > 0:
                            section.text = new_text

        # Metadatos del libro (autor/título/asunto...): identidad → vacío, resto → mapping
        try:
            scrub_core_props(wb.properties, replacer, "openpyxl")
        except Exception:
            pass

        wb.save(str(dst))
    finally:
        wb.close()


def _replace_in_chart_title(chart, replacer: Replacer) -> None:
    """Reemplaza en el título de un gráfico (openpyxl ChartBase). Defensivo:
    la estructura del título varía (texto plano o rich text con runs)."""
    try:
        title = getattr(chart, "title", None)
        if title is None:
            return
        tx = getattr(title, "tx", None)
        if tx is None:
            return
        rich = getattr(tx, "rich", None)
        if rich is None:
            return
        for para in getattr(rich, "p", []) or []:
            for run in getattr(para, "r", []) or []:
                t = getattr(run, "t", None)
                if isinstance(t, str) and t:
                    new_t, n = replacer.apply(t)
                    if n > 0:
                        run.t = new_t
    except Exception:
        pass
