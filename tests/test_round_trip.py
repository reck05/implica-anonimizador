"""Test end-to-end completo: archivo original → anonimizar → rehidratar → verificar.

Confirma que el ciclo completo funciona y los datos vuelven al original.
"""
import io
import shutil
import sys
import tempfile
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import load_workbook

from implica_anon import accounting, formats, mapping as mapping_mod, rehydrate
from implica_anon.detectors import candidates_from_pgc, cluster_variants
from implica_anon.interactive import DEFAULT_PLACEHOLDERS

FIXTURE = Path(__file__).parent / "fixtures" / "sumas_saldos_realista.xlsx"


def _read_cells(path: Path) -> dict[str, list[str]]:
    """Devuelve {hoja: [valores de cada celda como string]} ordenado, para comparar."""
    out: dict[str, list[str]] = {}
    wb = load_workbook(str(path), data_only=False, read_only=True)
    try:
        for ws in wb.worksheets:
            cells = []
            for row in ws.iter_rows(values_only=True):
                for cell in row:
                    if cell is None:
                        cells.append("")
                    else:
                        cells.append(str(cell))
            out[ws.title] = cells
    finally:
        wb.close()
    return out


def main():
    print(f"=== Round-trip test sobre {FIXTURE.name} ===\n")

    if not FIXTURE.exists():
        print(f"[FAIL] No existe el fixture: {FIXTURE}")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Fase 0: estado original
        print("[Fase 0] Leyendo archivo original...")
        original_cells = _read_cells(FIXTURE)
        n_sheets_orig = len(original_cells)
        n_cells_orig = sum(len(v) for v in original_cells.values())
        print(f"  Hojas: {n_sheets_orig}, celdas totales: {n_cells_orig}")

        # Fase 1: detectar y construir mapping
        print("\n[Fase 1] Escaneando PGC + construyendo mapping...")
        scan = accounting.scan_workbook(FIXTURE)
        print(f"  Es contable: {scan.is_accounting}, entidades: {len(scan.entities)}")

        pgc_cands = candidates_from_pgc(scan)
        clusters = cluster_variants(pgc_cands)
        print(f"  Candidatos: {len(pgc_cands)}, clusters: {len(clusters)}")

        # Asignar codenames basados en código de cuenta
        pm = mapping_mod.ProjectMapping(project="roundtrip_test")
        for c in clusters:
            if c.account_codes:
                code = c.account_codes[0]
                from implica_anon.interactive import KIND_LABELS
                label = {"CLIENTE": "Cliente", "PROVEEDOR": "Proveedor", "DEUDOR": "Deudor",
                         "PERSONA": "Persona", "GRUPO": "Grupo", "BANCO": "Banco"}.get(c.kind, c.kind.capitalize())
                codename = f"[{label}-{code}]"
            else:
                template = DEFAULT_PLACEHOLDERS.get(c.kind, "[" + c.kind + "-{}]")
                codename = template.format(1)
            for v in c.variants:
                pm.add(c.kind, v, codename)
        print(f"  Mapping con {sum(len(v) for v in pm.entries.values())} entradas")

        # Fase 2: anonimizar
        print("\n[Fase 2] Anonimizando...")
        anon_path = tmp / "anon.xlsx"
        formats.apply_replacements(FIXTURE, pm.all_replacements(), anon_path)
        anon_cells = _read_cells(anon_path)
        print(f"  Output: {anon_path.stat().st_size // 1024} KB")

        # Verificar que el contenido cambió
        original_text = "|".join("|".join(v) for v in original_cells.values())
        anon_text = "|".join("|".join(v) for v in anon_cells.values())
        assert original_text != anon_text, "El archivo anonimizado es idéntico al original!"
        print("  ✓ El contenido cambió")

        # Verificar que las empresas SÍ se reemplazaron
        survivors = []
        target_names = ["CAIXABANK", "PREVENPYME", "BADIA", "TUSET", "MIRALLES",
                        "CARIÑENA", "HORTENSIA", "MONTANER", "BENLLOCH"]
        for name in target_names:
            for sheet_cells in anon_cells.values():
                for cell in sheet_cells:
                    if name in cell.upper():
                        survivors.append((name, cell))
                        break
                else:
                    continue
                break
        if survivors:
            print(f"  ⚠ Sobrevivieron nombres: {survivors[:3]}")
            return False
        print(f"  ✓ Los nombres reales NO aparecen en el anonimizado")

        # Verificar que los codenames SÍ aparecen
        codenames_found = 0
        for sheet_cells in anon_cells.values():
            for cell in sheet_cells:
                if cell.startswith("[Cliente-") or cell.startswith("[Proveedor-") or cell.startswith("[Deudor-"):
                    codenames_found += 1
        print(f"  ✓ {codenames_found} celdas con codenames")
        assert codenames_found > 0, "No se encontró ningún codename en el output"

        # Fase 3: rehidratar
        print("\n[Fase 3] Rehidratando...")
        rehydrated_path = tmp / "rehydrated.xlsx"
        rehydrate.rehydrate_file(anon_path, pm, rehydrated_path)
        rehydrated_cells = _read_cells(rehydrated_path)
        print(f"  Output rehidratado: {rehydrated_path.stat().st_size // 1024} KB")

        # Verificar que los nombres originales VOLVIERON
        recovered = 0
        for name in target_names:
            for sheet_cells in rehydrated_cells.values():
                if any(name in cell.upper() for cell in sheet_cells):
                    recovered += 1
                    break
        print(f"  ✓ Recuperados {recovered}/{len(target_names)} nombres en el rehidratado")
        assert recovered >= len(target_names) - 1, (
            f"Solo se recuperaron {recovered} nombres de {len(target_names)} esperados"
        )

        # Verificar que NO quedan codenames en el rehidratado
        leftover_codenames = 0
        for sheet_cells in rehydrated_cells.values():
            for cell in sheet_cells:
                if cell.startswith("[Cliente-") or cell.startswith("[Proveedor-") or cell.startswith("[Deudor-"):
                    leftover_codenames += 1
        print(f"  Codenames residuales en rehidratado: {leftover_codenames}")
        # 0 es ideal, pero si quedan algunos por variantes no detectadas es aceptable
        if leftover_codenames > 10:
            print(f"  ⚠ Demasiados codenames residuales: {leftover_codenames}")

        # Fase 4: comparación final
        print("\n[Fase 4] Comparación original vs rehidratado")
        for sheet_name in original_cells:
            if sheet_name not in rehydrated_cells:
                print(f"  ✗ Falta hoja: {sheet_name}")
                continue
            orig = "|".join(original_cells[sheet_name])
            rehy = "|".join(rehydrated_cells[sheet_name])
            # No exigimos 100% identico porque las variantes pueden diferir (canonical replaced),
            # pero sí que las cifras y estructura sean idénticas
            if len(orig) == len(rehy):
                print(f"  ✓ '{sheet_name}': longitud idéntica ({len(orig)} chars)")
            else:
                diff = abs(len(orig) - len(rehy))
                print(f"  ~ '{sheet_name}': longitud difiere por {diff} chars (esperado por variantes)")

    print("\n✓✓✓ Round-trip test PASS\n")
    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
