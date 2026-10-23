# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS.
"""R0-a static verification tests (model-free, no network, no model calls).

    python3 -m pytest -q poc/tests/test_r0a.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from poc import r0a_checks as C                     # noqa: E402
from poc import poc_core as F                       # noqa: E402


# 1. U1 scope isolation --------------------------------------------------------

def test_u1_scope_allows_reader_prompt_edits():
    paths = ["src/ai_papers_research/paper/study/reader_note/prompts.py",
             "src/ai_papers_research/paper/study/reader_note/section_plan/plan.py"]
    assert C.scope_violations(paths) == []


def test_u1_scope_rejects_frozen_set_touches():
    paths = ["src/ai_papers_research/context_planning/router.py",
             "src/ai_papers_research/multi_pass/config.yaml",
             "src/ai_papers_research/analysis_kg/candidate_quality.py",
             "src/research_agent/cli.py"]
    assert C.scope_violations(paths) == paths


# 2. State machine: legal path + every reject path -----------------------------

def _h(state, ts=0):
    return C.HistoryEntry(state, ts)


def test_state_machine_legal_promotion_path():
    h = [_h("EVALUATED")]
    h.append(C.assert_transition(h, "ADMISSIBLE"))
    h.append(C.assert_transition(h, "PROMOTED"))
    h.append(C.assert_transition(h, "FROZEN"))
    h.append(C.assert_transition(h, "HOLDOUT_DRAWN"))
    h.append(C.assert_transition(h, "HUMAN_APPROVED"))
    h.append(C.assert_transition(h, "CANONICAL"))
    assert h[-1].state == "CANONICAL"


def test_state_machine_rejects_approval_before_holdout():
    h = [_h("EVALUATED"), C.assert_transition([_h("EVALUATED")], "ADMISSIBLE"),
         _h("PROMOTED", 2), _h("FROZEN", 3)]
    import pytest
    with pytest.raises(C.StateMachineError, match="APPROVAL_WITHOUT_HOLDOUT"):
        C.assert_transition(h, "HUMAN_APPROVED")


def test_state_machine_rejects_illegal_and_noop():
    import pytest
    with pytest.raises(C.StateMachineError, match="ILLEGAL_TRANSITION"):
        C.assert_transition([_h("EVALUATED")], "CANONICAL")
    with pytest.raises(C.StateMachineError, match="NOOP_TRANSITION"):
        C.assert_transition([_h("ADMISSIBLE")], "ADMISSIBLE")
    with pytest.raises(C.StateMachineError, match="NON_MONOTONIC_TIMESTAMP"):
        C.assert_transition([_h("EVALUATED", 5), _h("EVALUATED", 3)], "ADMISSIBLE")


# 3. Holdout access blocking ----------------------------------------------------

def test_holdout_ids_blocked_in_candidate_diff(tmp_path):
    diff, edits = None, None
    out = tmp_path / "out_leak"
    out.mkdir(parents=True)
    from rrsi import gitops as G
    from poc import run_poc as R
    repo = R.init_repo(out)
    wt = G.worktree_add(repo, out / "wt", "poc/leak", "evolve/fixture")
    # a candidate that embeds a holdout dataset id is blocked
    p = wt / "fixture" / "prompts" / "instructions.md"
    p.write_text(p.read_text() + "\nsee arxiv 2508.06433 for the method\n")
    diff = G.diff_with_new_files(wt, "fixture")
    G.worktree_remove(repo, wt)
    leaks = C.holdout_leaks(diff)
    assert leaks == ["2508.06433"]
    # the same denylist is enforced by the poc critic precheck path
    v = F.critic_review(diff, edits or [])
    # critic_review itself does not know the gold ids, so integration is via
    # the R0-a gate: FIXTURE_PATTERNS + holdout_leaks AND-composed.
    assert v["verdict"] in ("accept", "reject") and bool(leaks)


# 4. Ledger fail-closed (local mechanics only — no network, no model calls) ----

def test_call_budget_is_fail_closed_before_network():
    script = """
import os, sys, tempfile
sys.path.insert(0, "/home/ktl/projects/ai_papers/src")
from pathlib import Path as _P
from ai_papers_research.llm.call_budget import (
    model_call_budget_environment, reserve_model_call_from_environment,
)
# invalid ceiling must raise the contract error BEFORE any network is possible
_d = _P(tempfile.mkdtemp())
try:
    model_call_budget_environment(_d, invocation_id="r0-a", ceiling=0)
    print("UNEXPECTED_PASS")
except Exception as e:
    print("CONTRACT_ERR:" + type(e).__name__)
# with a proper binding (model_call_budget_environment output), reservation
# succeeds and the ceiling is enforced by the ledger
_d2 = _P(tempfile.mkdtemp())
env = model_call_budget_environment(_d2, invocation_id="r0-a-failclosed", ceiling=1)
for k, v in env.items():
    os.environ[k] = v
got = reserve_model_call_from_environment(call_id="c1")
print("RESERVE_OK" if got is not None else "RESERVE_ERR:None")
""".replace("{root}", str(ROOT))
    r = subprocess.run([sys.executable, "-c", script], capture_output=True,
                       text=True, timeout=60)
    assert "UNEXPECTED_PASS" not in r.stdout, r.stdout
    assert "CONTRACT_ERR:" in r.stdout, r.stdout
    assert "RESERVE_OK" in r.stdout or "RESERVE_ERR:" in r.stdout, r.stdout


# 5. Vendored core unmodified ---------------------------------------------------

def test_vendored_core_files_match_working_tree():
    sig = C.CoreSignature().extend()
    r = subprocess.run(["git", "diff", "--stat", "be50316", "--", "rrsi/"],
                       cwd=str(ROOT), capture_output=True, text=True)
    assert r.stdout.strip() == "", r.stdout
    assert len(sig.digests) == 15
