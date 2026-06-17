"""Procesador de PDF con PyMuPDF (fitz).

Usa redact_annot + apply_redactions + insert_textbox para reemplazar in-place
preservando layout. Funciona para PDFs con texto seleccionable.

PDFs ESCANEADOS (sin capa de texto): capa OPCIONAL de OCR (Tesseract) que SOLO
extrae texto para que la DETECCIÓN vea los nombres. El reemplazo in-place sobre la
imagen NO es posible con search_for, así que el verify pass (que vuelve a hacer OCR
del resultado) AVISARÁ de que el nombre sigue en la imagen — sin dar un falso "OK".
Se activa con IMPLICA_ENABLE_OCR=true y requiere el binario Tesseract instalado.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import fitz  # PyMuPDF

from ..replacer import replace_in_text

# Protección de memoria: tope de páginas a procesar de un PDF
MAX_PDF_PAGES = 1000


def _ocr_enabled() -> bool:
    return os.environ.get("IMPLICA_ENABLE_OCR", "").lower() in ("1", "true", "yes", "on")


@lru_cache(maxsize=1)
def ocr_available() -> bool:
    """True si pytesseract Y el binario Tesseract están disponibles."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_page_text(page) -> str:
    """OCR de una página (rasteriza a imagen y la pasa por Tesseract). Defensivo:
    si falta el binario o falla, devuelve '' (nunca rompe)."""
    try:
        import io
        import pytesseract
        from PIL import Image
        lang = os.environ.get("IMPLICA_OCR_LANG", "spa")
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img, lang=lang) or ""
    except Exception:
        return ""


def extract_text(path: Path) -> list[str]:
    texts: list[str] = []
    with fitz.open(str(path)) as doc:
        # Metadatos (autor/título/asunto/keywords): fuga silenciosa si no se ven.
        try:
            md = doc.metadata or {}
            for k in ("title", "author", "subject", "keywords"):
                v = md.get(k)
                if isinstance(v, str) and v.strip():
                    texts.append(v.strip())
        except Exception:
            pass
        use_ocr = _ocr_enabled() and ocr_available()
        for i, page in enumerate(doc):
            if i >= MAX_PDF_PAGES:
                break
            page_text = page.get_text("text")
            if page_text.strip():
                # Devolver por bloques para que NER tenga contexto, no por línea suelta
                texts.append(page_text)
            elif use_ocr:
                # Página sin capa de texto (escaneada): OCR para DETECTAR los nombres.
                ocr_text = _ocr_page_text(page)
                if ocr_text.strip():
                    texts.append(ocr_text)
    return texts


def page_count(path: Path) -> int:
    """Número de páginas del PDF (para avisar de truncamiento por MAX_PDF_PAGES)."""
    try:
        with fitz.open(str(path)) as doc:
            return doc.page_count
    except Exception:
        return 0


def count_images(path: Path) -> int:
    """Cuenta imágenes embebidas en el PDF. Útil para avisar de posibles
    nombres dentro de imágenes que la anonimización de texto no toca."""
    total = 0
    try:
        with fitz.open(str(path)) as doc:
            for page in doc:
                total += len(page.get_images(full=True))
    except Exception:
        return 0
    return total


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

    def _scrub_pdf_metadata(doc) -> None:
        """Limpia metadatos del PDF: identidad → vacío; título/asunto/keywords →
        mapping. Borra también el XMP. Evita la fuga por «Propiedades» del PDF."""
        try:
            md = dict(doc.metadata or {})
            for k in ("title", "subject", "keywords"):
                v = md.get(k)
                if isinstance(v, str) and v:
                    md[k] = replace_in_text(v, mapping)[0]
            md["author"] = ""
            md["creator"] = ""
            md["producer"] = "Implica Anonimizador"
            doc.set_metadata(md)
            try:
                doc.del_xml_metadata()
            except Exception:
                pass
        except Exception:
            pass

    with fitz.open(str(src)) as doc:
        for i, page in enumerate(doc):
            if i >= MAX_PDF_PAGES:
                break
            # Color blanco (asume fondo blanco — para PDFs con fondo coloreado
            # esto se vería raro pero los teasers M&A suelen ser blancos)
            for original, replacement in ordered:
                if not original:
                    continue
                # search_for de PyMuPDF distingue mayúsculas. Probamos varias
                # variantes de caso para no dejar el nombre visible. El verify
                # pass en formats/__init__ re-escanea el output y avisa de
                # cualquier ocurrencia que aun así se escape.
                rects = []
                seen_variants = set()
                for variant in (original, original.lower(), original.upper(), original.title()):
                    if variant in seen_variants:
                        continue
                    seen_variants.add(variant)
                    found = list(page.search_for(variant))
                    if found:
                        rects.extend(found)
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
        _scrub_pdf_metadata(doc)
        doc.save(str(dst), garbage=4, deflate=True)
