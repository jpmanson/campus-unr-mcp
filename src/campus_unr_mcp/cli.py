"""Command-line interface for Campus Virtual FCEIA UNR.

Usage::

    campus site-info
    campus courses
    campus courses --json
    campus categories
    campus contents <course_id>
    campus users <course_id>
    campus groups <course_id>
    campus activities <course_id>
    campus assignments <course_id>
    campus grades <course_id>
    campus serve
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .client import CampusClient, CampusConfig

console = Console()


def _get_client(env: str | None = None) -> CampusClient:
    env_path = env or Path.cwd() / ".env"
    config = CampusConfig.from_env(env_path)
    if not config.username and not config.token:
        raise click.ClickException(
            "No credentials found. Create a .env file with CAMPUS_USER and CAMPUS_PASS"
        )
    return CampusClient(config)


def _print_json(data: object) -> None:
    """Print clean JSON (no rich formatting)."""
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


@click.group()
@click.option(
    "--env",
    type=click.Path(exists=True),
    default=None,
    help="Path to .env file (default: ./.env)",
)
@click.pass_context
def main(ctx: click.Context, env: str | None) -> None:
    """Campus Virtual FCEIA UNR - herramental docente."""
    ctx.ensure_object(dict)
    ctx.obj["env"] = env


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def site_info(as_json: bool) -> None:
    """Show site info and current user."""
    with _get_client() as c:
        info = c.get_site_info()
    if as_json:
        _print_json(info)
        return
    console.print(f"\n[bold]{info.get('sitename')}[/bold]")
    console.print(f"  URL: {info.get('siteurl')}")
    console.print(f"  Usuario: {info.get('fullname')} (id={info.get('userid')})")
    console.print(f"  Username: {info.get('username')}")
    console.print(f"  Lang: {info.get('lang')}")
    fns = info.get("functions", [])
    console.print(f"  WS functions: {len(fns)}")


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def courses(as_json: bool) -> None:
    """List my courses (cursadas)."""
    with _get_client() as c:
        courses_list = c.get_courses()
    if as_json:
        _print_json(courses_list)
        return
    if not courses_list:
        console.print("[yellow]No hay cursos.[/yellow]")
        return
    table = Table(title="Mis Cursos")
    table.add_column("ID", style="dim")
    table.add_column("Sigla", style="cyan")
    table.add_column("Nombre")
    table.add_column("Cat.")
    table.add_column("Inicio")
    for c in courses_list:
        table.add_row(
            str(c.get("id")),
            str(c.get("shortname", "")),
            str(c.get("fullname", "")),
            str(c.get("category", "")),
            str(c.get("startdate_iso", "") or ""),
        )
    console.print(table)
    console.print(f"\nTotal: {len(courses_list)} cursos")


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def categories(as_json: bool) -> None:
    """List course categories (períodos lectivos / carreras)."""
    with _get_client() as c:
        cats = c.get_categories()
    if as_json:
        _print_json(cats)
        return
    if not cats:
        console.print("[yellow]No hay categorías.[/yellow]")
        return
    # Sort by depth then name for hierarchical display
    cats_sorted = sorted(cats, key=lambda x: (x.get("depth", 0), x.get("sortorder", 0)))
    for cat in cats_sorted:
        depth = cat.get("depth", 1)
        indent = "  " * (depth - 1)
        console.print(
            f"{indent}[dim]id={cat.get('id')}[/dim] "
            f"[bold]{cat.get('name')}[/bold] "
            f"[dim](cursos: {cat.get('coursecount', 0)})[/dim]"
        )


@main.command()
@click.argument("course_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def contents(course_id: int, as_json: bool) -> None:
    """List course sections and contents."""
    with _get_client() as c:
        contents_data = c.get_course_contents(course_id)
    if as_json:
        _print_json(contents_data)
        return
    for section in contents_data:
        vis = "" if section.get("visible", 1) == 1 else " [hidden]"
        console.print(f"\n[bold cyan]{section.get('name')}[/bold cyan]{vis}")
        for mod in section.get("modules", []):
            modvis = "" if mod.get("visible", 1) == 1 else " [hidden]"
            console.print(
                f"  [{mod.get('modname')}] {mod.get('name')}{modvis}"
            )


@main.command()
@click.argument("course_id", type=int)
@click.option(
    "--role",
    type=str,
    default=None,
    help="Filter by role (student, editingteacher, etc.)",
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def users(course_id: int, role: str | None, as_json: bool) -> None:
    """List enrolled users in a course."""
    with _get_client() as c:
        users_list = c.get_enrolled_users(course_id)
    if role:
        users_list = [
            u
            for u in users_list
            if any(r.get("shortname") == role for r in u.get("roles", []))
        ]
    if as_json:
        _print_json(users_list)
        return
    if not users_list:
        console.print("[yellow]No hay usuarios.[/yellow]")
        return
    table = Table(title=f"Usuarios enrolados (curso {course_id})")
    table.add_column("ID", style="dim")
    table.add_column("Nombre")
    table.add_column("Roles", style="cyan")
    table.add_column("Email", style="dim")
    for u in users_list:
        roles_str = ", ".join(
            r.get("shortname", "?") for r in u.get("roles", [])
        )
        table.add_row(
            str(u.get("id")),
            str(u.get("fullname", "")),
            roles_str,
            str(u.get("email", "")),
        )
    console.print(table)
    console.print(f"\nTotal: {len(users_list)} usuarios")


@main.command()
@click.argument("course_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def groups(course_id: int, as_json: bool) -> None:
    """List groups in a course (comisiones)."""
    with _get_client() as c:
        groups_list = c.get_groups(course_id)
    if as_json:
        _print_json(groups_list)
        return
    if not groups_list:
        console.print("[yellow]No hay grupos.[/yellow]")
        return
    table = Table(title=f"Grupos (curso {course_id})")
    table.add_column("ID", style="dim")
    table.add_column("Nombre", style="cyan")
    table.add_column("Descripción")
    for g in groups_list:
        table.add_row(
            str(g.get("id")),
            str(g.get("name", "")),
            str(g.get("description", "") or ""),
        )
    console.print(table)


@main.command()
@click.argument("course_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def activities(course_id: int, as_json: bool) -> None:
    """List all activities in a course, grouped by type."""
    with _get_client() as c:
        activities_data = c.get_course_activities(course_id)
    if as_json:
        _print_json(activities_data)
        return
    for modtype, mods in sorted(activities_data.items()):
        console.print(f"\n[bold cyan]{modtype}[/bold cyan] ({len(mods)})")
        for m in mods:
            vis = "" if m.get("visible", True) else " [hidden]"
            console.print(f"  {m.get('name')}{vis} [dim](cmid={m.get('id')})[/dim]")


@main.command()
@click.argument("course_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def assignments(course_id: int, as_json: bool) -> None:
    """List assignments (TP/entregas) with submission/grade stats."""
    with _get_client() as c:
        assigns = c.get_assignments(course_id)
    if as_json:
        _print_json(assigns)
        return
    if not assigns:
        console.print("[yellow]No hay entregas (assignments).[/yellow]")
        return
    table = Table(title=f"Entregas (curso {course_id})")
    table.add_column("ID", style="dim")
    table.add_column("Nombre")
    table.add_column("Sección")
    table.add_column("Entregas", justify="right")
    table.add_column("Calificadas", justify="right")
    for a in assigns:
        table.add_row(
            str(a.get("id")),
            str(a.get("name", "")),
            str(a.get("section", "")),
            str(a.get("submission_count", "?")),
            str(a.get("graded_count", "?")),
        )
    console.print(table)


@main.command()
@click.argument("course_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def grades(course_id: int, as_json: bool) -> None:
    """Get grade report for a course."""
    with _get_client() as c:
        grades_data = c.get_grades_report(course_id)
    if as_json:
        _print_json(grades_data)
        return
    if not grades_data:
        console.print("[yellow]No hay datos de calificaciones.[/yellow]")
        return
    console.print(f"[bold]Calificaciones (curso {course_id})[/bold]")
    console.print(f"Total usuarios con notas: {len(grades_data)}")
    # Show structure of first entry to understand the data
    if grades_data:
        first = grades_data[0]
        console.print(
            f"\n[dim]Columnas disponibles en 'grade_items': "
            f"{len(first.get('grade_items', []))} items[/dim]"
        )
        for gi in first.get("grade_items", [])[:5]:
            console.print(
                f"  - {gi.get('itemname', '(course)')} "
                f"({gi.get('itemtype')}/{gi.get('itemmodule', '')})"
            )


@main.command()
def serve() -> None:
    """Run as MCP stdio server."""
    from .mcp_server import run_server

    run_server()


if __name__ == "__main__":
    main()
