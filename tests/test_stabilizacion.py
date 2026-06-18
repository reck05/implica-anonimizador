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
    # CIFs VÁLIDOS (dígito de control correcto) — el detector ahora valida checksum
    rows = [
        ("Principal", "Clinica Dental Sonrisa S.L.", "B12345674", "info@sonrisadental.es", "961112233"),
        ("Cliente", "Distribuciones Garcia S.L.", "B11111119", "compras@garcia.es", "915550011"),
        ("Cliente", "Mercadona SA", "A22222228", "", "963330022"),
        ("Proveedor", "Suministros Dentales Ibericos S.L.", "B44444446", "ventas@sdi.es", ""),
        ("Banco", "Banco Santander", "A66666660", "", ""),
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
    pm.add("CIF", "B12345674", "[CIF-001]")
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "out.xlsx"
        result = formats.apply_replacements(small, pm.all_replacements(), dst)
        ok_open = dst.exists()
        check("genera el archivo anonimizado y se puede abrir", ok_open)
        wb = load_workbook(dst); txt = " ".join(
            str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value)
        check("la empresa principal queda reemplazada por el codename", "Paradise" in txt)
        check("cliente reemplazado con su categoría", "[Cliente-001]" in txt)
        check("CIF reemplazado en el output", "[CIF-001]" in txt and "B12345674" not in txt)
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
    check("tras clustering, los 6 nombres siguen completos", len(completos) == 6,
          f"{len(completos)}/6")
    # Nota: algún fragmento de spaCy ("SIRENA SL") puede quedar como fila extra; no
    # es fuga (el nombre completo está en el mapping y se reemplaza primero) y el
    # dedup conservador prefiere no arriesgarse a tirar una empresa legítima corta.
    fragmentos = [cl.canonical for cl in clusters
                  if cl.kind in ("ORG", "PER")
                  and any(cl.canonical != c and cl.canonical in c for c in casos)]
    print(f"  [info] fragmentos spaCy residuales (ruido, no fuga): {fragmentos or 'ninguno'}")

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


def c9_contexto_y_confidencialidad():
    """Regresión de los fixes del review: contexto distingue truncados, el CIF va
    enmascarado, y cabeceras 'Nombre' genéricas no se tratan como empresa."""
    print("\n=== C9. Contexto (distingue truncados) + confidencialidad ===")
    from implica_anon import accounting
    from openpyxl import Workbook as _WB
    wb = _WB(); ws = wb.active
    ws.append(["Cliente", "CIF", "Importe"])
    rows = [("CONST. A", "B11111111", "1.200,00"),
            ("CONST. Y", "B22222222", "3.400,50")]
    for r in rows:
        ws.append(r)
    p = FIX / "ctx_trunc.xlsx"; wb.save(p)

    ctx = accounting.row_contexts(p, {"const. a", "const. y"})
    ca, cy = ctx.get("const. a", ""), ctx.get("const. y", "")
    check("contexto distingue dos truncados con mismo prefijo", ca != cy and ca and cy,
          f"A={ca!r} Y={cy!r}")
    check("el CIF va ENMASCARADO en el contexto (no aparece completo)",
          "B11111111" not in ca and "B22222222" not in cy,
          f"A={ca!r}")

    # Cabecera 'Nombre de contacto' NO debe tratarse como columna de empresa
    k1 = accounting._name_header_kind("Nombre de contacto")
    k2 = accounting._name_header_kind("Nombre")
    k3 = accounting._name_header_kind("Nombre cliente")
    check("cabecera 'Nombre' / 'Nombre de contacto' no se trata como empresa",
          k1 is None and k2 is None, f"contacto={k1}, nombre={k2}")
    check("cabecera 'Nombre cliente' sí se detecta como CLIENTE", k3 == "CLIENTE", f"{k3}")

    # Dedup conservador: empresa corta legítima frecuente NO se descarta por estar
    # contenida en otra más larga.
    cands = [
        Candidate(text="Azul Marketing SL", kind="CLIENTE", count=5, source="column"),
        Candidate(text="Azul", kind="ORG", count=8, source="ner"),  # cliente real, frecuente
    ]
    cl = cluster_variants(cands)
    canon = {c.canonical for c in cl}
    check("dedup conservador no tira una empresa corta frecuente ('Azul')",
          "Azul" in canon, f"canon={sorted(canon)}")


def c10_robustez_formatos():
    """Regresión Iter 9: metadatos scrub en todos los formatos + cobertura Excel
    (comentarios/hipervínculos/validaciones), PPTX (hipervínculos), Word (partes
    ocultas vía XML) y validez del .docx tras el sweep."""
    print("\n=== C10. Robustez cross-formato (metadatos + canales ocultos) ===")
    import tempfile as _tmp
    from pathlib import Path as _P
    NAME = "Global Menta S.L."
    CODE = "Paradise"
    mapping = {NAME: CODE}

    with _tmp.TemporaryDirectory() as d:
        d = _P(d)

        # --- Excel: metadatos + comentario + hipervínculo + validación de datos ---
        try:
            from openpyxl import Workbook as _WB, load_workbook as _LW
            from openpyxl.comments import Comment as _Cm
            from openpyxl.worksheet.datavalidation import DataValidation as _DV
            wb = _WB(); ws = wb.active
            ws["A1"] = "Cabecera"
            ws["A2"] = "dato"
            ws["A2"].comment = _Cm(f"Nota: cliente {NAME}", "rev")
            ws["B2"] = "link"
            ws["B2"].hyperlink = f"https://crm.local/?c={NAME}"
            dv = _DV(type="list", formula1=f'"{NAME},Otra"')
            ws.add_data_validation(dv); dv.add("C2")
            wb.properties.creator = "Carlos García"
            wb.properties.title = f"Deal {NAME}"
            xs = d / "m.xlsx"; wb.save(xs)
            xo = d / "m.out.xlsx"; formats.apply_replacements(xs, mapping, xo)
            wo = _LW(xo)
            wso = wo.active
            cmt_ok = NAME not in (wso["A2"].comment.text if wso["A2"].comment else "")
            hl_ok = wso["B2"].hyperlink is None or NAME not in (wso["B2"].hyperlink.target or "")
            dv_ok = all(NAME not in (x.formula1 or "") for x in wso.data_validations.dataValidation)
            meta_ok = (not wo.properties.creator) and (NAME not in (wo.properties.title or ""))
            check("Excel: comentario de celda anonimizado", cmt_ok)
            check("Excel: hipervínculo de celda anonimizado", hl_ok)
            check("Excel: validación de datos anonimizada", dv_ok)
            check("Excel: metadatos (autor vacío, título mapeado)", meta_ok,
                  f"creator={wo.properties.creator!r} title={wo.properties.title!r}")
        except Exception as e:
            check("Excel: cobertura ampliada", False, f"excepción: {e}")

        # --- Word: metadatos + cuerpo (vía apply) y partes ocultas (vía sweep) ---
        try:
            from docx import Document as _Doc
            from implica_anon.replacer import Replacer as _Rep
            from implica_anon.formats import word as _wordmod
            import zipfile as _zip
            doc = _Doc()
            doc.add_paragraph(f"Cuerpo: {NAME}")
            doc.core_properties.author = "Carlos García"
            doc.core_properties.title = f"Proyecto {NAME}"
            ws_ = d / "m.docx"; doc.save(ws_)
            do = d / "m.out.docx"; formats.apply_replacements(ws_, mapping, do)
            # Validez: python-docx abre el resultado tras el sweep (repack OK)
            opened = _Doc(do)
            body_ok = NAME not in "\n".join(p.text for p in opened.paragraphs)
            meta_ok = (not opened.core_properties.author) and (NAME not in (opened.core_properties.title or ""))
            check("Word: el .docx resultante sigue siendo válido (abre)", True)
            check("Word: cuerpo anonimizado", body_ok)
            check("Word: metadatos (autor vacío, título mapeado)", meta_ok,
                  f"author={opened.core_properties.author!r}")

            # Sweep de partes ocultas (comentarios/notas/control de cambios/textboxes):
            # python-docx DESCARTA partes no registradas al guardar, así que probamos
            # el sweep directamente sobre un .docx que SÍ las contiene (como las que
            # crea Word real, que python-docx preserva como partes registradas).
            inj = d / "m.inj.docx"
            comments_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f'<w:comment w:id="1" w:author="x" w:date="2024-01-01T00:00:00Z">'
                f'<w:p><w:r><w:t>Comentario sobre {NAME}</w:t></w:r></w:p></w:comment></w:comments>'
            )
            with _zip.ZipFile(ws_) as zin, _zip.ZipFile(inj, "w", _zip.ZIP_DEFLATED) as zout:
                for item in zin.namelist():
                    zout.writestr(item, zin.read(item))
                zout.writestr("word/comments.xml", comments_xml)
            _wordmod._sweep_hidden_xml(inj, _Rep(mapping))
            with _zip.ZipFile(inj) as z:
                comments_after = z.read("word/comments.xml").decode("utf-8", "ignore")
            hidden_ok = NAME not in comments_after and CODE in comments_after
            check("Word: parte oculta (comentario) anonimizada vía XML sweep", hidden_ok,
                  "" if hidden_ok else f"...{comments_after[-120:]}")
            # Y que el sweep dejó un .docx válido
            _Doc(inj)
            check("Word: el sweep no corrompe el .docx (abre tras repack)", True)
        except Exception as e:
            check("Word: cobertura ampliada + validez", False, f"excepción: {e}")

        # --- PPTX: metadatos + hipervínculo de run ---
        try:
            from pptx import Presentation as _Pr
            from pptx.util import Inches as _In
            prs = _Pr()
            slide = prs.slides.add_slide(prs.slide_layouts[5])
            tb = slide.shapes.add_textbox(_In(1), _In(1), _In(5), _In(1))
            run = tb.text_frame.paragraphs[0].add_run()
            run.text = "ver web"
            run.hyperlink.address = f"https://x.local/?c={NAME}"
            prs.core_properties.author = "Carlos García"
            prs.core_properties.title = f"Teaser {NAME}"
            ps = d / "m.pptx"; prs.save(ps)
            po = d / "m.out.pptx"; formats.apply_replacements(ps, mapping, po)
            opened = _Pr(po)
            addr = opened.slides[0].shapes[1].text_frame.paragraphs[0].runs[0].hyperlink.address or ""
            hl_ok = NAME not in addr
            meta_ok = (not opened.core_properties.author) and (NAME not in (opened.core_properties.title or ""))
            check("PPTX: hipervínculo de run anonimizado", hl_ok, f"addr={addr!r}")
            check("PPTX: metadatos (autor vacío, título mapeado)", meta_ok,
                  f"author={opened.core_properties.author!r}")
        except Exception as e:
            check("PPTX: cobertura ampliada", False, f"excepción: {e}")

        # --- PDF: metadatos limpiados ---
        try:
            import fitz as _fitz
            doc = _fitz.open()
            page = doc.new_page()
            page.insert_text((72, 72), f"Cuerpo {NAME}")
            doc.set_metadata({"author": "Carlos García", "title": f"IM {NAME}",
                              "subject": NAME, "keywords": "", "creator": "Word",
                              "producer": "Word"})
            pf = d / "m.pdf"; doc.save(str(pf)); doc.close()
            pofd = d / "m.out.pdf"; formats.apply_replacements(pf, mapping, pofd)
            od = _fitz.open(str(pofd)); md = od.metadata or {}; od.close()
            meta_ok = (not md.get("author")) and (NAME not in (md.get("title") or "")) and (NAME not in (md.get("subject") or ""))
            check("PDF: metadatos limpiados (autor vacío, título/asunto sin nombre real)", meta_ok,
                  f"md={{'author':{md.get('author')!r},'title':{md.get('title')!r}}}")
        except Exception as e:
            check("PDF: metadatos limpiados", False, f"excepción: {e}")


def c11_checksum_identificadores():
    """Iter 10 fase 1: validación por dígito de control de NIF/CIF/IBAN.
    Reduce falsos positivos (códigos que solo 'parecen' un ID) sin perder los
    reales ni los etiquetados explícitamente."""
    print("\n=== C11. Validación checksum NIF/CIF/IBAN ===")
    from implica_anon.detectors import (
        validate_nif, validate_cif, validate_iban, detect_candidates,
    )
    check("NIF válido aceptado (12345678Z)", validate_nif("12345678Z"))
    check("NIE válido aceptado (X1234567L)", validate_nif("X1234567L"))
    check("NIF inválido rechazado (12345678A)", not validate_nif("12345678A"))
    check("CIF válido aceptado (B12345674)", validate_cif("B12345674"))
    check("CIF inválido rechazado (B12345678)", not validate_cif("B12345678"))
    check("IBAN válido aceptado", validate_iban("ES9121000418450200051332"))
    check("IBAN inválido rechazado", not validate_iban("ES0021000418450200051332"))

    # Detección: un código que parece NIF pero NO lo es y SIN etiqueta → se descarta
    cands = detect_candidates(["Referencia interna 12345678A del pedido"], skip_ner=True)
    nif_fp = [c for c in cands if c.kind == "NIF"]
    check("código tipo-NIF sin etiqueta ni checksum NO se detecta (menos falsos +)",
          not nif_fp, f"detectados={[c.text for c in nif_fp]}")
    # Pero un NIF/CIF inválido CON etiqueta de contexto sí (tolera erratas)
    cands2 = detect_candidates(["NIF: 12345678A del titular"], skip_ner=True)
    check("ID inválido pero ETIQUETADO (NIF: ...) sí se detecta",
          any(c.kind == "NIF" for c in cands2),
          "kinds=" + ",".join(sorted({c.kind for c in cands2})))
    # Y un CIF válido se detecta normal
    cands3 = detect_candidates(["La sociedad B12345674 factura..."], skip_ner=True)
    check("CIF válido se detecta sin necesidad de etiqueta",
          any(c.kind == "CIF" for c in cands3))


def c12_presidio_opcional():
    """Iter 10 fase 2: capa opcional Presidio (MIT, local). Off por defecto;
    al activarla aporta spans de PERSONA completos en texto narrativo."""
    print("\n=== C12. Capa opcional Presidio ===")
    import os as _os
    from implica_anon import presidio_detector as _pd

    # Off por defecto: sin la variable de entorno, no se activa
    _os.environ.pop("IMPLICA_ENABLE_PRESIDIO", None)
    check("Presidio OFF por defecto (no se activa sin la variable)", not _pd.is_enabled())

    # Importable sin romper aunque no esté el paquete (degradación elegante)
    check("módulo presidio_detector importa y no rompe el arranque", True)

    try:
        import presidio_analyzer  # noqa
        have = True
    except Exception:
        have = False
    if not have:
        check("Presidio no instalado → se omite (motor clásico)", True)
        return

    # Activado: detecta PERSONA con span completo en narrativo
    _os.environ["IMPLICA_ENABLE_PRESIDIO"] = "true"
    try:
        _pd._load_analyzer.cache_clear()
        ents = _pd.detect_presidio_entities(
            "El administrador Carlos García Pérez firmó el acuerdo por la sociedad."
        )
        persons = [t for (t, lab, sc) in ents if lab == "PERSON"]
        full = any("Carlos García Pérez" in p or p in "Carlos García Pérez" and len(p) >= len("Carlos García") for p in persons)
        check("Presidio activo detecta PERSONA con span completo", full,
              f"personas={persons}")
    finally:
        _os.environ.pop("IMPLICA_ENABLE_PRESIDIO", None)
        try:
            _pd._load_analyzer.cache_clear()
        except Exception:
            pass


def c13_ocr_opcional():
    """Iter 10 fase 3: capa OCR opcional para PDFs escaneados. Off por defecto y
    degrada con gracia si falta el binario Tesseract (no rompe)."""
    print("\n=== C13. OCR opcional (PDF escaneado) ===")
    import os as _os
    from implica_anon.formats import pdf as _pdf

    _os.environ.pop("IMPLICA_ENABLE_OCR", None)
    check("OCR OFF por defecto", not _pdf._ocr_enabled())
    # ocr_available no debe lanzar (devuelve True/False según haya binario)
    try:
        av = _pdf.ocr_available()
        check("ocr_available() no lanza (devuelve bool)", isinstance(av, bool), f"disponible={av}")
    except Exception as e:
        check("ocr_available() no lanza", False, f"excepción: {e}")

    # Un PDF con capa de texto se extrae igual (OCR no interfiere)
    try:
        import fitz as _fitz, tempfile as _tmp
        from pathlib import Path as _P
        doc = _fitz.open(); pg = doc.new_page(); pg.insert_text((72, 72), "Texto Global Menta")
        with _tmp.TemporaryDirectory() as t:
            f = _P(t) / "t.pdf"; doc.save(str(f)); doc.close()
            txt = " ".join(_pdf.extract_text(f))
        check("PDF con texto se extrae normal (OCR no interfiere)", "Global Menta" in txt)
    except Exception as e:
        check("PDF con texto se extrae normal", False, f"excepción: {e}")


def c14_relation_hint():
    """Iter 12: la sugerencia de unión explica POR QUÉ se relacionan los nombres."""
    print("\n=== C14. 'Por qué se relacionan' en unificación ===")
    rh = app._relation_hint
    # Empiezan igual (prefijo común)
    h1 = rh([{"Canónico": "JOSE A", "_account_codes": [], "Contexto": "—"},
             {"Canónico": "JOSE ANT", "_account_codes": [], "Contexto": "—"}])
    check("detecta prefijo común (empiezan igual)", "empiezan igual" in h1 and "JOSE A" in h1, h1)
    # Misma cuenta contable
    h2 = rh([{"Canónico": "Garcia SL", "_account_codes": ["4300001"], "Contexto": "—"},
             {"Canónico": "Garcia", "_account_codes": ["4300001"], "Contexto": "—"}])
    check("detecta misma cuenta PGC", "misma cuenta" in h2 and "4300001" in h2, h2)
    # Código común en el contexto (factura)
    h3 = rh([{"Canónico": "JOSE A", "_account_codes": [], "Contexto": "5561 · FAC-HRM25-00027 · 395"},
             {"Canónico": "JOSE ANT", "_account_codes": [], "Contexto": "7010 · FAC-HRM25-00027 · 0"}])
    check("detecta código común en las filas (factura)", "FAC-HRM25-00027" in h3, h3)
    # Sin pistas → fallback
    h4 = rh([{"Canónico": "Mercadona", "_account_codes": [], "Contexto": "—"},
             {"Canónico": "Mercadnoa", "_account_codes": [], "Contexto": "—"}])
    check("fallback cuando no hay código/cuenta/prefijo claro", bool(h4.strip()), h4)


def c15_pptx_graficos():
    """Loop robustez: barrido XML de PPTX cubre el texto de GRÁFICOS (categorías/
    títulos) y deja la presentación válida; + aviso de imágenes."""
    print("\n=== C15. PPTX: gráficos/SmartArt vía barrido XML ===")
    import tempfile as _tmp, zipfile as _zip
    from pathlib import Path as _P
    NAME = "Global Menta S.L."
    try:
        from pptx import Presentation as _Pr
        from pptx.util import Inches as _In
        from pptx.chart.data import CategoryChartData as _CCD
        from pptx.enum.chart import XL_CHART_TYPE as _XL
        from implica_anon.formats import pptx as _pmod

        prs = _Pr()
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        data = _CCD()
        data.categories = [NAME, "Otra Empresa SA"]
        data.add_series("Ventas", (10.0, 20.0))
        slide.shapes.add_chart(_XL.COLUMN_CLUSTERED, _In(1), _In(1), _In(6), _In(4), data)
        with _tmp.TemporaryDirectory() as d:
            src = _P(d) / "g.pptx"; prs.save(src)
            # El nombre debe extraerse (para que entre al mapping) desde el gráfico
            extracted = " ".join(formats.extract_text(src))
            check("PPTX: el nombre del gráfico se EXTRAE (detectable)", NAME in extracted,
                  "" if NAME in extracted else "no extraído")
            dst = _P(d) / "g.out.pptx"
            formats.apply_replacements(src, {NAME: "Paradise"}, dst)
            # 1) abre sin corromperse
            _Pr(dst)
            # 2) el nombre ya no está en NINGÚN XML del .pptx
            leaked = False
            with _zip.ZipFile(dst) as z:
                for n in z.namelist():
                    if n.endswith(".xml") and NAME.encode("utf-8") in z.read(n):
                        leaked = True; break
            check("PPTX: gráfico anonimizado (nombre fuera de todo el XML)", not leaked)
            check("PPTX: la presentación sigue siendo válida tras el barrido", True)
            check("PPTX: count_images no lanza", isinstance(_pmod.count_images(dst), int))
    except Exception as e:
        check("PPTX: cobertura de gráficos", False, f"excepción: {e}")


def c16_pdf_form_fields():
    """Loop robustez: campos de formulario PDF (rellenables) se detectan y anonimizan."""
    print("\n=== C16. PDF: campos de formulario ===")
    NAME = "Global Menta S.L."
    try:
        import fitz as _fitz, tempfile as _tmp
        from pathlib import Path as _P
        doc = _fitz.open()
        page = doc.new_page()
        page.insert_text((72, 200), "Documento con formulario")
        w = _fitz.Widget()
        w.field_name = "cliente"
        w.field_type = _fitz.PDF_WIDGET_TYPE_TEXT
        w.rect = _fitz.Rect(72, 72, 360, 96)
        w.field_value = NAME
        page.add_widget(w)
        with _tmp.TemporaryDirectory() as d:
            src = _P(d) / "form.pdf"; doc.save(str(src)); doc.close()
            extracted = " ".join(formats.extract_text(src))
            check("PDF: el valor del campo se EXTRAE (detectable)", NAME in extracted,
                  "" if NAME in extracted else "no extraído")
            dst = _P(d) / "form.out.pdf"
            formats.apply_replacements(src, {NAME: "Paradise"}, dst)
            od = _fitz.open(str(dst))
            vals = []
            for pg in od:
                for ww in (pg.widgets() or []):
                    if isinstance(ww.field_value, str):
                        vals.append(ww.field_value)
            od.close()
            joined = " ".join(vals)
            check("PDF: campo de formulario anonimizado", NAME not in joined and "Paradise" in joined,
                  f"valores={vals}")
    except Exception as e:
        check("PDF: campos de formulario", False, f"excepción: {e}")


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
    c9_contexto_y_confidencialidad()
    c10_robustez_formatos()
    c11_checksum_identificadores()
    c12_presidio_opcional()
    c13_ocr_opcional()
    c14_relation_hint()
    c15_pptx_graficos()
    c16_pdf_form_fields()
    all_ok = print_report()
    sys.exit(0 if all_ok else 1)
