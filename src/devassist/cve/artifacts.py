"""Auditable artifact paths for CVE find/fix runs (Ambient-style ``artifacts/cve-fixer/``)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _cve_root(workspace: Path) -> Path:
    return Path(workspace).expanduser().resolve() / "cve" / "artifacts"


def find_artifacts_dir(workspace: Path) -> Path:
    """Directory for ``cve-issues-<timestamp>.md`` reports."""
    d = _cve_root(workspace) / "find"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fix_artifacts_dir(workspace: Path) -> Path:
    """Directory for fix-run summaries."""
    d = _cve_root(workspace) / "fixes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def triage_artifacts_dir(workspace: Path) -> Path:
    """Directory for AI triage bundle (default filename ``README.md``)."""
    d = _cve_root(workspace) / "triage"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ai_triage_readme_path(workspace: Path) -> Path:
    """Stable path overwritten on each ``cve find`` run — easy to open or feed to an LLM."""
    return triage_artifacts_dir(workspace) / "README.md"


def new_find_artifact_path(workspace: Path) -> Path:
    """Timestamped markdown path under ``cve/artifacts/find``."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return find_artifacts_dir(workspace) / f"cve-issues-{ts}.md"


def new_fix_artifact_path(workspace: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return fix_artifacts_dir(workspace) / f"cve-fix-{ts}.md"


def render_find_markdown(
    *,
    component: str,
    jql: str,
    issues: list[dict[str, Any]],
    ignored_keys: list[str],
) -> str:
    """GitHub-flavored markdown summary for humans and automation."""
    lines = [
        "# CVE finder report",
        "",
        f"- **Component**: {component}",
        f"- **JQL**: `{jql}`",
        f"- **Issues matched**: {len(issues)}",
        f"- **Ignored (comments)**: {len(ignored_keys)}",
        "",
    ]
    if ignored_keys:
        lines.append("## Skipped by comment markers")
        for k in ignored_keys:
            lines.append(f"- {k}")
        lines.append("")
    lines.append("## Issues")
    lines.append("")
    if not issues:
        lines.append("_No issues after filters._")
    else:
        for row in issues:
            lines.append(
                f"- **[{row['key']}]({row.get('browse_url', '#')})** — {row.get('summary', '')}"
            )
            if row.get("cves"):
                lines.append(f"  - CVEs: {', '.join(row['cves'])}")
    lines.append("")
    return "\n".join(lines)


def _calendar_date_from_generated(generated_at_utc: str) -> str:
    """``YYYY-MM-DD`` from ``generated_at_utc`` (first segment)."""
    s = (generated_at_utc or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _primary_issue_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Stable pick for title line (sort by issue key)."""
    return sorted(rows, key=lambda r: str(r.get("key", "")))[0]


def _min_duedate(rows: list[dict[str, Any]]) -> str:
    dates = [str(r.get("duedate") or "").strip() for r in rows if r.get("duedate")]
    return min(dates) if dates else "TBD"


def _unique_sorted(values: list[str]) -> str:
    return ", ".join(sorted(set(values))) if values else ""


def render_ai_triage_readme(
    *,
    component: str,
    jql: str,
    issues: list[dict[str, Any]],
    generated_at_utc: str,
) -> str:
    """Emit a constant **AI Retriage Update** block per CVE (ProdSec-style narrative shell).

    Fills CVE id, Jira-derived title, priority, due date, and links. Product-impact and
    image/SBOM sections are guidance prompts until filled from investigation.
    """
    cal = _calendar_date_from_generated(generated_at_utc)
    lines: list[str] = [
        "# AI Retriage bundle (from `devassist cve find`)",
        "",
        f"- **Component**: {component}",
        f"- **Finder JQL**: `{jql}`",
        f"- **Generated (UTC)**: {generated_at_utc}",
        "",
        "Each CVE below uses the same section order so updates stay comparable in email, Jira, or LLM handoff.",
        "",
        "---",
        "",
    ]

    by_cve: dict[str, list[dict[str, Any]]] = defaultdict(list)
    bare: list[dict[str, Any]] = []
    for row in issues:
        cves = row.get("cves") or []
        if isinstance(cves, list) and cves:
            for cid in cves:
                if isinstance(cid, str) and cid:
                    by_cve[cid].append(row)
        else:
            bare.append(row)

    for cve_id in sorted(by_cve.keys()):
        rows = by_cve[cve_id]
        primary = _primary_issue_row(rows)
        title = str(primary.get("summary") or "_no summary_").strip()
        nvd = f"https://nvd.nist.gov/vuln/detail/{cve_id}"
        due = _min_duedate(rows)
        prios = sorted({str(r.get("priority") or "").strip() for r in rows if r.get("priority")})
        if not prios:
            severity_line = "TBD (set from Jira priority / NVD CVSS after review)"
        elif len(prios) == 1:
            severity_line = prios[0]
        else:
            severity_line = _unique_sorted(prios)

        jira_links = ", ".join(
            f"[{r['key']}]({r.get('browse_url', '#')})"
            for r in sorted(rows, key=lambda x: str(x.get("key", "")))
            if r.get("key")
        )
        keys_csv = ", ".join(
            sorted({str(r.get("key")) for r in rows if r.get("key")})
        )

        lines.append(f"## AI Retriage Update - {cal}")
        lines.append("")
        lines.append(f"CVE: {cve_id} — {title}")
        lines.append(f"Severity: {severity_line}")
        lines.append(f"Due date: {due}")
        lines.append("Updated verdict: pending-triage")
        lines.append("")
        lines.append(
            "_Verdict examples after review: `ai-nonfixable`, `ai-fixable`, `needs-human`, "
            "`vex-not-applicable`, `pending-rpm-errata`._"
        )
        lines.append("")
        lines.append(f"NVD: {nvd}")
        lines.append(f"Linked Jira: {jira_links}")
        lines.append(f"Issue keys: {keys_csv}")
        lines.append("")
        lines.append("### RHOAI Product Impact")
        lines.append("")
        lines.append(
            "_Explain whether this is a pure source-scan / VEX false positive vs manifest-box "
            "evidence (customer-facing images, shipped binaries, notebook runtime paths). "
            "Reference SBOM or image inspection after version-matched confirmation._"
        )
        lines.append("")
        lines.append("### Representative built-image evidence")
        lines.append("")
        lines.append(
            "_Add one stanza per representative image (rhoai / ODH naming as used in your program)._"
        )
        lines.append("")
        lines.append("| Image / workload | Dependency | Version | Location |")
        lines.append("| --- | --- | --- | --- |")
        lines.append(
            "| _e.g. odh-workbench-codeserver-…_ | _e.g. google.golang.org/grpc_ | _e.g. v1.72.2_ | _e.g. /usr/bin/skopeo_ |"
        )
        lines.append("")
        lines.append("_Or free-form blocks:_")
        lines.append("")
        lines.append("```text")
        lines.append("<image-name>")
        lines.append("<module>@<version>")
        lines.append("location: <path>")
        lines.append("```")
        lines.append("")
        lines.append("### Repo-side evidence")
        lines.append("")
        lines.append(
            "- _Dockerfile paths (e.g. `codeserver/.../Dockerfile.cpu`), `go.mod` under `/scripts/`, "
            "and how that maps to the broad image families (codeserver / jupyter / runtime)._"
        )
        lines.append("- _Use `devassist cve fix-plan <KEY>…` for duplicate PR hints._")
        lines.append("")
        lines.append("### Why this is still not AI-fixable")
        lines.append("")
        lines.append(
            "- _e.g. intentionally shipped CLI/RPM; not Component-not-present / VEX closure; "
            "remediation gated on errata or base image — fill from product constraints._"
        )
        lines.append("")
        lines.append("### Recommended next step")
        lines.append("")
        lines.append(
            "- _e.g. confirm fixed RPM/errata for RHEL/AppStream layers; rebuild images; "
            "if no fix exists, keep open pending vendor packages._"
        )
        lines.append("")
        lines.append("### Additional note")
        lines.append("")
        lines.append(
            "- _Sibling trackers, secondary SBOM hits (e.g. repo tooling vs runtime), "
            "cross-link after manifest-box confirmation._"
        )
        lines.append("")
        lines.append("### Ticket snapshot (from finder)")
        lines.append("")
        lines.append("| Key | Status | Priority | Type | Due | Labels | Summary |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        seen_keys: set[str] = set()
        for r in sorted(rows, key=lambda x: str(x.get("key", ""))):
            k = str(r.get("key", ""))
            if not k or k in seen_keys:
                continue
            seen_keys.add(k)
            sum_esc = str(r.get("summary", "")).replace("|", r"\|")
            lab_esc = str(r.get("labels", "")).replace("|", r"\|")
            lines.append(
                f"| {k} | {r.get('status', '')} | {r.get('priority', '')} | "
                f"{r.get('issuetype', '')} | {r.get('duedate', '')} | {lab_esc} | {sum_esc} |"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

    if bare:
        lines.append("## Issues without a CVE id in summary or description")
        lines.append("")
        lines.append(
            "_These tickets matched the finder (label + component) but no `CVE-YYYY-NNNN` "
            "was parsed from summary/description — review manually or extend parsing._"
        )
        lines.append("")
        for row in bare:
            lines.append(
                f"- **[{row.get('key')}]({row.get('browse_url', '#')})** — {row.get('summary', '')}"
            )
        lines.append("")

    if not by_cve and not bare:
        lines.append("## No issues")
        lines.append("")
        lines.append("_Nothing to triage after filters._")
        lines.append("")

    return "\n".join(lines)
