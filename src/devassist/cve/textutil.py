"""CVE id extraction and Jira comment ignore markers."""

from __future__ import annotations

import re
from collections.abc import Iterable

_CVE_PATTERN = re.compile(r"\b(CVE-\d{4}-\d+)\b", re.IGNORECASE)

_DEFAULT_IGNORE_MARKER = "cve-automation-ignore"


def extract_cve_ids(text: str) -> list[str]:
    """Return unique CVE identifiers in ``CVE-YYYY-NNNN`` form, sorted lexicographically."""
    raw = {m.group(1).upper() for m in _CVE_PATTERN.finditer(text or "")}
    return sorted(raw)


def issue_should_be_ignored(
    comment_bodies: Iterable[str],
    extra_markers: tuple[str, ...] = (),
) -> bool:
    """Return True if any comment requests automation to skip this issue.

    Matches the Ambient CVE Fixer pattern: ``cve-automation-ignore`` in any comment,
    plus optional extra substrings from configuration.
    """
    markers = (_DEFAULT_IGNORE_MARKER,) + tuple(m for m in extra_markers if m)
    for body in comment_bodies:
        low = (body or "").lower()
        for m in markers:
            if m.lower() in low:
                return True
    return False
