# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""RRSI-RECURSIVE-LOOP-R1 deterministic closed-loop tests (§9) — mock
Workbench feedback only; zero model calls, zero benchmark runs."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RRSI_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RRSI_ROOT))

from poc.recursive_loop_r1 import (  # noqa: E402
    CHANGE_SCOPES, MockWorkbenchClient, REUSE_MATRIX,
    RecursiveLoopController, WorkbenchMockBlocked, assess_feedback,
    validate_candidate,
)

BASELINE = {"answer_quality": 0.60, "evidence_quality": 0.70,
            "token_cost": 1000, "gpu_cost": 100, "latency": 50,
            "reliability": 0.95, "regression_risk": 0.1}


def make_loop(**kw):
    client = MockWorkbenchClient(policy_version="r7-eval/v1",
                                 budget_eval_tokens=kw.pop(
                                     "budget", 5000))
    loop = RecursiveLoopController(**kw)
    loop.bind_baseline("researcher-baseline", "baseline-v1", BASELINE,
                       client=client)
    return loop, client


def generate_valid(loop, scope="system_task_prompt", cid="cand-1-a",
                   desc="lower retry cap to 1"):
    return loop.generate_candidate(
        candidate_id=cid, change_scope=scope,
        change_type="parameter_tuning", change_description=desc,
        execution_profile={"retries": 1},
        resource_envelope={"max_eval_tokens": 500})


def advance(loop, cid="cand-1-draft", desc="lower retry cap to 1"):
    generate_valid(loop, cid=cid, desc=desc)
    loop.validate_candidate_step()
    loop.request_evaluation()
    loop.poll_evaluation()
    return loop


# ------------------------------ §9 scenarios --------------------------------
def test_T01_improvement_advances_to_next_iteration():
    loop, client = make_loop()
    advance(loop)
    client.deliver_result(loop.job_id, dict(
        BASELINE, answer_quality=0.65, token_cost=1010))
    loop.complete_evaluation()
    r = loop.assess_feedback_step()
    assert r["decision"] == "ADVANCE" and r["state"] == "NEXT_ITERATION"


def test_T02_worsened_candidate_rejected():
    loop, client = make_loop()
    advance(loop)
    client.deliver_result(loop.job_id, dict(BASELINE, answer_quality=0.55))
    loop.complete_evaluation()
    r = loop.assess_feedback_step()
    assert r["decision"] == "REJECT" and loop.state == "REJECTED"


def test_T03_quality_up_cost_cap_worsening_holds():
    loop, client = make_loop()
    advance(loop)
    client.deliver_result(loop.job_id, dict(
        BASELINE, answer_quality=0.68, token_cost=1500))  # +50% > 10% cap
    loop.complete_evaluation()
    r = loop.assess_feedback_step()
    assert r["decision"] == "HOLD" and loop.state == "REVISE_CANDIDATE"


def test_T04_evidence_quality_regression_blocked():
    loop, client = make_loop()
    advance(loop)
    client.deliver_result(loop.job_id, dict(
        BASELINE, answer_quality=0.70, evidence_quality=0.60))
    loop.complete_evaluation()
    r = loop.assess_feedback_step()
    assert r["decision"] == "REJECT" and \
        r["reason"] == "EVIDENCE_QUALITY_REGRESSION"


def test_T05_invalid_evaluation_never_promotes():
    loop, client = make_loop()
    advance(loop)
    client.deliver_result(loop.job_id, dict(BASELINE, answer_quality=0.70),
                          valid=False)
    r = loop.complete_evaluation()
    assert loop.state == "TERMINATED" and r["reason"] == "EVALUATION_INVALID"


def test_T06_candidate_digest_drift_blocked():
    loop, client = make_loop()
    generate_valid(loop)
    loop.candidate["change_description"] = "tampered after signing"
    r = loop.validate_candidate_step()
    assert loop.state == "TERMINATED" and \
        r["reason"] == "CANDIDATE_DIGEST_DRIFT"


def test_T07_duplicate_evaluation_idempotent():
    loop, client = make_loop()
    generate_valid(loop)
    loop.validate_candidate_step()
    a = loop.request_evaluation()
    b = loop.request_evaluation()  # same candidate ⇒ same job
    assert a["job_id"] == b["job_id"] and b["duplicate"] is True
    assert loop.evaluations == 1  # not double-counted


def test_T08_budget_exhaustion_terminates():
    loop, client = make_loop(budget=5000)
    advance(loop)
    client.deliver_result(loop.job_id, dict(BASELINE, answer_quality=0.65),
                          token_cost=5000)  # settle the FULL budget
    with pytest.raises(WorkbenchMockBlocked) as ei:
        generate_valid(loop, cid="cand-2-a", desc="different change")
    assert "BUDGET_EXHAUSTED" in str(ei.value)  # loop refuses further work


def test_T09_stagnation_terminates_loop():
    loop, client = make_loop()
    for i in range(3):
        advance(loop, cid=f"cand-{i + 1}-a", desc=f"tune retry cap {i}")
        client.deliver_result(loop.job_id, dict(
            BASELINE, answer_quality=0.61 + 0.001 * i))  # +0.001 < epsilon
        loop.complete_evaluation()
        r = loop.assess_feedback_step()
    assert loop.state == "TERMINATED" and \
        loop.stop_reason == "IMPROVEMENT_STAGNATION"


def test_T10_promotion_proposal_pending_owner_approval():
    loop, client = make_loop()
    advance(loop)
    client.deliver_result(loop.job_id, dict(
        BASELINE, answer_quality=0.66))
    loop.complete_evaluation()
    loop.assess_feedback_step()
    req = loop.propose_promotion(
        rollback_plan="rebind baseline-v1 snapshot",
        residual_risks="unseen-paper generalization unverified")
    assert loop.state == "PROMOTION_PROPOSED"
    assert req["status"] == "PENDING_OWNER_APPROVAL"  # never approved
    for field in ("baseline_identity", "candidate_identity",
                  "evaluation_evidence", "quality_delta", "cost_delta_tokens",
                  "regression_summary", "evaluation_policy_version",
                  "residual_risks", "rollback_plan"):
        assert field in req


def test_T11_held_out_detail_feedback_blocked():
    loop, client = make_loop()
    advance(loop)
    with pytest.raises(WorkbenchMockBlocked) as ei:
        client.request_held_out_detail(loop.job_id)
    assert "HELD_OUT_DETAIL_ACCESS_DENIED" in str(ei.value)
    assert client.held_out_access_attempts == [loop.job_id]


def test_T12_resume_preserves_history_and_budget():
    loop, client = make_loop()
    advance(loop)
    client.deliver_result(loop.job_id, dict(
        BASELINE, answer_quality=0.64))
    loop.complete_evaluation()
    loop.assess_feedback_step()
    snap = loop.seal_snapshot(loop.snapshot())
    # controller restart: fresh controller + fresh client restored from snap
    loop2, client2 = make_loop()
    r = loop2.resume(snap, client=client2)
    assert r["resumed"] and loop2.state == "NEXT_ITERATION"
    assert loop2.history == snap["candidate_history"]  # history preserved
    assert client2.tokens_spent == snap["budget_ledger"][
        "client_tokens"]  # budget preserved
    assert loop2.iteration == snap["iteration"]
    # accounting CONTINUES after resume — never resets
    generate_valid(loop2, cid="cand-2-a", desc="new tuning after resume")
    loop2.validate_candidate_step()
    loop2.request_evaluation()
    loop2.poll_evaluation()
    client2.deliver_result(loop2.job_id, dict(
        BASELINE, answer_quality=0.70))
    loop2.complete_evaluation()
    r2 = loop2.assess_feedback_step()
    assert loop2.evaluations == 2 and r2["decision"] == "ADVANCE"


# ------------------------------ contract tests ------------------------------
def test_candidate_contract_harness_only_scopes():
    for scope in CHANGE_SCOPES:
        assert "prompt" in scope or "policy" in scope or \
            "strategy" in scope or "selection" in scope or \
            "parameters" in scope
    # production source code scope absent
    assert all("source_code" not in s for s in CHANGE_SCOPES)


def test_validate_candidate_rejects_forbidden_scope():
    bad = {"candidate_id": "cand-x", "parent_candidate_id": "baseline",
           "target_project": "researcher", "target_version": "v1",
           "candidate_digest": "sha256:a", "change_type": "prompt_revision",
           "change_scope": "production_source_code",
           "change_description": "edit harness.py directly",
           "execution_profile": {}, "resource_envelope": {"x": 1},
           "generation_provenance": "sha256:p"}
    r = validate_candidate(bad)
    assert not r["valid"] and "FORBIDDEN_CHANGE_SCOPE" in r["problems"]


def test_assess_undecidable_on_mismatched_baseline():
    r = assess_feedback(BASELINE, dict(BASELINE, answer_quality=0.90),
                        samples=10, comparison_baseline_version="baseline-v2",
                        bound_baseline_version="baseline-v1")
    assert r["decision"] == "UNDECIDABLE"  # no promotion on mismatch


def test_reuse_matrix_present():
    assert "poc_core.py" in REUSE_MATRIX and "r7_contract.py" in \
        REUSE_MATRIX
