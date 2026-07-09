"""Tests del Replacer precompilado y del verify pass anti-fuga (issues #1, #2, #3)."""
import io
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from implica_anon.replacer import Replacer, replace_in_text
from implica_anon import formats, accounting, mapping as mapping_mod
from implica_anon.detectors import candidates_from_pgc, cluster_variants

FIXTURE = Path(__file__).parent / "fixtures" / "sumas_saldos_realista.xlsx"


def test_replacer_equivalence():
    print("\n=== 1) Replacer da resultado correcto ===")
    mapping = {
        "Global Menta S.L.": "[Cliente-1]",
        "Global Menta": "[Cliente-1]",
        "CAIXABANK, SA": "[Banco-1]",
    }
    r = Replacer(mapping)

    # Orden por longitud: "Global Menta S.L." antes que "Global Menta"
    out, n = r.apply("Factura de Global Menta S.L. a CAIXABANK, SA")
    assert "[Cliente-1]" in out and "[Banco-1]" in out, out
    assert "Global Menta" not in out, f"Quedó nombre real: {out}"
    print(f"  ✓ '{out}' ({n} reemplazos)")

    # Case-insensitive
    out2, _ = r.apply("global menta s.l. paga")
    assert "[Cliente-1]" in out2, out2
    print(f"  ✓ case-insensitive: '{out2}'")

    # Equivalencia con replace_in_text(dict)
    out3, n3 = replace_in_text("Global Menta S.L.", mapping)
    out4, n4 = r.apply("Global Menta S.L.")
    assert out3 == out4 and n3 == n4, f"{out3!r} != {out4!r}"
    print("  ✓ replace_in_text(dict) == Replacer.apply")


def test_find_surviving():
    print("\n=== 2) find_surviving detecta fugas ===")
    r = Replacer({"Global Menta": "[Cliente-1]", "Tropical Frutas": "[Cliente-2]"})

    # Output limpio (todo reemplazado)
    clean = r.find_surviving("[Cliente-1] vende a [Cliente-2]")
    assert clean == [], f"Falso positivo: {clean}"
    print("  ✓ output limpio → sin fugas detectadas")

    # Output con fuga (un nombre sobrevivió)
    leak = r.find_surviving("[Cliente-1] vende a Tropical Frutas SA")
    assert "Tropical Frutas" in leak, f"No detectó la fuga: {leak}"
    print(f"  ✓ fuga detectada: {leak}")


def test_verify_pass_excel():
    print("\n=== 3) Verify pass end-to-end sobre Excel ===")
    import tempfile

    scan = accounting.scan_workbook(FIXTURE)
    clusters = cluster_variants(candidates_from_pgc(scan))
    pm = mapping_mod.ProjectMapping(project="verify_test")
    for c in clusters:
        code = c.account_codes[0] if c.account_codes else "0"
        for v in c.variants:
            pm.add(c.kind, v, f"[{c.kind}-{code}]")

    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "out.xlsx"
        # apply_replacements devuelve un VerifyResult
        result = formats.apply_replacements(FIXTURE, pm.all_replacements(), dst)
        print(f"  Supervivientes: {len(result.surviving)}, verificable: {result.verifiable}")
        assert result.surviving == [], f"Fugas inesperadas: {result.surviving[:10]}"
        assert result.verifiable, "El Excel debería ser verificable (tiene texto)"
        assert result.is_clean, "Debería estar limpio"
        print("  ✓ verify pass confirma anonimización limpia y verificable en Excel real")


def test_performance():
    print("\n=== 4) Performance: Replacer no recompila por celda ===")
    import tempfile

    scan = accounting.scan_workbook(FIXTURE)
    clusters = cluster_variants(candidates_from_pgc(scan))
    pm = mapping_mod.ProjectMapping(project="perf_test")
    for i, c in enumerate(clusters):
        for v in c.variants:
            pm.add(c.kind, v, f"[{c.kind}-{i}]")

    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "out.xlsx"
        t0 = time.time()
        formats.apply_replacements(FIXTURE, pm.all_replacements(), dst)
        elapsed = time.time() - t0
        print(f"  Anonimización + verify del fixture: {elapsed:.2f}s")
        # No es un assert estricto, pero deja constancia de que va rápido
        assert elapsed < 30, f"Demasiado lento: {elapsed}s"
        print("  ✓ dentro de límites razonables")


if __name__ == "__main__":
    test_replacer_equivalence()
    test_find_surviving()
    test_verify_pass_excel()
    test_performance()
    print("\n✓✓✓ Todos los tests del Replacer + verify PASS")
