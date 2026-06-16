"""Tests de la capa opcional GLiNER (FASE 5).

La mayoría de tests NO requieren GLiNER instalado: mockean la salida del modelo
para verificar la INTEGRACIÓN (conversión a Candidate, mapeo de etiquetas, dedup,
activación por env var, fallback). Hay un test final con el modelo REAL que se
salta limpiamente si gliner no está instalado.

Ejecutar:  python tests/test_gliner.py
"""
import io
import os
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from implica_anon import detectors, gliner_detector

# Frase de ejemplo M&A del enunciado
EJEMPLO = (
    "Proyecto Atlas: Clínica Vital S.L. está siendo analizada por Iberia Growth Fund. "
    "El comprador potencial es Salud Capital Partners. El asesor financiero es "
    "Implica Corporate Finance y el despacho legal es Pérez-Llorca."
)

# Salida simulada de GLiNER para la frase (texto, etiqueta, score)
MOCK_ATLAS = [
    ("Proyecto Atlas", "PROJECT_NAME", 0.95),
    ("Clínica Vital S.L.", "EMPRESA_OBJETIVO", 0.93),
    ("Iberia Growth Fund", "FONDO", 0.91),
    ("Salud Capital Partners", "COMPRADOR", 0.90),
    ("Implica Corporate Finance", "ASESOR_MA", 0.92),
    ("Pérez-Llorca", "DESPACHO_LEGAL", 0.89),
]


def _set_mock(raw):
    """Activa GLiNER y fuerza su salida (sin necesitar el modelo real)."""
    os.environ["IMPLICA_ENABLE_GLINER"] = "true"
    gliner_detector.detect_gliner_entities = lambda text, labels=None, threshold=None: raw


def _reset():
    os.environ.pop("IMPLICA_ENABLE_GLINER", None)
    # restaurar la función original recargando el atributo del módulo
    import importlib
    importlib.reload(gliner_detector)


def test_disabled_by_default():
    print("\n=== 1) Desactivado por defecto ===")
    os.environ.pop("IMPLICA_ENABLE_GLINER", None)
    out = detectors._gliner_candidates(EJEMPLO, existing=[])
    assert out == [], f"Debería estar OFF por defecto, devolvió {out}"
    print("  ✓ Sin IMPLICA_ENABLE_GLINER → no añade nada (comportamiento actual intacto)")


def test_label_mapping_complete():
    print("\n=== 2) Todas las etiquetas M&A tienen mapeo a kind ===")
    faltan = [l for l in gliner_detector.MA_LABELS if l not in gliner_detector.GLINER_LABEL_TO_KIND]
    assert not faltan, f"Etiquetas sin mapeo: {faltan}"
    print(f"  ✓ {len(gliner_detector.MA_LABELS)} etiquetas M&A mapeadas a kinds del pipeline")


def test_example_sentence():
    print("\n=== 3) Frase de ejemplo M&A (mock) ===")
    _set_mock(MOCK_ATLAS)
    try:
        cands = detectors._gliner_candidates(EJEMPLO, existing=[])
        by_text = {c.text: c for c in cands}
        # Comprobaciones del enunciado
        assert "Clínica Vital S.L." in by_text and by_text["Clínica Vital S.L."].kind == "ORG"
        assert "Iberia Growth Fund" in by_text and by_text["Iberia Growth Fund"].kind == "ORG"
        assert "Implica Corporate Finance" in by_text
        assert "Pérez-Llorca" in by_text
        assert "Proyecto Atlas" in by_text
        # La etiqueta fina se conserva en source
        assert by_text["Iberia Growth Fund"].source == "gliner:FONDO"
        assert by_text["Pérez-Llorca"].source == "gliner:DESPACHO_LEGAL"
        for c in cands:
            print(f"  [{c.kind:7}] {c.text:28} ({c.source})")
        print("  ✓ Detecta target, fondo, comprador, asesor y despacho con etiqueta fina")
    finally:
        _reset()


def test_dedup_vs_existing():
    print("\n=== 4) Dedup contra spaCy/regex ya detectados ===")
    _set_mock(MOCK_ATLAS)
    try:
        from implica_anon.detectors import Candidate
        # Simular que spaCy ya detectó "Implica Corporate Finance"
        existing = [Candidate(text="Implica Corporate Finance", kind="ORG", source="ner")]
        cands = detectors._gliner_candidates(EJEMPLO, existing=existing)
        textos = [c.text for c in cands]
        assert "Implica Corporate Finance" not in textos, "No debe duplicar lo ya detectado"
        assert "Clínica Vital S.L." in textos, "Sí debe añadir lo nuevo"
        print("  ✓ No duplica entidades ya detectadas; sí añade las nuevas")
    finally:
        _reset()


def test_suffixes_persons_domains_emails():
    print("\n=== 5) Sufijos societarios, personas, dominios y emails ===")
    raw = [
        ("Tech Solutions GmbH", "EMPRESA", 0.9),
        ("Global Corp Ltd", "EMPRESA", 0.9),
        ("Innovate LLC", "EMPRESA", 0.9),
        ("María García López", "PERSONA", 0.9),
        ("Carlos Ruiz", "CEO", 0.9),
        ("globalmenta.com", "DOMINIO_WEB", 0.9),
        ("Banco Sabadell", "BANCO", 0.9),
        ("Grupo Inditex", "GRUPO_EMPRESARIAL", 0.9),
    ]
    _set_mock(raw)
    try:
        cands = {c.text: c for c in detectors._gliner_candidates("texto", existing=[])}
        assert cands["Tech Solutions GmbH"].kind == "ORG"
        assert cands["Innovate LLC"].kind == "ORG"
        assert cands["María García López"].kind == "PER"
        assert cands["Carlos Ruiz"].kind == "PER"            # CEO → persona
        assert cands["globalmenta.com"].kind == "DOMINIO"
        assert cands["Banco Sabadell"].kind == "BANCO"
        assert cands["Grupo Inditex"].kind == "GRUPO"
        print("  ✓ GmbH/Ltd/LLC→Empresa, CEO→Persona, dominio→Dominio, banco/grupo→su kind")
    finally:
        _reset()


def test_fallback_no_model():
    print("\n=== 6) Fallback si el modelo no está disponible ===")
    # Forzar que _load_model devuelva None (como si gliner no estuviera instalado)
    import importlib
    importlib.reload(gliner_detector)
    gliner_detector._load_model = lambda: None
    os.environ["IMPLICA_ENABLE_GLINER"] = "true"
    try:
        out = gliner_detector.detect_gliner_entities(EJEMPLO)
        assert out == [], "Sin modelo debe devolver [] (no romper)"
        cands = detectors._gliner_candidates(EJEMPLO, existing=[])
        assert cands == [], "Sin modelo, la augmentación no añade nada"
        print("  ✓ Sin modelo → [] y la app sigue con spaCy+regex+heurísticas")
    finally:
        _reset()


def test_real_gliner_if_installed():
    print("\n=== 7) Modelo REAL (se salta si gliner no está instalado) ===")
    try:
        import gliner  # noqa: F401
    except Exception:
        print("  ⊘ SKIP: gliner no instalado (pip install -r requirements-gliner.txt)")
        return
    import importlib
    importlib.reload(gliner_detector)
    os.environ["IMPLICA_ENABLE_GLINER"] = "true"
    try:
        raw = gliner_detector.detect_gliner_entities(EJEMPLO)
        textos = " | ".join(t for t, _, _ in raw).lower()
        print(f"  Detectado por el modelo real: {[t for t,_,_ in raw]}")
        assert "vital" in textos or "iberia" in textos, "Debería detectar al menos una empresa/fondo"
        print("  ✓ El modelo real detecta entidades M&A")
    finally:
        _reset()


if __name__ == "__main__":
    test_disabled_by_default()
    test_label_mapping_complete()
    test_example_sentence()
    test_dedup_vs_existing()
    test_suffixes_persons_domains_emails()
    test_fallback_no_model()
    test_real_gliner_if_installed()
    print("\n✓✓✓ Tests de la capa GLiNER PASS")
