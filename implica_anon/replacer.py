"""Núcleo de reemplazo de texto.

El mapping siempre se ordena por longitud descendente para evitar reemplazos
parciales: "Global Menta S.L." debe procesarse antes que "Global Menta".

El reemplazo es case-sensitive por defecto pero también prueba el match
case-insensitive y conserva la capitalización del original cuando es posible.
"""
from __future__ import annotations

import re
from typing import Iterable


def _build_pattern(originals: Iterable[str]) -> re.Pattern[str]:
    """Pattern que matchea cualquiera de los originales, case-insensitive,
    con límites de palabra cuando el original empieza/termina en char alfanum."""
    parts = []
    for o in originals:
        if not o:
            continue
        escaped = re.escape(o)
        # word boundary solo si la primera/última char es alfanumérica
        prefix = r"\b" if o[0].isalnum() else ""
        suffix = r"\b" if o[-1].isalnum() else ""
        parts.append(f"{prefix}{escaped}{suffix}")
    if not parts:
        return re.compile(r"(?!)")  # never matches
    return re.compile("|".join(parts), re.IGNORECASE)


def replace_in_text(text: str, mapping: dict[str, str]) -> tuple[str, int]:
    """Aplica `mapping` a `text` (case-insensitive, ordenado por longitud desc).

    Devuelve (texto_modificado, num_reemplazos).
    """
    if not text or not mapping:
        return text, 0

    # mapping ya viene ordenado por longitud desc desde ProjectMapping.all_replacements
    # pero por seguridad lo re-ordenamos
    ordered = sorted(mapping.items(), key=lambda kv: -len(kv[0]))
    lookup = {k.lower(): v for k, v in ordered}
    pattern = _build_pattern(k for k, _ in ordered)

    count = 0

    def _sub(m: re.Match[str]) -> str:
        nonlocal count
        matched = m.group(0)
        replacement = lookup.get(matched.lower())
        if replacement is None:
            return matched
        count += 1
        return replacement

    return pattern.sub(_sub, text), count


def text_contains_any(text: str, originals: Iterable[str]) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(o.lower() in low for o in originals if o)
