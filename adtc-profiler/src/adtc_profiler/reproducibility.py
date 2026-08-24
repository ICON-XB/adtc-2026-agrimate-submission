"""Capture reproducibility block: git_commit_sha, docker_image_digest, random_seed.

Schema requires:
  - git_commit_sha: ^[a-f0-9]{7,40}$    (lowercase hex)
  - docker_image_digest: non-empty string (preferably "sha256:...")
  - random_seed: integer >= 0
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

_SHA_RE = re.compile(r"^[a-f0-9]{7,40}$")


def git_commit_sha(repo_path: Path | None = None) -> str:
    """Resolve HEAD SHA of `repo_path` (or CWD). Returns 7-char fallback if unavailable."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=str(repo_path) if repo_path else None,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        sha = proc.stdout.strip().lower()
        if _SHA_RE.match(sha):
            return sha
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass
    # Schema requires a hex SHA; emit a deterministic placeholder when no git.
    return "0" * 12


def docker_image_digest(image_ref: str | None) -> str:
    """Return the sha256 digest of the named image, or the ref itself if unknown.

    Schema requires a non-empty string; "unknown" is allowed but discouraged.
    """
    if not image_ref:
        return "unknown"
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image_ref],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        digest = proc.stdout.strip()
        if digest:
            return digest
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return image_ref


def capture(
    *,
    seed: int,
    repo_path: Path | None = None,
    docker_image: str | None = None,
) -> dict:
    return {
        "git_commit_sha": git_commit_sha(repo_path),
        "docker_image_digest": docker_image_digest(docker_image),
        "random_seed": int(seed),
    }
