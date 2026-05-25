"""Test del detector de tipo de documento + flujo NER sobre PPT largo."""
import io
import sys
import time
from collections import Counter
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from implica_anon import formats, doctype, mapping as mapping_mod
from implica_anon.detectors import cluster_variants, detect_candidates

PPTX_TEASER = Path(__file__).parent / "fixtures" / "teaser_atlas.pptx"
XLSX_SUMAS = Path(__file__).parent / "fixtures" / "sumas_saldos_sintetico.xlsx"
XLSX_DEAL = Path(__file__).parent / "fixtures" / "deal_sintetico.xlsx"


def test_doctype_detection():
    print("=== 1) Detector de tipo de documento ===\n")

    for path in [PPTX_TEASER, XLSX_SUMAS, XLSX_DEAL]:
        t0 = time.time()
        guess = doctype.guess_doctype(path)
        t1 = time.time()
        print(f"{path.name}")
        print(f"  Tipo: {guess.doctype.value} ({guess.confidence*100:.0f}% confianza)")
        for s in guess.signals:
            print(f"  - {s}")
        print(f"  Tiempo: {t1-t0:.2f}s\n")


def test_pptx_flow():
    print("=== 2) Flujo NER sobre PPT teaser ===\n")

    t0 = time.time()
    texts = formats.extract_text(PPTX_TEASER)
    t1 = time.time()
    print(f"Extracción: {len(texts)} fragmentos en {t1-t0:.2f}s")
    # Algunos fragmentos
    print("Muestra de texto extraído:")
    for t in texts[:5]:
        print(f"  > {t[:90]}")

    t2 = time.time()
    candidates = detect_candidates(texts)
    t3 = time.time()
    print(f"\nDetección NER+regex: {len(candidates)} candidatos en {t3-t2:.2f}s")

    t4 = time.time()
    clusters = cluster_variants(candidates)
    t5 = time.time()
    print(f"Clustering: {len(clusters)} clusters en {t5-t4:.2f}s")
    print(f"Tiempo total: {t5-t0:.2f}s\n")

    by_kind = Counter(c.kind for c in clusters)
    for kind, count in by_kind.most_common():
        print(f"  {kind}: {count}")

    # Mostrar top empresas detectadas
    org_clusters = sorted(
        [c for c in clusters if c.kind == "ORG"],
        key=lambda c: -c.total_count,
    )
    print(f"\nTop 10 empresas detectadas (por frecuencia):")
    for c in org_clusters[:10]:
        variants_str = f" (variantes: {c.variants})" if len(c.variants) > 1 else ""
        print(f"  {c.total_count}x  {c.canonical}{variants_str}")

    per_clusters = sorted(
        [c for c in clusters if c.kind == "PER"],
        key=lambda c: -c.total_count,
    )
    print(f"\nTop 5 personas detectadas:")
    for c in per_clusters[:5]:
        print(f"  {c.total_count}x  {c.canonical}")

    # Aplicar reemplazo y verificar
    print("\n=== 3) Aplicar reemplazos y verificar ===")
    pm = mapping_mod.ProjectMapping(project="atlas_test")
    # La empresa más mencionada → codename "Atlas"
    for i, c in enumerate(org_clusters):
        if i == 0:
            codename = "Atlas"
        else:
            codename = f"[Empresa-{i:03d}]"
        for v in c.variants:
            pm.add("ORG", v, codename)
    for i, c in enumerate(per_clusters):
        codename = f"[Persona-{i+1:03d}]"
        for v in c.variants:
            pm.add("PER", v, codename)
    # Resto kinds → placeholder genérico
    counters = {}
    for c in clusters:
        if c.kind in ("ORG", "PER"):
            continue
        counters[c.kind] = counters.get(c.kind, 0) + 1
        codename = f"[{c.kind}-{counters[c.kind]:03d}]"
        for v in c.variants:
            pm.add(c.kind, v, codename)

    out = PPTX_TEASER.with_name("teaser_atlas.anonimizado.pptx")
    t6 = time.time()
    formats.apply_replacements(PPTX_TEASER, pm.all_replacements(), out)
    t7 = time.time()
    print(f"Reemplazo: {t7-t6:.2f}s")
    print(f"Output: {out.name}")

    # Verificar
    texts_out = formats.extract_text(out)
    full = "\n".join(texts_out)
    # Buscar el nombre original
    survived = []
    for original in ["Innovaciones Mediterráneas", "Juan García Pérez", "María López"]:
        if original in full:
            survived.append(original)
    if survived:
        print(f"⚠ Sobrevivieron originales: {survived}")
    else:
        print("✓ Ningún nombre original quedó visible")

    # Verificar que sí aparece "Atlas"
    if "Atlas" in full:
        print("✓ Codename 'Atlas' aplicado correctamente")
    else:
        print("⚠ No se encuentra 'Atlas' en el output")


if __name__ == "__main__":
    test_doctype_detection()
    test_pptx_flow()
