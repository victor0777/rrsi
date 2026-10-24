# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""R0-b2 dataset split re-examination and freeze (directive item 2).

Resolves the R0-b1 defect 10(a): the R1 design's agent-memory-centered Evolve
set collides with the R0-a frozen holdout denylist (13 ids, ALL agent-memory
papers). Resolution policy, registered here:

  - the denylist stays authoritative and unchanged (it is the R0-a frozen
    safety surface);
  - Evolve may only contain denylist-safe ids;
  - split roles with an unresolved collision are NOT assigned; their papers
    are BLOCKED_CONFLICTED and must not be evaluated (directive: "충돌이
    해결되지 않은 데이터는 평가에 사용하지 않는다");
  - Validation and Final Holdout freeze empty until sources are acquired and
    a collision-free re-split is approved; re-splitting inside a promotion
    cycle is forbidden (R1 design §3.2 #5) — the freeze hash below is that
    registration.

Output: split-manifest/v0.1 JSON + SHA-256 (file list sorted, canonical JSON).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

AI_PAPERS = Path("/home/ktl/projects/ai_papers")
GOLD = AI_PAPERS / "docs/eval/reader-note-quality/gold"

# R0-a frozen holdout denylist (poc/r0a_checks.py::HOLDOUT_IDS) — unchanged.
DENYLIST_IDS = [
    "2502.12110", "2508.04700", "2508.06433", "2508.08997",
    "2508.09736", "2508.09874", "2509.11860", "2509.21212",
    "2510.08191", "2605.23723", "2508.01922", "2510.16729", "2510.17148",
]

SPLIT_SCHEMA = "rrsi-split-manifest/v0.1"


def canonical_gt_id(filename: str) -> tuple[str, str]:
    """agent-memory-arxiv-2502-12110... -> cohort axis + arxiv base id."""
    stem = filename.removesuffix(".reader-note-quality-gt.json")
    axis, arxiv = stem.split("-arxiv-")
    arxiv = arxiv.replace("-", ".")
    return axis, arxiv


def main() -> int:
    entries = []
    for f in sorted(GOLD.glob("*.reader-note-quality-gt.json")):
        axis, arxiv = canonical_gt_id(f.name)
        gt = json.loads(f.read_text())
        workflow_id = gt["workflow_id"]
        if arxiv in DENYLIST_IDS:
            role = "BLOCKED_CONFLICTED"
            role_reason = "R0-a holdout denylist id; Evolve collision unresolved"
        else:
            role = "EVOLVE"
            role_reason = ("denylist-safe; Evolve e2e pair of R1 design §3.1 "
                           "(agent-memory slots frozen empty)")
        entries.append({
            "workflow_id": workflow_id,
            "cohort_axis": axis,
            "arxiv_base_id": arxiv,
            "arxiv_version": None,      # recorded at acquisition; none acquired
            "source_status": "not_acquired",
            "role": role,
            "role_reason": role_reason,
        })

    acquired = [{"workflow_id": "e2e-arxiv-2508-11428",
                 "arxiv_base_id": "2508.11428", "arxiv_version": "2508.11428v2",
                 "source_sha256": "808e4f741338cda32030ca21f8af37eb9b1bfcdaa40909319b773105f9c5699d",
                 "dataset_manifest_sha256": "57d1a501f12306a79c06fed2ea4f62dce5c82179c4bf7eddb90048a99ee0bb51"}]
    by_id = {e["workflow_id"]: e for e in entries}
    for a in acquired:
        e = by_id[a["workflow_id"]]
        e.update(source_status="acquired",
                 arxiv_version=a["arxiv_version"],
                 source_sha256=a["source_sha256"],
                 dataset_manifest_sha256=a["dataset_manifest_sha256"])

    manifest = {
        "schema": SPLIT_SCHEMA,
        "frozen_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "base_commit_r0a": "4e0c1e5",
        "denylist_policy": "authoritative, unchanged; BLOCKED_CONFLICTED superset",
        "evolve": sorted(e["workflow_id"] for e in entries if e["role"] == "EVOLVE"),
        "validation": [],
        "final_holdout": [],
        "blocked_conflicted": sorted(e["workflow_id"] for e in entries
                                     if e["role"] == "BLOCKED_CONFLICTED"),
        "entries": entries,
    }

    # duplicate-role check: every id exactly one role
    ids = [e["workflow_id"] for e in entries]
    assert len(ids) == len(set(ids)), "duplicate gold id"
    overlap = set(manifest["evolve"]) & (set(manifest["validation"])
                                         | set(manifest["final_holdout"])
                                         | set(manifest["blocked_conflicted"]))
    assert not overlap, f"role overlap: {overlap}"
    deny_in_evolve = set(DENYLIST_IDS) & {e["arxiv_base_id"] for e in entries
                                          if e["role"] != "BLOCKED_CONFLICTED"}
    assert not deny_in_evolve, f"denylist leak into usable roles: {deny_in_evolve}"

    b = json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(b).hexdigest()
    out = Path(__file__).resolve().parent / "runs/r0b2"
    out.mkdir(parents=True, exist_ok=True)
    (out / "split-manifest.json").write_bytes(b)
    print(json.dumps({"split_manifest_sha256": digest,
                      "evolve": manifest["evolve"],
                      "blocked_conflicted": len(manifest["blocked_conflicted"]),
                      "checks": "uniqueness+disjointness+denylist-leak PASS"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
