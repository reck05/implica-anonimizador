"""Capa OPCIONAL de detección de entidades con GLiNER (100% local, sin APIs externas).

Desactivada por defecto. Se activa con IMPLICA_ENABLE_GLINER=true.

Diseño defensivo (degradación elegante):
- Si `gliner` no está instalado  → devuelve [] y la app sigue con spaCy+regex+heurísticas.
- Si el modelo no carga o falla   → devuelve [] (fallback), nunca lanza excepción al pipeline.
- NUNCA llama a servicios externos en runtime: el modelo se descarga UNA vez de
  HuggingFace (en la instalación/primer uso) y a partir de ahí corre offline.
- NO sustituye al motor PGC ni al detector determinista: solo añade candidatos.

Variables de entorno:
- IMPLICA_ENABLE_GLINER         activar (1/true/yes/on). Por defecto OFF.
- IMPLICA_GLINER_ALLOW_DOWNLOAD permitir descarga del modelo. Por defecto FALSE.
- IMPLICA_GLINER_THRESHOLD      umbral de confianza [0..1]. Por defecto 0.5.
- IMPLICA_GLINER_MODEL          modelo HuggingFace. Por defecto comercial-friendly.
- IMPLICA_GLINER_LABELS         etiquetas separadas por comas (override de las M&A).

Garantías de aislamiento (condiciones obligatorias):
- NO usa APIs externas de pago ni Inference Providers ni endpoints remotos ni token HF.
- NO envía documentos/texto/entidades a ningún servicio: la inferencia es 100% local.
- La descarga del modelo desde HuggingFace es OPCIONAL y EXPLÍCITA
  (IMPLICA_GLINER_ALLOW_DOWNLOAD=true). Por defecto está prohibida.
- Si la descarga está prohibida y el modelo NO está en caché local, NO se descarga
  nada: se fuerza modo offline (HF_HUB_OFFLINE) y se cae al motor clásico.

Logs: solo conteos y tipos de error. NUNCA se registra texto del documento.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

log = logging.getLogger("implica_anon.gliner")

# Mensaje exacto cuando GLiNER no está disponible (se muestra en la UI/logs).
STATUS_CLASSIC = "GLiNER no disponible, usando motor clásico"
_status_message: str = ""

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

# Modelo por defecto. IMPORTANTE (licencia): se elige uno de la organización
# "gliner-community", que re-publica modelos GLiNER bajo Apache-2.0 (uso comercial
# permitido) y es multilingüe (base mDeBERTa, soporta español).
#
# ⚠️ VERIFICAR LICENCIA ANTES DE USO COMERCIAL: confirma en la model card de
# HuggingFace que la licencia del modelo concreto permite uso comercial.
#   - gliner-community/*  → Apache-2.0 (comercial OK)  ← recomendado
#   - knowledgator/*      → Apache-2.0 (comercial OK), pero suelen ser solo inglés
#   - urchade/gliner_multi-* → OJO: suelen ser CC-BY-NC-4.0 (NO comercial). EVITAR.
DEFAULT_MODEL = "gliner-community/gliner_medium-v2.1"

# Límites de seguridad de rendimiento/memoria
MAX_CHARS_PER_CHUNK = 3000      # GLiNER pierde precisión con textos muy largos
MAX_TOTAL_CHARS = 2_000_000     # tope global para no agotar memoria


def is_enabled() -> bool:
    return os.environ.get("IMPLICA_ENABLE_GLINER", "").lower() in ("1", "true", "yes", "on")


def allow_download() -> bool:
    """¿Se permite descargar el modelo de HuggingFace? Por defecto NO.

    En producción debe quedarse en false: el modelo se descarga una vez de forma
    explícita (ver download_model / GLINER.md) y luego se usa offline."""
    return os.environ.get("IMPLICA_GLINER_ALLOW_DOWNLOAD", "").lower() in ("1", "true", "yes", "on")


def status_message() -> str:
    """Último mensaje de estado (p.ej. 'GLiNER no disponible, usando motor clásico')."""
    return _status_message


def _set_offline_env():
    """Fuerza modo OFFLINE en las librerías HuggingFace: nunca contactan la red.
    Solo usan la caché local. Si el modelo no está en caché, fallan → fallback."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"


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
    """Carga el modelo GLiNER. Devuelve el modelo o None si no se puede (sin romper).

    - Si IMPLICA_GLINER_ALLOW_DOWNLOAD != true → modo OFFLINE forzado: solo caché
      local, nunca descarga. Si no está en caché → None + 'usando motor clásico'.
    - Si == true → permite descargar el modelo (única conexión a HF, sin token,
      solo pesos del modelo; nunca se envía texto del documento).
    """
    global _status_message
    model_name = os.environ.get("IMPLICA_GLINER_MODEL", DEFAULT_MODEL)
    can_download = allow_download()

    if not can_download:
        _set_offline_env()  # bloquea cualquier acceso de red de las libs HF

    try:
        from gliner import GLiNER  # import perezoso: solo si está instalado
    except Exception:
        _status_message = STATUS_CLASSIC
        log.info("%s (gliner no instalado).", STATUS_CLASSIC)
        return None

    # Intento de carga. local_files_only=True cuando no se permite descargar:
    # garantiza que NO se contacta la red aunque cambie el comportamiento por defecto.
    try:
        if can_download:
            model = GLiNER.from_pretrained(model_name)
        else:
            try:
                model = GLiNER.from_pretrained(model_name, local_files_only=True)
            except TypeError:
                # versión de gliner que no acepta el kwarg: el env offline ya protege
                model = GLiNER.from_pretrained(model_name)
        _status_message = ""
        return model
    except Exception as e:
        # No está en caché y no se permite descargar (o fallo de carga) → motor clásico
        _status_message = STATUS_CLASSIC
        if not can_download:
            log.info("%s (modelo no en caché local y descarga deshabilitada).", STATUS_CLASSIC)
        else:
            log.warning("%s (fallo al cargar: %s).", STATUS_CLASSIC, type(e).__name__)
        return None


def download_model(model_name: str | None = None) -> bool:
    """Descarga EXPLÍCITA del modelo a la caché local (paso manual, una sola vez).

    Uso:  python -m implica_anon.gliner_detector
    Requiere `gliner` instalado. Tras esto, GLiNER funciona offline sin descargar.
    Devuelve True si se descargó/cargó correctamente.
    """
    model_name = model_name or os.environ.get("IMPLICA_GLINER_MODEL", DEFAULT_MODEL)
    try:
        from gliner import GLiNER
    except Exception:
        print("ERROR: 'gliner' no instalado. Ejecuta: pip install -r requirements-gliner.txt")
        return False
    print(f"Descargando modelo GLiNER '{model_name}' a la caché local...")
    print("⚠️ Verifica la licencia del modelo en su model card antes de uso comercial.")
    try:
        GLiNER.from_pretrained(model_name)
        print("OK. El modelo está en caché; ya puede usarse OFFLINE "
              "(IMPLICA_GLINER_ALLOW_DOWNLOAD puede quedarse en false).")
        return True
    except Exception as e:
        print(f"ERROR al descargar: {type(e).__name__}: {e}")
        return False


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


if __name__ == "__main__":
    # Descarga manual y explícita del modelo (paso único). Tras esto, uso offline.
    #   python -m implica_anon.gliner_detector
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else None
    ok = download_model(name)
    sys.exit(0 if ok else 1)
