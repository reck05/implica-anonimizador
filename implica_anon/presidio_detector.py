"""Capa OPCIONAL de detección con Microsoft Presidio (100% local, sin APIs externas).

Presidio (MIT) corre sobre el MISMO spaCy español que ya usamos (es_core_news_md),
sin Torch ni descargas extra. Su valor aquí: spans de PERSONA COMPLETOS en documentos
narrativos (Word/PPT/PDF), donde el spaCy "crudo" a veces recorta el nombre.

Diseño igual que la capa GLiNER (degradación elegante, nunca rompe el pipeline):
- Si `presidio_analyzer` no está instalado → devuelve [] y se sigue con spaCy+regex.
- Si el motor no carga → devuelve [] (fallback), sin lanzar excepción.
- NO llama a servicios externos: el análisis es 100% local.
- NO sustituye al motor PGC/regex/columna: solo AÑADE candidatos (personas).
- CIF/NIF/IBAN/email/teléfono los seguimos detectando con nuestro regex+checksum
  (más preciso para España); de Presidio tomamos PERSON (y ORG si aparece).

Variables de entorno:
- IMPLICA_ENABLE_PRESIDIO   activar (1/true/yes/on). Por defecto OFF.
- IMPLICA_PRESIDIO_THRESHOLD umbral de confianza [0..1]. Por defecto 0.4.
- IMPLICA_PRESIDIO_MODEL     modelo spaCy. Por defecto es_core_news_md (el que ya hay).
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

log = logging.getLogger("implica_anon.presidio")

STATUS_CLASSIC = "Presidio no disponible, usando motor clásico"
_status_message: str = ""

DEFAULT_MODEL = "es_core_news_md"

# Presidio → kind interno. Solo lo que aporta valor sobre lo que ya tenemos:
# PERSON (spans completos) y ORGANIZATION. CIF/NIF/IBAN/email/teléfono YA los
# cubrimos con regex+checksum (más preciso para España) → no los tomamos de aquí.
PRESIDIO_LABEL_TO_KIND = {
    "PERSON": "PER",
    "ORGANIZATION": "ORG",
}

MAX_TOTAL_CHARS = 2_000_000  # tope global anti-memoria


def is_enabled() -> bool:
    return os.environ.get("IMPLICA_ENABLE_PRESIDIO", "").lower() in ("1", "true", "yes", "on")


def status_message() -> str:
    return _status_message


def get_threshold() -> float:
    try:
        return float(os.environ.get("IMPLICA_PRESIDIO_THRESHOLD", "0.4"))
    except ValueError:
        return 0.4


@lru_cache(maxsize=1)
def _load_analyzer():
    """Crea el AnalyzerEngine de Presidio con el spaCy español. None si no se puede."""
    global _status_message
    model_name = os.environ.get("IMPLICA_PRESIDIO_MODEL", DEFAULT_MODEL)
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
    except Exception:
        _status_message = STATUS_CLASSIC
        log.info("%s (presidio_analyzer no instalado).", STATUS_CLASSIC)
        return None
    try:
        conf = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "es", "model_name": model_name}],
        }
        nlp_engine = NlpEngineProvider(nlp_configuration=conf).create_engine()
        analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["es"])
        _status_message = ""
        return analyzer
    except Exception as e:
        _status_message = STATUS_CLASSIC
        log.warning("%s (fallo al cargar: %s).", STATUS_CLASSIC, type(e).__name__)
        return None


def detect_presidio_entities(text: str, threshold: float | None = None) -> list[tuple]:
    """Detecta entidades con Presidio. Devuelve [(texto, etiqueta, score), ...].

    Solo PERSON/ORGANIZATION (lo demás ya lo cubrimos mejor con regex+checksum).
    Devuelve [] ante cualquier problema — nunca propaga excepción al pipeline.
    """
    analyzer = _load_analyzer()
    if analyzer is None or not text:
        return []
    threshold = get_threshold() if threshold is None else threshold
    wanted = list(PRESIDIO_LABEL_TO_KIND.keys())
    capped = text[:MAX_TOTAL_CHARS]
    out: list[tuple] = []
    try:
        results = analyzer.analyze(text=capped, language="es", entities=wanted)
        for r in results:
            if r.score < threshold:
                continue
            frag = capped[r.start:r.end].strip()
            if frag:
                out.append((frag, r.entity_type, float(r.score)))
    except Exception as e:
        log.warning("Fallo en Presidio analyze (%s); se omite.", type(e).__name__)
        return []
    log.info("Presidio detectó %d entidades (umbral %.2f).", len(out), threshold)
    return out
