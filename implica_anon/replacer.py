"""Núcleo de reemplazo de texto.

El mapping siempre se ordena por longitud descendente para evitar reemplazos
parciales: "Global Menta S.L." debe procesarse antes que "Global Menta".

El reemplazo es case-insensitive. La clase `Replacer` compila el patrón UNA vez
y se reutiliza para todas las celdas/párrafos de un documento — crítico para
rendimiento en Excels grandes (antes se recompilaba el regex por celda).
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


class Replacer:
    """Reemplazador precompilado. Construye el patrón una vez y lo reutiliza.

    Uso:
        r = Replacer(mapping)
        nuevo, n = r.apply(texto)          # reemplaza
        sobreviven = r.find_surviving(out) # verifica que nada quedó sin reemplazar
    """

    def __init__(self, mapping: dict[str, str]):
        # Ordenar por longitud descendente: "Global Menta S.L." antes que "Global Menta"
        ordered = sorted(
            ((k, v) for k, v in mapping.items() if k),
            key=lambda kv: -len(kv[0]),
        )
        self._lookup = {k.lower(): v for k, v in ordered}
        self._originals = [k for k, _ in ordered]
        self._pattern = _build_pattern(self._originals)

    def apply(self, text: str) -> tuple[str, int]:
        """Aplica el mapping a `text`. Devuelve (texto_modificado, num_reemplazos)."""
        if not text or not self._lookup:
            return text, 0
        count = 0

        def _sub(m: re.Match[str]) -> str:
            nonlocal count
            replacement = self._lookup.get(m.group(0).lower())
            if replacement is None:
                return m.group(0)
            count += 1
            return replacement

        return self._pattern.sub(_sub, text), count

    def find_surviving(self, text: str) -> list[str]:
        """Devuelve los originales que SIGUEN presentes en `text` (case-insensitive).

        Se usa para verificar tras anonimizar que ningún nombre real quedó visible.
        Lista vacía = anonimización limpia.
        """
        if not text:
            return []
        low = text.lower()
        return [o for o in self._originals if o.lower() in low]


def replace_in_text(text: str, mapping) -> tuple[str, int]:
    """Aplica `mapping` a `text` (case-insensitive, ordenado por longitud desc).

    Acepta un dict {original: codename} O un Replacer ya construido. Pasar un
    Replacer evita recompilar el patrón en cada llamada (úsalo en bucles).

    Devuelve (texto_modificado, num_reemplazos).
    """
    if isinstance(mapping, Replacer):
        return mapping.apply(text)
    if not text or not mapping:
        return text, 0
    return Replacer(mapping).apply(text)
