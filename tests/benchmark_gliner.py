"""Benchmark LOCAL: motor clásico (spaCy+regex+heurísticas) vs +GLiNER.

Genera 3 documentos ficticios M&A en español con entidades CONOCIDAS (ground truth)
y compara ambos motores midiendo, por documento y en total:
  - entidades detectadas SIN GLiNER
  - entidades detectadas CON GLiNER
  - entidades nuevas ÚTILES que añade GLiNER (estaban en el ground truth)
  - falsos positivos (detectadas pero NO en el ground truth)
  - tiempo de procesamiento
  - recomendación final (activar / no activar) según umbrales

REQUISITOS para números reales:
  - spaCy con es_core_news_md (motor clásico).
  - (opcional) GLiNER instalado para la columna CON GLiNER:
        pip install -r requirements-gliner.txt
        python -m implica_anon.gliner_detector        # descarga el modelo una vez

USO:
  # Solo motor clásico (la columna GLiNER saldrá "no disponible"):
  python tests/benchmark_gliner.py

  # Con GLiNER (Windows PowerShell):
  $env:IMPLICA_ENABLE_GLINER="true"; $env:IMPLICA_GLINER_ALLOW_DOWNLOAD="true"
  python tests/benchmark_gliner.py

NOTA: en un equipo donde spaCy esté bloqueado o no instalado, el motor clásico cae a
heurísticas (menos preciso) y el benchmark lo indica — los números solo son
representativos en una máquina con spaCy operativo.
"""
import io
import os
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIX = Path(__file__).parent / "fixtures" / "benchmark"
FIX.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# GROUND TRUTH: entidades reales que metemos en cada documento (lo que un humano
# consideraría que hay que anonimizar). Sirve para medir aciertos y falsos positivos.
# ---------------------------------------------------------------------------
GROUND_TRUTH = {
    "teaser": [
        "Proyecto Halcón", "Clínica Dental Sonrisa S.L.", "Implica Corporate Finance",
        "Mediterráneo Capital Partners", "DentalGroup Europe", "Alberto Ramírez",
        "María Fernández", "sonrisadental.es",
    ],
    "excel": [
        "Distribuciones García S.L.", "Mercadona S.A.", "Supermercados Día",
        "Suministros Dentales Ibéricos S.L.", "Material Médico Europa S.A.",
    ],
    "pptx": [
        "Proyecto Halcón", "Salud Capital Partners", "Grupo Ramírez S.L.",
        "Implica Corporate Finance", "Garrigues", "Alberto Ramírez",
    ],
}


def make_teaser_pdf() -> Path:
    import fitz
    path = FIX / "teaser_proyecto_halcon.pdf"
    lines = [
        "PROYECTO HALCÓN — Información Confidencial",
        "",
        "Implica Corporate Finance presenta una oportunidad de inversión en el sector dental.",
        "",
        "La compañía objetivo, Clínica Dental Sonrisa S.L. (CIF B12345678), es una cadena",
        "de clínicas dentales con sede en Valencia y web sonrisadental.es.",
        "",
        "Fundada por el Dr. Alberto Ramírez (CEO), la dirección financiera está a cargo de",
        "María Fernández (CFO). La compañía ha mostrado un crecimiento sólido.",
        "",
        "Entre los inversores interesados figura Mediterráneo Capital Partners, fondo de",
        "private equity especializado en salud. Como comparable de mercado se cita a",
        "DentalGroup Europe.",
        "",
        "Para más información, contactar con el asesor financiero Implica Corporate Finance.",
    ]
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for ln in lines:
        page.insert_text((72, y), ln, fontsize=11, fontname="helv")
        y += 18
    doc.save(str(path))
    doc.close()
    return path


def make_excel() -> Path:
    from openpyxl import Workbook
    path = FIX / "listado_clientes_proveedores.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes y Proveedores"
    ws.append(["Tipo", "Nombre", "CIF", "Sector"])
    rows = [
        ("Cliente", "Distribuciones García S.L.", "B11111111", "Distribución"),
        ("Cliente", "Mercadona S.A.", "A22222222", "Retail"),
        ("Cliente", "Supermercados Día", "A33333333", "Retail"),
        ("Proveedor", "Suministros Dentales Ibéricos S.L.", "B44444444", "Material dental"),
        ("Proveedor", "Material Médico Europa S.A.", "A55555555", "Material médico"),
    ]
    for r in rows:
        ws.append(r)
    wb.save(str(path))
    return path


def make_pptx() -> Path:
    from pptx import Presentation
    from pptx.util import Inches
    path = FIX / "presentacion_proyecto_halcon.pptx"
    prs = Presentation()
    slides_text = [
        ("Proyecto Halcón", "Resumen de la operación — Confidencial"),
        ("Partes de la operación",
         "Vendedor: Grupo Ramírez S.L.\nComprador: Salud Capital Partners\n"
         "Asesor financiero: Implica Corporate Finance\nDespacho legal: Garrigues"),
        ("Dirección", "CEO y fundador: Alberto Ramírez\nLa familia controla el 100% del capital."),
    ]
    blank = prs.slide_layouts[1]
    for title, body in slides_text:
        s = prs.slides.add_slide(blank)
        s.shapes.title.text = title
        s.placeholders[1].text = body
    prs.save(str(path))
    return path


def detect_entities(path: Path, kind_doc: str):
    """Devuelve (set de entidades canónicas ORG/PER/DOMINIO, segundos)."""
    from implica_anon import formats
    from implica_anon.detectors import detect_candidates, cluster_variants

    t0 = time.time()
    texts = formats.extract_text(path)
    # Ruta NER (texto libre). El Excel listado no tiene códigos PGC → también NER.
    candidates = detect_candidates(texts, skip_ner=False)
    clusters = cluster_variants(candidates)
    elapsed = time.time() - t0
    # Nos quedamos con entidades "de nombre" (no CIF/IBAN/email/teléfono puros)
    name_kinds = {"ORG", "PER", "CLIENTE", "PROVEEDOR", "DEUDOR", "GRUPO", "BANCO", "DOMINIO"}
    ents = {c.canonical for c in clusters if c.kind in name_kinds}
    return ents, elapsed


def _norm(s: str) -> str:
    return s.strip().lower()


def _hits(detected: set, truth: list) -> list:
    dl = [_norm(d) for d in detected]
    found = []
    for t in truth:
        tl = _norm(t)
        if any(tl in d or d in tl for d in dl):
            found.append(t)
    return found


def _false_positives(detected: set, truth: list) -> list:
    tl = [_norm(t) for t in truth]
    fps = []
    for d in detected:
        dl = _norm(d)
        if not any(dl in t or t in dl for t in tl):
            fps.append(d)
    return fps


def run():
    print("Generando fixtures ficticios...")
    paths = {
        "teaser": make_teaser_pdf(),
        "excel": make_excel(),
        "pptx": make_pptx(),
    }
    for k, p in paths.items():
        print(f"  {k:7} -> {p.name}")

    # ¿GLiNER disponible/activo?
    from implica_anon import gliner_detector
    gliner_active = gliner_detector.is_enabled()

    print("\n" + "=" * 78)
    print("BENCHMARK: motor clásico (spaCy+regex+heurísticas) vs +GLiNER")
    print("=" * 78)
    if not gliner_active:
        print("⚠️ GLiNER NO activo (IMPLICA_ENABLE_GLINER!=true). Columna GLiNER = clásico.")
    print()

    tot = {"base_hits": 0, "gln_hits": 0, "truth": 0, "base_fp": 0, "gln_fp": 0,
           "base_t": 0.0, "gln_t": 0.0, "new_useful": 0}

    for k, p in paths.items():
        truth = GROUND_TRUTH[k]

        # Motor clásico: GLiNER off
        os.environ.pop("IMPLICA_ENABLE_GLINER", None)
        try:
            base_ents, base_t = detect_entities(p, k)
        except Exception as e:
            print(f"[{k}] ERROR motor clásico: {type(e).__name__}: {e}")
            continue

        # Con GLiNER: on (si el usuario lo activó globalmente)
        if gliner_active:
            os.environ["IMPLICA_ENABLE_GLINER"] = "true"
        gln_ents, gln_t = detect_entities(p, k) if gliner_active else (base_ents, base_t)

        base_hits = _hits(base_ents, truth)
        gln_hits = _hits(gln_ents, truth)
        new_useful = [e for e in gln_hits if e not in base_hits]
        base_fp = _false_positives(base_ents, truth)
        gln_fp = _false_positives(gln_ents, truth)

        print(f"--- {k.upper()} ({p.name}) — {len(truth)} entidades reales ---")
        print(f"  SIN GLiNER : {len(base_hits)}/{len(truth)} aciertos · {len(base_fp)} FP · {base_t:.2f}s")
        print(f"  CON GLiNER : {len(gln_hits)}/{len(truth)} aciertos · {len(gln_fp)} FP · {gln_t:.2f}s")
        if new_useful:
            print(f"  + nuevas útiles de GLiNER: {new_useful}")
        if gliner_active and gln_fp:
            print(f"  posibles FP (revisar): {gln_fp[:8]}")
        print()

        tot["truth"] += len(truth)
        tot["base_hits"] += len(base_hits)
        tot["gln_hits"] += len(gln_hits)
        tot["base_fp"] += len(base_fp)
        tot["gln_fp"] += len(gln_fp)
        tot["base_t"] += base_t
        tot["gln_t"] += gln_t
        tot["new_useful"] += len(new_useful)

    os.environ.pop("IMPLICA_ENABLE_GLINER", None)

    print("=" * 78)
    print("TOTAL")
    print(f"  Entidades reales (ground truth) : {tot['truth']}")
    print(f"  Aciertos SIN GLiNER             : {tot['base_hits']}  · FP {tot['base_fp']} · {tot['base_t']:.2f}s")
    print(f"  Aciertos CON GLiNER             : {tot['gln_hits']}  · FP {tot['gln_fp']} · {tot['gln_t']:.2f}s")
    print(f"  Entidades nuevas útiles (GLiNER): {tot['new_useful']}")
    print("=" * 78)

    # Recomendación automática (solo significativa si GLiNER estaba activo)
    print("\nRECOMENDACIÓN:")
    if not gliner_active:
        print("  ⊘ GLiNER no estaba activo: no hay comparación real. Reejecuta con")
        print("    IMPLICA_ENABLE_GLINER=true e IMPLICA_GLINER_ALLOW_DOWNLOAD=true en una")
        print("    máquina con spaCy + GLiNER instalados.")
    else:
        extra = tot["gln_hits"] - tot["base_hits"]
        extra_fp = tot["gln_fp"] - tot["base_fp"]
        slowdown = tot["gln_t"] - tot["base_t"]
        if extra >= 3 and extra_fp <= extra:
            print(f"  ✅ ACTIVAR: +{extra} entidades útiles, +{extra_fp} FP, +{slowdown:.1f}s. "
                  "La ganancia en texto libre compensa.")
        elif extra >= 1:
            print(f"  🤔 OPCIONAL: +{extra} útiles pero +{extra_fp} FP / +{slowdown:.1f}s. "
                  "Valóralo según tu tolerancia a FP y tiempo.")
        else:
            print(f"  ❌ NO ACTIVAR: no aporta entidades útiles netas (+{extra_fp} FP, +{slowdown:.1f}s).")
    print("\n(Recuerda: GLiNER no afecta a sumas y saldos PGC — ahí el motor clásico ya es 100%.)")


if __name__ == "__main__":
    run()
