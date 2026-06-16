"""UI interactiva con Rich.

Pregunta a Ricardo el codename para cada cluster de entidades detectadas.
Reutiliza mapping previo: si "Global Menta" ya tiene codename "Paradise"
guardado, no vuelve a preguntar.
"""
from __future__ import annotations

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .detectors import Cluster
from .mapping import ProjectMapping

console = Console()

KIND_LABELS = {
    "ORG": "Empresa",
    "PER": "Persona",
    "CIF": "CIF",
    "NIF": "NIF/NIE",
    "IBAN": "IBAN",
    "ADDRESS": "Dirección",
    "EMAIL": "Email",
    "PHONE": "Teléfono",
    # PGC kinds
    "CLIENTE": "Cliente (PGC 43x)",
    "PROVEEDOR": "Proveedor (PGC 40x/41x)",
    "DEUDOR": "Deudor (PGC 44x)",
    "PERSONA": "Persona/Personal (PGC 46x)",
    "GRUPO": "Empresa grupo (PGC 45x/55x)",
    "BANCO": "Banco (PGC 57x/52x)",
    "DOMINIO": "Dominio web",
}

DEFAULT_PLACEHOLDERS = {
    "PER": "[Persona-{}]",
    "CIF": "[CIF-{}]",
    "NIF": "[NIF-{}]",
    "IBAN": "[IBAN-{}]",
    "ADDRESS": "[Dirección-{}]",
    "EMAIL": "[Email-{}]",
    "PHONE": "[Teléfono-{}]",
    # PGC kinds — placeholders secuenciales para anonimización masiva
    "CLIENTE": "[Cliente-{:03d}]",
    "PROVEEDOR": "[Proveedor-{:03d}]",
    "DEUDOR": "[Deudor-{:03d}]",
    "PERSONA": "[Persona-{:03d}]",
    "GRUPO": "[Grupo-{:03d}]",
    "BANCO": "[Banco-{:03d}]",
    "DOMINIO": "[Dominio-{:03d}]",
}


def _is_known(cluster: Cluster, mapping: ProjectMapping) -> bool:
    return any(mapping.has(v) for v in cluster.variants)


def resolve_clusters(
    clusters: list[Cluster],
    mapping: ProjectMapping,
    *,
    auto_struct: bool = True,
) -> ProjectMapping:
    """Para cada cluster nuevo pregunta el codename y lo añade al mapping.

    `auto_struct=True` → identificadores estructurados (CIF/NIF/IBAN/etc.)
    se asignan automáticamente como [CIF-1], [CIF-2], etc., sin preguntar.

    Returns el mapping actualizado.
    """
    # Filtrar los que ya tienen codename
    pending = [c for c in clusters if not _is_known(c, mapping)]
    if not pending:
        console.print("[green]✓ Todos los candidatos ya están en el mapping del proyecto[/]")
        return mapping

    # Resumen
    table = Table(title=f"Candidatos detectados — proyecto [bold cyan]{mapping.project}[/]")
    table.add_column("Tipo")
    table.add_column("Canónico", overflow="fold")
    table.add_column("Variantes", overflow="fold")
    table.add_column("Ocurrencias", justify="right")
    for c in pending:
        variants_str = ", ".join(
            v for v in c.variants if v != c.canonical
        ) or "—"
        table.add_row(
            KIND_LABELS.get(c.kind, c.kind),
            c.canonical,
            variants_str,
            str(c.total_count),
        )
    console.print(table)

    # Procesar ORG y PER primero (requieren input), después estructurados
    org_clusters = [c for c in pending if c.kind == "ORG"]
    per_clusters = [c for c in pending if c.kind == "PER"]
    struct_clusters = [
        c for c in pending if c.kind not in ("ORG", "PER")
    ]

    # --- Empresas ---
    for c in org_clusters:
        _ask_org(c, mapping)

    # --- Personas ---
    for c in per_clusters:
        _ask_per(c, mapping)

    # --- Estructurados ---
    if struct_clusters:
        if auto_struct:
            _auto_struct(struct_clusters, mapping)
        else:
            for c in struct_clusters:
                _ask_struct(c, mapping)

    return mapping


def _ask_org(cluster: Cluster, mapping: ProjectMapping) -> None:
    console.rule(f"[bold]Empresa:[/] {cluster.canonical}")
    if len(cluster.variants) > 1:
        console.print(
            f"[dim]Variantes detectadas:[/] {', '.join(cluster.variants)}"
        )
    keep = Confirm.ask(
        "¿Anonimizar esta empresa?", default=True
    )
    if not keep:
        return
    codename = Prompt.ask(
        "Codename (ej. Paradise)",
        default=mapping.project.capitalize(),
    )
    if not codename:
        return
    # Permitir excluir variantes erróneas
    if len(cluster.variants) > 1:
        edit_variants = Confirm.ask(
            "¿Las variantes son todas correctas?", default=True
        )
        if not edit_variants:
            kept: list[str] = []
            for v in cluster.variants:
                if Confirm.ask(f"  Mantener '[cyan]{v}[/]'?", default=True):
                    kept.append(v)
            cluster.variants = kept
    for v in cluster.variants:
        mapping.add("ORG", v, codename)


def _ask_per(cluster: Cluster, mapping: ProjectMapping) -> None:
    console.rule(f"[bold]Persona:[/] {cluster.canonical}")
    if len(cluster.variants) > 1:
        console.print(
            f"[dim]Variantes detectadas:[/] {', '.join(cluster.variants)}"
        )
    choice = Prompt.ask(
        "Anonimizar como [1]Rol genérico  [2]Codename custom  [3]Saltar",
        choices=["1", "2", "3"],
        default="1",
    )
    if choice == "3":
        return
    if choice == "1":
        role = Prompt.ask(
            "Rol (ej. CEO, Founder, CFO)", default="Persona"
        )
        codename = f"[{role}]"
    else:
        codename = Prompt.ask("Codename")
    if not codename:
        return
    for v in cluster.variants:
        mapping.add("PER", v, codename)


def _ask_struct(cluster: Cluster, mapping: ProjectMapping) -> None:
    console.rule(
        f"[bold]{KIND_LABELS.get(cluster.kind, cluster.kind)}:[/] {cluster.canonical}"
    )
    keep = Confirm.ask("¿Anonimizar?", default=True)
    if not keep:
        return
    template = DEFAULT_PLACEHOLDERS.get(cluster.kind, "[{}]")
    existing = len(mapping.entries.get(cluster.kind, {}))
    default = template.format(existing + 1)
    codename = Prompt.ask("Placeholder", default=default)
    if codename:
        mapping.add(cluster.kind, cluster.canonical, codename)


def _auto_struct(clusters: list[Cluster], mapping: ProjectMapping) -> None:
    """Asigna placeholders automáticos a CIF/NIF/IBAN/etc."""
    for c in clusters:
        template = DEFAULT_PLACEHOLDERS.get(c.kind, "[{}-{{}}]".format(c.kind))
        existing = len(mapping.entries.get(c.kind, {}))
        codename = template.format(existing + 1)
        for v in c.variants:
            mapping.add(c.kind, v, codename)
    console.print(
        f"[dim]Auto-asignados placeholders para "
        f"{sum(len(c.variants) for c in clusters)} identificadores estructurados.[/]"
    )
