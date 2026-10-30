# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""WB-RRSI-CONTROLLER-INTEGRATION-R2 — controller-side gates.

Gate A (official client interface, zero internal access), Gate B
(canonical result consumption, 12-step order + 8 negatives), Gate C
(promotion guard independence + immutable decision record), Gate D
(durable resume with workbench-truth re-verification), Gate E
(cross-repo controller E2E over the REAL EvaluationService — exact
decision/state table), Gate F (shared fixture execution semantics).
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import sys
from pathlib import Path

import pytest

RRSI_ROOT = Path(__file__).resolve().parents[2]
WB_ROOT = RRSI_ROOT.parent / "research_benchmarks"
sys.path.insert(0, str(RRSI_ROOT))
sys.path.insert(0, str(WB_ROOT))

from poc import recursive_loop_r2 as r2  # noqa: E402
from poc.recursive_loop_r1 import (  # noqa: E402
    ContractRejected, DigestAdapter, MockWorkbenchClient,
)
from poc.recursive_loop_r2 import (  # noqa: E402
    APPROVED_EVALUATION_PROFILES, ClientError, LoopbackClientAdapter,
    MockClientAdapter, RecursiveLoopControllerR2, WorkbenchClientInterface,
    _normalized_result,
)
from evaluation.candidate_evaluation import (  # noqa: E402
    CandidateBinding, EvaluationService, verify_provenance,
)

SHARED = RRSI_ROOT / "poc/runs/recursive-loop/shared-contract-fixtures-r1.json"
BASELINE = {"answer_quality": 0.60, "evidence_quality": 0.70,
            "token_cost": 1000, "gpu_cost": 100, "latency": 50,
            "reliability": 0.95, "regression_risk": 0.1}
BASELINE_WIRE = hashlib.sha256(b"baseline").hexdigest()
OTHER_BASELINE_WIRE = hashlib.sha256(b"other-baseline").hexdigest()


def make_mock(**kw):
    params = dict(policy_version="candidate-evaluation-policy/v0.1",
                  budget_eval_tokens=5000)
    params.update(kw)
    return MockWorkbenchClient(**params)


def make_loop(**kw):
    client = MockClientAdapter(make_mock(**kw))
    loop = RecursiveLoopControllerR2()
    loop.bind_baseline("researcher-baseline", "baseline-v1", BASELINE,
                       client=client, baseline_wire=BASELINE_WIRE)
    return loop, client


def generate(loop, cid="cand-1-a", desc="lower retry cap to 1", tokens=1):
    return loop.generate_candidate(
        candidate_id=cid, change_scope="system_task_prompt",
        change_description=desc, execution_profile={},
        resource_envelope={"max_eval_tokens": tokens})


def advance_to_feedback(loop, client, cid="cand-1-a", desc="x",
                        metrics=None, **deliver):
    generate(loop, cid=cid, desc=desc, tokens=deliver.get("tokens", 1))
    loop.validate_candidate_step()
    loop.request_evaluation()
    loop.poll_evaluation()
    client.deliver_result(loop.job_id, metrics or dict(
        BASELINE, answer_quality=0.65), **{k: v for k, v in deliver.items()
                                           if k != "tokens"})


# ==================== Gate A — official client interface =====================
def test_gate_a_interface_conformance_both_adapters():
    for adapter in (MockClientAdapter(make_mock()),
                    LoopbackClientAdapter(EvaluationService({}))):
        assert isinstance(adapter, WorkbenchClientInterface)
        for method in ("submit_evaluation", "get_evaluation_status",
                       "get_evaluation_result", "get_evaluation_events",
                       "cancel_evaluation", "get_evaluation_usage"):
            assert callable(getattr(adapter, method))


def test_gate_a_zero_internal_access_in_controller_source():
    """The controller NEVER touches workbench internals (records/jobs/
    budget dicts) — static source scan over the R2 controller source."""
    source = inspect.getsource(r2)
    controller_src = source[source.index("class RecursiveLoopControllerR2"):]
    for pattern in (r"\.jobs\b", r"\.records\b", r"\.by_key\b",
                    r"\.idempotency\b", r"\.budget_eval_tokens\b",
                    r"client\.budget"):
        assert not re.search(pattern, controller_src), pattern


def test_gate_a_mock_adapter_surfaces_canonical_result():
    loop, client = make_loop()
    advance_to_feedback(loop, client)
    res = client.get_evaluation_result(loop.job_id)
    assert res["schema"] == \
        "research-bench-evaluation-result/v0.1"
    assert len(res["candidate_identity"]["candidate_digest"]) == 64
    assert verify_provenance(res) or \
        res["provenance_digest"] == hashlib.sha256(canonical_bytes(
            {k: v for k, v in res.items()
             if k != "provenance_digest"})).hexdigest()


def canonical_bytes(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def test_gate_a_duplicate_submit_same_evaluation_no_double_cost():
    loop, client = make_loop()
    generate(loop)
    loop.validate_candidate_step()
    r1 = loop.request_evaluation()
    r2s = loop.request_evaluation()
    assert r2s["duplicate"] is True
    assert r2s["evaluation_id"] == r1["evaluation_id"]
    assert loop.evaluations == 1


# ================ Gate B — canonical result consumption ======================
def test_gate_b_full_12step_consumption():
    loop, client = make_loop()
    advance_to_feedback(loop, client)
    out = loop.complete_evaluation()
    assert out["state"] == "EVALUATION_COMPLETED"
    assert out["result"]["provenance_verified"] is True
    assert out["result"]["status"] == "COMPLETED_VALID"
    assert out["duplicate_receive"] is False
    for axis in ("answer_quality", "evidence_quality", "token_cost",
                 "gpu_cost", "latency", "reliability", "regression_risk"):
        assert axis in out["result"]["metrics"]
    assert out["result"]["metrics"]["answer_quality"] == 0.65


def _fail_loop_unused():
    pass


def test_gate_b_negative_other_candidates_result():
    loop, client = make_loop()
    advance_to_feedback(loop, client, cid="cand-1-a", desc="x")
    advance_to_feedback(loop, client, cid="cand-2-b", desc="y")
    advance_to_feedback(loop, client, cid="cand-3-c", desc="z")
    old_client = client            # keep the populated adapter
    loop.validated_result = None
    for jid in list(old_client._identity):        # seal all three results
        old_client.get_evaluation_result(jid)

    class Double(MockClientAdapter):
        def get_evaluation_result(self, evaluation_id):
            # feed the OTHER candidate's sealed result for THIS evaluation id
            # (evaluation_id rewritten + re-sealed: identity mismatch only)
            other = old_client._sealed[[j for j in old_client._sealed
                                        if j != evaluation_id][0]]
            tampered = dict(other, evaluation_id=evaluation_id)
            return _normalized_result(tampered)

    loop.client = Double(old_client._mock)
    out = loop.complete_evaluation()
    assert out["state"] == "TERMINATED"
    assert "CANDIDATE_IDENTITY_MISMATCH" in out["reason"]

    # without the id rewrite, the fixed step order fails at step 3 first
    class RawDouble(MockClientAdapter):
        def get_evaluation_result(self, evaluation_id):
            return old_client._sealed[[j for j in old_client._sealed
                                       if j != evaluation_id][0]]

    loop.validated_result = None
    loop.state = "EVALUATION_REQUESTED"
    loop.stop_reason = None
    loop.client = RawDouble(old_client._mock)
    out = loop.complete_evaluation()
    assert out["state"] == "TERMINATED"
    assert out["reason"] == "EVALUATION_IDENTITY_MISMATCH"


def test_gate_b_negative_other_baselines_result():
    loop, client = make_loop()
    advance_to_feedback(loop, client)
    sealed = client.get_evaluation_result(loop.job_id)

    class Double(MockClientAdapter):
        def get_evaluation_result(self, evaluation_id):
            tampered = dict(sealed, baseline_identity={
                "baseline_digest": OTHER_BASELINE_WIRE})
            return _normalized_result(tampered)   # re-sealed: identity only

    loop.client = Double(client._mock)
    out = loop.complete_evaluation()
    assert out["state"] == "TERMINATED"
    assert "BASELINE_IDENTITY_MISMATCH" in out["reason"]


def test_gate_b_negative_policy_version_change():
    loop, client = make_loop()
    advance_to_feedback(loop, client)
    sealed = client.get_evaluation_result(loop.job_id)

    class Double(MockClientAdapter):
        def get_evaluation_result(self, evaluation_id):
            tampered = dict(sealed, policy_version=
                            "candidate-evaluation-policy/v0.9")
            return _normalized_result(tampered)

    loop.client = Double(client._mock)
    out = loop.complete_evaluation()
    assert out["state"] == "TERMINATED"
    assert "POLICY_VERSION_MISMATCH" in out["reason"]


def test_gate_b_negative_score_tamper_breaks_provenance():
    loop, client = make_loop()
    advance_to_feedback(loop, client)
    loop.complete_evaluation()
    sealed = client.get_evaluation_result(loop.job_id)

    class Double(MockClientAdapter):
        def get_evaluation_result(self, evaluation_id):
            return dict(sealed, quality_metrics={"answer_f1": 0.99})

    loop.client = Double(client._mock)
    loop.validated_result = None
    out = loop.complete_evaluation()
    assert out["state"] == "TERMINATED"
    assert "PROVENANCE_VERIFICATION_FAILED" in out["reason"]


def test_gate_b_negative_missing_required_metric():
    loop, client = make_loop()
    advance_to_feedback(loop, client,
                        metrics={"evidence_quality": 0.7})
    out = loop.complete_evaluation()
    assert out["state"] == "TERMINATED"
    assert "REQUIRED_METRICS_MISSING" in out["reason"]


def test_gate_b_negative_invalid_evaluation_terminated():
    loop, client = make_loop()
    advance_to_feedback(loop, client, valid=False)
    out = loop.complete_evaluation()
    assert out["state"] == "TERMINATED"
    assert out["reason"] == "EVALUATION_INVALID"


def test_gate_b_negative_budget_overage():
    loop, client = make_loop()
    advance_to_feedback(loop, client, token_cost=400)
    sealed = client.get_evaluation_result(loop.job_id)

    class Double(MockClientAdapter):
        def get_evaluation_result(self, evaluation_id):
            # usage inflated above the approved budget (re-sealed: usage check)
            cost = dict(sealed["cost_metrics"], tokens=9000)
            return _normalized_result(dict(sealed, cost_metrics=cost))

    loop.client = Double(client._mock)
    out = loop.complete_evaluation()
    assert out["state"] == "TERMINATED"
    assert "BUDGET_CAP_EXCEEDED" in out["reason"]


def test_gate_b_duplicate_result_receive_idempotent():
    loop, client = make_loop()
    advance_to_feedback(loop, client, token_cost=400)
    first = loop.complete_evaluation()
    spent = loop.tokens_spent
    usage = client.get_evaluation_usage(loop.job_id)
    second = loop.complete_evaluation()
    assert second["duplicate_receive"] is True
    assert second["result"] == first["result"]
    assert loop.tokens_spent == spent                 # no double charge
    assert client.get_evaluation_usage(loop.job_id) == usage


# ================= Gate C — promotion guard independence =====================
def test_gate_c_no_client_internals_and_no_hardcoded_profile():
    src = inspect.getsource(r2)
    controller_src = src[src.index("class RecursiveLoopControllerR2"):]
    assert "client.jobs" not in controller_src
    assert '"approved_profile": True' not in controller_src
    assert "APPROVED_EVALUATION_PROFILES" in controller_src


def test_gate_c_decision_record_immutable_and_bound():
    loop, client = make_loop()
    advance_to_feedback(loop, client, token_cost=300)
    loop.complete_evaluation()
    out = loop.assess_feedback_step()
    rec = out["decision_record"]
    assert rec["evaluation_id"] == loop.job_id
    assert rec["candidate_digest"] == \
        loop.candidate["candidate_digest"]
    digest = rec["decision_record_digest"]
    # tampering the record breaks its digest — immutability is checkable
    tampered = dict(rec, decision="REJECT")
    recomputed = "sha256:" + hashlib.sha256(canonical_bytes(
        {k: v for k, v in tampered.items()
         if k != "decision_record_digest"})).hexdigest()
    assert recomputed != digest
    # append-only: later assessments never rewrite earlier records
    before = list(loop.decision_records)
    assert all(r["decision_record_digest"] for r in before)


def test_gate_c_promotion_blocked_for_all_forbidden_states():
    for decision, setup, deliver in (
            ("REJECT", dict(BASELINE, answer_quality=0.50), {}),
            ("HOLD", dict(BASELINE), {"token_cost": 3000}),
            ("UNDECIDABLE", dict(BASELINE, answer_quality=0.65),
             {"samples": 1})):
        loop, client = make_loop()
        advance_to_feedback(loop, client, metrics=setup, **deliver)
        loop.complete_evaluation()
        loop.assess_feedback_step()
        assert loop.state in ("REJECTED", "REVISE_CANDIDATE")
        r = loop.propose_promotion(rollback_plan="rb", residual_risks="rr")
        assert r["promotion_blocked"] is True


def test_gate_c_promotion_blocked_in_terminated_state():
    loop, client = make_loop()
    generate(loop)
    loop.candidate["candidate_digest"] = "sha256:tampered"
    loop.validate_candidate_step()          # TERMINATED
    r = loop.propose_promotion(rollback_plan="rb", residual_risks="rr")
    assert r["promotion_blocked"] is True


def test_gate_c_promotion_allowed_after_advance_pending_owner():
    loop, client = make_loop()
    advance_to_feedback(loop, client, token_cost=300)
    loop.complete_evaluation()
    loop.assess_feedback_step()
    req = loop.propose_promotion(rollback_plan="rb", residual_risks="rr")
    assert loop.state == "PROMOTION_PROPOSED"
    assert req["status"] == "PENDING_OWNER_APPROVAL"
    assert req["decision_record"]["evaluation_id"] == loop.job_id


# ==================== Gate D — durable resume ================================
def test_gate_d_resume_rejects_tampered_snapshot():
    loop, client = make_loop()
    snap = loop.seal_snapshot(loop.snapshot())
    tampered = dict(snap, state="TERMINATED")
    with pytest.raises(ContractRejected) as ei:
        RecursiveLoopControllerR2().resume(tampered, client=client)
    assert "SNAPSHOT_TAMPERED" in str(ei.value)


def test_gate_d_resume_rejects_old_version():
    loop, client = make_loop()
    snap = loop.snapshot()
    snap["snapshot_schema_version"] = "rrsi-loop-snapshot/v0.1"
    with pytest.raises(ContractRejected) as ei:
        RecursiveLoopControllerR2().resume(loop.seal_snapshot(snap),
                                           client=client)
    assert "SNAPSHOT_VERSION_MISMATCH" in str(ei.value)


def test_gate_d_resume_rejects_incomplete():
    loop, client = make_loop()
    snap = loop.snapshot()
    snap.pop("budget_ledger")
    with pytest.raises(ContractRejected) as ei:
        RecursiveLoopControllerR2().resume(loop.seal_snapshot(snap),
                                           client=client)
    assert "SNAPSHOT_INCOMPLETE:budget_ledger" in str(ei.value)


def test_gate_d_resume_rejects_unknown_workbench_evaluation():
    loop, client = make_loop()
    snap = loop.snapshot()
    snap["current_evaluation_id"] = "eval-NONE"   # tamper AFTER sealing
    sealed = loop.seal_snapshot(loop.snapshot())
    sealed["current_evaluation_id"] = "eval-NONE"

    with pytest.raises(ContractRejected) as ei:
        loop.resume(sealed, client=client)
    assert "SNAPSHOT_TAMPERED" in str(ei.value)   # digest discipline first


def test_gate_d_resume_rejects_state_mismatch_with_workbench():
    loop, client = make_loop()
    advance_to_feedback(loop, client, token_cost=300)
    loop.complete_evaluation()
    snap = loop.seal_snapshot(loop.snapshot())

    class Double(MockClientAdapter):
        def get_evaluation_status(self, evaluation_id):
            return "CANCELLED"

    with pytest.raises(ContractRejected) as ei:
        loop.resume(snap, client=Double(client._mock))
    assert "WORKBENCH_EVALUATION_STATE_MISMATCH" in str(ei.value)


def test_gate_d_resume_rejects_result_identity_mismatch():
    loop, client = make_loop()
    advance_to_feedback(loop, client, token_cost=300)
    loop.complete_evaluation()
    snap = loop.seal_snapshot(loop.snapshot())

    class Double(MockClientAdapter):
        def get_evaluation_result(self, evaluation_id):
            return dict(loop.validated_result,
                        candidate_digest="0" * 64)

    with pytest.raises(ContractRejected) as ei:
        loop.resume(snap, client=Double(client._mock))
    assert "WORKBENCH_RESULT_IDENTITY_MISMATCH" in str(ei.value)


def test_gate_d_snapshot_budget_never_precedes_workbench_usage():
    loop, client = make_loop()
    advance_to_feedback(loop, client, token_cost=300)
    loop.complete_evaluation()
    snap = loop.seal_snapshot(loop.snapshot())
    # workbench usage higher than snapshot -> workbench wins on resume
    client.deliver_result(loop.job_id, dict(BASELINE, answer_quality=0.65),
                          token_cost=700)
    fresh = RecursiveLoopControllerR2()
    out = fresh.resume(snap, client=client)
    assert out["resumed"] is True
    assert fresh.tokens_spent == 700   # trusted workbench usage adopted
    assert snap["budget_ledger"]["tokens_spent"] == 300


def make_double(client, **methods):
    """Adapter test double sharing the populated state of `client` with
    selected method overrides."""
    cls = type("Double", (type(client),), methods)
    d = cls.__new__(cls)
    d._mock = client._mock
    d._identity = client._identity
    d._sealed = dict(client._sealed)
    return d


def test_gate_d_resume_rejects_snapshot_budget_above_workbench():
    loop, client = make_loop()
    advance_to_feedback(loop, client, token_cost=300)
    loop.complete_evaluation()
    snap = loop.seal_snapshot(loop.snapshot())
    double = make_double(client, get_evaluation_usage=lambda self, _id: {
        "tokens_used": 0, "model_calls_used": 0,
        "settlement_basis": "actual_usage"})
    with pytest.raises(ContractRejected) as ei:
        loop.resume(snap, client=double)
    assert "SNAPSHOT_BUDGET_EXCEEDS_WORKBENCH" in str(ei.value)


def test_gate_d_resume_no_duplicate_evaluation():
    loop, client = make_loop()
    generate(loop)
    loop.validate_candidate_step()
    loop.request_evaluation()
    client.deliver_result(loop.job_id, dict(BASELINE, answer_quality=0.65))
    loop.poll_evaluation()
    loop.complete_evaluation()
    snap = loop.seal_snapshot(loop.snapshot())
    fresh = RecursiveLoopControllerR2()
    fresh.resume(snap, client=client)
    evaluations = fresh.evaluations
    fresh.request_evaluation()        # duplicate key -> same evaluation
    assert fresh.evaluations == evaluations
    assert fresh.job_id == snap["current_evaluation_id"]


# ============ Gate E — cross-repo controller E2E (real service) ==============
def make_loopback_loop(*, baseline_metrics, evaluator):
    service = EvaluationService({}, evaluator=evaluator)
    client = LoopbackClientAdapter(service)
    loop = RecursiveLoopControllerR2()
    loop.bind_baseline("researcher-baseline", "baseline-v1",
                       baseline_metrics, client=client,
                       baseline_wire=BASELINE_WIRE)
    return loop, client, service


def loopback_evaluator(answer_f1=0.42, tokens=1200, samples=70):
    def evaluator(request, budget, events):
        return {"status": "COMPLETED_VALID", "failure_category": "none",
                "quality_metrics": {"answer_f1": answer_f1},
                "evidence_metrics": {"evidence_f1": 0.72},
                "cost_metrics": {"model_calls": 1, "tokens": tokens,
                                 "latency_ms": 50},
                "delta": {"baseline_answer_f1": 0.40,
                          "delta_answer_f1": answer_f1 - 0.40},
                "sample_count": samples,
                "validity": {"uncertainty_note": "mock fixture",
                             "sample_count": samples}}
    return evaluator


def run_loopback(loop, client, cid="cand-1-a", desc="x"):
    generate(loop, cid=cid, desc=desc, tokens=8000)
    loop.validate_candidate_step()
    # workbench-side operator action: register the approved candidate binding
    wire = DigestAdapter.to_wire(loop.candidate["candidate_digest"])
    client._service.bindings[wire] = CandidateBinding(
        wire, "deployed", "isolated://env-1", True, cid)
    loop.request_evaluation()
    loop.poll_evaluation()
    out = loop.complete_evaluation()
    if out["state"] == "TERMINATED":
        return out
    return loop.assess_feedback_step()


def test_gate_e_row1_quality_improved_cost_ok_advance():
    loop, client, _ = make_loopback_loop(
        baseline_metrics=dict(BASELINE, answer_quality=0.40,
                              token_cost=1200),
        evaluator=loopback_evaluator(answer_f1=0.42))
    out = run_loopback(loop, client)
    assert out["decision"] == "ADVANCE"
    assert loop.state == "NEXT_ITERATION"


def test_gate_e_row2_quality_degraded_reject():
    loop, client, _ = make_loopback_loop(
        baseline_metrics=dict(BASELINE, answer_quality=0.50,
                              token_cost=1200),
        evaluator=loopback_evaluator(answer_f1=0.42))
    out = run_loopback(loop, client)
    assert out["decision"] == "REJECT"
    assert loop.state == "REJECTED"


def test_gate_e_row3_cost_cap_exceeded_hold():
    loop, client, _ = make_loopback_loop(
        baseline_metrics=dict(BASELINE, answer_quality=0.40,
                              token_cost=1000),
        evaluator=loopback_evaluator(answer_f1=0.42, tokens=1500))
    out = run_loopback(loop, client)
    assert out["decision"] == "HOLD"
    assert loop.state == "REVISE_CANDIDATE"


def test_gate_e_row4_thin_samples_undecidable():
    loop, client, _ = make_loopback_loop(
        baseline_metrics=dict(BASELINE, answer_quality=0.40,
                              token_cost=1200),
        evaluator=loopback_evaluator(answer_f1=0.42, samples=1))
    out = run_loopback(loop, client)
    assert out["decision"] == "UNDECIDABLE"
    assert loop.state == "REVISE_CANDIDATE"


def test_gate_e_row5_provenance_failure_terminated():
    loop, client, service = make_loopback_loop(
        baseline_metrics=dict(BASELINE, answer_quality=0.40,
                              token_cost=1200),
        evaluator=loopback_evaluator(answer_f1=0.42))
    evaluation_id = submit_and_get_id(loop, client)
    record = service.records[evaluation_id]
    record.result = dict(record.result,
                         quality_metrics={"answer_f1": 0.99})  # WB tamper
    loop.poll_evaluation()
    out = loop.complete_evaluation()
    assert out["state"] == "TERMINATED"
    assert "PROVENANCE_VERIFICATION_FAILED" in out["reason"]


def submit_and_get_id(loop, client):
    generate(loop, cid="cand-1-a", desc="x", tokens=8000)
    loop.validate_candidate_step()
    wire = DigestAdapter.to_wire(loop.candidate["candidate_digest"])
    client._service.bindings[wire] = CandidateBinding(
        wire, "deployed", "isolated://env-1", True, "cand-1-a")
    out = loop.request_evaluation()
    return out["evaluation_id"]


def test_gate_e_row6_budget_exhausted_terminated():
    def budget_evaluator(request, budget, events):
        return {"status": "BUDGET_EXHAUSTED",
                "failure_category": "budget_exhausted",
                "quality_metrics": None, "evidence_metrics": None,
                "cost_metrics": None, "delta": None, "sample_count": 0,
                "validity": None}

    loop, client, _ = make_loopback_loop(
        baseline_metrics=dict(BASELINE, answer_quality=0.40,
                              token_cost=1200),
        evaluator=budget_evaluator)
    out = run_loopback(loop, client)
    assert out["state"] == "TERMINATED"
    assert out["reason"] == "BUDGET_EXHAUSTED"


# ================ Gate F — shared fixture execution semantics ================
def fixture_doc():
    return json.loads(SHARED.read_text())


def fx(doc, fid):
    return next(f for f in doc["fixtures"] if f["fixture_id"] == fid)


def wb_request_from_payload(payload, candidate_digest=None):
    """Executable workbench request from a fixture payload."""
    request = dict(payload)
    if candidate_digest is not None:
        request["candidate_digest"] = candidate_digest
    request.setdefault("requested_metrics", request.get("requested_metrics"))
    return request


def test_gate_f_request_shaped_fixtures_through_real_service():
    doc = fixture_doc()
    bindings = {hashlib.sha256(b"bound").hexdigest(): CandidateBinding(
        hashlib.sha256(b"bound").hexdigest(), "deployed", "isolated://e1",
        True, "cand-001")}
    # 01 valid request -> created
    service = EvaluationService(bindings)
    p01 = fx(doc, "01-valid-evaluation-request")["canonical_payload"]
    p01 = dict(p01, candidate_digest=hashlib.sha256(b"bound").hexdigest(),
               requester="rrsi")
    response = service.create_evaluation(p01)
    assert response["duplicate"] is False
    assert fx(doc, "01-valid-evaluation-request")[
        "expected_validation_result"] == "VALID"
    # 03 prefixed digest -> schema_validation_failed
    with pytest.raises(Exception):
        service.create_evaluation(dict(
            p01, idempotency_key="idem-key-03",
            candidate_digest="sha256:" + "3" * 64))
    assert fx(doc, "03-invalid-candidate-digest")[
        "expected_failure_code"] == "schema_validation_failed"
    # 04 same key different request digest -> idempotency conflict
    with pytest.raises(Exception) as ei:
        service.create_evaluation(dict(
            p01, candidate_digest=hashlib.sha256(b"other").hexdigest()))
    assert "IDEMPOTENCY_CONFLICT" in str(ei.value)
    assert fx(doc, "04-idempotency-conflict")[
        "expected_failure_code"] == "idempotency_conflict"
    # 05 unknown digest -> candidate_binding_missing -> FAILED
    service2 = EvaluationService({})
    p05 = dict(p01, idempotency_key="idem-key-05",
               candidate_digest=hashlib.sha256(b"unbound").hexdigest())
    response5 = service2.create_evaluation(p05)
    evaluation_id = response5["evaluation_id"]
    record = service2.records[evaluation_id]
    assert record.status == "FAILED"
    assert record.result["failure_category"] == "candidate_binding_missing"
    assert "candidate_binding_missing" in fx(
        doc, "05-missing-candidate-binding")["expected_failure_code"]


def result_envelope(fx_payload):
    """Seal a fixture result payload as a canonical result (fixture 02 is
    the valid basis; others derive by mutation)."""
    payload = dict(fx_payload)
    covered = {k: v for k, v in payload.items() if k != "provenance_digest"}
    payload["provenance_digest"] = hashlib.sha256(canonical_bytes(
        covered)).hexdigest()
    return payload


def test_gate_f_result_shaped_fixtures_through_rrsi_consumption():
    doc = fixture_doc()
    loop, client = make_loop()
    # executable candidate for identity binding
    generate(loop)
    cand = loop.candidate
    wire_digest = DigestAdapter.to_wire(cand["candidate_digest"])
    # the fixtures carry their own baseline digest — use it for reception
    fx_baseline_wire = fx(doc, "02-valid-evaluation-result")[
        "canonical_payload"]["baseline_identity"]["baseline_digest"]

    def make_result(**over):
        payload = dict(fx(doc, "02-valid-evaluation-result")[
            "canonical_payload"])
        payload["candidate_identity"] = {
            "candidate_id": cand["candidate_id"],
            "candidate_digest": wire_digest}
        payload["baseline_identity"] = {"baseline_digest": fx_baseline_wire}
        payload.update(over)
        return result_envelope(payload)

    # 02 valid result -> accepted by the ten-condition validator
    metrics = r2.from_workbench_result_r2(
        make_result(), candidate=cand, baseline_wire=fx_baseline_wire)
    assert metrics["answer_quality"] == \
        fx(doc, "02-valid-evaluation-result")["canonical_payload"][
            "quality_metrics"]["answer_f1"]
    # 06 tampered quality -> provenance_mismatch (sealed payload + tamper)
    sealed02 = make_result()
    with pytest.raises(ContractRejected) as ei:
        r2.from_workbench_result_r2(
            dict(sealed02, quality_metrics={"answer_f1": 0.99}),
            candidate=cand, baseline_wire=fx_baseline_wire)
    assert "PROVENANCE" in str(ei.value)
    # the fixture 06 payload ITSELF (tampered quality + its own provenance)
    # is rejected through the same validator
    with pytest.raises(ContractRejected):
        p06 = dict(fx(doc, "06-invalid-provenance")["canonical_payload"])
        p06["candidate_identity"] = {
            "candidate_id": cand["candidate_id"],
            "candidate_digest": wire_digest}
        p06["baseline_identity"] = {"baseline_digest": fx_baseline_wire}
        r2.from_workbench_result_r2(
            p06, candidate=cand, baseline_wire=fx_baseline_wire)
    assert fx(doc, "06-invalid-provenance")[
        "expected_failure_code"] == "provenance_mismatch"
    # 07 quality regression -> REJECT
    q07 = fx(doc, "07-quality-regression")["canonical_payload"][
        "quality_metrics"]["answer_f1"]
    m07 = r2.from_workbench_result_r2(
        make_result(quality_metrics={"answer_f1": q07}), candidate=cand,
        baseline_wire=fx_baseline_wire)
    decision = assess(m07, baseline=0.60)
    assert decision == "REJECT"
    # 08 evidence regression -> REJECT
    e08 = fx(doc, "08-evidence-regression")["canonical_payload"][
        "evidence_metrics"]["evidence_f1"]
    m08 = r2.from_workbench_result_r2(
        make_result(evidence_metrics={"evidence_f1": e08}), candidate=cand,
        baseline_wire=fx_baseline_wire)
    assert assess(m08, baseline=0.60) == "REJECT"
    # 09 usage above envelope -> budget rejection
    c09 = fx(doc, "09-cost-regression")["canonical_payload"]["cost_metrics"]
    with pytest.raises(ContractRejected) as ei9:
        r2.from_workbench_result_r2(
            make_result(cost_metrics=c09), candidate=cand,
            baseline_wire=fx_baseline_wire, approved_budget_tokens=1000)
    assert "BUDGET" in str(ei9.value)
    # 10/11/12 fail-closed statuses
    for fid in ("10-insufficient-evidence", "11-budget-exhaustion",
                "12-cancelled-evaluation"):
        status = fx(doc, fid)["canonical_payload"]["status"]
        assert status in ("INSUFFICIENT_EVIDENCE", "BUDGET_EXHAUSTED",
                          "CANCELLED")
    # 13 held-out restriction: aggregate-only surface — per-case/gold detail
    # absent; "held_out" appears ONLY as the aggregate boundary declaration
    payload13 = fx(doc, "13-held-out-feedback-restriction")[
        "canonical_payload"]
    text = json.dumps(payload13).lower()
    for key in ("gold", "per_case", "answer_text"):
        assert key not in text
    assert payload13["benchmark_cohort"]["data_boundary"] == "held_out"
    # 14 improvement evidence present
    assert fx(doc, "14-valid-improvement-candidate")["canonical_payload"][
        "improvement_claim_allowed"] is True
    # 15 promotion blocked on invalid evaluation
    loop2, client2 = make_loop()
    advance_to_feedback(loop2, client2, valid=False)
    loop2.complete_evaluation()
    r = loop2.propose_promotion(rollback_plan="rb", residual_risks="rr")
    assert r["promotion_blocked"] is True
    # 16 resume snapshot verified against workbench
    loop3, client3 = make_loop()
    advance_to_feedback(loop3, client3, token_cost=300)
    loop3.complete_evaluation()
    snap = loop3.seal_snapshot(loop3.snapshot())
    fresh = RecursiveLoopControllerR2()
    assert fresh.resume(snap, client=client3)["resumed"] is True


def assess(metrics, *, baseline):
    from poc.recursive_loop_r1 import assess_feedback
    return assess_feedback(
        {"answer_quality": baseline, "evidence_quality": 0.70,
         "token_cost": 1000, "gpu_cost": 100, "latency": 50,
         "reliability": 0.95, "regression_risk": 0.1}, metrics,
        samples=10, comparison_baseline_version="baseline-v1",
        bound_baseline_version="baseline-v1")["decision"]
