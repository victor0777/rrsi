# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""R6I launch: prepare (zero calls) by default; execute ONLY with approval.

  python poc/run_r6i.py              # preparation + verification report
  python poc/run_r6i.py --execute    # owner-approved execution

--execute issues the permit via the frozen machinery (model_call_budget_
environment + register_permit) for a FRESH workflow budget root, sets
AI_PAPERS_OWNER_APPROVAL=<invocation id>, and runs execute(). It must be
invoked with --approve passed by the owner:  --execute --approve
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
    MAX_RESERVATION_ORDINALS, prepare, execute,
)
from ai_papers_research.llm.call_budget import (  # noqa: E402
    model_call_budget_environment,
)
from poc.execution_permit import register_permit  # noqa: E402

BUDGET_ROOT = WORK_ROOT / "budget"
PERMIT_PATH = WORK_ROOT / "permit-semjudge-r6i-g4g7.json"


def issue() -> dict:
    from poc.qasper_fulltext_calibration import DATASET
    BUDGET_ROOT.mkdir(parents=True, exist_ok=True)
    permit = {
        "schema": "rrsi-execution-permit/v0.1",
        "invocation_id": INVOCATION_ID,
        "workstream": "semantic_judge_pilot",
        "call_type": "judge_evaluation",
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "paper_ids": ["1802.07862", "1901.10133"],
        "model_factors": {"model": MODEL, "endpoint": ENDPOINT},
        "budget": {"max_model_calls": MAX_MODEL_CALLS,
                   "max_reservation_ordinals": MAX_RESERVATION_ORDINALS,
                   "max_total_tokens": 6000, "max_wall_seconds": 300},
        "ledger_reservation": {"ledger_path":
                               str(BUDGET_ROOT.resolve()
                                   / "model-call-budget-reservations.jsonl")},
    }
    PERMIT_PATH.write_text(json.dumps(permit, indent=1))
    return {"permit": str(PERMIT_PATH),
            "issuance": register_permit(PERMIT_PATH, issued_by=
                                        "owner-directive (r6i corrected pilot)"),
            "budget_env": model_call_budget_environment(
                BUDGET_ROOT, invocation_id=INVOCATION_ID,
                ceiling=MAX_RESERVATION_ORDINALS)}


if __name__ == "__main__":
    if "--execute" in sys.argv:
        assert "--approve" in sys.argv, \
            "execution requires the owner's explicit --approve"
        issued = issue()
        os.environ.update(issued["budget_env"])
        os.environ["AI_PAPERS_EXECUTION_PERMIT"] = str(PERMIT_PATH)
        os.environ["AI_PAPERS_INVOCATION_ID"] = INVOCATION_ID
        os.environ["AI_PAPERS_OWNER_APPROVAL"] = INVOCATION_ID
        print(json.dumps(execute(), indent=1, ensure_ascii=False))
    else:
        print(json.dumps(prepare(), indent=1, ensure_ascii=False))
