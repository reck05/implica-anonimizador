"""Test con el fixture realista que replica los bugs reales."""
import io
import sys
import time
from collections import Counter
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from implica_anon import accounting, doctype, formats
from implica_anon.detectors import candidates_from_pgc, cluster_variants, detect_candidates

FIXTURE = Path(__file__).parent / "fixtures" / "sumas_saldos_realista.xlsx"


def main():
    print("=== 1) Detección de tipo ===")
    guess = doctype.guess_doctype(FIXTURE)
    print(f"Tipo: {guess.doctype.value} ({guess.confidence*100:.0f}% confianza)")
    for s in guess.signals:
        print(f"  - {s}")

    print("\n=== 2) Escaneo PGC ===")
    t0 = time.time()
    scan = accounting.scan_workbook(FIXTURE)
    t1 = time.time()
    print(f"Escaneo en {t1-t0:.2f}s")
    print(f"Es contable: {scan.is_accounting}")
    print(f"Total entidades detectadas: {len(scan.entities)}")
    print(f"\nHojas con cuentas:")
    for sheet, info in scan.sheet_findings.items():
        print(f"  '{sheet}': mode={info.get('mode', '?')}, header_row={info['header_row']}, "
              f"{info['rows_matched']}/{info['rows_scanned']} filas con cuenta")

    by_kind = Counter(e.kind for e in scan.entities)
    print(f"\nPor tipo:")
    for kind, count in by_kind.most_common():
        print(f"  {kind}: {count}")

    print("\n=== 3) Extract text del Excel (con filtro de fórmulas) ===")
    texts = formats.extract_text(FIXTURE)
    print(f"Fragmentos: {len(texts)}")
    # Buscar si quedan fórmulas/referencias en el texto extraído
    formula_remnants = []
    for t in texts:
        if any(token in t for token in ["SUMIFS(", "SUBSTITUTE(", "$A:$A", "!$"]):
            formula_remnants.append(t)
        elif t.startswith("="):
            formula_remnants.append(t)
    if formula_remnants:
        print(f"⚠ {len(formula_remnants)} fragmentos parecen fórmulas (debería ser 0):")
        for f in formula_remnants[:5]:
            print(f"    {f[:80]}")
    else:
        print("✓ Sin fórmulas en el texto extraído")

    print("\n=== 4) Detectar con NER + regex (skip_ner=False) ===")
    t2 = time.time()
    candidates = detect_candidates(texts)
    t3 = time.time()
    print(f"Detectados en {t3-t2:.2f}s: {len(candidates)} candidatos")

    # Buscar falsos positivos típicos
    bad_words = ["HP", "SS", "IS", "TR", "MOB", "IVA", "EUROS", "TARJETA", "OFICINA",
                 "PUBLICIDAD", "GANANCIAS", "PROFUNDIDAD", "INMOB", "ARTE", "PERIODO"]
    bad_names = ["BEATRIZ", "ANDREA", "SANDRA", "LAURA", "CAROLINA", "CLARA", "ALBA",
                 "ADA", "BELEN"]
    bad_refs = ["A10", "AB141", "AC15", "M27+AV27", "Apertura-Jun"]

    fp_words = [c for c in candidates if any(c.text == w or c.text.lower() == w.lower() for w in bad_words)]
    fp_lone_names = [c for c in candidates if any(c.text == n or c.text.lower() == n.lower() for n in bad_names)]
    fp_refs = [c for c in candidates if any(r in c.text for r in bad_refs)]

    print(f"  Falsos positivos abreviaturas (HP/SS/IS/etc.): {len(fp_words)}")
    for c in fp_words[:5]:
        print(f"    [{c.kind}] {c.text}")
    print(f"  Falsos positivos nombres sueltos (BEATRIZ/ANDREA/etc.): {len(fp_lone_names)}")
    for c in fp_lone_names[:5]:
        print(f"    [{c.kind}] {c.text}")
    print(f"  Falsos positivos referencias Excel (A10, AB141+BK141, etc.): {len(fp_refs)}")
    for c in fp_refs[:5]:
        print(f"    [{c.kind}] {c.text}")

    print("\n=== 5) Candidates desde PGC ===")
    pgc_cands = candidates_from_pgc(scan)
    print(f"Candidatos PGC: {len(pgc_cands)}")
    pgc_by_kind = Counter(c.kind for c in pgc_cands)
    for kind, count in pgc_by_kind.most_common():
        print(f"  {kind}: {count}")
    print(f"\nMuestra de candidatos PGC:")
    for c in pgc_cands[:10]:
        print(f"  [{c.kind}] {c.text} (count={c.count})")

    print("\n=== 6) Verificación: ¿se detectaron las 30 empresas/personas esperadas? ===")
    expected_company_names = [
        "BANCO SABADELL", "CAIXABANK", "PREVENPYME", "EVENTOS MEDITERRÁNEOS",
        "DISTRIBUCIONES BADIA", "INMOBILIARIA TUSET", "ASESORÍA MIRALLES",
        "FRUTAS CARIÑENA", "ARNAU TORRES", "NATALIA POLO",
        "ADRIANA HUERTAS", "HORTENSIA HERRERO", "FUNDACIÓN ARTE",
        "TALLERES MONTANER", "BENLLOCH", "MODICA", "ASENSI",
        "RIERA", "BELLO", "VALCARCEL",
        "JUAN PEDRO", "MIGUEL CAMACHO", "LAURA GURREA", "BEATRIZ HERGUETA",
        "CAROLINA LLARIO", "CLARA SANTAMARIA",
        "DISTRIBUCIONES CHUST", "LAMATA", "JUAN LARA", "ALBA EVENTOS",
    ]
    pgc_texts = {c.text.upper() for c in pgc_cands}
    found = 0
    missing = []
    for exp in expected_company_names:
        if any(exp in t for t in pgc_texts):
            found += 1
        else:
            missing.append(exp)
    print(f"  Encontradas: {found}/{len(expected_company_names)}")
    if missing:
        print(f"  No detectadas: {missing}")


if __name__ == "__main__":
    main()
