"""Suite de ESTABILIZACIÓN de la app de anonimización local.

Genera fixtures sintéticos (nunca datos reales) y comprueba los 7 criterios de
aceptación con métricas. Uso:

    python tests/test_stabilizacion.py

Reporta: tiempos frío/caliente, entidades, clusters, sugerencias, tiempos de
clustering y sugerencias, si reanudar funciona, y PASS/FAIL por criterio.
"""
import io
import os
import sys
import time
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "fixtures" / "stab"
FIX.mkdir(parents=True, exist_ok=True)

from openpyxl import Workbook, load_workbook
from implica_anon import formats, mapping as mapping_mod
from implica_anon.detectors import (
    detect_candidates, cluster_variants, suggest_unifications,
    _maybe_same_entity, Candidate, Cluster, _load_nlp,
)
import streamlit_app as app

RESULTS = []          # (criterio, passed, detalle)
METRICS = {}


def check(crit, cond, detail=""):
    RESULTS.append((crit, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FALLO'}] {crit}" + (f" — {detail}" if detail else ""))
    return bool(cond)


# ------------------------- Fixtures -------------------------
def make_small_mixto():
    p = FIX / "small_mixto.xlsx"
    wb = Workbook(); ws = wb.active; ws.title = "Datos"
    ws.append(["Tipo", "Nombre", "CIF", "Email", "Telefono"])
    rows = [
        ("Principal", "Clinica Dental Sonrisa S.L.", "B12345678", "info@sonrisadental.es", "961112233"),
        ("Cliente", "Distribuciones Garcia S.L.", "B11111111", "compras@garcia.es", "915550011"),
        ("Cliente", "Mercadona SA", "A22222222", "", "963330022"),
        ("Proveedor", "Suministros Dentales Ibericos S.L.", "B44444444", "ventas@sdi.es", ""),
        ("Banco", "Banco Santander", "A66666666", "", ""),
        ("Persona", "Laura Gomez Ruiz", "12345678Z", "lgomez@sonrisadental.es", "600111222"),
    ]
    for r in rows:
        ws.append(r)
    wb.save(p)
    return p


def make_grande_dup(n=1500):
    p = FIX / "grande_dup.xlsx"
    import random
    random.seed(7)
    bases = ["Distribuciones Garcia", "Mercadona", "Supermercados Dia", "Talleres Iberia",
             "Construcciones Lopez", "Frutas Cariñena", "Bricolaje Oriol", "Servicios Vallcarca",
             "Inversiones Halcon", "Montajes Badia"]
    # Falsos parecidos: NO deben agruparse entre sí
    falsos = ["ORIOL", "BRICOL", "BRICOLAJ", "CONST", "CONSTRUC", "CONAST"]
    wb = Workbook(); ws = wb.active; ws.append(["Cliente", "CIF"])
    for i in range(n):
        if i % 7 == 0:
            nombre = random.choice(falsos)
        else:
            b = random.choice(bases)
            suf = random.choice([" S.L.", " SA", " S.L", "", "  SLU", ", S.L."])
            nombre = f"{b}{suf}"
        ws.append([nombre, f"B{10000000 + i}"])
    wb.save(p)
    return p


def make_principal():
    p = FIX / "principal.xlsx"
    wb = Workbook(); ws = wb.active; ws.append(["Nombre"])
    # principal aparece 40 veces; clientes/proveedores también mucho
    for _ in range(40):
        ws.append(["Clinica Dental Sonrisa S.L."])
    for _ in range(60):
        ws.append(["Distribuciones Garcia S.L."])
    for _ in range(55):
        ws.append(["Suministros Dentales Ibericos S.L."])
    wb.save(p)
    return p


# ------------------------- Criterios -------------------------
def c1_arranque():
    print("\n=== C1. Arranque limpio (imports / sin deps obligatorias) ===")
    ok_imp = all(hasattr(app, fn) for fn in
                 ["_clusters_to_df", "_df_to_mapping", "_process_files",
                  "_save_session_cache", "_load_session_cache"])
    check("imports del pipeline OK", ok_imp)
    # gliner NO debe ser obligatorio: importable sin él
    gliner_obligatorio = "gliner" in sys.modules
    check("GLiNER no es dependencia obligatoria", not gliner_obligatorio,
          "gliner no se importa al arrancar")


def c2_rendimiento(grande):
    print("\n=== C2. Rendimiento (Excel grande tipo duplicados) ===")
    nlp = _load_nlp()
    METRICS["spacy_ok"] = nlp is not None
    texts = formats.extract_text(grande)

    t0 = time.time(); cands_cold = detect_candidates(texts, skip_ner=False); t_cold = time.time() - t0
    t0 = time.time(); cands = detect_candidates(texts, skip_ner=False); t_warm = time.time() - t0
    t0 = time.time(); clusters = cluster_variants(cands); t_clu = time.time() - t0
    entries = [(i, c.kind, c.canonical) for i, c in enumerate(clusters)]
    t0 = time.time(); sugg = suggest_unifications(entries); t_sug = time.time() - t0

    METRICS.update({
        "t_cold": round(t_cold, 2), "t_warm": round(t_warm, 2),
        "n_entidades": len(cands), "n_clusters": len(clusters),
        "n_sugerencias": len(sugg), "t_clustering": round(t_clu, 3),
        "t_sugerencias": round(t_sug, 3),
    })
    check("primer análisis ≤ 15s", t_cold <= 15, f"{t_cold:.1f}s")
    check("segundo análisis ≤ 5s", t_warm <= 5, f"{t_warm:.1f}s")
    check("clustering 1500 ≤ 1s", t_clu <= 1, f"{t_clu:.3f}s")
    check("sugerencias ≤ 1s", t_sug <= 1, f"{t_sug:.3f}s")
    return clusters


def c3_persistencia():
    print("\n=== C3. Persistencia / reanudar ===")
    import pandas as pd
    proj = "stab_sesion"
    df = pd.DataFrame([{"_rowid": 0, "Anonimizar": True, "Tipo": "Empresa", "_kind": "ORG",
                        "Canónico": "ACME S.L.", "_variants": ["ACME S.L."], "_account_codes": [],
                        "Variantes": "—", "Cuenta(s)": "—", "Ocurrencias": 5, "Codename": "Paradise"}])
    payload = {"upload_data": [("x.xlsx", b"datos")], "df": df,
               "is_accounting": False, "clusters_raw": []}
    app._save_session_cache(proj, payload)
    loaded = app._load_session_cache(proj)
    ok = (loaded is not None and len(loaded["upload_data"]) == 1
          and list(loaded["df"]["Codename"]) == ["Paradise"])
    check("reanudar recupera análisis (archivo + tabla + codename editado)", ok)
    METRICS["reanudar_ok"] = ok

    # Simular edición manual + re-guardado (como hace la UI tras editar/unificar)
    df.loc[0, "Codename"] = "Eden"          # el usuario cambia el codename
    payload["df"] = df
    app._save_session_cache(proj, payload)  # la UI re-guarda tras el cambio
    loaded2 = app._load_session_cache(proj)
    check("ediciones/merges persisten tras refrescar (no se pierden)",
          loaded2 is not None and list(loaded2["df"]["Codename"]) == ["Eden"])

    app._clear_session_cache(proj)
    cleared = app._load_session_cache(proj) is None
    check("borrar caché funciona", cleared)


def c4_empresa_principal():
    print("\n=== C4. Empresa principal ===")
    pm = mapping_mod.ProjectMapping(project="paradise")
    clusters = [
        Cluster(kind="ORG", canonical="Clinica Dental Sonrisa S.L.",
                variants=["Clinica Dental Sonrisa S.L.", "Clinica Dental Sonrisa"], total_count=40),
        Cluster(kind="CLIENTE", canonical="Distribuciones Garcia S.L.",
                variants=["Distribuciones Garcia S.L."], total_count=60, account_codes=["4300000001"]),
        Cluster(kind="BANCO", canonical="Banco Santander", variants=["Banco Santander"], total_count=10),
        Cluster(kind="PER", canonical="Laura Gomez Ruiz", variants=["Laura Gomez Ruiz"], total_count=3),
    ]
    df = app._clusters_to_df(clusters, pm, "paradise", codename_mode="sequential",
                             main_company="Clinica Dental Sonrisa S.L.")
    row_by_canon = {r["Canónico"]: r for _, r in df.iterrows()}
    principal = row_by_canon.get("Clinica Dental Sonrisa S.L.")
    check("empresa principal → codename del proyecto", principal is not None and principal["Codename"] == "Paradise",
          principal["Codename"] if principal is not None else "no encontrada")
    # clientes/bancos/personas NO deben llevar el codename del proyecto
    otros_ok = all(r["Codename"] != "Paradise" for c, r in row_by_canon.items()
                   if c != "Clinica Dental Sonrisa S.L.")
    check("clientes/proveedores/bancos/personas NO se confunden con la principal", otros_ok)

    # Si la principal no está entre los clusters, debe añadirse igualmente
    df2 = app._clusters_to_df(clusters[1:], pm, "paradise", codename_mode="sequential",
                              main_company="Empresa Fantasma S.L.")
    tiene_fantasma = any(r["Canónico"] == "Empresa Fantasma S.L." and r["Codename"] == "Paradise"
                         for _, r in df2.iterrows())
    check("principal no detectada se añade igualmente al mapping", tiene_fantasma)

    # Sin main_company, no debe haber error (heurística por frecuencia)
    df3 = app._clusters_to_df(clusters, pm, "paradise", codename_mode="sequential")
    check("sin empresa principal indicada, no rompe (deduce por frecuencia)", len(df3) >= 1)


def c5_unificacion():
    print("\n=== C5. Unificación de duplicados ===")
    # Abreviaturas SÍ se sugieren (prefijo): "Mercad" → "Mercadona"
    check("abreviatura se sugiere (Mercad → Mercadona)",
          _maybe_same_entity("Mercadona", "Mercad"))
    # Typo real con cuerpo SÍ se sugiere
    check("typo real se sugiere (Mercadona ~ Mercadnoa)",
          _maybe_same_entity("Mercadona SA", "Mercadnoa SA"))
    # Falsos parecidos cortos NO deben agruparse
    check("parecido superficial NO se une (BRICOL ≠ ORIOL)",
          not _maybe_same_entity("BRICOL", "ORIOL"))
    check("parecido superficial NO se une (CONST ≠ CONAST)",
          not _maybe_same_entity("CONST", "CONAST"))
    # suggest_unifications no debe meter ORIOL con BRICOLAJE
    entries = [(0, "ORG", "Bricolaje Oler"), (1, "ORG", "Bricolajes Oler"),
               (2, "ORG", "Oriol"), (3, "ORG", "Mercadona SA"), (4, "ORG", "Mercadona S.L.")]
    groups = suggest_unifications(entries)
    # Buscar el grupo que contiene 0
    g0 = next((g for g in groups if 0 in g), [0])
    check("ORIOL no entra en el grupo de Bricolaje", 2 not in g0)


def c6_exportacion(small):
    print("\n=== C6. Exportación ===")
    import tempfile
    # Regresión: el CIF debe DETECTARSE (no filtrarse en la extracción)
    cands = detect_candidates(formats.extract_text(small), skip_ner=False)
    check("CIF se detecta (no se filtra en extracción)",
          any(c.kind == "CIF" for c in cands),
          "kinds=" + ",".join(sorted({c.kind for c in cands})))
    pm = mapping_mod.ProjectMapping(project="paradise")
    pm.add("ORG", "Clinica Dental Sonrisa S.L.", "Paradise")
    pm.add("CLIENTE", "Distribuciones Garcia S.L.", "[Cliente-001]")
    pm.add("PROVEEDOR", "Suministros Dentales Ibericos S.L.", "[Proveedor-001]")
    pm.add("CIF", "B12345678", "[CIF-001]")
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "out.xlsx"
        result = formats.apply_replacements(small, pm.all_replacements(), dst)
        ok_open = dst.exists()
        check("genera el archivo anonimizado y se puede abrir", ok_open)
        wb = load_workbook(dst); txt = " ".join(
            str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value)
        check("la empresa principal queda reemplazada por el codename", "Paradise" in txt)
        check("cliente reemplazado con su categoría", "[Cliente-001]" in txt)
        check("CIF reemplazado en el output", "[CIF-001]" in txt and "B12345678" not in txt)
        check("nombre real de la principal NO sobrevive", "Clinica Dental Sonrisa" not in txt)
        check("verify pass confirma limpio (sin las entidades del mapping)", result.is_clean,
              f"surviving={result.surviving}, verifiable={result.verifiable}")


def c7_verify():
    print("\n=== C7. Verify pass básico (no da falso OK) ===")
    from implica_anon.replacer import Replacer
    r = Replacer({"Mercadona": "[Cliente-1]"})
    # Output donde 'Mercadona' SIGUE presente → debe detectarse
    surviv = r.find_surviving("Factura de Mercadona pendiente")
    check("verify detecta entidad que sobrevivió (no falso OK)", "Mercadona" in surviv)
    # Output limpio → sin supervivientes
    check("verify no inventa fugas en output limpio", r.find_surviving("Factura de [Cliente-1]") == [])
    # Fragmentos cortos / substrings NO deben dar falso positivo
    r2 = Replacer({"CON": "[X]", "ALE": "[Y]", "CONSTR": "[Z]"})
    fp = r2.find_surviving("Construcciones varias con alegria y [Z]")  # 'con','ale','constr' como substrings
    check("verify NO marca fragmentos cortos/substrings (CON, ALE dentro de palabras)",
          fp == [], f"falsos positivos={fp}")


def make_columna_nombre():
    """Excel tabular SIN códigos PGC, con columna 'Cliente' de nombres reales:
    varios de varias palabras (con artículo 'LA'/'EL') y uno corto ('ARTEC')."""
    p = FIX / "columna_nombre.xlsx"
    wb = Workbook(); ws = wb.active
    ws.append(["Descripcion", "Cliente"])
    casos = ["LA SIRENA SL", "RIVAS ALMACENES", "ARTEC",
             "Suministros Garcia e Hijos SL", "EL CORTE AZUL SA",
             "Distribuciones Lopez y Asociados SL"]
    for c in casos:
        ws.append([f"Abono ABC-PRE25-00001 {c}", c])
    wb.save(p)
    return p, casos


def c8_columna_nombre():
    """Regresión: nombres de columna 'Cliente' capturados COMPLETOS (no recortados
    por spaCy) y reemplazados en TODAS las columnas, incluida la descripción."""
    print("\n=== C8. Columnas de nombre (multi-palabra + cortos, sin PGC) ===")
    from implica_anon import accounting
    p, casos = make_columna_nombre()

    named = accounting.scan_named_columns(p)
    named_texts = {t for t, _ in named}
    faltan = [c for c in casos if c not in named_texts]
    check("columna 'Cliente': todos los nombres capturados COMPLETOS (incl. cortos)",
          not faltan, f"faltan={faltan}" if faltan else "6/6")

    # Pipeline completo como en la app (no PGC → use_ner=True): named + NER + cluster
    cands = [Candidate(text=t, kind=k, count=1, source="column") for t, k in named]
    cands += detect_candidates(formats.extract_text(p), skip_ner=False)
    clusters = cluster_variants(cands)
    canon = {cl.canonical for cl in clusters}
    completos = [c for c in casos if c in canon]
    # No deben quedar fragmentos recortados ("SIRENA SL", "ALMACENES", "AZUL SA")
    fragmentos = [cl.canonical for cl in clusters
                  if cl.kind in ("ORG", "PER")
                  and any(cl.canonical != c and cl.canonical in c for c in casos)]
    check("tras clustering, los 6 nombres siguen completos", len(completos) == 6,
          f"{len(completos)}/6")
    check("sin fragmentos recortados por spaCy en la tabla", not fragmentos,
          f"fragmentos={fragmentos}" if fragmentos else "ninguno")

    # Reemplazo end-to-end: ni la columna Cliente ni la Descripción dejan rastro
    mapping = {c: f"[Cliente-{i+1:03d}]" for i, c in enumerate(casos)}
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "out.xlsx"
        formats.apply_replacements(p, mapping, dst)
        wb = load_workbook(dst)
        txt = " ".join(str(c.value) for ws in wb.worksheets
                       for row in ws.iter_rows() for c in row if c.value)
    fugas = [frag for frag in ("SIRENA", "RIVAS", "ARTEC", "CORTE", "Distribuciones",
                               "Suministros", "ALMACENES")
             if frag.lower() in txt.lower()]
    check("output sin fugas: ningún nombre real sobrevive (Cliente + Descripción)",
          not fugas, f"fugas={fugas}" if fugas else "limpio")


def print_report():
    print("\n" + "=" * 70)
    print("MÉTRICAS")
    for k, v in METRICS.items():
        print(f"  {k}: {v}")
    print("  connection_error: N/A (suite offline; el server no se prueba aquí)")
    passed = sum(1 for _, p, _ in RESULTS if p)
    total = len(RESULTS)
    print(f"\nTests: {passed}/{total} PASS")
    fails = [c for c, p, _ in RESULTS if not p]
    if fails:
        print("FALLOS:")
        for f in fails:
            print(f"  - {f}")
    print("=" * 70)
    return passed == total


if __name__ == "__main__":
    print("Generando fixtures sintéticos...")
    small = make_small_mixto()
    grande = make_grande_dup()
    make_principal()
    print(f"  {small.name}, {grande.name}, principal.xlsx")

    c1_arranque()
    c2_rendimiento(grande)
    c3_persistencia()
    c4_empresa_principal()
    c5_unificacion()
    c6_exportacion(small)
    c7_verify()
    c8_columna_nombre()
    all_ok = print_report()
    sys.exit(0 if all_ok else 1)
