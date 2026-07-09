"""Registro de auditoría de anonimizaciones.

Escribe un JSONL por proyecto en `projects/<proyecto>.audit.jsonl` con metadata
AGREGADA de cada operación: cuándo, cuántos archivos, cuántas entidades, si hubo
fugas. NUNCA registra nombres reales ni nombres de archivo (que en M&A pueden
ser sensibles) — solo conteos, para compliance y trazabilidad.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

AUDIT_DIR = Path(__file__).resolve().parent.parent / "projects"


def log_event(project: str, action: str, **metadata) -> None:
    """Añade una línea al log de auditoría del proyecto. Best-effort (no rompe
    el flujo si falla). Pasa solo metadata no sensible (conteos, flags)."""
    try:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        path = AUDIT_DIR / f"{project.lower()}.audit.jsonl"
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            **metadata,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_log(project: str) -> list[dict]:
    """Lee el log de auditoría de un proyecto (lista de eventos)."""
    path = AUDIT_DIR / f"{project.lower()}.audit.jsonl"
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events
