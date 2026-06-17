"""Benchmark LOCAL: motor clásico (spaCy+regex+heurísticas) vs +GLiNER.

Genera 3 documentos ficticios M&A en español con entidades CONOCIDAS (ground truth)
y compara ambos motores. Vuelca un informe orientado a DECISIÓN DE EQUIPO en:
  - benchmark_resultado.md   (informe legible para jefe/IT)
  - benchmark_resultado.csv  (para Excel)
  - benchmark_resultado.json (trazabilidad)

REQUISITOS para números reales:
  - spaCy con es_core_news_md (motor clásico).
  - (opcional) GLiNER para la columna CON GLiNER:
        pip install -r requirements-gliner.txt
        python -m implica_anon.gliner_detector        # descarga el modelo una vez

USO:
  python tests/benchmark_gliner.py                    # solo clásico
  # Con GLiNER (PowerShell):
  $env:IMPLICA_ENABLE_GLINER="true"; $env:IMPLICA_GLINER_ALLOW_DOWNLOAD="true"
  python tests/benchmark_gliner.py

NOTA: si spaCy está bloqueado/no instalado, el motor clásico cae a heurísticas
(menos preciso) y el informe lo indica — los números solo son representativos en una
máquina con spaCy operativo.
"""
import csv
import io
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures" / "benchmark"
FIX.mkdir(parents=True, exist_ok=True)

GROUND_TRUTH = {
    "teaser": [
        "Proyecto Halcón", "Clínica Dental Sonrisa S.L.", "Implica Corporate Finance",
        "Mediterráneo Capital Partners", "DentalGroup Europe", "Alberto Ramírez",
        "María Fernández", "sonrisadental.es",
    ],
    "excel": [
        "Distribuciones García S.L.", "Mercadona S.A.", "Supermercados Día",
        "Suministros Dentales Ibéricos S.L.", "Material Médico Europa S.A.",
        "Banco Santander", "CaixaBank",
        "Laura Gómez Ruiz", "Javier Torres Molina",
        "Inversiones Halcón S.L.", "Patrimonial Ramírez S.A.",
    ],
    "pptx": [
        "Proyecto Halcón", "Salud Capital Partners", "Grupo Ramírez S.L.",
        "Implica Corporate Finance", "Mediterráneo Capital Partners",
        "Garrigues", "Alberto Ramírez",
    ],
}

DOC_LABEL = {"teaser": "Teaser M&A (PDF)", "excel": "Excel listado (no contable)",
             "pptx": "Presentación (PPTX)"}


def make_teaser_pdf() -> Path:
    import fitz
    path = FIX / "teaser_proyecto_halcon.pdf"
    lines = [
        "PROYECTO HALCÓN — Información Confidencial", "",
        "Implica Corporate Finance presenta una oportunidad de inversión en el sector dental.", "",
        "La compañía objetivo, Clínica Dental Sonrisa S.L. (CIF B12345678), es una cadena",
        "de clínicas dentales con sede en Valencia y web sonrisadental.es.", "",
        "Fundada por el Dr. Alberto Ramírez (CEO), la dirección financiera está a cargo de",
        "María Fernández (CFO). La compañía ha mostrado un crecimiento sólido.", "",
        "Entre los inversores interesados figura Mediterráneo Capital Partners, fondo de",
        "private equity especializado en salud. Como comparable de mercado se cita a",
        "DentalGroup Europe.", "",
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
    ws.append(["Tipo", "Nombre", "CIF / DNI", "Sector / Puesto"])
    rows = [
        ("Cliente", "Distribuciones García S.L.", "B11111111", "Distribución"),
        ("Cliente", "Mercadona S.A.", "A22222222", "Retail"),
        ("Cliente", "Supermercados Día", "A33333333", "Retail"),
        ("Proveedor", "Suministros Dentales Ibéricos S.L.", "B44444444", "Material dental"),
        ("Proveedor", "Material Médico Europa S.A.", "A55555555", "Material médico"),
        ("Banco", "Banco Santander", "A66666666", "Entidad financiera"),
        ("Banco", "CaixaBank", "A77777777", "Entidad financiera"),
        ("Empleado", "Laura Gómez Ruiz", "12345678Z", "Directora comercial"),
        ("Empleado", "Javier Torres Molina", "87654321X", "Responsable de compras"),
        ("Sociedad", "Inversiones Halcón S.L.", "B88888888", "Holding"),
        ("Sociedad", "Patrimonial Ramírez S.A.", "A99999999", "Patrimonial"),
    ]
    for r in rows:
        ws.append(r)
    wb.save(str(path))
    return path


def make_pptx() -> Path:
    from pptx import Presentation
    path = FIX / "presentacion_proyecto_halcon.pptx"
    prs = Presentation()
    slides_text = [
        ("Proyecto Halcón", "Resumen de la operación — Confidencial"),
        ("Partes de la operación",
         "Vendedor: Grupo Ramírez S.L.\nComprador: Salud Capital Partners\n"
         "Fondo coinversor: Mediterráneo Capital Partners\n"
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


def detect_entities(path: Path):
    from implica_anon import formats
    from implica_anon.detectors import detect_candidates, cluster_variants
    t0 = time.time()
    texts = formats.extract_text(path)
    candidates = detect_candidates(texts, skip_ner=False)
    clusters = cluster_variants(candidates)
    elapsed = time.time() - t0
    name_kinds = {"ORG", "PER", "CLIENTE", "PROVEEDOR", "DEUDOR", "GRUPO", "BANCO", "DOMINIO"}
    ents = {c.canonical for c in clusters if c.kind in name_kinds}
    return ents, elapsed


def _norm(s: str) -> str:
    return s.strip().lower()


def _hits(detected: set, truth: list) -> list:
    dl = [_norm(d) for d in detected]
    return [t for t in truth if any(_norm(t) in d or d in _norm(t) for d in dl)]


def _false_positives(detected: set, truth: list) -> list:
    tl = [_norm(t) for t in truth]
    return [d for d in detected if not any(_norm(d) in t or t in _norm(d) for t in tl)]


def _spacy_ok() -> bool:
    try:
        from implica_anon.detectors import _load_nlp
        return _load_nlp() is not None
    except Exception:
        return False


def collect():
    paths = {"teaser": make_teaser_pdf(), "excel": make_excel(), "pptx": make_pptx()}
    from implica_anon import gliner_detector
    gliner_active = gliner_detector.is_enabled()
    spacy_ok = _spacy_ok()

    docs = []
    for k, p in paths.items():
        truth = GROUND_TRUTH[k]
        os.environ.pop("IMPLICA_ENABLE_GLINER", None)
        base_ents, base_t = detect_entities(p)
        if gliner_active:
            os.environ["IMPLICA_ENABLE_GLINER"] = "true"
            gln_ents, gln_t = detect_entities(p)
        else:
            gln_ents, gln_t = base_ents, base_t

        base_hits = _hits(base_ents, truth)
        gln_hits = _hits(gln_ents, truth)
        new_useful = [e for e in gln_hits if e not in base_hits]
        rec = _doc_reco(gliner_active, len(base_hits), len(gln_hits),
                        len(_false_positives(base_ents, truth)),
                        len(_false_positives(gln_ents, truth)))
        docs.append({
            "doc": k, "label": DOC_LABEL[k], "file": p.name, "truth": len(truth),
            "base_hits": len(base_hits), "gln_hits": len(gln_hits),
            "new_useful": new_useful,
            "base_fp": len(_false_positives(base_ents, truth)),
            "gln_fp": len(_false_positives(gln_ents, truth)),
            "base_t": round(base_t, 2), "gln_t": round(gln_t, 2),
            "recommendation": rec,
        })
    os.environ.pop("IMPLICA_ENABLE_GLINER", None)

    totals = {kk: sum(d[kk] for d in docs) for kk in
              ("truth", "base_hits", "gln_hits", "base_fp", "gln_fp")}
    totals["new_useful"] = sum(len(d["new_useful"]) for d in docs)
    totals["base_t"] = round(sum(d["base_t"] for d in docs), 2)
    totals["gln_t"] = round(sum(d["gln_t"] for d in docs), 2)

    return {
        "meta": {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "gliner_active": gliner_active,
            "spacy_ok": spacy_ok,
            "model": os.environ.get("IMPLICA_GLINER_MODEL", gliner_detector.DEFAULT_MODEL),
        },
        "docs": docs,
        "totals": totals,
    }


def _doc_reco(active, bh, gh, bfp, gfp):
    if not active:
        return "Pendiente (GLiNER no activo)"
    extra = gh - bh
    if extra >= 2 and (gfp - bfp) <= extra:
        return "Activar"
    if extra >= 1:
        return "Opcional"
    return "No aporta"


def _overall_reco(res):
    if not res["meta"]["gliner_active"]:
        return "Seguir probando"
    t = res["totals"]
    extra = t["gln_hits"] - t["base_hits"]
    extra_fp = t["gln_fp"] - t["base_fp"]
    # Si solo mejora texto libre, recomendamos activación selectiva
    narrative_gain = sum(d["gln_hits"] - d["base_hits"] for d in res["docs"] if d["doc"] in ("teaser", "pptx"))
    if extra >= 3 and extra_fp <= extra and narrative_gain >= extra * 0.6:
        return "Activar GLiNER solo para documentos narrativos"
    if extra >= 4 and extra_fp <= extra:
        return "Activar GLiNER para todo"
    if extra >= 1:
        return "Seguir probando"
    return "Mantener GLiNER apagado"


# --- Secciones estáticas (no dependen de los números) ---

SECCION_EQUIPO = """## 5. Pensado para equipo

Si esto lo usara **todo el equipo de Implica**, hay dos formas de desplegarlo:

| | A) App centralizada (servidor/Azure) | B) App local por analista |
|---|---|---|
| Instalación | 1 sola (la hace IT) | Cada persona instala Python/Torch/modelo |
| Acceso | Por navegador | App en cada equipo |
| Mantenimiento | IT controla deps, modelo y versiones | Cada uno mantiene lo suyo |
| Consistencia | Todos la misma versión/modelo | Riesgo de versiones distintas |
| Confidencialidad | En el tenant de Implica (ya privado) | En el equipo de cada analista |
| Coste de arranque | Imagen más pesada (Torch+modelo) una vez | Torch+modelo en N equipos |
| Facilidad para el equipo | Alta | Baja |

**Recomendación para Implica: opción A (centralizada).**
- El anonimizador YA está desplegado centralizado (Azure Container App en el tenant de Implica). Añadir GLiNER ahí (cuando se apruebe) es **una sola decisión**, no diez instalaciones.
- Nadie instala Torch (pesado) ni descarga modelos; el equipo solo usa el navegador.
- IT controla el modelo, su **licencia** y la versión → consistencia y trazabilidad.
- La ventaja de privacidad de la opción B es **redundante**: la app central ya vive dentro del perímetro de Implica (igual que OneDrive). No se gana privacidad instalando en cada equipo, solo complejidad.
"""

SECCION_REQUISITOS = """## 6. Requisitos antes de que lo use el equipo

- [ ] **spaCy funcionando** (es_core_news_md) en el servidor — desbloquear DLLs en Application Control si aplica.
- [ ] **GLiNER instalado solo si IT lo aprueba** (no por defecto).
- [ ] **Modelo descargado manualmente** una vez (`python -m implica_anon.gliner_detector`); después, offline.
- [ ] **Licencia documentada** del modelo (Apache-2.0 verificada para `urchade/gliner_multi-v2.1`).
- [ ] **Pruebas con documentos ficticios** (este benchmark).
- [ ] **Pruebas con documentos anonimizados** reales (sin PII) para validar en casos propios.
- [ ] **Decisión de IT antes de producción**.
- [ ] **No activar en Azure todavía** (la imagen no lleva GLiNER; sigue dormido).
"""


def write_reports(res):
    md = _build_md(res)
    (ROOT / "benchmark_resultado.md").write_text(md, encoding="utf-8")

    with (ROOT / "benchmark_resultado.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Documento", "Entidades reales", "Aciertos sin GLiNER",
                    "Aciertos con GLiNER", "Nuevas utiles", "FP sin", "FP con",
                    "Tiempo sin (s)", "Tiempo con (s)", "Recomendacion"])
        for d in res["docs"]:
            w.writerow([d["label"], d["truth"], d["base_hits"], d["gln_hits"],
                        len(d["new_useful"]), d["base_fp"], d["gln_fp"],
                        d["base_t"], d["gln_t"], d["recommendation"]])
        t = res["totals"]
        w.writerow(["TOTAL", t["truth"], t["base_hits"], t["gln_hits"], t["new_useful"],
                    t["base_fp"], t["gln_fp"], t["base_t"], t["gln_t"], _overall_reco(res)])

    (ROOT / "benchmark_resultado.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_md(res):
    m, t = res["meta"], res["totals"]
    active, spok = m["gliner_active"], m["spacy_ok"]
    overall = _overall_reco(res)

    L = []
    L.append("# Benchmark GLiNER — Implica Anonimizador\n")
    L.append(f"_Generado: {m['timestamp']} · Modelo: `{m['model']}`_\n")
    if not spok:
        L.append("> ⚠️ **spaCy no estaba operativo**: el motor clásico cayó a heurísticas. "
                 "Los números infravaloran el clásico. Repite en una máquina con spaCy.\n")
    if not active:
        L.append("> ⚠️ **GLiNER no estaba activo**: la columna 'con GLiNER' = clásico. "
                 "Repite con `IMPLICA_ENABLE_GLINER=true` y GLiNER instalado.\n")

    # 1. Resumen ejecutivo
    L.append("## 1. Resumen ejecutivo\n")
    if not active:
        L.append("No se ha ejecutado la comparación real con GLiNER (estaba desactivado). "
                 "El motor clásico detectó **{}/{}** entidades con **{} falsos positivos** en "
                 "{:.1f}s. Para decidir si GLiNER aporta, hay que repetir el benchmark con "
                 "GLiNER instalado y activo en una máquina con spaCy operativo. Hasta entonces, "
                 "la recomendación es **seguir probando**.\n".format(
                     t["base_hits"], t["truth"], t["base_fp"], t["base_t"]))
    else:
        extra = t["gln_hits"] - t["base_hits"]
        extra_fp = t["gln_fp"] - t["base_fp"]
        L.append("Sobre {} entidades reales, el motor clásico detectó {} y con GLiNER {} "
                 "(**{:+d}** entidades útiles). Falsos positivos: {} → {} (**{:+d}**). "
                 "Tiempo total: {:.1f}s → {:.1f}s. GLiNER {} en documentos narrativos "
                 "(teaser/PPT) y no interviene en Excel contable PGC. "
                 "Recomendación global: **{}**.\n".format(
                     t["truth"], t["base_hits"], t["gln_hits"], extra,
                     t["base_fp"], t["gln_fp"], extra_fp, t["base_t"], t["gln_t"],
                     "aporta" if extra > 0 else "no aporta valor neto", overall))

    # 2. Tabla comparativa
    L.append("## 2. Tabla comparativa\n")
    L.append("| Documento | Reales | Sin GLiNER | Con GLiNER | Nuevas útiles | FP sin | FP con | Tiempo sin | Tiempo con | Recomendación |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for d in res["docs"]:
        L.append("| {} | {} | {} | {} | {} | {} | {} | {:.2f}s | {:.2f}s | {} |".format(
            d["label"], d["truth"], d["base_hits"], d["gln_hits"], len(d["new_useful"]),
            d["base_fp"], d["gln_fp"], d["base_t"], d["gln_t"], d["recommendation"]))
    L.append("| **TOTAL** | {} | {} | {} | {} | {} | {} | {:.2f}s | {:.2f}s | **{}** |".format(
        t["truth"], t["base_hits"], t["gln_hits"], t["new_useful"], t["base_fp"],
        t["gln_fp"], t["base_t"], t["gln_t"], overall))
    L.append("")
    new_all = [e for d in res["docs"] for e in d["new_useful"]]
    if new_all:
        L.append("**Entidades nuevas útiles que añadió GLiNER:** " + ", ".join(new_all) + "\n")

    # 3. Conclusión funcional
    L.append("## 3. Conclusión funcional (por tipo de documento)\n")
    def verdict(doc_key, measured=True):
        if not active:
            return "Pendiente de medir"
        d = next((x for x in res["docs"] if x["doc"] == doc_key), None)
        if d is None:
            return "Inferido"
        g = d["gln_hits"] - d["base_hits"]
        return "Sí aporta (+{})".format(g) if g > 0 else "No aporta"
    L.append("| Tipo | ¿Merece la pena GLiNER? | Nota |")
    L.append("|---|---|---|")
    L.append(f"| Teasers | {verdict('teaser')} | Medido (texto libre, es su punto fuerte) |")
    L.append(f"| PDFs con texto | {verdict('teaser')} | Misma ruta NER que el teaser |")
    L.append(f"| PowerPoints | {verdict('pptx')} | Medido |")
    L.append("| Word | Inferido = igual que teaser | Misma ruta NER (no medido aparte) |")
    L.append("| Excels CONTABLES (PGC) | No aplica | El motor PGC ya es 100%; GLiNER no interviene por diseño |")
    L.append(f"| Excels NO contables | {verdict('excel')} | Medido (listado de nombres) |")
    L.append("")

    # 4. Recomendación de activación
    L.append("## 4. Recomendación de activación\n")
    L.append(f"**➡️ {overall}**\n")
    opts = ["Activar GLiNER para todo", "Activar GLiNER solo para documentos narrativos",
            "Mantener GLiNER apagado", "Seguir probando"]
    L.append("Opciones consideradas: " + " · ".join(
        ("**" + o + "**" if o == overall else o) for o in opts) + "\n")

    # 5 y 6 (estáticas)
    L.append(SECCION_EQUIPO)
    L.append(SECCION_REQUISITOS)

    # 7. Output adicional
    L.append("## 7. Output adicional\n")
    L.append("- `benchmark_resultado.csv` — la tabla para abrir en Excel.")
    L.append("- `benchmark_resultado.json` — datos completos para trazabilidad.\n")
    return "\n".join(L)


def run():
    print("Generando fixtures y ejecutando benchmark...")
    res = collect()
    write_reports(res)
    t = res["totals"]
    print(f"\nTotal: clásico {t['base_hits']}/{t['truth']} (FP {t['base_fp']}) · "
          f"GLiNER {t['gln_hits']}/{t['truth']} (FP {t['gln_fp']}) · recomendación: {_overall_reco(res)}")
    print("\nInformes generados en la raíz del proyecto:")
    print("  - benchmark_resultado.md")
    print("  - benchmark_resultado.csv")
    print("  - benchmark_resultado.json")
    if not res["meta"]["gliner_active"]:
        print("\n⚠️ GLiNER no estaba activo → repite con IMPLICA_ENABLE_GLINER=true "
              "e IMPLICA_GLINER_ALLOW_DOWNLOAD=true para la comparación real.")


if __name__ == "__main__":
    run()
