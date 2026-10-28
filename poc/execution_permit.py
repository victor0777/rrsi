# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Execution Permit contract (fail-closed pre-call execution authorization).

Incident post-condition (report 22 §E): 10 unauthorized QA calls were executed
because an identity PASS let the runner fall through into an unapproved
workstream, and a budget environment alone was treated as sufficient. This
contract makes execution authorization explicit and independent of environment:

A permit is a bound JSON document authorizing ONE invocation with ONE
workstream, call type, dataset, paper set, model profile, endpoint, and
budget. Before the first model call the executor must verify:

    1. PERMIT_REQUIRED        an execution permit exists
    2. PERMIT_WORKSTREAM      the executed workstream is the permitted one
    3. PERMIT_CALL_TYPE       the model call type is permitted (e.g. reader vs qa)
    4. PERMIT_DATASET_PAPERS  dataset and every case paper are permitted
    5. PERMIT_MODEL_ENDPOINT  model profile and endpoint match
    6. PERMIT_BUDGET          call and wall-clock budgets are stated
    7. PERMIT_LEDGER          ledger path is stated and reservation-capable

A bound ledger/telemetry environment does NOT authorize anything: if the
permit is absent, or any executed scope element disagrees with the permit,
the run fails closed before a single call.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

PERMIT_ENV = "AI_PAPERS_EXECUTION_PERMIT"
PERMIT_SCHEMA = "rrsi-execution-permit/v0.1"

KNOWN_WORKSTREAMS = ("reader_note_generation", "reader_context_qa",
                     "fulltext_qa", "abstract_qa", "diagnostic_analysis")
KNOWN_CALL_TYPES = ("reader_chain", "qa_inference")


class ExecutionPermitBlocked(Exception):
    """Fail-closed execution refusal (never reaches a model call)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"BLOCKED:{code}" + (f" ({detail})" if detail else ""))
        self.code = code
        self.detail = detail


def load_permit(env_value: Optional[str] = None) -> dict:
    value = env_value if env_value is not None else os.environ.get(PERMIT_ENV)
    if not value:
        raise ExecutionPermitBlocked("PERMIT_REQUIRED",
                                     f"{PERMIT_ENV} absent")
    path = Path(value)
    if not path.exists():
        raise ExecutionPermitBlocked("PERMIT_FILE_MISSING", value)
    permit = json.loads(path.read_text(encoding="utf-8"))
    if str(permit.get("schema") or "") != PERMIT_SCHEMA:
        raise ExecutionPermitBlocked("PERMIT_SCHEMA_UNKNOWN", str(permit.get("schema")))
    return permit


def verify_permit(
    permit: dict,
    *,
    workstream: str,
    call_type: str,
    dataset_sha256: str,
    paper_ids,
    model: str,
    endpoint: str,
    invocation_id: str,
) -> dict:
    """Verify all 7 conditions; raise before any model call on mismatch."""
    checks = []

    def ok(check: str) -> None:
        checks.append(check)

    if workstream not in KNOWN_WORKSTREAMS:
        raise ExecutionPermitBlocked("PERMIT_WORKSTREAM_UNKNOWN", workstream)
    if str(permit.get("workstream") or "") != workstream:
        raise ExecutionPermitBlocked("PERMIT_WORKSTREAM_MISMATCH",
                                     f"permit={permit.get('workstream')} actual={workstream}")
    ok("PERMIT_WORKSTREAM")

    if call_type not in KNOWN_CALL_TYPES:
        raise ExecutionPermitBlocked("PERMIT_CALL_TYPE_UNKNOWN", call_type)
    if str(permit.get("call_type") or "") != call_type:
        raise ExecutionPermitBlocked("PERMIT_CALL_TYPE_MISMATCH",
                                     f"permit={permit.get('call_type')} actual={call_type}")
    ok("PERMIT_CALL_TYPE")

    if str(permit.get("dataset_sha256") or "") != dataset_sha256:
        raise ExecutionPermitBlocked("PERMIT_DATASET_MISMATCH",
                                     f"permit={str(permit.get('dataset_sha256'))[:16]}"
                                     f" actual={dataset_sha256[:16]}")
    permitted_papers = set(permit.get("paper_ids") or [])
    if not permitted_papers or set(paper_ids) - permitted_papers:
        raise ExecutionPermitBlocked("PERMIT_PAPERS_MISMATCH",
                                     f"unpermitted={sorted(set(paper_ids) - permitted_papers)}")
    ok("PERMIT_DATASET_PAPERS")

    factors = permit.get("model_factors") or {}
    if str(factors.get("model") or "") != model:
        raise ExecutionPermitBlocked("PERMIT_MODEL_MISMATCH",
                                     f"permit={factors.get('model')} actual={model}")
    if str(factors.get("endpoint") or "") != endpoint:
        raise ExecutionPermitBlocked("PERMIT_ENDPOINT_MISMATCH",
                                     f"permit={factors.get('endpoint')} actual={endpoint}")
    ok("PERMIT_MODEL_ENDPOINT")

    budget = permit.get("budget") or {}
    calls = budget.get("max_calls")
    wall = budget.get("max_wall_seconds")
    if not isinstance(calls, int) or isinstance(calls, bool) or calls < 1:
        raise ExecutionPermitBlocked("PERMIT_CALL_BUDGET_ABSENT", str(calls))
    if not isinstance(wall, (int, float)) or wall <= 0:
        raise ExecutionPermitBlocked("PERMIT_WALL_BUDGET_ABSENT", str(wall))
    if calls > int(os.environ.get("AI_PAPERS_MODEL_CALL_CEILING", calls)):
        raise ExecutionPermitBlocked("PERMIT_BUDGET_EXCEEDED",
                                     f"permit={calls} ceiling={os.environ.get('AI_PAPERS_MODEL_CALL_CEILING')}")
    ok("PERMIT_BUDGET")

    reservation = permit.get("ledger_reservation")
    ledger = reservation.get("ledger_path") if isinstance(reservation, dict) else None
    env_ledger = os.environ.get("AI_PAPERS_MODEL_CALL_BUDGET_LEDGER") or ""
    if not ledger or not env_ledger or \
            Path(ledger).resolve() != Path(env_ledger).resolve():
        raise ExecutionPermitBlocked("PERMIT_LEDGER_MISMATCH", f"permit={ledger}")
    ok("PERMIT_LEDGER")

    if str(permit.get("invocation_id") or "") != invocation_id:
        raise ExecutionPermitBlocked("PERMIT_INVOCATION_MISMATCH",
                                     f"permit={permit.get('invocation_id')} actual={invocation_id}")

    return {"schema": "rrsi-execution-permit-verified/v0.1",
            "invocation_id": invocation_id, "checks": checks}


def assert_authorized(**kwargs) -> dict:
    """Load the permit from the environment and verify it in one step."""
    permit = load_permit()
    return verify_permit(permit, **kwargs)
