"""Load/save ``component-repository-mappings.json`` under the DevAssist workspace."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from devassist.cve.models import ComponentMapping


def mappings_path(workspace: Path | str) -> Path:
    """Path to the mapping file (same structural role as ambient-code's JSON)."""
    return Path(workspace).expanduser().resolve() / "cve" / "component-repository-mappings.json"


def load_mappings(workspace: Path | str) -> dict[str, ComponentMapping]:
    """Load component → repositories map; returns empty dict if missing."""
    path = mappings_path(workspace)
    if not path.is_file():
        return {}
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    out: dict[str, ComponentMapping] = {}
    for key, val in raw.items():
        if isinstance(val, dict):
            out[str(key)] = ComponentMapping.model_validate(val)
    return out


def save_mappings(workspace: Path | str, data: dict[str, ComponentMapping]) -> None:
    """Persist mappings as indented JSON."""
    path = mappings_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: v.model_dump() for k, v in data.items()}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
