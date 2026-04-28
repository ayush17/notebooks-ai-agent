"""Orchestration for CVE find (Jira) and fix planning (mapping + GitHub duplicate check)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from devassist.cve.artifacts import (
    ai_triage_readme_path,
    new_find_artifact_path,
    new_fix_artifact_path,
    render_ai_triage_readme,
    render_find_markdown,
)
from devassist.cve.credentials import JiraAuth, resolve_github_token, resolve_jira_auth
from devassist.cve.description import field_to_plain
from devassist.cve.github_cve import (
    github_browse_url,
    parse_github_owner_repo,
    search_pull_requests_with_text,
)
from devassist.cve.jira_cve import build_cve_jql
from devassist.cve.mapping_store import load_mappings
from devassist.cve.scanner_hints import hints_for_repo_path
from devassist.cve.textutil import extract_cve_ids, issue_should_be_ignored
from devassist.core.config_manager import ConfigManager
from devassist.jira_enhanced_search import fetch_jql_search_jql_page


_ISSUE_FIELDS = "summary,status,issuetype,description,components,duedate,labels"


def _auth_tuple(auth: JiraAuth) -> tuple[str, str]:
    return auth.email, auth.api_token


def _jira_field_name(fields: dict[str, Any], key: str) -> str:
    obj = fields.get(key)
    if isinstance(obj, dict):
        return str(obj.get("name") or obj.get("displayName") or "")
    return ""


def _jira_duedate(fields: dict[str, Any]) -> str:
    raw = fields.get("duedate")
    return raw.strip() if isinstance(raw, str) and raw.strip() else ""


def _jira_labels_csv(fields: dict[str, Any]) -> str:
    raw = fields.get("labels")
    if not isinstance(raw, list):
        return ""
    return ", ".join(str(x) for x in raw if x is not None and str(x).strip())


@dataclass(frozen=True)
class FindRunResult:
    """Outputs from `run_find`: timestamped finder report + stable AI triage README."""

    find_report: Path
    ai_triage_readme: Path


async def _fetch_comment_bodies(
    client: httpx.AsyncClient,
    base_url: str,
    auth: tuple[str, str],
    issue_key: str,
) -> list[str]:
    url = f"{base_url.rstrip('/')}/rest/api/3/issue/{issue_key}/comment"
    bodies: list[str] = []
    start_at = 0
    page_size = 100
    while True:
        r = await client.get(
            url,
            auth=auth,
            params={"startAt": start_at, "maxResults": page_size},
        )
        r.raise_for_status()
        data = r.json()
        comments = data.get("comments")
        if not isinstance(comments, list):
            break
        for c in comments:
            if not isinstance(c, dict):
                continue
            bodies.append(field_to_plain(c.get("body")))
        total = int(data.get("total", 0))
        start_at += len(comments)
        if start_at >= total or not comments:
            break
    return bodies


def _issue_components(fields: dict[str, Any]) -> list[str]:
    raw = fields.get("components")
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for c in raw:
        if isinstance(c, dict) and c.get("name"):
            names.append(str(c["name"]))
    return names


async def run_find(
    *,
    workspace: Path,
    component: str,
    project_key: str | None,
    ignore_resolved: bool,
    extra_ignore_markers: tuple[str, ...] = (),
    auth: JiraAuth | None = None,
) -> FindRunResult:
    """Paginated Jira search; writes finder report + ``cve/artifacts/triage/README.md``."""
    jira = auth or resolve_jira_auth()
    if not jira:
        raise RuntimeError("Jira credentials not configured (env or devassist config add jira).")

    jql = build_cve_jql(
        component=component,
        project_key=project_key,
        ignore_resolved=ignore_resolved,
    )
    auth_h = _auth_tuple(jira)
    kept: list[dict[str, Any]] = []
    ignored_keys: list[str] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        next_token: str | None = None
        while True:
            issues, next_token, page_is_last = await fetch_jql_search_jql_page(
                client,
                jira.base_url,
                auth_h,
                jql=jql,
                max_results=50,
                fields=_ISSUE_FIELDS,
                next_page_token=next_token,
            )
            for issue in issues:
                if not isinstance(issue, dict):
                    continue
                key = str(issue.get("key") or "")
                fields = issue.get("fields")
                if not isinstance(fields, dict):
                    continue
                summary = str(fields.get("summary") or "")
                desc = field_to_plain(fields.get("description"))
                bodies = await _fetch_comment_bodies(client, jira.base_url, auth_h, key)
                if issue_should_be_ignored(bodies, extra_ignore_markers):
                    ignored_keys.append(key)
                    continue
                text_for_cve = f"{summary}\n{desc}"
                cves = extract_cve_ids(text_for_cve)
                kept.append(
                    {
                        "key": key,
                        "summary": summary,
                        "cves": cves,
                        "browse_url": github_browse_url(jira.base_url, key),
                        "status": _jira_field_name(fields, "status"),
                        "priority": _jira_field_name(fields, "priority"),
                        "issuetype": _jira_field_name(fields, "issuetype"),
                        "duedate": _jira_duedate(fields),
                        "labels": _jira_labels_csv(fields),
                    }
                )
            if page_is_last:
                break

    body = render_find_markdown(
        component=component,
        jql=jql,
        issues=kept,
        ignored_keys=ignored_keys,
    )
    out = new_find_artifact_path(workspace)
    out.write_text(body, encoding="utf-8")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    triage_path = ai_triage_readme_path(workspace)
    triage_path.write_text(
        render_ai_triage_readme(
            component=component,
            jql=jql,
            issues=kept,
            generated_at_utc=ts,
        ),
        encoding="utf-8",
    )
    return FindRunResult(find_report=out, ai_triage_readme=triage_path)


async def _get_issue_json(
    client: httpx.AsyncClient,
    base_url: str,
    auth: tuple[str, str],
    issue_key: str,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/rest/api/3/issue/{issue_key}"
    r = await client.get(url, auth=auth, params={"fields": _ISSUE_FIELDS})
    r.raise_for_status()
    raw = r.json()
    return raw if isinstance(raw, dict) else {}


async def run_fix_plan(
    *,
    workspace: Path,
    issue_keys: list[str],
    auth: JiraAuth | None = None,
    clone_base: Path | None = None,
) -> Path:
    """Resolve mappings, check GitHub for duplicate PRs, emit scanner hints (no force-push)."""
    jira = auth or resolve_jira_auth()
    if not jira:
        raise RuntimeError("Jira credentials not configured.")
    gh_token = resolve_github_token()
    mappings = load_mappings(workspace)
    auth_h = _auth_tuple(jira)
    lines: list[str] = [
        "# CVE fix plan",
        "",
        "Isolated automation pattern: verify → skip duplicates → patch → open PR (human review).",
        "",
    ]

    base_clone = clone_base or Path("/tmp")

    async with httpx.AsyncClient(timeout=60.0) as client:
        for key in issue_keys:
            issue = await _get_issue_json(client, jira.base_url, auth_h, key)
            fields = issue.get("fields")
            if not isinstance(fields, dict):
                lines.append(f"## {key}\n\n_Issue not found or inaccessible._\n")
                continue
            summary = str(fields.get("summary") or "")
            desc = field_to_plain(fields.get("description"))
            comp_names = _issue_components(fields)
            cves = extract_cve_ids(f"{summary}\n{desc}")
            lines.append(f"## {key}: {summary}")
            lines.append("")
            lines.append(f"- **CVEs**: {', '.join(cves) if cves else '_none in summary/description_'}")
            lines.append(f"- **Components**: {', '.join(comp_names) if comp_names else '_none_'}")
            lines.append("")

            matched_repo = False
            for comp in comp_names:
                cmap = mappings.get(comp)
                if not cmap:
                    continue
                for slug, entry in cmap.repositories.items():
                    matched_repo = True
                    parsed = parse_github_owner_repo(entry.github_url)
                    lines.append(f"### Repo `{slug}` → {entry.github_url}")
                    lines.append(f"- **Line**: {entry.repo_type} | **branch**: `{entry.default_branch}`")
                    if not gh_token:
                        lines.append("- **GitHub**: token not set — cannot search for duplicate PRs.")
                    elif parsed:
                        owner, repo = parsed
                        for cve in cves:
                            prs = search_pull_requests_with_text(
                                gh_token, owner=owner, repo=repo, text=cve
                            )
                            if prs:
                                nums = [str(p.get("number", "")) for p in prs[:5]]
                                hit = f"#{', #'.join(n for n in nums if n)}"
                                lines.append(
                                    f"  - `{cve}`: PR search hit(s) ({hit}) — skip or review before new PR"
                                )
                            else:
                                lines.append(f"  - `{cve}`: no PR search hit for this repo + CVE")
                    hint_root = base_clone / f"devassist-cve-{key.replace('-', '_').lower()}" / slug.replace("/", "_")
                    lines.append(f"- **Suggested temp clone**: `{hint_root}` (under `{base_clone}`)")
                    lines.append("")
                    for hint in hints_for_repo_path(hint_root):
                        lines.append(f"  - {hint}")
                    lines.append("")
            if not matched_repo:
                lines.append(
                    "_No repository mapping for these components — edit "
                    "`cve/component-repository-mappings.json` or run onboarding._"
                )
                lines.append("")

    out = new_fix_artifact_path(workspace)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def workspace_default() -> Path:
    """Resolve DevAssist workspace (``~/.devassist``)."""
    return ConfigManager().workspace_dir


def run_find_sync(**kwargs: Any) -> FindRunResult:
    import asyncio

    return asyncio.run(run_find(**kwargs))


def run_fix_plan_sync(**kwargs: Any) -> Path:
    import asyncio

    return asyncio.run(run_fix_plan(**kwargs))
