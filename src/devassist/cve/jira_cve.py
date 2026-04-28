"""JQL builders for ProdSec-style CVE issues."""

from __future__ import annotations


def _escape_jql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_cve_jql(
    *,
    component: str,
    project_key: str | None,
    ignore_resolved: bool,
) -> str:
    """Build JQL for issues with the ``CVE`` label for a given component."""
    parts: list[str] = []
    if project_key:
        pk = _escape_jql_string(project_key.strip())
        parts.append(f'project = "{pk}"')
    comp = _escape_jql_string(component.strip())
    parts.append(f'component = "{comp}"')
    parts.append('labels = "CVE"')
    if ignore_resolved:
        parts.append("statusCategory != Done")
    return " AND ".join(parts)
