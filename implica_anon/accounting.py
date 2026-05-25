"""Detector específico para libros contables españoles (sumas y saldos, mayor).

Estrategia:
- Identifica si una hoja parece un libro contable buscando columnas como
  'Cuenta', 'Debe', 'Haber', 'Saldo'.
- Lee fila a fila: si el código de cuenta empieza por un prefijo PGC de
  terceros (430-433 clientes, 410-411 proveedores, etc.), la DESCRIPCIÓN
  es por definición una entidad a anonimizar — sin necesidad de NER.

Esto da 100% de cobertura para esos prefijos y cero falsos positivos en
cuentas PGC genéricas (las que no empiezan por esos prefijos).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from openpyxl import load_workbook

# Prefijos PGC y su categoría
PGC_PREFIXES: list[tuple[str, str]] = [
    # (prefijo, kind)
    # Clientes
    ("430", "CLIENTE"),
    ("431", "CLIENTE"),
    ("432", "CLIENTE"),
    ("433", "CLIENTE"),
    ("434", "CLIENTE"),
    ("435", "CLIENTE"),
    ("436", "CLIENTE"),
    ("437", "CLIENTE"),
    # Proveedores
    ("400", "PROVEEDOR"),
    ("401", "PROVEEDOR"),
    ("403", "PROVEEDOR"),
    ("404", "PROVEEDOR"),
    ("405", "PROVEEDOR"),
    ("406", "PROVEEDOR"),
    # Acreedores
    ("410", "PROVEEDOR"),
    ("411", "PROVEEDOR"),
    ("419", "PROVEEDOR"),
    # Deudores varios
    ("440", "DEUDOR"),
    ("441", "DEUDOR"),
    ("446", "DEUDOR"),
    ("449", "DEUDOR"),
    # Personal
    ("460", "PERSONA"),
    ("465", "PERSONA"),
    # Empresas del grupo y asociadas
    ("450", "GRUPO"),
    ("451", "GRUPO"),
    ("452", "GRUPO"),
    ("453", "GRUPO"),
    ("550", "GRUPO"),
    ("551", "GRUPO"),
    # Bancos
    ("572", "BANCO"),
    ("573", "BANCO"),
    ("574", "BANCO"),
    ("575", "BANCO"),
    ("576", "BANCO"),
    ("520", "BANCO"),  # deudas con entidades de crédito
]

# Cuentas que NO deben anonimizarse (administraciones públicas, HP, SS)
PGC_PUBLIC_PREFIXES = ("470", "471", "472", "473", "475", "476", "477", "479")


def classify_account(code: str) -> str | None:
    """Devuelve la categoría PGC del código, o None si no es de terceros."""
    if not code:
        return None
    code = str(code).strip()
    # Saltar admins públicas
    if any(code.startswith(p) for p in PGC_PUBLIC_PREFIXES):
        return None
    for prefix, kind in PGC_PREFIXES:
        if code.startswith(prefix):
            return kind
    return None


# Sinónimos de columnas (case-insensitive). Cubre exports de Contaplus, Sage, A3, Holded, etc.
COLUMN_HINTS_ACCOUNT = (
    "cuenta", "código", "codigo", "cuenta contable", "cta", "subcuenta",
    "account", "código cuenta", "núm cuenta", "num cuenta", "n cuenta",
    "nº cuenta", "n.º cuenta", "código contable",
)
COLUMN_HINTS_DESCRIPTION = (
    "descripción", "descripcion", "concepto", "nombre", "denominación", "denominacion",
    "title", "description", "razón social", "razon social", "titular",
    "nombre cuenta", "nombre cta", "subcuenta nombre",
)
COLUMN_HINTS_NUMERIC = (
    "debe", "haber", "saldo", "saldo inicial", "saldo final", "saldo anterior",
    "saldo actual", "saldo periodo", "importe", "balance", "debit", "credit",
    "movimiento", "mvto", "mvto. debe", "mvto. haber", "movto debe", "movto haber",
    "acumulado debe", "acumulado haber", "total debe", "total haber",
)


@dataclass
class AccountingEntity:
    """Una entidad encontrada en una fila contable."""
    code: str
    description: str
    kind: str  # CLIENTE | PROVEEDOR | DEUDOR | PERSONA | GRUPO | BANCO
    sheet: str
    row: int


@dataclass
class AccountingScanResult:
    is_accounting: bool
    sheet_findings: dict[str, dict] = field(default_factory=dict)
    entities: list[AccountingEntity] = field(default_factory=list)


def _normalize_header(value) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _find_header_row(ws, max_scan: int = 40) -> tuple[int | None, int | None, int | None]:
    """Busca la fila de cabecera (Cuenta / Descripción / [Debe/Haber/Saldo]).

    Escanea las primeras 40 filas (no 20) porque muchos exports tienen filas de
    cabecera con info de empresa, periodo, etc. antes de la tabla.

    Devuelve (fila, col_cuenta, col_descripcion) o (None, None, None).
    """
    max_row = ws.max_row if ws.max_row else max_scan
    for r in range(1, min(max_scan, max_row) + 1):
        col_account = None
        col_desc = None
        has_numeric = False
        for c in range(1, ws.max_column + 1):
            v = _normalize_header(ws.cell(row=r, column=c).value)
            if not v:
                continue
            if col_account is None and any(h == v or h in v for h in COLUMN_HINTS_ACCOUNT):
                col_account = c
            if col_desc is None and any(h == v or h in v for h in COLUMN_HINTS_DESCRIPTION):
                col_desc = c
            if any(h == v or h in v for h in COLUMN_HINTS_NUMERIC):
                has_numeric = True
        if col_account and col_desc and has_numeric:
            return r, col_account, col_desc
    return None, None, None


def _detect_by_content(ws, max_scan: int = 100) -> tuple[int | None, int | None, int | None]:
    """Fallback: si no hay headers reconocibles, busca columnas por contenido.

    Si una columna tiene muchos valores con patrón de código PGC (8-10 dígitos
    empezando por 4, 5, 6 o 7), asumimos que es la columna 'cuenta' y la
    siguiente con texto es 'descripción'.
    """
    if not ws.max_row or not ws.max_column:
        return None, None, None

    # Contar cuántas celdas en cada columna parecen códigos PGC
    pgc_pattern = re.compile(r"^\d{3,10}$")
    col_score: dict[int, int] = {}
    for r in range(1, min(max_scan, ws.max_row) + 1):
        for c in range(1, ws.max_column + 1):
            val = ws.cell(row=r, column=c).value
            if val is None:
                continue
            sval = str(val).strip()
            if pgc_pattern.fullmatch(sval) and sval[0] in "456":
                col_score[c] = col_score.get(c, 0) + 1

    if not col_score:
        return None, None, None

    # Columna con más matches = cuenta
    col_account = max(col_score, key=col_score.get)
    if col_score[col_account] < 5:
        return None, None, None

    # Columna descripción = siguiente columna con texto en muchas filas
    col_desc = None
    for c in range(col_account + 1, min(col_account + 5, ws.max_column + 1)):
        text_count = 0
        for r in range(1, min(max_scan, ws.max_row) + 1):
            val = ws.cell(row=r, column=c).value
            if isinstance(val, str) and val.strip() and not pgc_pattern.fullmatch(val.strip()):
                text_count += 1
        if text_count >= 5:
            col_desc = c
            break

    if col_desc is None:
        return None, None, None

    # No tenemos fila de cabecera real — usamos fila 1
    return 1, col_account, col_desc


def scan_workbook(path: Path) -> AccountingScanResult:
    """Escanea un .xlsx en busca de hojas que parezcan libros contables.

    No carga todo en memoria — usa read_only=True para hojas grandes.
    """
    result = AccountingScanResult(is_accounting=False)
    try:
        wb = load_workbook(filename=str(path), data_only=True, read_only=True)
    except Exception:
        try:
            wb = load_workbook(filename=str(path), data_only=False, read_only=True)
        except Exception:
            return result
    try:
        for ws in wb.worksheets:
            try:
                header_row, col_account, col_desc = _find_header_row(ws)
                detection_mode = "headers"
                if not header_row:
                    header_row, col_account, col_desc = _detect_by_content(ws)
                    detection_mode = "content"
                if not header_row:
                    continue

                entities: list[AccountingEntity] = []
                n_rows = 0
                n_matched = 0
                max_rows = 100_000  # protección
                for r in ws.iter_rows(min_row=header_row + 1, values_only=False):
                    if n_rows >= max_rows:
                        break
                    cell_account = r[col_account - 1]
                    cell_desc = r[col_desc - 1]
                    code = cell_account.value
                    desc = cell_desc.value
                    if code is None and desc is None:
                        continue
                    n_rows += 1
                    code_str = "" if code is None else str(code).strip()
                    desc_str = "" if desc is None else str(desc).strip()
                    kind = classify_account(code_str)
                    if kind and desc_str:
                        entities.append(
                            AccountingEntity(
                                code=code_str,
                                description=desc_str,
                                kind=kind,
                                sheet=ws.title,
                                row=cell_account.row,
                            )
                        )
                        n_matched += 1

                if entities:
                    result.is_accounting = True
                    result.sheet_findings[ws.title] = {
                        "header_row": header_row,
                        "col_account": col_account,
                        "col_desc": col_desc,
                        "rows_scanned": n_rows,
                        "rows_matched": n_matched,
                        "mode": detection_mode,
                    }
                    result.entities.extend(entities)
            except Exception:
                # Una hoja problemática no debe tumbar todo
                continue
    finally:
        try:
            wb.close()
        except Exception:
            pass
    return result


# --- Limpieza y normalización de descripciones contables ---

# Patrones para extraer el nombre "neto" de la descripción
CIF_IN_DESC_RE = re.compile(r"[,;\s]*[\(\[]?\s*(?:CIF[:\s]*)?[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]\s*[\)\]]?", re.IGNORECASE)
ANTICIPO_RE = re.compile(r"^\s*(?:Anticipo|Préstamo|Préstamo a|Crédito a|Crédito)\s+", re.IGNORECASE)
SERVPRO_RE = re.compile(r"^\s*Servicios profesionales\s+", re.IGNORECASE)
# IBAN tras guion, referencia tras "ref", o "C/C ..."
BANK_REF_RE = re.compile(r"\s*-\s*ES\d{2}[\d\s]*$|\s+ref[\.\s][^.]*$|\s+c/c[^.]*$", re.IGNORECASE)


def clean_description(kind: str, desc: str) -> str:
    """Extrae el nombre limpio de la descripción según el tipo de cuenta."""
    text = desc.strip()

    # Quitar CIF entre paréntesis o tras coma
    text = CIF_IN_DESC_RE.sub("", text).strip(" ,;-")

    if kind == "PERSONA":
        text = ANTICIPO_RE.sub("", text)
    elif kind == "BANCO":
        text = BANK_REF_RE.sub("", text)

    # 623xxxxx "Servicios profesionales X" → X
    text = SERVPRO_RE.sub("", text)

    return text.strip()


# --- Agrupación de entidades en clusters listos para mapping ---

def entities_to_buckets(
    entities: Iterable[AccountingEntity],
) -> dict[str, list[tuple[str, str, int]]]:
    """Agrupa por kind y devuelve (nombre_limpio, original_completo, count)."""
    from collections import Counter, defaultdict
    by_kind: dict[str, Counter] = defaultdict(Counter)
    for e in entities:
        cleaned = clean_description(e.kind, e.description)
        if cleaned:
            by_kind[e.kind][(cleaned, e.description)] += 1
    out: dict[str, list[tuple[str, str, int]]] = {}
    for kind, counter in by_kind.items():
        out[kind] = [
            (cleaned, original, count)
            for (cleaned, original), count in counter.most_common()
        ]
    return out
