"""CLI de Implica Anonimizador (Typer + Rich)."""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import formats, mapping as mapping_mod
from .detectors import cluster_variants, detect_candidates
from .interactive import resolve_clusters

app = typer.Typer(
    add_completion=False,
    rich_markup_mode="rich",
    help="Anonimizador local de documentos M&A para Implica CF.",
    no_args_is_help=True,
)
console = Console()


def _expand_paths(patterns: list[str]) -> list[Path]:
    """Expande wildcards (PowerShell no los expande en argumentos)."""
    paths: list[Path] = []
    for pattern in patterns:
        # Si tiene wildcards, usar glob
        if any(c in pattern for c in "*?[]"):
            matches = glob.glob(pattern, recursive=True)
            paths.extend(Path(m) for m in matches)
        else:
            paths.append(Path(pattern))
    return paths


@app.command()
def run(
    files: list[str] = typer.Argument(
        ..., help="Archivos a anonimizar (.xlsx, .docx, .pptx, .pdf). Acepta wildcards."
    ),
    project: str = typer.Option(
        ..., "--project", "-p", help="Nombre del proyecto/codename (ej. paradise)."
    ),
    output_dir: Path | None = typer.Option(
        None, "--out", "-o", help="Carpeta de salida (por defecto: junto al original)."
    ),
    suffix: str = typer.Option(
        "", "--suffix", help="Sufijo para el output (por defecto: el codename del proyecto)."
    ),
    auto_struct: bool = typer.Option(
        True,
        "--auto-struct/--ask-struct",
        help="Auto-asignar placeholders para CIF/NIF/IBAN sin preguntar.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Detecta y muestra candidatos sin escribir archivos."
    ),
):
    """Anonimiza archivos para un proyecto. Pregunta los codenames la primera vez."""
    paths = _expand_paths(files)
    paths = [p for p in paths if p.exists()]
    if not paths:
        console.print("[red]✗ No se encontró ningún archivo válido.[/]")
        raise typer.Exit(1)

    unsupported = [p for p in paths if not formats.is_supported(p)]
    if unsupported:
        console.print(
            "[yellow]⚠ Formatos no soportados (se ignorarán):[/] "
            + ", ".join(str(p) for p in unsupported)
        )
        paths = [p for p in paths if formats.is_supported(p)]
    if not paths:
        raise typer.Exit(1)

    console.print(
        f"[bold]Proyecto:[/] [cyan]{project}[/]  "
        f"[bold]Archivos:[/] {len(paths)}"
    )

    # 1) Cargar mapping previo
    pm = mapping_mod.load(project)
    if pm.entries:
        total = sum(len(v) for v in pm.entries.values())
        console.print(f"[dim]Mapping previo cargado: {total} entradas.[/]")

    # 2) Extraer texto de todos los archivos
    console.print("[dim]Extrayendo texto...[/]")
    all_texts: list[str] = []
    for p in paths:
        try:
            all_texts.extend(formats.extract_text(p))
        except Exception as e:
            console.print(f"[red]✗ Error extrayendo {p.name}: {e}[/]")

    # 3) Detectar candidatos
    console.print("[dim]Detectando entidades (spaCy + regex)... esto tarda un poco la 1ª vez[/]")
    candidates = detect_candidates(all_texts)
    clusters = cluster_variants(candidates)

    if not clusters:
        console.print("[yellow]No se detectaron entidades sensibles.[/]")
        if not pm.entries:
            console.print("[yellow]No hay nada que reemplazar. Saliendo.[/]")
            raise typer.Exit(0)

    # 4) Resolver clusters interactivamente
    if clusters:
        pm = resolve_clusters(clusters, pm, auto_struct=auto_struct)
        mapping_mod.save(pm)
        console.print(
            f"[green]✓ Mapping guardado en projects/{project.lower()}.json[/]"
        )

    if dry_run:
        console.print("[yellow]--dry-run: no se escribirán archivos.[/]")
        raise typer.Exit(0)

    # 5) Aplicar reemplazos
    replacements = pm.all_replacements()
    if not replacements:
        console.print("[yellow]Mapping vacío, no se procesará nada.[/]")
        raise typer.Exit(0)

    suffix_str = suffix or project.lower()

    console.print("[dim]Aplicando reemplazos...[/]")
    results_table = Table(title="Resultados")
    results_table.add_column("Archivo")
    results_table.add_column("Salida", overflow="fold")
    results_table.add_column("Estado")

    for p in paths:
        out_path = _output_path(p, suffix_str, output_dir)
        try:
            formats.apply_replacements(p, replacements, out_path)
            results_table.add_row(p.name, str(out_path), "[green]OK[/]")
        except Exception as e:
            results_table.add_row(p.name, "—", f"[red]ERROR: {e}[/]")

    console.print(results_table)


@app.command("list")
def list_cmd():
    """Lista los proyectos con mapping guardado."""
    projects = mapping_mod.list_projects()
    if not projects:
        console.print("[dim]No hay proyectos guardados todavía.[/]")
        return
    table = Table(title="Proyectos guardados")
    table.add_column("Proyecto")
    table.add_column("Entradas", justify="right")
    table.add_column("Actualizado")
    for project in projects:
        pm = mapping_mod.load(project)
        total = sum(len(v) for v in pm.entries.values())
        table.add_row(project, str(total), pm.updated_at or "—")
    console.print(table)


@app.command()
def show(project: str = typer.Argument(..., help="Nombre del proyecto")):
    """Muestra el mapping completo de un proyecto."""
    pm = mapping_mod.load(project)
    if not pm.entries:
        console.print(f"[yellow]Proyecto '{project}' no tiene entradas.[/]")
        return
    for kind, entries in pm.entries.items():
        table = Table(title=f"{kind} ({len(entries)})")
        table.add_column("Original", overflow="fold")
        table.add_column("Codename")
        for original, codename in sorted(entries.items()):
            table.add_row(original, codename)
        console.print(table)


@app.command()
def edit(project: str = typer.Argument(..., help="Nombre del proyecto")):
    """Abre el JSON del proyecto en el editor por defecto."""
    pm = mapping_mod.load(project)
    path = mapping_mod._path_for(project)
    if not path.exists():
        mapping_mod.save(pm)
    console.print(f"Abriendo [cyan]{path}[/]...")
    if sys.platform == "win32":
        import os
        os.startfile(str(path))  # noqa: S606
    else:
        import subprocess
        subprocess.Popen(["xdg-open", str(path)])


@app.command()
def add_entry(
    project: str = typer.Argument(..., help="Nombre del proyecto"),
    original: str = typer.Argument(..., help="Texto original"),
    codename: str = typer.Argument(..., help="Texto de reemplazo"),
    kind: str = typer.Option("ORG", "--kind", "-k", help="Tipo: ORG/PER/CIF/NIF/IBAN/ADDRESS"),
):
    """Añade manualmente una entrada al mapping."""
    pm = mapping_mod.load(project)
    pm.add(kind, original, codename)
    mapping_mod.save(pm)
    console.print(f"[green]✓ Añadido[/] [{kind}] '{original}' → '{codename}'")


def _output_path(src: Path, suffix: str, output_dir: Path | None) -> Path:
    stem = src.stem
    new_name = f"{stem}.{suffix}{src.suffix}"
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / new_name
    return src.with_name(new_name)


if __name__ == "__main__":
    app()
