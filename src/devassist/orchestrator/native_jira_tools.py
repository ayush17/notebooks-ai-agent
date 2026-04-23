"""Jira Cloud REST tools for ``ask`` / ``chat`` (email + API token).

Uses ``GET /rest/api/3/search/jql`` and ``GET /rest/api/3/issue/{key}`` — no browser OAuth.
"""

from __future__ import annotations

import json
import os
from typing import Any, cast

import httpx

from devassist.jira_enhanced_search import fetch_jql_search_jql_page
from devassist.mcp.client import ToolResult, ToolSchema

_SERVER = "jira_api"
_SEARCH_FIELDS = "summary,description,assignee,status,updated,priority,issuetype,project"


def resolve_jira_rest_credentials() -> tuple[str, tuple[str, str]] | None:
    """Return ``(base_url, (email, api_token))`` from environment."""
    base = (os.environ.get("ATLASSIAN_BASE_URL") or os.environ.get("JIRA_URL") or "").strip().rstrip("/")
    email = (os.environ.get("ATLASSIAN_EMAIL") or os.environ.get("JIRA_USERNAME") or "").strip()
    token = (
        os.environ.get("ATLASSIAN_API_TOKEN")
        or os.environ.get("JIRA_API_TOKEN")
        or os.environ.get("JIRA_PERSONAL_TOKEN")
        or ""
    ).strip()
    if base and email and token:
        return base, (email, token)
    return None


def jira_native_tools_enabled() -> bool:
    return resolve_jira_rest_credentials() is not None


def build_jira_native_tool_schemas() -> list[ToolSchema]:
    """Tool schemas to merge with MCP tools when Jira REST env is set."""
    if not jira_native_tools_enabled():
        return []
    return [
        ToolSchema(
            name="jira_rest_search",
            description=(
                "Search Jira issues with JQL via Jira Cloud REST (API token auth, no browser). "
                "Use for open issues, assignments, projects. "
                "Example jql: assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC"
            ),
            server=_SERVER,
            input_schema={
                "type": "object",
                "properties": {
                    "jql": {"type": "string", "description": "JQL query"},
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum issues to return (1-100, default 25)",
                    },
                },
                "required": ["jql"],
            },
        ),
        ToolSchema(
            name="jira_rest_get_issue",
            description="Get one Jira issue by key (e.g. TEAM-42) via REST API.",
            server=_SERVER,
            input_schema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string"},
                    "fields": {
                        "type": "string",
                        "description": "Optional comma-separated field ids",
                    },
                },
                "required": ["issue_key"],
            },
        ),
    ]


def _adf_to_text(adf: dict[str, Any]) -> str:
    if not adf or not isinstance(adf, dict):
        return ""
    parts: list[str] = []

    def walk(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            t = node.get("type")
            if t == "paragraph":
                walk(node.get("content", []))
            elif t == "text":
                parts.append(str(node.get("text", "")))

    walk(adf.get("content", []))
    return "\n".join(parts)


def _normalize_description(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return _adf_to_text(value) or None
    return str(value)


async def run_jira_native_tool(
    tool_name: str,
    arguments: dict[str, Any] | None,
) -> ToolResult | None:
    """Run a native Jira REST tool, or return ``None`` if ``tool_name`` is not handled here."""
    if tool_name not in ("jira_rest_search", "jira_rest_get_issue"):
        return None
    creds = resolve_jira_rest_credentials()
    if not creds:
        return ToolResult(
            tool_name=tool_name,
            server=_SERVER,
            content=(
                "Jira REST is not configured. Set ATLASSIAN_BASE_URL, ATLASSIAN_EMAIL, "
                "and ATLASSIAN_API_TOKEN (or JIRA_URL, JIRA_USERNAME, JIRA_PERSONAL_TOKEN / JIRA_API_TOKEN)."
            ),
            is_error=True,
        )
    args = arguments or {}
    if tool_name == "jira_rest_search":
        return await _run_search(creds, args)
    return await _run_get_issue(creds, args)


async def _run_search(
    creds: tuple[str, tuple[str, str]],
    args: dict[str, Any],
) -> ToolResult:
    jql = str(args.get("jql") or "").strip()
    if not jql:
        return ToolResult(
            tool_name="jira_rest_search",
            server=_SERVER,
            content="Error: jql is required",
            is_error=True,
        )
    max_results = int(args.get("max_results") or 25)
    max_results = min(100, max(1, max_results))
    base, auth = creds
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            while len(rows) < max_results:
                page = min(100, max_results - len(rows))
                issues, next_cursor, page_last = await fetch_jql_search_jql_page(
                    client,
                    base,
                    auth,
                    jql=jql,
                    max_results=page,
                    fields=_SEARCH_FIELDS,
                    next_page_token=cursor,
                )
                for issue in issues:
                    if len(rows) >= max_results:
                        break
                    key = issue.get("key")
                    fields = issue.get("fields") or {}
                    assignee = fields.get("assignee")
                    assignee_name = assignee.get("displayName") if isinstance(assignee, dict) else None
                    rows.append(
                        {
                            "key": key,
                            "summary": fields.get("summary"),
                            "status": (fields.get("status") or {}).get("name"),
                            "assignee": assignee_name,
                            "updated": fields.get("updated"),
                            "url": f"{base}/browse/{key}" if key else None,
                        }
                    )
                if page_last or not next_cursor or not issues:
                    break
                cursor = next_cursor
    except httpx.HTTPStatusError as e:
        body = e.response.text[:500] if e.response else ""
        return ToolResult(
            tool_name="jira_rest_search",
            server=_SERVER,
            content=f"Jira HTTP {e.response.status_code}: {body}",
            is_error=True,
        )
    except httpx.RequestError as e:
        return ToolResult(
            tool_name="jira_rest_search",
            server=_SERVER,
            content=f"Jira request failed: {e}",
            is_error=True,
        )

    return ToolResult(
        tool_name="jira_rest_search",
        server=_SERVER,
        content=json.dumps({"issues": rows, "count": len(rows)}, indent=2),
        is_error=False,
    )


async def _run_get_issue(
    creds: tuple[str, tuple[str, str]],
    args: dict[str, Any],
) -> ToolResult:
    key = str(args.get("issue_key") or "").strip()
    if not key:
        return ToolResult(
            tool_name="jira_rest_get_issue",
            server=_SERVER,
            content="Error: issue_key is required",
            is_error=True,
        )
    fields = str(args.get("fields") or "summary,description,status,assignee,priority,updated,issuetype,project").strip()
    base, auth = creds
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(
                f"{base}/rest/api/3/issue/{key}",
                auth=auth,
                params={"fields": fields},
            )
            if r.status_code == 404:
                return ToolResult(
                    tool_name="jira_rest_get_issue",
                    server=_SERVER,
                    content=f"Issue {key} not found",
                    is_error=True,
                )
            r.raise_for_status()
            data = cast(dict[str, Any], r.json())
    except httpx.HTTPStatusError as e:
        body = e.response.text[:500] if e.response else ""
        return ToolResult(
            tool_name="jira_rest_get_issue",
            server=_SERVER,
            content=f"Jira HTTP {e.response.status_code}: {body}",
            is_error=True,
        )
    except httpx.RequestError as e:
        return ToolResult(
            tool_name="jira_rest_get_issue",
            server=_SERVER,
            content=f"Jira request failed: {e}",
            is_error=True,
        )

    f = data.get("fields") or {}
    out = {
        "key": data.get("key"),
        "summary": f.get("summary"),
        "description": _normalize_description(f.get("description")),
        "status": (f.get("status") or {}).get("name"),
        "assignee": (f.get("assignee") or {}).get("displayName") if f.get("assignee") else None,
        "priority": (f.get("priority") or {}).get("name") if f.get("priority") else None,
        "updated": f.get("updated"),
        "issuetype": (f.get("issuetype") or {}).get("name"),
        "project": (f.get("project") or {}).get("key"),
        "browse_url": f"{base}/browse/{data.get('key')}",
    }
    return ToolResult(
        tool_name="jira_rest_get_issue",
        server=_SERVER,
        content=json.dumps(out, indent=2),
        is_error=False,
    )
