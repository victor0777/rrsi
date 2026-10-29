# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""R6 Recovery issuance + launch (directive §C/§D).

Issuance uses ONLY the frozen machinery:
  - budget environment  : ai_papers_research.llm.call_budget.
                          model_call_budget_environment (fresh workflow root;
                          the reservations ledger itself is created by the
                          official reservation API, never hand-written);
  - execution permit    : poc.execution_permit.register_permit (issuer-side,
                          append-only issuance ledger).

The r6f recovery directive is the owner's execution approval; the permit
binds exactly the §C limits. Run:  python poc/run_r6f_recovery.py
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

from poc.semantic_pilot_r6_recovery import (  # noqa: E402
    ENDPOINT, MODEL, WORK_ROOT, INVOCATION_ID, main,
)
from ai_papers_research.llm.call_budget import (  # noqa: E402
    model_call_budget_environment,
)
from poc.execution_permit import register_permit  # noqa: E402

PERMIT_PATH = WORK_ROOT / "permit-semjudge-r6g-recovery.json"
BUDGET_ROOT = WORK_ROOT / "budget"
CEILING = 6  # each directed model call books 2 ordinals
# (runner reservation + the frozen call path's own reservation); 3 calls max


def issue() -> dict:
    from poc.qasper_fulltext_calibration import DATASET
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    BUDGET_ROOT.mkdir(parents=True, exist_ok=True)

    permit = {
        "schema": "rrsi-execution-permit/v0.1",
        "invocation_id": INVOCATION_ID,
        "workstream": "semantic_judge_pilot",
        "call_type": "judge_evaluation",
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "paper_ids": ["1802.07862", "1901.10133"],
        "model_factors": {"model": MODEL, "endpoint": ENDPOINT},
        "budget": {"max_calls": CEILING, "max_total_tokens": 6000,
                   "max_wall_seconds": 300},
        "ledger_reservation": {"ledger_path":
                               str(BUDGET_ROOT.resolve()
                                   / "model-call-budget-reservations.jsonl")},
    }
    PERMIT_PATH.write_text(json.dumps(permit, indent=1))
    issuance = register_permit(PERMIT_PATH, issued_by="owner-directive "
                               "(r6f recovery, commit 1197d4d halt accepted)")
    env = model_call_budget_environment(BUDGET_ROOT,
                                        invocation_id=INVOCATION_ID,
                                        ceiling=CEILING)
    return {"permit": str(PERMIT_PATH), "issuance": issuance,
            "budget_env": env}


if __name__ == "__main__":
    issued = issue()
    os.environ.update(issued["budget_env"])
    os.environ["AI_PAPERS_EXECUTION_PERMIT"] = str(PERMIT_PATH)
    os.environ["AI_PAPERS_INVOCATION_ID"] = INVOCATION_ID
    print(json.dumps({"issued": issued, "run": main()}, indent=1,
                     ensure_ascii=False))
