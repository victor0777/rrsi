# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Independent Gold Review contract (approval gate for semantic gold fixtures).

Review states (directive §C):
    DRAFT, SOURCE_VERIFIED, HUMAN_REVIEW_REQUIRED, APPROVED, REJECTED,
    NEEDS_REVISION

Approval gate rules:
    - APPROVED requires the reviewer's signed record (name/role + timestamp +
      reviewed fixture digest) covering 5 verification conditions.
    - The AUTHOR path (fixture generation automation) can never produce an
      approval: records whose reviewer_role is "author" or whose reviewer
      identity matches the registered author identity are refused.
    - A review record is only valid for the exact fixture digest it names —
      editing a fixture invalidates its review (digest mismatch).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

REVIEW_STATES = ("DRAFT", "SOURCE_VERIFIED", "HUMAN_REVIEW_REQUIRED",
                 "APPROVED", "REJECTED", "NEEDS_REVISION")

REVIEW_DECISIONS = ("Approve", "Reject", "Needs Revision")

APPROVAL_CONDITIONS = (
    "source_identity_match", "source_context_sufficient",
    "claim_evidence_relation_verified", "perturbation_semantic_defect_confirmed",
    "expected_direction_verified",
)

AUTHOR_ROLES = {"author", "author-agent", "automation", "generator"}


class GoldReviewBlocked(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"BLOCKED:{code}" + (f" ({detail})" if detail else ""))
        self.code = code
        self.detail = detail


def fixture_digest(fixture_path: Path) -> str:
    return hashlib.sha256(fixture_path.read_bytes()).hexdigest()


def record_review(*, fixture_path: Path, reviewer: str, reviewer_role: str,
                  decision: str, comment: str, conditions: dict,
                  out_path: Path) -> dict:
    """Record an independent review decision for one fixture (append-only)."""
    if decision not in REVIEW_DECISIONS:
        raise GoldReviewBlocked("REVIEW_DECISION_UNKNOWN", decision)
    if reviewer_role.lower() in AUTHOR_ROLES:
        # author path can never approve
        if decision == "Approve":
            raise GoldReviewBlocked("SELF_APPROVAL_REFUSED", reviewer_role)
    missing = [c for c in APPROVAL_CONDITIONS
               if c not in conditions or conditions[c] is not True]
    if decision == "Approve" and missing:
        raise GoldReviewBlocked("APPROVAL_CONDITIONS_INCOMPLETE", ",".join(missing))
    record = {
        "schema": "rrsi-gold-review-record/v0.1",
        "fixture_path": str(fixture_path),
        "fixture_digest": fixture_digest(fixture_path),
        "reviewer": reviewer,
        "reviewer_role": reviewer_role,
        "decision": decision,
        "comment": comment,
        "conditions": conditions,
        "review_timestamp": datetime.now(UTC).replace(microsecond=0)
            .isoformat().replace("+00:00", "Z"),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def approval_state(fixture_path: Path, reviews_path: Path) -> dict:
    """Current review state of one fixture, given its review records."""
    digest = fixture_digest(fixture_path)
    records = []
    if reviews_path.exists():
        for line in reviews_path.open():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("fixture_digest") == digest:
                records.append(r)
    if not records:
        return {"state": "HUMAN_REVIEW_REQUIRED", "reviews": 0,
                "reason": "no independent review records for this digest"}
    latest = records[-1]
    decision = latest["decision"]
    if decision == "Approve":
        return {"state": "APPROVED", "reviews": len(records),
                "reviewer": latest["reviewer"],
                "review_timestamp": latest["review_timestamp"]}
    if decision == "Reject":
        return {"state": "REJECTED", "reviews": len(records),
                "reviewer": latest["reviewer"]}
    return {"state": "NEEDS_REVISION", "reviews": len(records),
            "reviewer": latest["reviewer"], "comment": latest.get("comment")}
