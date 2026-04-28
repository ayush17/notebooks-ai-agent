"""CVE remediation Typer commands (Jira discovery, mapping, duplicate PR hints)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from devassist.core.config_manager import ConfigManager
from devassist.cve.mapping_store import load_mappings, mappings_path, save_mappings
from devassist.cve.models import ComponentMapping, RepoEntry
from devassist.cve.workflow import run_find_sync, run_fix_plan_sync

console = Console()
app = typer.Typer(
    name="cve",
    help="CVE Fixer–style workflow: Jira CVE issues, repo mappings, verification hints.",
    no_args_is_help=True,
)


def _workspace() -> Path:
    return ConfigManager().workspace_dir


@app.command("find")
def cve_find(
    component: str = typer.Argument(..., help='Jira component name (e.g. "My Service")'),
    project_key: Optional[str] = typer.Option(
        None,
        "--project-key",
        "-p",
        help='Restrict with project = "KEY"',
    ),
    ignore_resolved: bool = typer.Option(
        False,
        "--ignore-resolved",
        "-r",
        help="Exclude issues whose status category is Done",
    ),
    extra_marker: list[str] = typer.Option(
        [],
        "--ignore-marker",
        "-m",
        help="Extra comment substrings that mean 'skip automation' (repeatable)",
    ),
) -> None:
    """Search Jira for issues with label CVE (and matching component), apply comment ignores, write artifact."""
    try:
        result = run_find_sync(
            workspace=_workspace(),
            component=component,
            project_key=project_key,
            ignore_resolved=ignore_resolved,
            extra_ignore_markers=tuple(extra_marker),
        )
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    console.print(f"[green]Finder report[/green] {result.find_report}")
    console.print(f"[green]AI triage README[/green] {result.ai_triage_readme}")


@app.command("fix-plan")
def cve_fix_plan(
    issue_key: list[str] = typer.Argument(
        ...,
        help="One or more Jira issue keys (e.g. PROJ-123 PROJ-456)",
    ),
    clone_base: Optional[Path] = typer.Option(
        None,
        "--clone-base",
        help="Root for suggested temp clone paths (default: /tmp)",
    ),
) -> None:
    """Resolve mappings + GitHub PR search; emit a fix plan artifact (no git writes)."""
    try:
        out = run_fix_plan_sync(
            workspace=_workspace(),
            issue_keys=list(issue_key),
            clone_base=clone_base,
        )
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    console.print(f"[green]Wrote[/green] {out}")


mappings_app = typer.Typer(help="Component → GitHub repository map (JSON on disk).")
app.add_typer(mappings_app, name="mappings")


@mappings_app.command("path")
def mappings_path_cmd() -> None:
    """Print the path to component-repository-mappings.json."""
    console.print(str(mappings_path(_workspace())))


@mappings_app.command("validate")
def mappings_validate() -> None:
    """Load the mapping file and report component / repo counts."""
    ws = _workspace()
    data = load_mappings(ws)
    if not data:
        console.print(f"[yellow]No mappings at[/yellow] {mappings_path(ws)}")
        raise typer.Exit(0)
    n_repos = sum(len(c.repositories) for c in data.values())
    console.print(f"Components: {len(data)} | Repository entries: {n_repos}")


@mappings_app.command("init-example")
def mappings_init_example() -> None:
    """Create an example mapping you can edit (does not overwrite existing)."""
    ws = _workspace()
    path = mappings_path(ws)
    if path.exists():
        console.print(f"[yellow]Already exists:[/yellow] {path}")
        raise typer.Exit(0)
    example = {
        "Example Jira Component": ComponentMapping(
            repositories={
                "acme/api": RepoEntry(
                    github_url="https://github.com/acme/api",
                    default_branch="main",
                    repo_type="upstream",
                )
            }
        )
    }
    save_mappings(ws, example)
    console.print(f"[green]Wrote example[/green] {path}")
