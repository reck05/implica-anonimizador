"""Procesador de PDF con PyMuPDF (fitz).

Usa redact_annot + apply_redactions + insert_textbox para reemplazar in-place
preservando layout. Funciona para PDFs con texto seleccionable. Para PDFs
escaneados (sin OCR) no detecta nada — habría que pre-procesarlos con OCR.
"""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from ..replacer import replace_in_text


def extract_text(path: Path) -> list[str]:
    texts: list[str] = []
    with fitz.open(str(path)) as doc:
        for page in doc:
            page_text = page.get_text("text")
            if page_text.strip():
                # Devolver por bloques para que NER tenga contexto, no por línea suelta
                texts.append(page_text)
    return texts


def apply_replacements(src: Path, mapping: dict[str, str], dst: Path) -> None:
    """Estrategia:
    - Para cada página, buscar instancias de cada `original` con page.search_for
    - Crear redact_annot con replacement como text overlay
    - apply_redactions para fundir
    """
    if not mapping:
        # Solo copiar
        with fitz.open(str(src)) as doc:
            doc.save(str(dst))
        return

    # Orden por longitud desc para evitar matches parciales
    ordered = sorted(mapping.items(), key=lambda kv: -len(kv[0]))

    with fitz.open(str(src)) as doc:
        for page in doc:
            # Color blanco (asume fondo blanco — para PDFs con fondo coloreado
            # esto se vería raro pero los teasers M&A suelen ser blancos)
            for original, replacement in ordered:
                if not original:
                    continue
                # search_for es case-sensitive en PyMuPDF; buscamos también lower
                rects = list(page.search_for(original))
                # Probar variante en lowercase si no encontramos nada
                if not rects:
                    rects = list(page.search_for(original.lower()))
                for rect in rects:
                    # Inflar levemente para asegurar cobertura
                    annot = page.add_redact_annot(
                        rect,
                        text=replacement,
                        fontname="helv",
                        fontsize=max(6, rect.height * 0.7),
                        align=fitz.TEXT_ALIGN_LEFT,
                        fill=(1, 1, 1),
                    )
                    annot.update()
            page.apply_redactions()
        doc.save(str(dst), garbage=4, deflate=True)
