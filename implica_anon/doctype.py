"""Detector del tipo de documento M&A.

Cinco categorías relevantes para Implica:
- accounting: sumas y saldos, mayor, balance de comprobación. Usa flujo PGC.
- teaser_im: teasers, IMs, presentaciones de oportunidad. NER + empresa principal.
- legal: contratos, NDAs, SPAs. NER + foco en partes y direcciones.
- datapack: mezcla típica de DD (Excel financieros + Word + PDF). Flujo combinado.
- generic: cualquier otra cosa. NER + regex.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from . import accounting


class DocType(str, Enum):
    ACCOUNTING = "accounting"
    TEASER_IM = "teaser_im"
    LEGAL = "legal"
    DATAPACK = "datapack"
    GENERIC = "generic"


LABELS = {
    DocType.ACCOUNTING: "📊 Sumas y saldos / Libro contable",
    DocType.TEASER_IM: "📑 Teaser / IM / Presentación corporativa",
    DocType.LEGAL: "⚖️ Contrato / Legal (NDA, SPA, etc.)",
    DocType.DATAPACK: "📦 Datapack mixto de due diligence",
    DocType.GENERIC: "📄 Documento general",
}

DESCRIPTIONS = {
    DocType.ACCOUNTING: (
        "Anonimización masiva: detecta cuentas PGC (430xxx clientes, 410xxx proveedores, "
        "etc.) y las anonimiza automáticamente sin preguntar uno por uno."
    ),
    DocType.TEASER_IM: (
        "Detecta la empresa principal (la que más aparece) y la mapea al codename del "
        "proyecto. Resto de empresas y personas se preguntan o auto-asignan."
    ),
    DocType.LEGAL: (
        "Foco en partes contratantes, personas firmantes, direcciones y NIF/CIF. "
        "Útil para NDAs, SPAs, contratos de servicios."
    ),
    DocType.DATAPACK: (
        "Para carpetas con mezcla de tipos: trata cada Excel como contable si tiene "
        "estructura PGC, y el resto con NER."
    ),
    DocType.GENERIC: (
        "Anonimización estándar con NER en español + regex. Para cualquier documento "
        "que no encaje en las otras categorías."
    ),
}


# Palabras clave que indican tipo legal (en orden descendente de fuerza)
LEGAL_KEYWORDS = (
    "arrendador", "arrendatario", "comprador", "vendedor", "partes contratantes",
    "cláusula primera", "clausula primera", "estipulaciones",
    "manifiestan que", "ambas partes",
    "non-disclosure agreement", "share purchase agreement", "confidentiality agreement",
    "spa", "letter of intent", "loi", "term sheet",
    "reunidos:", "comparecen", "ante mí, el notario",
)

TEASER_KEYWORDS = (
    "confidential information memorandum", "investment opportunity",
    "executive summary", "disclaimer", "non-binding",
    "highlights", "investment highlights", "cap table", "investor",
    "valoración", "múltiplo de ebitda", "transacciones comparables",
    "due diligence", "process letter", "proceso de venta",
    "teaser", "information memorandum",
)


@dataclass
class DocTypeGuess:
    doctype: DocType
    confidence: float  # 0..1
    signals: list[str]  # razones humanamente leíbles


def _count_keywords(text: str, keywords: tuple[str, ...]) -> tuple[int, list[str]]:
    found = []
    low = text.lower()
    for kw in keywords:
        if kw in low:
            found.append(kw)
    return len(found), found


def guess_doctype(path: Path) -> DocTypeGuess:
    """Mira el archivo y decide qué tipo es. No carga modelos pesados, es rápido."""
    suffix = path.suffix.lower()
    signals: list[str] = []

    # 1) Excel: ¿es libro contable?
    if suffix in (".xlsx", ".xlsm"):
        try:
            scan = accounting.scan_workbook(path)
            if scan.is_accounting and scan.entities:
                signals.append(
                    f"Excel con estructura contable detectada "
                    f"({len(scan.entities)} cuentas PGC en {len(scan.sheet_findings)} hojas)"
                )
                conf = min(1.0, 0.7 + len(scan.entities) / 1000)
                return DocTypeGuess(DocType.ACCOUNTING, conf, signals)
            else:
                signals.append("Excel sin estructura PGC clara")
        except Exception as e:
            signals.append(f"Error escaneando Excel: {e}")

    # 2) Para PPT, Word, PDF: leer texto y buscar keywords
    from . import formats
    try:
        texts = formats.extract_text(path)
        full_text = "\n".join(texts).lower()
    except Exception:
        return DocTypeGuess(DocType.GENERIC, 0.3, [f"No se pudo extraer texto"])

    n_legal, legal_found = _count_keywords(full_text, LEGAL_KEYWORDS)
    n_teaser, teaser_found = _count_keywords(full_text, TEASER_KEYWORDS)

    if n_legal >= 2 and n_legal > n_teaser:
        signals.append(f"Palabras clave de contrato: {', '.join(legal_found[:5])}")
        return DocTypeGuess(DocType.LEGAL, min(1.0, 0.5 + 0.1 * n_legal), signals)

    if n_teaser >= 2 or (suffix == ".pptx" and n_teaser >= 1):
        signals.append(f"Palabras clave de teaser/IM: {', '.join(teaser_found[:5])}")
        if suffix == ".pptx":
            signals.append("Formato PPTX (típico de teasers e IMs)")
        return DocTypeGuess(DocType.TEASER_IM, min(1.0, 0.5 + 0.1 * n_teaser), signals)

    # PPTX por defecto → teaser
    if suffix == ".pptx":
        signals.append("PPTX sin palabras clave fuertes — tratado como presentación")
        return DocTypeGuess(DocType.TEASER_IM, 0.4, signals)

    signals.append("Sin señales claras de tipo específico")
    return DocTypeGuess(DocType.GENERIC, 0.3, signals)


def guess_doctype_batch(paths: list[Path]) -> DocTypeGuess:
    """Para múltiples archivos: si la mayoría es del mismo tipo, devuelve eso.
    Si hay mezcla significativa, devuelve DATAPACK."""
    if not paths:
        return DocTypeGuess(DocType.GENERIC, 0.0, ["sin archivos"])
    if len(paths) == 1:
        return guess_doctype(paths[0])

    guesses = [guess_doctype(p) for p in paths]
    by_type: dict[DocType, list[DocTypeGuess]] = {}
    for g in guesses:
        by_type.setdefault(g.doctype, []).append(g)

    # Si todo el mismo tipo
    if len(by_type) == 1:
        only = list(by_type.keys())[0]
        return DocTypeGuess(
            only,
            0.9,
            [f"Todos los {len(paths)} archivos del tipo {LABELS[only]}"],
        )

    # Si una mayoría clara (>70%)
    sorted_types = sorted(by_type.items(), key=lambda kv: -len(kv[1]))
    dominant, items = sorted_types[0]
    if len(items) / len(paths) >= 0.7:
        return DocTypeGuess(
            dominant,
            0.7,
            [
                f"{len(items)}/{len(paths)} archivos parecen {LABELS[dominant]}",
                f"otros: {', '.join(t.value for t, _ in sorted_types[1:])}",
            ],
        )

    return DocTypeGuess(
        DocType.DATAPACK,
        0.6,
        [
            f"Mezcla: {', '.join(f'{len(v)} {t.value}' for t, v in sorted_types)}",
            "Tratado como datapack mixto (cada archivo con su estrategia)",
        ],
    )
