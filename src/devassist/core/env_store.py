"""DevAssist secrets and shell-oriented settings: ``~/.devassist/env`` (canonical).

Legacy ``~/.devassist/.env`` is still read when present (lower precedence) and is
updated alongside ``env`` on write so existing ``source ~/.devassist/.env`` flows keep working.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

_CANONICAL_ENV = "env"
_LEGACY_DOT_ENV = ".env"


def get_env_file_path() -> Path:
    """Canonical credential file: ``~/.devassist/env``."""
    return Path.home() / ".devassist" / _CANONICAL_ENV


def get_legacy_env_file_path() -> Path:
    """Legacy path kept in sync on write for backwards compatibility."""
    return Path.home() / ".devassist" / _LEGACY_DOT_ENV


def _parse_export_env_file(env_file: Path) -> dict[str, str]:
    """Parse export KEY=value lines into key/value pairs (non-empty values only)."""
    out: dict[str, str] = {}
    if not env_file.is_file():
        return out
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.replace("export ", "").strip()
            value = value.strip().strip('"').strip("'")
            if key:
                out[key] = value
    return out


def read_devassist_env_dict() -> dict[str, str]:
    """Parse merged env files: legacy ``.env`` first, then ``env`` (canonical overrides)."""
    legacy = _parse_export_env_file(get_legacy_env_file_path())
    canonical = _parse_export_env_file(get_env_file_path())
    return {**legacy, **canonical}


def _sync_github_pat_into_os() -> None:
    """``@modelcontextprotocol/server-github`` only reads ``GITHUB_PERSONAL_ACCESS_TOKEN``.

    Copy from ``GITHUB_TOKEN`` / ``GH_TOKEN`` when the PAT name is unset so ``ask`` /
    ``chat`` work with the variable names GitHub documents most often.
    """
    current = (os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or "").strip()
    if current:
        return
    alt = (os.environ.get("GITHUB_TOKEN") or "").strip() or (os.environ.get("GH_TOKEN") or "").strip()
    if alt:
        os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = alt


def load_devassist_env_into_os(*, prefer_file: bool = True) -> None:
    """Apply ``~/.devassist/env`` (and legacy ``.env`` if present) to ``os.environ``.

    If ``prefer_file`` is True (default), every non-empty value in the file **overrides**
    the current process environment for that key so shell exports do not mask the
    canonical DevAssist config file.

    If ``prefer_file`` is False, only sets keys that are not already set (legacy behavior).
    """
    data = read_devassist_env_dict()
    if prefer_file:
        for key, value in data.items():
            if value:
                os.environ[key] = value
    else:
        for key, value in data.items():
            if value and not os.environ.get(key):
                os.environ[key] = value
    _sync_github_pat_into_os()


def merge_devassist_env_updates(updates: dict[str, str]) -> None:
    """Merge ``updates`` into ``~/.devassist/env`` (and mirror ``.env``) and apply to ``os.environ``."""
    merged = read_devassist_env_dict()
    for k, v in updates.items():
        if v:
            merged[k] = v
    write_devassist_env_from_dict(merged)
    load_devassist_env_into_os(prefer_file=True)


def remove_devassist_env_keys(keys: Iterable[str]) -> None:
    """Remove keys from env files and from ``os.environ``."""
    merged = read_devassist_env_dict()
    for k in keys:
        merged.pop(k, None)
        os.environ.pop(k, None)
    write_devassist_env_from_dict(merged)


def write_devassist_env_from_dict(config: dict[str, str]) -> None:
    """Write the full env dictionary to ``~/.devassist/env`` and mirror ``~/.devassist/.env``."""
    env_file = get_env_file_path()
    legacy_file = get_legacy_env_file_path()
    env_file.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# DevAssist configuration — edit with: devassist setup init | devassist config add",
        "# Canonical file: ~/.devassist/env (.env is a mirror for older scripts).",
        "# The CLI loads these on every run (overrides shell for set keys).",
        "",
    ]

    categories: dict[str, list[str]] = {
        "Claude on Vertex AI (Red Hat)": [
            "CLAUDE_CODE_USE_VERTEX",
            "CLOUD_ML_REGION",
            "ANTHROPIC_VERTEX_PROJECT_ID",
        ],
        "Claude (direct API)": ["ANTHROPIC_API_KEY"],
        "GitHub": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
        "Atlassian (Jira / Confluence)": [
            "ATLASSIAN_BASE_URL",
            "ATLASSIAN_EMAIL",
            "ATLASSIAN_API_TOKEN",
            "ATLASSIAN_SITE_URL",
        ],
        "Slack": ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID", "SLACK_USER_ID"],
        "Gmail": ["DEVASSIST_GMAIL_CREDENTIALS_FILE"],
    }

    known: set[str] = set()
    for keys in categories.values():
        known.update(keys)

    written: set[str] = set()
    for title, keys in categories.items():
        to_emit: list[tuple[str, str]] = []
        for key in keys:
            val = config.get(key, "")
            if not val or key in written:
                continue
            to_emit.append((key, val))
            written.add(key)
        if not to_emit:
            continue
        lines.append(f"# {title}")
        for key, val in to_emit:
            lines.append(f'export {key}="{_escape_env_value(val)}"')
        lines.append("")

    other = sorted(k for k in config if k not in known and config[k])
    if other:
        lines.append("# Other")
        for key in other:
            lines.append(f'export {key}="{_escape_env_value(config[key])}"')
        lines.append("")

    body = "\n".join(lines)
    for path in (env_file, legacy_file):
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _escape_env_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


# Keys written by ``config add`` / ``setup`` for a source (used by ``config remove``).
SOURCE_ENV_KEYS: dict[str, tuple[str, ...]] = {
    "github": ("GITHUB_PERSONAL_ACCESS_TOKEN",),
    "jira": (
        "ATLASSIAN_BASE_URL",
        "ATLASSIAN_EMAIL",
        "ATLASSIAN_API_TOKEN",
        "ATLASSIAN_SITE_URL",
    ),
    "slack": ("SLACK_BOT_TOKEN",),
    "gmail": ("DEVASSIST_GMAIL_CREDENTIALS_FILE",),
}


def source_config_from_env(source_name: str) -> dict[str, str]:
    """Build adapter-style config dict from ``os.environ`` (after ``.env`` has been loaded)."""
    n = (source_name or "").strip().lower()
    out: dict[str, str] = {}
    if n == "github":
        pat = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        if pat:
            out["personal_access_token"] = pat
    elif n == "jira":
        url = (os.environ.get("ATLASSIAN_BASE_URL") or os.environ.get("JIRA_URL") or "").strip().rstrip("/")
        email = (os.environ.get("ATLASSIAN_EMAIL") or os.environ.get("JIRA_USERNAME") or "").strip()
        token = (
            os.environ.get("ATLASSIAN_API_TOKEN")
            or os.environ.get("JIRA_API_TOKEN")
            or os.environ.get("JIRA_PERSONAL_TOKEN")
            or ""
        ).strip()
        if url and email and token:
            out.update({"url": url, "email": email, "api_token": token})
    elif n == "slack":
        tok = (os.environ.get("SLACK_BOT_TOKEN") or "").strip()
        if tok:
            out["bot_token"] = tok
    elif n == "gmail":
        path = (
            os.environ.get("DEVASSIST_GMAIL_CREDENTIALS_FILE")
            or os.environ.get("GMAIL_CREDENTIALS_FILE")
            or ""
        ).strip()
        if path:
            out["credentials_file"] = path
    return out


def source_prompt_config_to_env_updates(source: str, cfg: dict[str, str]) -> dict[str, str]:
    """Map interactive ``config add`` field names to ``~/.devassist/env`` keys."""
    n = source.strip().lower()
    if n == "github":
        return {"GITHUB_PERSONAL_ACCESS_TOKEN": cfg.get("personal_access_token", "").strip()}
    if n == "jira":
        url = (cfg.get("url") or "").strip().rstrip("/")
        email = (cfg.get("email") or "").strip()
        token = (cfg.get("api_token") or "").strip()
        out = {
            "ATLASSIAN_BASE_URL": url,
            "ATLASSIAN_EMAIL": email,
            "ATLASSIAN_API_TOKEN": token,
        }
        if url:
            out["ATLASSIAN_SITE_URL"] = f"{url}/"
        return {k: v for k, v in out.items() if v}
    if n == "slack":
        return {"SLACK_BOT_TOKEN": (cfg.get("bot_token") or "").strip()}
    if n == "gmail":
        return {"DEVASSIST_GMAIL_CREDENTIALS_FILE": (cfg.get("credentials_file") or "").strip()}
    return {}
