# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""R6I launch: prepare (zero calls) by default; execute ONLY with approval.

  python poc/run_r6i.py              # preparation + verification report
  python poc/run_r6i.py --execute --owner-approval <record.json>

§C approval boundary (owner-issued permit): the OWNER issues the permit
with poc/owner_issue_permit.py (which registers it in the frozen issuance
ledger) and exports the budget environment. The RUNNER never issues or
registers a permit — it only reads the owner-issued permit from the
environment, verifies it (7 conditions), verifies the owner approval
record (presence AND authority), and executes.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RRSI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RRSI_ROOT))
sys.path.insert(0, "/home/ktl/projects/ai_papers/src")

from poc.semantic_pilot_r6i import (  # noqa: E402
    INVOCATION_ID, prepare, execute,
)


if __name__ == "__main__":
    if "--execute" in sys.argv:
        argv = sys.argv[1:]
        assert "--owner-approval" in argv, \
            "execution requires an owner-issued approval record; the runner " \
            "cannot self-approve"
        assert "--owner-permit" in argv, \
            "execution requires an owner-ISSUED permit path (see " \
            "poc/owner_issue_permit.py); the runner does not issue permits"
        approval = argv[argv.index("--owner-approval") + 1]
        permit_path = argv[argv.index("--owner-permit") + 1]
        os.environ["AI_PAPERS_EXECUTION_PERMIT"] = permit_path
        os.environ["AI_PAPERS_INVOCATION_ID"] = INVOCATION_ID
        print(json.dumps(execute(approval_record_path=approval),
                         indent=1, ensure_ascii=False))
    else:
        print(json.dumps(prepare(), indent=1, ensure_ascii=False))
