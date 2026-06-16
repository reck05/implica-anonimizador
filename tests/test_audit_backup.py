"""Test de backup automático de mappings y log de auditoría."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from implica_anon import mapping as m, audit

PROJECT = "_smoke_test"


def cleanup():
    base = Path(m.PROJECTS_DIR)
    for f in base.glob(f"{PROJECT}.*"):
        f.unlink(missing_ok=True)
    for f in (base / ".backups").glob(f"{PROJECT}.*.json"):
        f.unlink(missing_ok=True)


def main():
    cleanup()
    print("=== Backup automático ===")
    pm = m.ProjectMapping(project=PROJECT)
    pm.add("CLIENTE", "Test SL", "[Cliente-1]")
    m.save(pm)  # primer save, no hay backup previo
    pm.add("CLIENTE", "Otro SA", "[Cliente-2]")
    m.save(pm)  # segundo save -> backup del primero

    backups = list((Path(m.PROJECTS_DIR) / ".backups").glob(f"{PROJECT}.*.json"))
    print(f"  Backups creados: {len(backups)}")
    assert len(backups) >= 1, "No se creó backup en el segundo save"
    print("  ✓ backup automático funciona")

    # El JSON guardado es válido (escritura atómica no lo corrompió)
    reloaded = m.load(PROJECT)
    assert reloaded.get_codename("CLIENTE", "Otro SA") == "[Cliente-2]"
    print("  ✓ JSON válido tras escritura atómica")

    print("\n=== Log de auditoría ===")
    audit.log_event(PROJECT, "anonymize", files=2, entities=2, leaks=0, unverifiable=0)
    audit.log_event(PROJECT, "anonymize", files=1, entities=5, leaks=1, unverifiable=0)
    events = audit.read_log(PROJECT)
    print(f"  Eventos: {len(events)}")
    assert len(events) == 2
    assert events[-1]["leaks"] == 1
    # Verificar que NO hay PII: solo conteos y metadata
    assert all(set(e.keys()) <= {"ts", "action", "files", "entities", "leaks", "unverifiable"}
               for e in events), "El audit log no debe contener PII"
    print(f"  ✓ {len(events)} eventos registrados, sin PII")

    cleanup()
    print("\n✓✓✓ Backup + auditoría PASS")


if __name__ == "__main__":
    main()
