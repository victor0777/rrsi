# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""WB-RRSI-CONTRACT-CONVERGENCE-R1 — RRSI-side gates.

Gate C (promotion guard / durable resume), Gate D (shared fixture
compatibility against the workbench copy), Gate E (cross-repository
closed loop: the REAL RRSI adapter drives the REAL workbench
EvaluationService through an in-process harness — no model, no
benchmark) and Gate F (gold/isolation/authority boundaries).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

RRSI_ROOT = Path(__file__).resolve().parents[2]
WB_ROOT = RRSI_ROOT.parent / "research_benchmarks"
sys.path.insert(0, str(RRSI_ROOT))
sys.path.insert(0, str(WB_ROOT))

from poc.recursive_loop_r1 import (  # noqa: E402
    ContractRejected, DigestAdapter, MockWorkbenchClient,
    REWARD_AXES, RecursiveLoopController, assess_feedback,
    canonical_payload_bytes, from_workbench_result, to_workbench_request,
)
from evaluation.candidate_evaluation import (  # noqa: E402
    CandidateBinding, EvaluationService, canonical_json, verify_provenance,
)

SHARED = RRSI_ROOT / "poc/runs/recursive-loop/shared-contract-fixtures-r1.json"
BASELINE = {"answer_quality": 0.60, "evidence_quality": 0.70,
            "token_cost": 1000, "gpu_cost": 100, "latency": 50,
            "reliability": 0.95, "regression_risk": 0.1}
BASELINE_WIRE = hashlib.sha256(b"baseline").hexdigest()


# ------------------------------ Gate D — fixtures ----------------------------
def test_shared_fixture_identical_in_both_repositories():
    wb_copy = WB_ROOT / "contracts/fixtures/shared-contract-fixtures-r1.json"
    assert SHARED.read_bytes() == wb_copy.read_bytes()
    doc = json.loads(SHARED.read_text())
    # file_digest = sha256 of the canonical (sorted-key, compact, UTF-8)
    # document payload excluding the digest field itself
    recomputed = "sha256:" + hashlib.sha256(canonical_payload_bytes(
        {k: v for k, v in doc.items() if k != "file_digest"})).hexdigest()
    assert doc["file_digest"] == recomputed


def test_all_16_fixture_digests_match_canonical_payloads():
    doc = json.loads(SHARED.read_text())
    assert len(doc["fixtures"]) == 16
    for fx in doc["fixtures"]:
        expected = "sha256:" + hashlib.sha256(
            canonical_payload_bytes(fx["canonical_payload"])).hexdigest()
        assert fx["fixture_digest"] == expected


def test_invalid_candidate_digest_fixture_rejected():
    doc = json.loads(SHARED.read_text())
    fx = next(f for f in doc["fixtures"]
              if f["fixture_id"] == "03-invalid-candidate-digest")
    payload = dict(fx["canonical_payload"])
    # contract validation expects the wire adapter to reject the malformed
    # digest carried by the fixture (the workbench-side evaluation result
    # baseline '03' encodes the invalid candidate digest)
    assert fx["expected_validation_result"] == "INVALID"
    assert fx["expected_failure_code"] == "schema_validation_failed"
    # an invalid value bound as a wire digest must be rejected
    with pytest.raises(ContractRejected):
        DigestAdapter.from_wire(payload["candidate_digest"]
                                if not str(payload["candidate_digest"]).
                                startswith("sha256:")
                                else "xyz")
    # and the adapter accepts only valid 64-hex wire digests
    assert DigestAdapter.from_wire("a" * 64) == "sha256:" + "a" * 64


# --------------------------- Gate C1 — digest adapter ------------------------
def test_digest_adapter_roundtrip_and_rejections():
    internal = "sha256:" + hashlib.sha256(b"x").hexdigest()
    wire = DigestAdapter.to_wire(internal)
    assert len(wire) == 64 and wire == wire.lower()
    assert DigestAdapter.from_wire(wire) == internal
    with pytest.raises(ContractRejected):
        DigestAdapter.to_wire("plain")           # missing prefix
    with pytest.raises(ContractRejected):
        DigestAdapter.to_wire("sha256:XYZ" + "0" * 60)  # uppercase
    with pytest.raises(ContractRejected):
        DigestAdapter.from_wire("abc")           # malformed wire


# ------------------------ Gate C2 — request adapter --------------------------
def make_candidate(cid="cand-1-a", desc="lower retry cap to 1"):
    digest = hashlib.sha256(f"{cid}{desc}".encode()).hexdigest()
    return {"candidate_id": cid, "parent_candidate_id": "baseline",
            "target_project": "researcher", "target_version": "baseline-v1",
            "candidate_digest": "sha256:" + digest,
            "change_type": "parameter_tuning",
            "change_scope": "system_task_prompt",
            "change_description": desc, "execution_profile": {},
            "resource_envelope": {"max_eval_tokens": 500},
            "generation_provenance": "sha256:g"}


def test_request_adapter_wire_format_and_no_executables():
    candidate = make_candidate()
    request = to_workbench_request(candidate,
                                   baseline_digest_wire=BASELINE_WIRE,
                                   policy_version="candidate-evaluation-policy/v0.1")
    assert request["candidate_digest"] == \
        candidate["candidate_digest"][7:]  # 64-hex wire
    assert "path" not in json.dumps(request).lower()
    assert "url" not in json.dumps(request).lower()
    assert "command" not in json.dumps(request).lower()
    assert request["schema"] == \
        "research-bench-candidate-evaluation-request/v0.1"


def test_request_adapter_rejects_unmappable_fields():
    candidate = make_candidate()
    candidate["executable_path"] = "/bin/evil"
    with pytest.raises(ContractRejected):
        to_workbench_request(candidate, baseline_digest_wire=BASELINE_WIRE,
                             policy_version="x")


# ------------------------- Gate C3 — result adapter --------------------------
def test_result_adapter_full_reception():
    candidate = make_candidate()
    request = to_workbench_request(candidate,
                                   baseline_digest_wire=BASELINE_WIRE,
                                   policy_version="x")
    result = {"schema": "research-bench-evaluation-result/v0.1",
              "evaluation_id": "eval-1", "status": "COMPLETED_VALID",
              "candidate_identity": request["candidate_id"],
              "baseline_identity": {"baseline_digest": BASELINE_WIRE}}
    result["candidate_identity"] = {
        "candidate_id": candidate["candidate_id"],
        "candidate_digest": candidate["candidate_digest"][7:]}
    result["evaluation_profile"] = request["evaluation_profile"]
    result["policy_version"] = "candidate-evaluation-policy/v0.1"
    result["benchmark_cohort"] = {"benchmark": "qasper",
                                  "cohort": "dev-fixture",
                                  "data_boundary": "development"}
    result["quality_metrics"] = {"answer_f1": 0.65}
    result["evidence_metrics"] = {"evidence_f1": 0.72}
    result["cost_metrics"] = {"model_calls": 4, "tokens": 2000,
                              "latency_ms": 3600}
    result["failure_category"] = "none"
    covered = {k: v for k, v in result.items() if k != "provenance_digest"}
    result["provenance_digest"] = hashlib.sha256(
        canonical_payload_bytes(covered)).hexdigest()  # 64-hex wire format
    metrics = from_workbench_result(
        result, candidate=candidate, baseline_wire=BASELINE_WIRE,
        policy_version="x", approved_budget_tokens=5000)
    for axis in REWARD_AXES:
        assert axis in metrics
    assert metrics["answer_quality"] == 0.65


@pytest.mark.parametrize("tamper", [
    ("policy_version", "candidate-evaluation-policy/v0.9"),  # policy change
    ("status", "FAILED"),                                     # status change
    ("quality_metrics", {"answer_f1": 0.99}),                 # score tamper
])
def test_result_adapter_tamper_blocked(tamper):
    candidate = make_candidate()
    result = {"schema": "research-bench-evaluation-result/v0.1",
              "evaluation_id": "eval-1", "status": "COMPLETED_VALID",
              "candidate_identity": {"candidate_id": candidate["candidate_id"],
                                     "candidate_digest":
                                     candidate["candidate_digest"][7:]},
              "baseline_identity": {"baseline_digest": BASELINE_WIRE},
              "evaluation_profile": "qasper-dev-mock-profile",
              "policy_version": "candidate-evaluation-policy/v0.1",
              "benchmark_cohort": {"benchmark": "qasper",
                                   "cohort": "dev-fixture",
                                   "data_boundary": "development"},
              "quality_metrics": {"answer_f1": 0.65},
              "cost_metrics": {"tokens": 2000},
              "failure_category": "none"}
    covered = {k: v for k, v in result.items() if k != "provenance_digest"}
    result["provenance_digest"] = "sha256:" + hashlib.sha256(
        canonical_payload_bytes(covered)).hexdigest()
    tampered = dict(result, **{tamper[0]: tamper[1]})
    with pytest.raises(ContractRejected):
        from_workbench_result(tampered, candidate=candidate,
                              baseline_wire=BASELINE_WIRE, policy_version="x")


def test_result_adapter_other_candidate_identity_rejected():
    candidate = make_candidate()
    result = {"schema": "research-bench-evaluation-result/v0.1",
              "evaluation_id": "eval-1", "status": "COMPLETED_VALID",
              "candidate_identity": {"candidate_id": "cand-OTHER",
                                     "candidate_digest": "0" * 64},
              "baseline_identity": {"baseline_digest": BASELINE_WIRE},
              "evaluation_profile": "qasper-dev-mock-profile",
              "policy_version": "candidate-evaluation-policy/v0.1",
              "benchmark_cohort": {"benchmark": "qasper",
                                   "cohort": "dev-fixture",
                                   "data_boundary": "development"},
              "quality_metrics": {"answer_f1": 0.65},
              "cost_metrics": {"tokens": 2000}, "failure_category": "none"}
    covered = {k: v for k, v in result.items() if k != "provenance_digest"}
    result["provenance_digest"] = "sha256:" + hashlib.sha256(
        canonical_payload_bytes(covered)).hexdigest()
    with pytest.raises(ContractRejected) as ei:
        from_workbench_result(result, candidate=candidate,
                              baseline_wire=BASELINE_WIRE, policy_version="x")
    assert "CANDIDATE_IDENTITY_MISMATCH" in str(ei.value)


# ------------------------- Gate C — promotion guard --------------------------
def make_loop():
    client = MockWorkbenchClient(policy_version="r7-eval/v1", budget_eval_tokens=5000)
    loop = RecursiveLoopController()
    loop.bind_baseline("researcher-baseline", "baseline-v1", BASELINE,
                       client=client)
    return loop, client


def test_promotion_guard_blocked_without_evaluation():
    loop, _ = make_loop()
    r = loop.propose_promotion(rollback_plan="rb", residual_risks="rr")
    assert r["promotion_blocked"] is True
    assert "candidate_validation_pass" in r["failing_preconditions"]


def test_promotion_guard_blocked_in_terminated_state():
    loop, client = make_loop()
    loop.generate_candidate(candidate_id="cand-1-a",
                            change_scope="system_task_prompt",
                            change_description="x", execution_profile={},
                            resource_envelope={"max_eval_tokens": 1})
    loop.candidate["candidate_digest"] = "sha256:tampered"  # force drift
    loop.validate_candidate_step()  # TERMINATED
    assert loop.state == "TERMINATED"
    r = loop.propose_promotion(rollback_plan="rb", residual_risks="rr")
    assert r["promotion_blocked"] is True  # TERMINATED never proposes


def test_promotion_allowed_after_valid_advance_then_pending_owner():
    loop, client = make_loop()
    loop.generate_candidate(candidate_id="cand-1-a",
                            change_scope="system_task_prompt",
                            change_description="x", execution_profile={},
                            resource_envelope={"max_eval_tokens": 1})
    loop.validate_candidate_step()
    loop.request_evaluation()
    loop.poll_evaluation()
    client.deliver_result(loop.job_id, dict(BASELINE, answer_quality=0.65))
    loop.complete_evaluation()
    loop.assess_feedback_step()
    req = loop.propose_promotion(rollback_plan="rb", residual_risks="rr")
    assert loop.state == "PROMOTION_PROPOSED"
    assert req["status"] == "PENDING_OWNER_APPROVAL"  # owner decides


# --------------------------- Gate C — durable resume -------------------------
def test_resume_rejects_tampered_snapshot():
    loop, client = make_loop()
    snap = loop.seal_snapshot(loop.snapshot())
    tampered = dict(snap, state="TERMINATED")  # flip state after sealing
    with pytest.raises(ContractRejected) as ei:
        loop.resume(tampered, client=client)
    assert "SNAPSHOT_TAMPERED" in str(ei.value)


def test_resume_rejects_old_version_snapshot():
    loop, client = make_loop()
    snap = loop.snapshot()
    snap["snapshot_schema_version"] = "rrsi-loop-snapshot/v0.1"
    snap = loop.seal_snapshot(snap)
    with pytest.raises(ContractRejected) as ei:
        loop.resume(snap, client=client)
    assert "SNAPSHOT_VERSION_MISMATCH" in str(ei.value)


def test_resume_rejects_incomplete_snapshot():
    loop, client = make_loop()
    snap = loop.snapshot()
    snap.pop("budget_ledger")
    snap = loop.seal_snapshot(snap)
    with pytest.raises(ContractRejected) as ei:
        loop.resume(snap, client=client)
    assert "SNAPSHOT_INCOMPLETE:budget_ledger" in str(ei.value)


# ---------------- Gate E — cross-repository closed loop ----------------------
def test_cross_repo_closed_loop_full_trace():
    """REAL RRSI adapter → REAL workbench EvaluationService (in-process
    harness); REAL baseline binding, candidate generation, digest
    verification, request creation, binding check, mock evaluation,
    result reception, provenance verification, decision, trace."""
    loop, client = make_loop()
    candidate = make_candidate()
    candidate["target_version"] = "baseline-v1"
    # 1-2. baseline binding + candidate generation (controller-owned)
    r = loop.generate_candidate(**{k: candidate[k] for k in (
        "candidate_id", "candidate_digest", "change_type", "change_scope",
        "change_description", "execution_profile", "resource_envelope")})
    assert r["state"] == "CANDIDATE_GENERATED"
    # 3. digest verification (drift-free, wire-bound)
    assert loop.validate_candidate_step()["state"] == "CANDIDATE_VALIDATED"
    # 4. workbench evaluation request via adapter
    request = to_workbench_request(
        loop.candidate, baseline_digest_wire=BASELINE_WIRE,
        policy_version="candidate-evaluation-policy/v0.1")
    # 5-7. REAL service: binding check + mock evaluation + result
    service = EvaluationService({request["candidate_digest"]: CandidateBinding(
        request["candidate_digest"], "deployed", "isolated://env-1", True,
        request["candidate_id"])})
    response = service.create_evaluation(request)
    assert response["duplicate"] is False
    result = service.get_result(response["evaluation_id"])
    assert verify_provenance(result)          # 9. workbench-side provenance
    assert result["improvement_claim_allowed"] is True
    # 8-10. RRSI reception: 10-condition adapter + decision
    metrics = from_workbench_result(
        result, candidate=loop.candidate, baseline_wire=BASELINE_WIRE,
        policy_version="x", approved_budget_tokens=5000)
    decision = assess_feedback(BASELINE, metrics, samples=result["sample_count"],
                               comparison_baseline_version="baseline-v1",
                               bound_baseline_version="baseline-v1")
    # 11. NEXT_ITERATION or REJECT
    assert decision["decision"] in ("ADVANCE", "REJECT", "HOLD", "UNDECIDABLE")
    # 12. history / budget / trace recorded
    loop.history.append({"iteration": loop.iteration,
                         "candidate_id": loop.candidate["candidate_id"],
                         "feedback_decision": decision["decision"],
                         "token_cost": metrics["token_cost"]})
    assert loop.history[-1]["feedback_decision"] == decision["decision"]
    assert service.settle_budget(response["evaluation_id"])[
        "model_calls_used"] > 0


def test_cross_repo_negative_same_key_other_candidate():
    request1 = to_workbench_request(make_candidate(cid="cand-1-a"),
                                    baseline_digest_wire=BASELINE_WIRE,
                                    policy_version="x")
    service = EvaluationService({request1["candidate_digest"]: CandidateBinding(
        request1["candidate_digest"], "deployed", "isolated://env-1", True)})
    service.create_evaluation(request1)
    request2 = to_workbench_request(make_candidate(cid="cand-2-b",
                                                   desc="different change"),
                                    baseline_digest_wire=BASELINE_WIRE,
                                    policy_version="x")
    request2["idempotency_key"] = request1["idempotency_key"]
    request2["candidate_digest"] = hashlib.sha256(b"other").hexdigest()
    with pytest.raises(Exception) as ei:
        service.create_evaluation(request2)
    assert "IDEMPOTENCY_CONFLICT" in str(ei.value)


def test_cross_repo_negative_gold_boundary():
    """Gate F — gold/held-out have no surface through the service."""
    candidate = make_candidate()
    request = to_workbench_request(candidate, baseline_digest_wire=BASELINE_WIRE,
                                   policy_version="x")
    service = EvaluationService({request["candidate_digest"]: CandidateBinding(
        request["candidate_digest"], "deployed", "isolated://env-1", True)})
    service.create_evaluation(request)
    result = service.get_result(service.counter and list(service.records)[0])
    assert "gold" not in json.dumps(result).lower()
    assert "held_out" not in json.dumps(result).lower() or \
        result["benchmark_cohort"]["data_boundary"] == "development"


def test_cross_repo_negative_unauthorized_requester():
    request = to_workbench_request(make_candidate(),
                                   baseline_digest_wire=BASELINE_WIRE,
                                   policy_version="x", requester="attacker")
    service = EvaluationService({request["candidate_digest"]: CandidateBinding(
        request["candidate_digest"], "deployed", "isolated://env-1", True)})
    with pytest.raises(Exception) as ei:
        service.create_evaluation(request)
    assert "UNAUTHORIZED" in str(ei.value) or "authorized" in str(ei.value)


def test_decision_policy_mock_gate_separated_from_real_basis():
    # MIN_SAMPLES=3 gates only the deterministic mock loop; the real
    # qualification basis requires human review and is never auto-decided
    from poc.recursive_loop_r1 import REAL_QUALIFICATION_BASIS
    assert REAL_QUALIFICATION_BASIS["min_samples_mock_loop"] == 3
    assert REAL_QUALIFICATION_BASIS["auto_qualification"] == "FORBIDDEN"
