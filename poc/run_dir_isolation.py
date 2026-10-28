# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Invocation-bound RUN_DIR isolation (artifact immutability contract).

Post-condition of the dbe2d21 finding: a fixed shared RUN_DIR let successive
executions overwrite prior raw packets (three generations were collapsed).
Every QA execution now resolves a run directory that is uniquely bound to its
invocation and refuses to reuse or overwrite anything:

    resolve_run_dir(invocation_id, root, allow_ready=True)

Rules (fail-closed, before any model call):
    1. one-to-one binding: the run dir is exactly <root>/<invocation_id>
    2. reuse of another invocation's run dir is impossible by construction
       (the dir name is the invocation id) and checked against the permit
    3. existing raw packet overwrite is refused: any pre-existing
       packet-*.json in <run_dir>/raw blocks the run
    4. output collision: when the run dir already contains a completed
       run summary (or any execution artifacts) it is refused entirely
    5. after the run, seal_run_dir fixes the manifest + artifact digests
    6. sealing never deletes or rewrites prior runs (each has its own dir)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class RunDirCollisionBlocked(Exception):
    """Fail-closed run-directory refusal (never reaches a model call)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"BLOCKED:{code}" + (f" ({detail})" if detail else ""))
        self.code = code
        self.detail = detail


def run_dir_for(invocation_id: str, root: Path) -> Path:
    if not invocation_id or "/" in invocation_id or invocation_id in (".", ".."):
        raise RunDirCollisionBlocked("INVOCATION_ID_INVALID", invocation_id)
    return Path(root) / invocation_id


def resolve_run_dir(
    invocation_id: str,
    root: Path,
    *,
    permit_invocation_id: str = "",
    allow_existing_empty: bool = True,
) -> Path:
    """Resolve and validate the run dir; raise before any model call."""
    run_dir = run_dir_for(invocation_id, root)
    if permit_invocation_id and invocation_id != permit_invocation_id:
        raise RunDirCollisionBlocked("INVOCATION_ID_MISMATCH",
                                     f"run_dir={invocation_id} permit={permit_invocation_id}")
    if run_dir.exists():
        # 3. pre-existing raw packet overwrite is refused
        raw = run_dir / "raw"
        if raw.is_dir() and any(raw.glob("packet-*.json")):
            raise RunDirCollisionBlocked("RAW_PACKET_COLLISION", str(raw))
        # 4. output collision: a completed execution already occupies the dir
        summary = run_dir / "run-summary.json"
        if summary.exists():
            raise RunDirCollisionBlocked("RUN_DIR_REUSED_COMPLETED", str(summary))
        # any execution artifact at all means the dir was used before
        if not allow_existing_empty or any(p.name not in (".", "..") for p in run_dir.iterdir()):
            raise RunDirCollisionBlocked("RUN_DIR_ALREADY_USED", str(run_dir))
    return run_dir


def seal_run_dir(run_dir: Path) -> dict:
    """Fix the manifest + artifact digests after execution (rule 5).

    Writes seal-run-dir.json with per-artifact sha256 digests; never rewrites
    the artifacts themselves.
    """
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    artifacts = {}
    for p in sorted(run_dir.rglob("*")):
        if p.is_file() and p.name != "seal-run-dir.json":
            artifacts[str(p.relative_to(run_dir))] = digest(p)
    seal = {"schema": "rrsi-run-dir-seal/v0.1",
            "run_dir": str(run_dir),
            "artifact_digests": artifacts}
    (run_dir / "seal-run-dir.json").write_text(json.dumps(seal, indent=1, sort_keys=True))
    return seal


def verify_seal(run_dir: Path) -> bool:
    """Check that a seal exists and every artifact digest still matches."""
    seal_path = run_dir / "seal-run-dir.json"
    if not seal_path.exists():
        return False
    seal = json.loads(seal_path.read_text())
    for rel, expected in seal["artifact_digests"].items():
        p = run_dir / rel
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            return False
    return True
