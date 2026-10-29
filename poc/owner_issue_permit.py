# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""OWNER-SIDE permit issuance (issuer script — run by the OWNER only).

Runners NEVER call this module. Permit issuance REQUIRES a valid owner
approval record (existing file, invocation/scope match, registered
authority) — the runner-side verifier in semantic_pilot_r6i is reused so
issuance and execution check the same record. `issue_test_only` is the
ONLY record-free path and exists exclusively for offline tests; the CLI
never reaches it.

  python poc/owner_issue_permit.py --owner-approval <record.json>
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

RRSI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RRSI_ROOT))
sys.path.insert(0, "/home/ktl/projects/ai_papers/src")

from poc.semantic_pilot_r6i import (  # noqa: E402
    ENDPOINT, MODEL, WORK_ROOT, INVOCATION_ID, MAX_MODEL_CALLS,
    MAX_RESERVATION_ORDINALS, verify_owner_approval_record,
)
from ai_papers_research.llm.call_budget import (  # noqa: E402
    model_call_budget_environment,
)
from poc.execution_permit import register_permit  # noqa: E402

BUDGET_ROOT = WORK_ROOT / "budget"
PERMIT_PATH = WORK_ROOT / "permit-semjudge-r6i-g4g7.json"
PERMIT_SCOPE = {"workstream": "semantic_judge_pilot",
                "call_type": "judge_evaluation",
                "paper_ids": ["1802.07862", "1901.10133"]}


def _verify_record_binding(record_path: str, record: dict) -> str | None:
    """Permit↔record binding: invocation id, digest (embedding) and scope
    must all match."""
    if record.get("invocation_id") != INVOCATION_ID:
        return "RECORD_INVOCATION_MISMATCH"
    for key, expected in PERMIT_SCOPE.items():
        if record.get("scope", {}).get(key) != expected:
            return f"RECORD_SCOPE_MISMATCH:{key}"
    if record.get("workstream") != PERMIT_SCOPE["workstream"]:
        return "RECORD_SCOPE_MISMATCH:workstream"
    return None


def issue(*, approval_record_path: str) -> dict:
    """Strict issuance: refuse without a VALID owner approval record."""
    if not approval_record_path:
        raise PermissionError("OWNER_APPROVAL_REQUIRED")
    provenance = verify_owner_approval_record(approval_record_path)
    if provenance.get("error"):
        raise PermissionError(provenance["error"])
    record = json.loads(Path(approval_record_path).read_text())
    binding_error = _verify_record_binding(approval_record_path, record)
    if binding_error:
        raise PermissionError(binding_error)
    from poc.qasper_fulltext_calibration import DATASET
    BUDGET_ROOT.mkdir(parents=True, exist_ok=True)
    record_sha = "sha256:" + hashlib.sha256(
        Path(approval_record_path).read_bytes()).hexdigest()
    permit = {
        "schema": "rrsi-execution-permit/v0.1",
        "invocation_id": INVOCATION_ID,
        "workstream": PERMIT_SCOPE["workstream"],
        "call_type": PERMIT_SCOPE["call_type"],
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "paper_ids": PERMIT_SCOPE["paper_ids"],
        "model_factors": {"model": MODEL, "endpoint": ENDPOINT},
        # existing contract fields (verify_permit):
        "budget": {"max_calls": MAX_MODEL_CALLS,
                   "max_wall_seconds": 300,
                   # supplemental, metered separately from model calls:
                   "max_model_calls": MAX_MODEL_CALLS,
                   "max_reservation_ordinals": MAX_RESERVATION_ORDINALS,
                   "max_total_tokens": 6000},
        "owner_approval_record": {
            "path": str(approval_record_path), "sha256": record_sha,
            "approved_by": record.get("approved_by"),
        },
        "ledger_reservation": {"ledger_path":
                               str(BUDGET_ROOT.resolve()
                                   / "model-call-budget-reservations.jsonl")},
    }
    PERMIT_PATH.write_text(json.dumps(permit, indent=1))
    return {"permit": str(PERMIT_PATH),
            "issuance": register_permit(
                PERMIT_PATH,
                issued_by=("owner approval record "
                           f"({record.get('approved_by')})")),
            "budget_env": model_call_budget_environment(
                BUDGET_ROOT, invocation_id=INVOCATION_ID,
                ceiling=MAX_RESERVATION_ORDINALS)}


def issue_test_only(*, tmp_root: Path) -> dict:
    """TEST-ONLY structural issuance: no approval record. Isolated from the
    CLI; writes only under tmp_root."""
    global WORK_ROOT, BUDGET_ROOT, PERMIT_PATH
    from poc.qasper_fulltext_calibration import DATASET
    BUDGET_ROOT = tmp_root / "work" / "budget"
    PERMIT_PATH = tmp_root / "work" / "permit-test.json"
    BUDGET_ROOT.mkdir(parents=True, exist_ok=True)
    permit = {
        "schema": "rrsi-execution-permit/v0.1",
        "invocation_id": INVOCATION_ID,
        "workstream": PERMIT_SCOPE["workstream"],
        "call_type": PERMIT_SCOPE["call_type"],
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "paper_ids": PERMIT_SCOPE["paper_ids"],
        "model_factors": {"model": MODEL, "endpoint": ENDPOINT},
        "budget": {"max_calls": MAX_MODEL_CALLS, "max_wall_seconds": 300,
                   "max_model_calls": MAX_MODEL_CALLS,
                   "max_reservation_ordinals": MAX_RESERVATION_ORDINALS,
                   "max_total_tokens": 6000},
        "ledger_reservation": {"ledger_path":
                               str(BUDGET_ROOT.resolve()
                                   / "model-call-budget-reservations.jsonl")},
        "test_only": True,
    }
    PERMIT_PATH.write_text(json.dumps(permit, indent=1))
    return {"permit": str(PERMIT_PATH),
            "issuance": {"event": "test_only", "registered": False},
            "budget_env": model_call_budget_environment(
                BUDGET_ROOT, invocation_id=INVOCATION_ID,
                ceiling=MAX_RESERVATION_ORDINALS)}


if __name__ == "__main__":
    argv = sys.argv[1:]
    assert "--owner-approval" in argv, \
        "permit issuance requires an owner approval record"
    print(json.dumps(issue(
        approval_record_path=argv[argv.index("--owner-approval") + 1]),
        indent=1, ensure_ascii=False))
