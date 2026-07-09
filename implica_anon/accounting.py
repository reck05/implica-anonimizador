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


def _normalize_account_code(code) -> str:
    """Normaliza el código de cuenta. Excel suele guardarlo como número, así que
    openpyxl devuelve int/float: '4300001.0' → '4300001'."""
    s = str(code).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def classify_account(code: str) -> str | None:
    """Devuelve la categoría PGC del código, o None si no es de terceros."""
    if code is None or code == "":
        return None
    code = _normalize_account_code(code)
    # Códigos demasiado cortos (1-2 dígitos) no son subcuentas de terceros fiables.
    if len(code) < 3:
        return None
    # Saltar admins públicas
    if any(code.startswith(p) for p in PGC_PUBLIC_PREFIXES):
        return None
    for prefix, kind in PGC_PREFIXES:
        if code.startswith(prefix):
            return kind
    return None


# Sinónimos de columnas (case-insensitive). Cubre exports de Contaplus, Sage, A3,
# Holded, SAP, etc. — distintos software nombran las columnas de formas muy diversas.
COLUMN_HINTS_ACCOUNT = (
    "cuenta", "código", "codigo", "cuenta contable", "cta", "subcuenta",
    "account", "código cuenta", "núm cuenta", "num cuenta", "n cuenta",
    "nº cuenta", "n.º cuenta", "código contable",
    # Variantes Contaplus/Sage/A3/SAP
    "num. cta", "n. cta", "cod. contable", "cód.", "cód contable", "cod contable",
    "n. cuenta", "número de cuenta", "numero de cuenta", "g/l", "gl account",
    "nº cta", "cta contable", "código de cuenta", "codigo de cuenta",
)
COLUMN_HINTS_DESCRIPTION = (
    "descripción", "descripcion", "concepto", "nombre", "denominación", "denominacion",
    "title", "description", "razón social", "razon social", "titular",
    "nombre cuenta", "nombre cta", "subcuenta nombre",
    # Variantes por software / legislación
    "tercero", "terceros", "contraparte", "acreedor", "acreedora", "deudor",
    "deudora", "titular cuenta", "nombre tercero", "razón social tercero",
    "concepto/descripción", "detalle",
)
COLUMN_HINTS_NUMERIC = (
    "debe", "haber", "saldo", "saldo inicial", "saldo final", "saldo anterior",
    "saldo actual", "saldo periodo", "importe", "balance", "debit", "credit",
    "movimiento", "mvto", "mvto. debe", "mvto. haber", "movto debe", "movto haber",
    "acumulado debe", "acumulado haber", "total debe", "total haber",
)

# --- Columnas de NOMBRE (no PGC): la celda completa ES la entidad ---
# Caso: Excels tabulares (listados de clientes, extractos, CRM exportado) con una
# columna claramente etiquetada "Cliente"/"Proveedor"/"Razón social" pero SIN
# códigos de cuenta PGC. Aquí la cabecera ya nos dice que toda la columna son
# nombres → tomamos el valor COMPLETO de la celda como entidad, sin pasar por
# spaCy (que recorta mal "LA SIRENA SL" → "SIRENA SL" y se salta los cortos).
# El orden importa: las pistas específicas (cliente/proveedor) ganan a "nombre".
NAME_COLUMN_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("cliente", "clientes"), "CLIENTE"),
    (("proveedor", "proveedores", "acreedor", "acreedores"), "PROVEEDOR"),
    (("deudor", "deudores"), "DEUDOR"),
    (("razón social", "razon social", "denominación social", "denominacion social",
      "denominación", "denominacion", "titular", "nombre fiscal",
      "razón social", "contraparte"), "ORG"),
    (("nombre", "empresa", "sociedad", "entidad", "razón", "razon"), "ORG"),
]

# Si la cabecera contiene alguna de estas, NO es columna de nombre (es código,
# tipo, fecha, importe, identificador o dato de contacto estructurado).
NAME_COLUMN_EXCLUDE = (
    "código", "codigo", "cod.", "cód.", " id", "id ", "nº", "n.º", "núm", "num",
    "tipo", "estado", "fecha", "importe", "saldo", "debe", "haber", "total",
    "teléfono", "telefono", "email", "correo", "cif", "nif", "iban",
    "dirección", "direccion", "postal", "población", "poblacion", "provincia",
    "país", "pais", "móvil", "movil", "cuenta",
)

# Valores genéricos de una columna de cliente/proveedor que NO son nombres reales.
NAME_COLUMN_GENERIC_VALUES = frozenset(s.lower() for s in [
    "varios", "vario", "cliente", "clientes", "proveedor", "proveedores",
    "cliente contado", "contado", "cliente genérico", "cliente generico",
    "clientes varios", "proveedores varios", "otros", "otro", "varios clientes",
    "sin nombre", "n/a", "na", "ninguno", "no aplica", "-", "—", "varios proveedores",
])


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


def _find_header_row(ws, max_scan: int = 100) -> tuple[int | None, int | None, int | None]:
    """Busca la fila de cabecera (Cuenta / Descripción / [Debe/Haber/Saldo]).

    Escanea las primeras 100 filas porque muchos exports (Sage/Contaplus/SAP)
    arrastran bloques largos de cabecera (empresa, periodo, logos, espacios)
    antes de la tabla real.

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

    # Contar cuántas celdas en cada columna parecen códigos PGC de terceros.
    # Patrón estricto: empieza por 4/5/6 y 8-10 dígitos (subcuenta real) → evita
    # confundir años (2024), referencias o fechas con códigos de cuenta.
    pgc_pattern = re.compile(r"^[456]\d{7,9}$")
    col_score: dict[int, int] = {}
    for r in range(1, min(max_scan, ws.max_row) + 1):
        for c in range(1, ws.max_column + 1):
            val = ws.cell(row=r, column=c).value
            if val is None:
                continue
            sval = _normalize_account_code(val)  # Excel guarda códigos como número
            if pgc_pattern.fullmatch(sval):
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


# Código + nombre en la MISMA celda: "4300001 GLOBAL MENTA SL" (Holded, exports
# manuales, mayores heredados). El código de cuenta y el nombre van juntos.
_COMBINED_RE = re.compile(r"^\s*(\d{6,10})\s+(.+\S)\s*$")
_COMBINED_PGC_RE = re.compile(r"^\s*[456]\d{5,9}\s+\S")


def _detect_combined_code_name(ws, max_scan: int = 100) -> tuple[int | None, int | None]:
    """Detecta una columna con 'código nombre' en la misma celda. Devuelve
    (fila_inicio, col) o (None, None)."""
    if not ws.max_row or not ws.max_column:
        return None, None
    col_score: dict[int, int] = {}
    for r in range(1, min(max_scan, ws.max_row) + 1):
        for c in range(1, ws.max_column + 1):
            val = ws.cell(row=r, column=c).value
            if isinstance(val, str) and _COMBINED_PGC_RE.match(val):
                col_score[c] = col_score.get(c, 0) + 1
    if not col_score:
        return None, None
    col = max(col_score, key=col_score.get)
    if col_score[col] < 5:
        return None, None
    return 1, col


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
                combined_col = None
                if not header_row:
                    # Último intento: 'código nombre' en la misma celda.
                    header_row, combined_col = _detect_combined_code_name(ws)
                    if header_row:
                        col_account = combined_col
                        col_desc = combined_col
                        detection_mode = "combined"
                if not header_row:
                    continue

                entities: list[AccountingEntity] = []
                n_rows = 0
                n_matched = 0
                max_rows = 100_000  # protección
                for r in ws.iter_rows(min_row=header_row + 1, values_only=False):
                    if n_rows >= max_rows:
                        break
                    if combined_col is not None:
                        # 'código nombre' juntos: separar la celda.
                        raw = r[combined_col - 1].value
                        n_rows += 1
                        m = _COMBINED_RE.match(str(raw)) if isinstance(raw, str) else None
                        if not m:
                            continue
                        code_str = _normalize_account_code(m.group(1))
                        desc_str = m.group(2).strip()
                        row_num = r[combined_col - 1].row
                    else:
                        cell_account = r[col_account - 1]
                        cell_desc = r[col_desc - 1]
                        code = cell_account.value
                        desc = cell_desc.value
                        if code is None and desc is None:
                            continue
                        n_rows += 1
                        code_str = "" if code is None else _normalize_account_code(code)
                        desc_str = "" if desc is None else str(desc).strip()
                        row_num = cell_account.row
                    kind = classify_account(code_str)
                    if kind and desc_str:
                        entities.append(
                            AccountingEntity(
                                code=code_str,
                                description=desc_str,
                                kind=kind,
                                sheet=ws.title,
                                row=row_num,
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


# --- Detección de columnas de nombre (Cliente/Proveedor/Razón social...) ---

def _name_header_kind(value) -> str | None:
    """Si la cabecera identifica una columna de NOMBRES de entidad, devuelve el
    kind (CLIENTE/PROVEEDOR/DEUDOR/ORG). Si no, None."""
    h = _normalize_header(value)
    if not h or len(h) > 60:
        return None
    if any(x in h for x in NAME_COLUMN_EXCLUDE):
        return None
    # "nombre" a secas o "nombre de X" genérico es ambiguo: puede ser una columna
    # de personas/contactos/proyectos, no de empresas. Solo lo aceptamos como
    # columna de nombre si además aparece cliente/proveedor/empresa/razón/fiscal.
    if h == "nombre" or (
        h.startswith("nombre de ")
        and not any(w in h for w in (
            "cliente", "proveedor", "empresa", "razón", "razon",
            "fiscal", "social", "deudor", "acreedor",
        ))
    ):
        return None
    for hints, kind in NAME_COLUMN_HINTS:
        if any(hint in h for hint in hints):
            return kind
    return None


def _find_name_columns(ws, max_scan: int = 40) -> tuple[int, dict[int, str]]:
    """Busca la fila de cabecera con MÁS columnas de nombre y devuelve
    (fila_cabecera, {col_idx: kind}). Si no hay ninguna, ({}, 0)."""
    best_row = 0
    best_cols: dict[int, str] = {}
    max_row = ws.max_row if ws.max_row else max_scan
    max_col = ws.max_column or 0
    for r in range(1, min(max_scan, max_row) + 1):
        cols: dict[int, str] = {}
        for c in range(1, max_col + 1):
            kind = _name_header_kind(ws.cell(row=r, column=c).value)
            if kind:
                cols[c] = kind
        if len(cols) > len(best_cols):
            best_cols = cols
            best_row = r
    return best_row, best_cols


def _is_anonymizable_name(s: str) -> bool:
    """True si el valor de una celda de columna-nombre parece un nombre real
    (no un genérico, una referencia, un identificador o un número)."""
    # Import diferido para evitar ciclo de imports a nivel de módulo.
    from .detectors import (
        GENERIC_STOPWORDS, _looks_like_excel_artifact, _is_document_ref,
        CIF_RE, NIF_RE, IBAN_RE,
    )
    if not s or len(s) < 2:
        return False
    low = s.lower()
    if low in NAME_COLUMN_GENERIC_VALUES or low in GENERIC_STOPWORDS:
        return False
    # Identificadores estructurados: los cubre el detector regex, no aquí.
    if CIF_RE.fullmatch(s) or NIF_RE.fullmatch(s) or IBAN_RE.fullmatch(s.replace(" ", "")):
        return False
    # Sólo números/fechas/símbolos
    if re.fullmatch(r"[\d.,/\-\s€$%]+", s):
        return False
    if _looks_like_excel_artifact(s) or _is_document_ref(s):
        return False
    return True


def scan_named_columns(path: Path, max_rows: int = 100_000) -> list[tuple[str, str]]:
    """Extrae nombres de columnas etiquetadas (Cliente/Proveedor/Razón social...).

    Toma la CELDA COMPLETA como entidad — resuelve el caso de Excels tabulares
    (no sumas y saldos PGC) donde spaCy recorta los nombres de varias palabras y
    se salta los cortos. Determinista: la cabecera es la autoridad.

    Devuelve [(texto, kind), ...] deduplicado por (texto, kind).
    """
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    try:
        wb = load_workbook(filename=str(path), data_only=True, read_only=True)
    except Exception:
        try:
            wb = load_workbook(filename=str(path), data_only=False, read_only=True)
        except Exception:
            return out
    try:
        for ws in wb.worksheets:
            try:
                header_row, name_cols = _find_name_columns(ws)
                if not name_cols:
                    continue
                n = 0
                for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
                    if n >= max_rows:
                        break
                    n += 1
                    for col_idx, kind in name_cols.items():
                        if col_idx - 1 >= len(row):
                            continue
                        val = row[col_idx - 1]
                        if not isinstance(val, str):
                            continue
                        s = val.strip()
                        if not _is_anonymizable_name(s):
                            continue
                        key = (s, kind)
                        if key not in seen:
                            seen.add(key)
                            out.append((s, kind))
            except Exception:
                # Una hoja problemática no debe tumbar la herramienta.
                continue
    finally:
        try:
            wb.close()
        except Exception:
            pass
    return out


def _redact_ids(s: str) -> str:
    """Enmascara CIF/NIF/IBAN en una celda dejando solo los últimos dígitos, para
    que el contexto siga distinguiendo entidades sin exponer el identificador
    fiscal completo (que se muestra en pantalla y podría cachearse)."""
    from .detectors import CIF_RE, NIF_RE, IBAN_RE
    bare = s.replace(" ", "")
    if CIF_RE.fullmatch(s) or NIF_RE.fullmatch(s):
        return "···" + s[-3:]
    if IBAN_RE.fullmatch(bare):
        return "ES··" + bare[-4:]
    return s


def row_contexts(
    path: Path,
    wanted_lower: set[str],
    *,
    max_rows: int = 100_000,
    max_len: int = 120,
    budget: int = 2_000_000,
) -> dict[str, str]:
    """Para cada nombre buscado, devuelve la PRIMERA fila del Excel donde aparece
    (todas sus celdas unidas y recortadas). Sirve para distinguir nombres
    truncados/abreviados en origen ('CONST. A' vs 'CONST. Y') por el resto de la
    fila: su CIF, su importe, su nº de factura, etc.

    `wanted_lower`: conjunto de textos a localizar, EN MINÚSCULAS.
    Devuelve {texto_lower: 'celda1 · celda2 · …'}.

    `budget` acota el nº de comprobaciones (texto×fila) para no degradar en Excels
    enormes: si se supera, devuelve lo encontrado hasta ese punto (las entidades
    frecuentes aparecen en las primeras filas, así que se capturan igual)."""
    out: dict[str, str] = {}
    remaining = {w for w in wanted_lower if w}
    if not remaining:
        return out
    # Pre-filtro compilado: una sola pasada de regex descarta de golpe las filas que
    # NO contienen ningún nombre buscado (la inmensa mayoría en un Excel grande),
    # evitando el bucle por-nombre en esas filas (de O(filas×nombres) a casi O(filas)).
    try:
        prefilter = re.compile("|".join(re.escape(w) for w in remaining))
    except Exception:
        prefilter = None
    try:
        wb = load_workbook(filename=str(path), data_only=True, read_only=True)
    except Exception:
        try:
            wb = load_workbook(filename=str(path), data_only=False, read_only=True)
        except Exception:
            return out
    comps = 0
    try:
        for ws in wb.worksheets:
            try:
                n = 0
                for row in ws.iter_rows(values_only=True):
                    if not remaining or comps > budget:
                        return out
                    if n >= max_rows:
                        break
                    n += 1
                    cells = []
                    for c in row:
                        if c is None:
                            continue
                        s = str(c).strip()
                        if s:
                            cells.append(_redact_ids(s))
                    if not cells:
                        continue
                    rowtext = " · ".join(cells)
                    # Normalizar espacios para que 'ACME  CORP' (doble espacio) case
                    # con el nombre buscado 'acme corp'.
                    low = re.sub(r"\s+", " ", rowtext).lower()
                    # Fast-skip: si la fila no contiene NINGÚN nombre buscado, no
                    # entramos al bucle por-nombre (ahorra el grueso del trabajo).
                    if prefilter is not None and not prefilter.search(low):
                        continue
                    found_here = []
                    for w in remaining:
                        comps += 1
                        if w in low:
                            found_here.append(w)
                        if comps > budget:
                            break
                    if found_here:
                        snippet = (rowtext if len(rowtext) <= max_len
                                   else rowtext[: max_len - 1].rstrip() + "…")
                        for w in found_here:
                            out[w] = snippet
                            remaining.discard(w)
            except Exception:
                # Una hoja problemática no debe tumbar la herramienta.
                continue
    finally:
        try:
            wb.close()
        except Exception:
            pass
    return out


# --- Limpieza y normalización de descripciones contables ---

# Patrones para extraer el nombre "neto" de la descripción
CIF_IN_DESC_RE = re.compile(r"[,;\s]*[\(\[]?\s*(?:CIF[:\s]*)?[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]\s*[\)\]]?", re.IGNORECASE)
ANTICIPO_RE = re.compile(r"^\s*(?:Anticipo|Préstamo|Préstamo a|Crédito a|Crédito)\s+", re.IGNORECASE)
SERVPRO_RE = re.compile(r"^\s*Servicios profesionales\s+", re.IGNORECASE)
# IBAN tras guion, referencia tras "ref", o "C/C ..."
BANK_REF_RE = re.compile(r"\s*-\s*ES\d{2}[\d\s]*$|\s+ref[\.\s][^.]*$|\s+c/c[^.]*$", re.IGNORECASE)

# Prefijos de documento al inicio de la descripción ("Fra. 123 Acme" → "Acme").
DOC_PREFIX_RE = re.compile(
    r"^\s*(?:Fra\.?|Fact\.?|Factura|FAC|Albar[áa]n|ALB|Pedido|PED|Ref\.?|Referencia|Recibo|Abono|N[ºo°]\.?)"
    r"[:.\s/-]*\d*[:.\s/-]*",
    re.IGNORECASE,
)
# Fecha al final ("Acme 12/03/2024" → "Acme"). Solo formatos claros de fecha.
TRAILING_DATE_RE = re.compile(r"[\s,;-]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*$")
# Importe CON símbolo de moneda al final ("Acme 1.250,00 €" → "Acme"). Exigimos
# € o EUR para NO mutilar nombres que acaban en número ("Garaje 2000", "Canal 7").
TRAILING_AMOUNT_RE = re.compile(
    r"[\s,;-]*\d[\d.,]*\s*(?:€|EUR|eur|\$|USD)\s*$"
)


def clean_description(kind: str, desc: str) -> str:
    """Extrae el nombre limpio de la descripción según el tipo de cuenta.

    Quita ruido típico de los apuntes: CIF embebido, prefijos de factura/albarán,
    fechas e importes con moneda al final. NO toca números 'pegados' a un nombre
    sin separador claro (para no romper 'Garaje 2000')."""
    text = desc.strip()

    # Quitar CIF entre paréntesis o tras coma
    text = CIF_IN_DESC_RE.sub("", text).strip(" ,;-")

    # Prefijo de documento al inicio (Fra./Albarán/Ref. + número)
    text = DOC_PREFIX_RE.sub("", text)

    if kind == "PERSONA":
        text = ANTICIPO_RE.sub("", text)
    elif kind == "BANCO":
        text = BANK_REF_RE.sub("", text)

    # 623xxxxx "Servicios profesionales X" → X
    text = SERVPRO_RE.sub("", text)

    # Fecha / importe-con-moneda al final
    text = TRAILING_DATE_RE.sub("", text)
    text = TRAILING_AMOUNT_RE.sub("", text)

    return text.strip(" ,;-")


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
