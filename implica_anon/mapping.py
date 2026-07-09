"""Persistencia del mapping original→codename por proyecto.

Cada proyecto tiene un JSON en `projects/<codename>.json` con:
    {
      "project": "paradise",
      "created_at": "...",
      "entries": {
        "ORG": {"Global Menta S.L.": "Paradise", "GlobalMenta": "Paradise"},
        "PER": {"Juan Pérez": "[CEO]"},
        "CIF": {"B12345678": "[CIF-1]"},
        ...
      }
    }
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"
BACKUPS_DIR = PROJECTS_DIR / ".backups"


@dataclass
class ProjectMapping:
    project: str
    entries: dict[str, dict[str, str]] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def all_replacements(self) -> dict[str, str]:
        """Devuelve un solo dict {original: codename} para usar en reemplazo.

        Ordenado por longitud descendente (más largo primero) para evitar
        reemplazos parciales: "Global Menta S.L." antes que "Global Menta".
        """
        merged: dict[str, str] = {}
        for kind_entries in self.entries.values():
            merged.update(kind_entries)
        return dict(sorted(merged.items(), key=lambda kv: -len(kv[0])))

    def add(self, kind: str, original: str, codename: str) -> None:
        self.entries.setdefault(kind, {})[original] = codename

    def get_codename(self, kind: str, original: str) -> str | None:
        return self.entries.get(kind, {}).get(original)

    def has(self, original: str) -> bool:
        return any(original in entries for entries in self.entries.values())


def _path_for(project: str) -> Path:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return PROJECTS_DIR / f"{project.lower()}.json"


def load(project: str) -> ProjectMapping:
    path = _path_for(project)
    if not path.exists():
        return ProjectMapping(
            project=project,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ProjectMapping(
        project=raw.get("project", project),
        entries=raw.get("entries", {}),
        created_at=raw.get("created_at", ""),
        updated_at=raw.get("updated_at", ""),
    )


def _backup_existing(path: Path) -> None:
    """Antes de sobrescribir, copia el JSON actual a .backups/ con timestamp."""
    if not path.exists():
        return
    try:
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = BACKUPS_DIR / f"{path.stem}.{stamp}.json"
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        # Conservar solo los 20 backups más recientes por proyecto
        existing = sorted(BACKUPS_DIR.glob(f"{path.stem}.*.json"))
        for old in existing[:-20]:
            old.unlink(missing_ok=True)
    except Exception:
        # El backup es best-effort; nunca debe impedir guardar
        pass


def save(mapping: ProjectMapping) -> Path:
    mapping.updated_at = datetime.now().isoformat(timespec="seconds")
    path = _path_for(mapping.project)

    # Backup del estado anterior antes de pisarlo
    _backup_existing(path)

    payload = json.dumps(
        {
            "project": mapping.project,
            "created_at": mapping.created_at,
            "updated_at": mapping.updated_at,
            "entries": mapping.entries,
        },
        indent=2,
        ensure_ascii=False,
    )

    # Escritura atómica: escribir a tmp y renombrar (os.replace es atómico).
    # Evita que dos guardados concurrentes dejen un JSON corrupto a medias.
    fd, tmp_path = tempfile.mkstemp(dir=str(PROJECTS_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, path)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise
    return path


def list_projects() -> list[str]:
    if not PROJECTS_DIR.exists():
        return []
    return sorted(
        p.stem for p in PROJECTS_DIR.glob("*.json")
    )
