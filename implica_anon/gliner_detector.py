"""Capa OPCIONAL de detección de entidades con GLiNER (100% local, sin APIs externas).

Desactivada por defecto. Se activa con IMPLICA_ENABLE_GLINER=true.

Diseño defensivo (degradación elegante):
- Si `gliner` no está instalado  → devuelve [] y la app sigue con spaCy+regex+heurísticas.
- Si el modelo no carga o falla   → devuelve [] (fallback), nunca lanza excepción al pipeline.
- NUNCA llama a servicios externos en runtime: el modelo se descarga UNA vez de
  HuggingFace (en la instalación/primer uso) y a partir de ahí corre offline.
- NO sustituye al motor PGC ni al detector determinista: solo añade candidatos.

Variables de entorno:
- IMPLICA_ENABLE_GLINER     activar (1/true/yes/on). Por defecto OFF.
- IMPLICA_GLINER_THRESHOLD  umbral de confianza [0..1]. Por defecto 0.5.
- IMPLICA_GLINER_MODEL      modelo HuggingFace. Por defecto multilingüe.
- IMPLICA_GLINER_LABELS     etiquetas separadas por comas (override de las M&A).

Logs: solo conteos y tipos de error. NUNCA se registra texto del documento.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

log = logging.getLogger("implica_anon.gliner")

# --- FASE 3: etiquetas M&A por defecto ---
MA_LABELS = [
    "PERSONA", "EMPRESA", "EMPRESA_OBJETIVO", "COMPRADOR", "VENDEDOR", "FONDO",
    "BANCO", "ASESOR_MA", "DESPACHO_LEGAL", "AUDITOR", "ACCIONISTA", "CEO", "CFO",
    "FOUNDER", "PROJECT_NAME", "DEAL_NAME", "MARCA", "GRUPO_EMPRESARIAL", "DOMINIO_WEB",
]

# Mapeo de la etiqueta fina GLiNER → kind interno del pipeline (Candidate.kind).
# Las etiquetas finas se conservan aparte (en Candidate.source) para trazabilidad.
GLINER_LABEL_TO_KIND = {
    # Personas
    "PERSONA": "PER", "CEO": "PER", "CFO": "PER", "FOUNDER": "PER", "ACCIONISTA": "PER",
    # Empresas (todas las variantes M&A colapsan a ORG para el reemplazo)
    "EMPRESA": "ORG", "EMPRESA_OBJETIVO": "ORG", "COMPRADOR": "ORG", "VENDEDOR": "ORG",
    "FONDO": "ORG", "ASESOR_MA": "ORG", "DESPACHO_LEGAL": "ORG", "AUDITOR": "ORG",
    "MARCA": "ORG", "PROJECT_NAME": "ORG", "DEAL_NAME": "ORG",
    # Tipos con kind propio
    "BANCO": "BANCO", "GRUPO_EMPRESARIAL": "GRUPO", "DOMINIO_WEB": "DOMINIO",
}

# Modelo multilingüe por defecto (soporta español). Alternativa PII:
# "urchade/gliner_multi_pii-v1". Configurable con IMPLICA_GLINER_MODEL.
DEFAULT_MODEL = "urchade/gliner_multi-2.1"

# Límites de seguridad de rendimiento/memoria
MAX_CHARS_PER_CHUNK = 3000      # GLiNER pierde precisión con textos muy largos
MAX_TOTAL_CHARS = 2_000_000     # tope global para no agotar memoria


def is_enabled() -> bool:
    return os.environ.get("IMPLICA_ENABLE_GLINER", "").lower() in ("1", "true", "yes", "on")


def get_threshold() -> float:
    try:
        return float(os.environ.get("IMPLICA_GLINER_THRESHOLD", "0.5"))
    except ValueError:
        return 0.5


def get_labels() -> list[str]:
    raw = os.environ.get("IMPLICA_GLINER_LABELS", "").strip()
    if raw:
        return [lbl.strip() for lbl in raw.split(",") if lbl.strip()]
    return list(MA_LABELS)


@lru_cache(maxsize=1)
def _load_model():
    """Carga el modelo GLiNER. Devuelve el modelo o None si no se puede (sin romper)."""
    model_name = os.environ.get("IMPLICA_GLINER_MODEL", DEFAULT_MODEL)
    try:
        from gliner import GLiNER  # import perezoso: solo si está instalado
    except Exception:
        log.info("GLiNER no instalado; se omite la capa GLiNER (fallback a spaCy+regex).")
        return None
    try:
        return GLiNER.from_pretrained(model_name)
    except Exception as e:
        log.warning("No se pudo cargar el modelo GLiNER (%s); se omite.", type(e).__name__)
        return None


def _chunks(text: str, size: int):
    capped = text[:MAX_TOTAL_CHARS]
    for i in range(0, len(capped), size):
        yield capped[i:i + size]


def detect_gliner_entities(text: str, labels=None, threshold=None) -> list[tuple]:
    """Detecta entidades con GLiNER. Devuelve lista de (texto, etiqueta_gliner, score).

    Devuelve [] si GLiNER no está disponible o ante cualquier fallo (degradación
    elegante — nunca propaga excepción al pipeline).
    """
    model = _load_model()
    if model is None or not text:
        return []
    labels = labels or get_labels()
    threshold = get_threshold() if threshold is None else threshold

    results: list[tuple] = []
    try:
        for chunk in _chunks(text, MAX_CHARS_PER_CHUNK):
            for ent in model.predict_entities(chunk, labels, threshold=threshold):
                t = (ent.get("text") or "").strip()
                lab = ent.get("label")
                score = float(ent.get("score", 0.0))
                if t and lab:
                    results.append((t, lab, score))
    except Exception as e:
        log.warning("Fallo en GLiNER predict_entities (%s); se omite.", type(e).__name__)
        return []

    log.info("GLiNER detectó %d entidades (umbral %.2f).", len(results), threshold)
    return results
