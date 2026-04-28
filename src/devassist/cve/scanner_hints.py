"""Ecosystem-specific verification commands (verify-before-fix, pinned toolchains)."""

from __future__ import annotations

from pathlib import Path


def hints_for_repo_path(repo_root: Path) -> list[str]:
    """Suggest scanners based on files present at the repo root (or subtree heuristics)."""
    hints: list[str] = []
    root = repo_root.resolve()

    if (root / "go.mod").is_file():
        hints.append(
            "Go: set GOTOOLCHAIN to match go.mod, then run `govulncheck ./...` "
            "(and `go test ./...` after dependency changes)."
        )
    if (root / "package.json").is_file():
        hints.append("Node: run `npm audit --production` (or `pnpm audit`) with the repo's Node version.")
    if (root / "pnpm-lock.yaml").is_file() or (root / "yarn.lock").is_file():
        hints.append("Node: lockfile present — use the same package manager the repo documents.")
    if (root / "requirements.txt").is_file() or (root / "pyproject.toml").is_file():
        hints.append("Python: run `pip-audit` / `uv pip audit` against the project's environment.")
    if (root / "pom.xml").is_file() or (root / "build.gradle").is_file() or (root / "build.gradle.kts").is_file():
        hints.append("JVM: run `mvn -q -DskipTests dependency:tree` / Gradle dependency insight as appropriate.")

    if not hints:
        hints.append(
            "No standard manifest detected at repo root; pin the project's documented toolchain "
            "and run the security scanner your team uses for this stack."
        )
    return hints
