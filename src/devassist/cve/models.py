"""Structured component → repository mapping (CVE Fixer–style routing)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RepoEntry(BaseModel):
    """One GitHub repo and branch line for a Jira component."""

    github_url: str = Field(..., description="HTTPS URL for the GitHub repository")
    default_branch: str = Field("main", description="Primary integration branch")
    repo_type: str = Field(
        "upstream",
        description="upstream | midstream | downstream (routing metadata only)",
    )


class ComponentMapping(BaseModel):
    """Maps a Jira component name to one or more GitHub repositories."""

    repositories: dict[str, RepoEntry] = Field(default_factory=dict)
