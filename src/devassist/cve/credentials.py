"""Resolve Jira and GitHub credentials from environment and DevAssist config."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class JiraAuth:
    """Base URL and Basic-auth pair for Jira REST API."""

    base_url: str
    email: str
    api_token: str


def _merge_devassist_dotenv() -> None:
    """Load ``~/.devassist/env`` into ``os.environ`` (same as the main CLI)."""
    from devassist.core.env_store import load_devassist_env_into_os

    load_devassist_env_into_os(prefer_file=True)


def _jira_from_saved_config() -> JiraAuth | None:
    """Use ``sources.jira`` from ``~/.devassist/config.yaml`` (``devassist config add jira``)."""
    from devassist.core.config_manager import ConfigManager

    mgr = ConfigManager()
    cfg = mgr.load_config()
    raw = cfg.sources.get("jira")
    if not raw:
        return None
    if raw.get("enabled") is False:
        return None

    base = (
        (raw.get("url") or raw.get("base_url") or "").strip()
        or (raw.get("ATLASSIAN_BASE_URL") or "").strip()
    )
    email = (raw.get("email") or raw.get("username") or "").strip()
    token = (
        (raw.get("api_token") or raw.get("personal_access_token") or "").strip()
        or (raw.get("ATLASSIAN_API_TOKEN") or "").strip()
    )

    if not (base and email and token):
        return None

    url = base.rstrip("/")
    return JiraAuth(base_url=url, email=email, api_token=token)


def resolve_github_token() -> str | None:
    """Return GitHub token from common env var names (after merging ``~/.devassist/env``)."""
    _merge_devassist_dotenv()
    return (
        os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
    )


def resolve_jira_auth() -> JiraAuth | None:
    """Resolve Jira auth: merge ``~/.devassist/env``, then env vars, then ``config.yaml``.

    Order matches other commands that rely on setup wizard output without requiring a shell export.
    """
    _merge_devassist_dotenv()

    base = (
        os.environ.get("ATLASSIAN_BASE_URL")
        or os.environ.get("ATLASSIAN_SITE_URL")
        or os.environ.get("JIRA_URL")
        or os.environ.get("JIRA_URI")
    )
    email = os.environ.get("ATLASSIAN_EMAIL") or os.environ.get("JIRA_USERNAME")
    token = os.environ.get("ATLASSIAN_API_TOKEN") or os.environ.get("JIRA_PERSONAL_TOKEN")

    if base and email and token:
        url = base.rstrip("/")
        return JiraAuth(base_url=url, email=email, api_token=token)

    return _jira_from_saved_config()
