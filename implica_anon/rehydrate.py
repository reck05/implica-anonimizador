"""Rehydrate: convierte codenames de vuelta a nombres reales.

Caso de uso: pasaste un sumas y saldos anonimizado a Claude, Claude te devuelve
un análisis con "[Cliente-125] tiene un saldo atípico". Quieres ver el nombre
real para tu informe interno → rehydrate ese texto/archivo con el mapping.

NOTA: el resultado contiene PII real, NO lo subas a APIs externas.
"""
from __future__ import annotations

from pathlib import Path

from . import formats, mapping as mapping_mod
from .replacer import replace_in_text


def invert_mapping(pm: mapping_mod.ProjectMapping) -> dict[str, str]:
    """Devuelve un dict {codename: original}.

    Si varios originales mapearon al mismo codename (típico: 3 variantes
    "Global Menta", "GlobalMenta", "Global Menta S.L." → "Paradise"),
    se queda con el original más largo (el más informativo).
    """
    inverted: dict[str, str] = {}
    for kind_entries in pm.entries.values():
        for original, codename in kind_entries.items():
            existing = inverted.get(codename)
            if existing is None or len(original) > len(existing):
                inverted[codename] = original
    return inverted


def rehydrate_text(text: str, pm: mapping_mod.ProjectMapping) -> tuple[str, int]:
    """Aplica el mapping inverso a un texto."""
    inverted = invert_mapping(pm)
    return replace_in_text(text, inverted)


def rehydrate_file(src: Path, pm: mapping_mod.ProjectMapping, dst: Path) -> None:
    """Aplica el mapping inverso a un archivo (xlsx/docx/pptx/pdf)."""
    inverted = invert_mapping(pm)
    formats.apply_replacements(src, inverted, dst)
