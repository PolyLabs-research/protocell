"""Provenance kept beside every run's data: which code, settings, seeds and platform produced it, and how long it took.

The manifest is provenance, not data: nothing in it enters a result or a hash, and it is the one file in a run's
directory that carries wall-clock time. ``git.dirty`` is True when a tracked file has uncommitted changes (untracked
files do not count); outside a repository it is None, so a clean tree is never claimed without being known.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from protocell.determinism import blas_info

MANIFEST_VERSION = 1
_REPO = Path(__file__).resolve().parent.parent


def _git(*args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], cwd=_REPO, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def git_state() -> Dict[str, Any]:
    sha = _git("rev-parse", "HEAD")
    if sha is None:
        return {"sha": "unknown", "branch": "unknown", "dirty": None}
    status = _git("status", "--porcelain", "--untracked-files=no")
    return {"sha": sha, "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown",
            "dirty": None if status is None else bool(status)}


def build_manifest(*, protocol: str, settings: Mapping[str, Any], seeds: Sequence[int], extra: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    return {"manifest_version": MANIFEST_VERSION, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git": git_state(), "protocol": protocol, "settings": dict(settings), "seeds": list(seeds),
            "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(),
                         "python": sys.version.split()[0], **blas_info()},
            "command": " ".join(sys.argv), **(dict(extra) if extra else {})}


def finish_manifest(manifest: Dict[str, Any], *, wall_seconds: float, **counts: Any) -> Dict[str, Any]:
    manifest["timing"] = {"wall_seconds": wall_seconds, **counts}
    return manifest


def write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=1, sort_keys=True, default=str) + "\n")
