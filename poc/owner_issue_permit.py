# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""OWNER-SIDE permit issuance (issuer script — run by the OWNER only).

Runners NEVER call this module. It issues the execution permit through the
frozen machinery (model_call_budget_environment + register_permit) and
binds the owner approval record into the permit. The budget contract uses
the fields execution_permit.verify_permit() has always required
(max_calls, max_wall_seconds); the call/ordinal separation is carried as
SUPPLEMENTAL fields so the existing permit security contract is untouched.

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
    MAX_RESERVATION_ORDINALS,
)
from ai_papers_research.llm.call_budget import (  # noqa: E402
    model_call_budget_environment,
)
from poc.execution_permit import register_permit  # noqa: E402

BUDGET_ROOT = WORK_ROOT / "budget"
PERMIT_PATH = WORK_ROOT / "permit-semjudge-r6i-g4g7.json"


def issue(*, approval_record=None, approval_record_path: str = "") -> dict:
    from poc.qasper_fulltext_calibration import DATASET
    BUDGET_ROOT.mkdir(parents=True, exist_ok=True)
    approved_by = None
    if approval_record is not None:
        approved_by = approval_record.get("approved_by")
    permit = {
        "schema": "rrsi-execution-permit/v0.1",
        "invocation_id": INVOCATION_ID,
        "workstream": "semantic_judge_pilot",
        "call_type": "judge_evaluation",
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "paper_ids": ["1802.07862", "1901.10133"],
        "model_factors": {"model": MODEL, "endpoint": ENDPOINT},
        # existing contract fields (verify_permit):
        "budget": {"max_calls": MAX_MODEL_CALLS,
                   "max_wall_seconds": 300,
                   # supplemental, metered separately from model calls:
                   "max_model_calls": MAX_MODEL_CALLS,
                   "max_reservation_ordinals": MAX_RESERVATION_ORDINALS,
                   "max_total_tokens": 6000},
        "ledger_reservation": {"ledger_path":
                               str(BUDGET_ROOT.resolve()
                                   / "model-call-budget-reservations.jsonl")},
    }
    if approval_record_path:
        record_sha = "sha256:" + hashlib.sha256(
            Path(approval_record_path).read_bytes()).hexdigest()
        permit["owner_approval_record"] = {
            "path": str(approval_record_path), "sha256": record_sha,
            "approved_by": approved_by,
        }
    PERMIT_PATH.write_text(json.dumps(permit, indent=1))
    return {"permit": str(PERMIT_PATH),
            "issuance": register_permit(
                PERMIT_PATH,
                issued_by=("owner approval record "
                           f"({approved_by})" if approved_by else
                           "owner (structural issuance, pre-approval)")),
            "budget_env": model_call_budget_environment(
                BUDGET_ROOT, invocation_id=INVOCATION_ID,
                ceiling=MAX_RESERVATION_ORDINALS)}


if __name__ == "__main__":
    argv = sys.argv[1:]
    approval = ""
    if "--owner-approval" in argv:
        approval = argv[argv.index("--owner-approval") + 1]
    record = json.loads(Path(approval).read_text()) if approval else None
    print(json.dumps(issue(approval_record=record,
                           approval_record_path=approval),
                     indent=1, ensure_ascii=False))
