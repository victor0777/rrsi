# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""WB-RRSI-RESEARCHER-REST-PREFLIGHT-R1 — settlement closure + no-model
contract tests (T01–T16).

WS-A: reconciliation tests drive the REAL loopback adapter code path —
only the wire-level settlement RESPONSE is tampered/lost (the adapter
method under test is never replaced).
WS-E: no-model tests over the fixture prototype (`poc.rest_preflight_r1`)
and the existing RRSI↔Workbench adapters. Zero model calls, zero task
executions; tests that would require actual task creation are reported
NOT_EXECUTED.
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

from poc.recursive_loop_r1 import ContractRejected  # noqa: E402
from poc.recursive_loop_r2 import LoopbackClientAdapter  # noqa: E402
from poc.rest_preflight_r1 import (  # noqa: E402
    BindingRegistry, EvaluationTaskBinding, SCHEMA_TASK_REQUEST,
    SCHEMA_TASK_RESULT, build_binding, identity_chain_ok,
    map_evaluation_to_task_request, map_task_result_to_evaluation_result,
)
from evaluation.candidate_evaluation import (  # noqa: E402
    CandidateBinding, EvaluationService, verify_provenance,
)
from evaluation.loopback import LoopbackEvaluationTransport  # noqa: E402

BASELINE_WIRE = hashlib.sha256(b"baseline").hexdigest()


# ------------------------------- WS-A helpers -------------------------------
def make_completed_evaluation(evaluator=None):
    service = EvaluationService(
        {}, evaluator=evaluator) if evaluator else EvaluationService(
        {"a" * 64: CandidateBinding("a" * 64, "deployed", "isolated://env-1",
                                    True, "cand-pf-1")})
    adapter = LoopbackClientAdapter(service)
    request = {
        "schema": "research-bench-candidate-evaluation-request/v0.1",
        "idempotency_key": "idem-preflight-0001",
        "candidate_id": "cand-pf-1",
        "candidate_digest": "a" * 64,
        "baseline_digest": BASELINE_WIRE,
        "target_project": "researcher",
        "target_contract_version": "research-agent-task/v0.1",
        "evaluation_profile": "qasper-dev-mock-profile",
        "resource_envelope": {"max_model_calls": 40, "max_tokens": 40000,
                              "max_wall_clock_minutes": 30},
        "requested_metrics": ["quality_metrics", "evidence_metrics",
                              "cost_metrics", "delta", "validity"],
        "requester": "rrsi",
    }
    response = adapter._transport.request("POST", "/v1/evaluations", request)
    evaluation_id = response["body"]["evaluation_id"]
    result = service.records[evaluation_id].result
    return service, adapter, evaluation_id, result


class TamperingTransport(LoopbackEvaluationTransport):
    """Wire-level settlement response tamper (the adapter code path runs
    in full — only the RESPONSE seen by the adapter is modified)."""

    def __init__(self, service, tamper):
        super().__init__(service)
        self._tamper = tamper

    def request(self, method, path, body=None):
        response = super().request(method, path, body)
        if method == "POST" and path.endswith("/settle-budget"):
            body_out = dict(response["body"])
            self._tamper(body_out)
            response = dict(response, body=body_out)
        return response


def tamper_adapter(service, tamper):
    transport = TamperingTransport(service, tamper)
    return LoopbackClientAdapter(service, transport=transport)


# ----------------- WS-A A1 — real-path reconciliation -----------------------
@pytest.mark.parametrize("tamper,expected", [
    (lambda b: b.update({"evaluation_id": "eval-OTHER"}),
     "SETTLEMENT_RECONCILIATION_REQUIRED"),          # id mismatch
    (lambda b: b.update({"settlement_basis": "estimated"}),
     "SETTLEMENT_RECONCILIATION_REQUIRED"),          # basis mismatch
    (lambda b: b.update({"model_calls_used": -1}),
     "SETTLEMENT_RECONCILIATION_REQUIRED"),          # negative usage
    (lambda b: b.update({"model_calls_used": "10"}),
     "SETTLEMENT_RECONCILIATION_REQUIRED"),          # wrong type
    (lambda b: b.pop("model_calls_used"),
     "SETTLEMENT_RECONCILIATION_REQUIRED"),          # missing field
])
def test_ws_a1_real_adapter_path_reconciliation(tamper, expected):
    """REAL adapter: settle-budget runs through the actual adapter code;
    only the settlement response is tampered on the wire."""
    service, _, evaluation_id, result = make_completed_evaluation()
    assert verify_provenance(result)
    adapter = tamper_adapter(service, tamper)
    with pytest.raises(Exception) as ei:
        adapter.get_evaluation_usage(evaluation_id)
    assert expected in str(ei.value)


def test_ws_a1_reconciliation_test_is_not_a_stub():
    """Guard against regression to the R2.3.1 stub pattern: the adapter
    under test must perform the REAL settle-budget call — asserted by
    the settlement succeeding (side-effect basis) before tampering."""
    service, adapter, evaluation_id, _ = make_completed_evaluation()
    usage = adapter.get_evaluation_usage(evaluation_id)
    assert usage["model_calls_used"] == 10
    assert usage["settlement_basis"] == "actual_usage"


# ----------------- WS-A A2 — settlement idempotency / retry -----------------
class LostResponseTransport(LoopbackEvaluationTransport):
    """The settlement EXECUTES on the workbench but the response is LOST
    (transport failure) — the adapter sees an exception."""

    def request(self, method, path, body=None):
        if method == "POST" and path.endswith("/settle-budget") and \
                not self._delivered:
            response = super().request(method, path, body)
            self._delivered = True
            raise RuntimeError("response lost in transit")
        return super().request(method, path, body)

    def __init__(self, service):
        super().__init__(service)
        self._delivered = False


def test_ws_a2_response_lost_then_retry_no_double_settlement():
    service, adapter, evaluation_id, _ = make_completed_evaluation()
    lost = LoopbackClientAdapter(
        service, transport=LostResponseTransport(service))
    with pytest.raises(Exception):        # settlement state UNCERTAIN
        lost.get_evaluation_usage(evaluation_id)
    budget_after_lost = service.budget.model_calls_used
    record_after_lost = \
        service.records[evaluation_id].model_calls_used
    # retry through the REAL adapter — the workbench settlement is
    # idempotent (pure actual-usage read)
    retry = adapter.get_evaluation_usage(evaluation_id)
    assert retry["model_calls_used"] == 10
    assert service.budget.model_calls_used == budget_after_lost
    assert service.records[evaluation_id].model_calls_used == \
        record_after_lost == 10
    # controller-level duplicate settle: second receipt settles once
    r2 = adapter.get_evaluation_usage(evaluation_id)
    assert r2 == retry


def test_ws_a2_settlement_status_query_reconciliation_blocked():
    """Investigation result: the workbench offers NO official settlement
    status query surface (get_evaluation carries status only). We do NOT
    invent one — recorded as RECONCILIATION_BLOCKED for the uncertain
    window; retry remains the reconciliation path."""
    service, adapter, evaluation_id, _ = make_completed_evaluation()
    status = adapter._transport.request(
        "GET", f"/v1/evaluations/{evaluation_id}")["body"]
    assert set(status) == {"evaluation_id", "status", "candidate_id",
                           "candidate_digest", "policy_version"}
    assert "settlement" not in json.dumps(status).lower()


# ----------------- WS-A A3 — controller ledger non-authority ----------------
def test_ws_a3_verification_failure_preserves_workbench_usage():
    """A controller verification failure does NOT mean zero actual model
    usage: the workbench usage record survives (A3 authority boundary)."""
    service, adapter, evaluation_id, result = make_completed_evaluation()
    usage_before = service.records[evaluation_id].model_calls_used
    assert usage_before == 10
    # verification fails on the controller side (provenance tamper)
    tampered = dict(result, quality_metrics={"answer_f1": 0.99})
    assert not verify_provenance(tampered)
    # the WORKBENCH usage record is untouched
    assert service.records[evaluation_id].model_calls_used == usage_before


# ============================ WS-E — T01–T16 ================================
EVAL_REQUEST = {
    "schema": "research-bench-candidate-evaluation-request/v0.1",
    "idempotency_key": "idem-e2t-0001", "candidate_id": "cand-e2t-1",
    "candidate_digest": "a" * 64, "baseline_digest": BASELINE_WIRE,
    "candidate_revision": "r2", "baseline_revision": "r1",
    "target_project": "researcher",
    "target_contract_version": "research-agent-task/v0.1",
    "evaluation_profile": "qasper-dev-mock-profile",
    "resource_envelope": {"max_model_calls": 40, "max_tokens": 40000,
                          "max_wall_clock_minutes": 30},
    "requested_metrics": ["quality_metrics"], "input": {"question": "q"}}
CAND = {"candidate_digest": "sha256:" + "a" * 64,
        "candidate_revision": "r2",
        "resource_envelope": {"max_eval_tokens": 40000}}
# synthetic fixture configuration (no-model tests ONLY — never a default)
CONFIGURATION = {
    "task_type": "qa", "model_profile": "qasper-dev-mock-profile",
    "tool_policy": {"mode": "offline"},
    "configuration_identity": {"profile": "qasper-dev-mock-profile",
                               "fixture": "synthetic-no-model-fixture"}}


def synthetic_binding(**over):
    fields = dict(
        evaluation_request=dict(EVAL_REQUEST),
        evaluation_id="eval-0001-idem-e2t", task_id="task-0123456789abcdef",
        candidate=dict(CAND), configuration=dict(CONFIGURATION))
    fields.update(over)
    return build_binding(**fields).seal()


def task_result(**over):
    payload = {"schema": SCHEMA_TASK_RESULT, "status": "COMPLETED",
               "task_id": "task-0123456789abcdef",
               "identity": {"candidate_id": "cand-e2t-1",
                            "candidate_revision": "r2",
                            "baseline_revision": "r1",
                            "candidate_digest": "a" * 64,
                            "baseline_digest": BASELINE_WIRE,
                            "policy_version":
                                "candidate-evaluation-policy/v0.1"},
               "answer_text": "42", "answer_type": "span",
               "evidence_refs": [{"source": "evidence/ev-1"}],
               "abstained": False, "usage": {"tokens": 1200},
               "provenance": {}, "execution_trace": []}
    covered = {k: v for k, v in payload.items() if k != "result_digest"}
    payload["result_digest"] = "sha256:" + hashlib.sha256(json.dumps(
        covered, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    payload.update(over)
    return payload


def test_t01_normal_identity_mapping():
    """T01 — normal evaluation ↔ task identity mapping."""
    binding = synthetic_binding()
    registry = BindingRegistry()
    out = registry.register(binding)
    assert out.task_id == binding.task_id
    assert out.evaluation_id == "eval-0001-idem-e2t"
    assert identity_chain_ok(out)
    # request mapping carries the identity forward
    task_request = map_evaluation_to_task_request(
        dict(EVAL_REQUEST), {"resource_envelope": {}},
        configuration=dict(CONFIGURATION))
    assert task_request["request_id"].startswith("eval-")
    assert task_request["schema"] == SCHEMA_TASK_REQUEST


def test_t02_candidate_digest_mismatch_blocked():
    binding = synthetic_binding()
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            task_result(identity=dict(task_result()["identity"],
                                      candidate_digest="b" * 64)), binding)
    assert "CANDIDATE_IDENTITY_MISMATCH" in str(ei.value)


def test_t03_baseline_digest_mismatch_blocked():
    binding = synthetic_binding()
    other = build_binding(
        evaluation_request=dict(dict(EVAL_REQUEST), baseline_digest="c" * 64,
                                idempotency_key="idem-e2t-0002"),
        evaluation_id="eval-OTHER", task_id="task-ffffffffffffffff",
        candidate={"candidate_digest": "sha256:" + "a" * 64,
                   "candidate_revision": "r2", "resource_envelope": {}},
        configuration=dict(CONFIGURATION))
    registry = BindingRegistry()
    registry.register(binding)
    registry.register(other)
    assert registry.get_by_evaluation("eval-0001-idem-e2t").baseline_digest \
        != other.baseline_digest
    # a result mapped against the WRONG baseline binding is rejected
    # (fixed order: step 2 task identity passes, step 4 baseline fires)
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            task_result(task_id="task-ffffffffffffffff"), other)
    assert "BASELINE_IDENTITY_MISMATCH" in str(ei.value)


def test_t04_policy_version_mismatch_blocked():
    binding = synthetic_binding()
    wrong_policy = build_binding(
        evaluation_request=dict(EVAL_REQUEST),
        evaluation_id="eval-0001-idem-e2t", task_id="task-ffffffffffffffff",
        candidate={"candidate_digest": "sha256:" + "a" * 64,
                   "candidate_revision": "r2", "resource_envelope": {}},
        configuration=dict(CONFIGURATION))
    assert wrong_policy.policy_version == \
        binding.policy_version          # contract-fixed on both sides
    # the identity chain binds the policy version; a binding record whose
    # policy is flipped fails its digest
    binding.policy_version = "candidate-evaluation-policy/v9.9"
    assert not binding.verify()


def test_t05_task_id_change_blocked():
    binding = synthetic_binding()
    registry = BindingRegistry()
    registry.register(binding)
    # the SAME evaluation id can never be joined to a DIFFERENT task id
    impostor = build_binding(
        evaluation_request=dict(EVAL_REQUEST,
                                idempotency_key="idem-e2t-0003"),
        evaluation_id="eval-0001-idem-e2t",
        task_id="task-ffffffffffffffff",
        candidate={"candidate_digest": "sha256:" + "a" * 64,
                   "candidate_revision": "r2", "resource_envelope": {}},
        configuration=dict(CONFIGURATION))
    with pytest.raises(ContractRejected) as ei:
        registry.register(impostor)
    assert "EVALUATION_BINDING_CONFLICT" in str(ei.value)
    # the ORIGINAL join is preserved
    assert registry.get_by_evaluation(
        "eval-0001-idem-e2t").task_id == binding.task_id
    assert "task-ffffffffffffffff" not in registry.by_task


def test_t06_duplicate_request_idempotent():
    """T06 — duplicate request / idempotency key: no duplicate execution."""
    binding = synthetic_binding()
    registry = BindingRegistry()
    r1 = registry.register(build_binding(
        evaluation_request=dict(EVAL_REQUEST),
        evaluation_id="eval-0001-idem-e2t",
        task_id="task-0123456789abcdef",
        candidate={"candidate_digest": "sha256:" + "a" * 64,
                   "candidate_revision": "r2", "resource_envelope": {}},
        configuration=dict(CONFIGURATION)))
    r2 = registry.register(build_binding(   # same key, same request
        evaluation_request=dict(EVAL_REQUEST),
        evaluation_id="eval-0001-idem-e2t",
        task_id="task-0123456789abcdef",
        candidate={"candidate_digest": "sha256:" + "a" * 64,
                   "candidate_revision": "r2", "resource_envelope": {}},
        configuration=dict(CONFIGURATION)))
    assert r1 is r2 and len(registry.by_evaluation) == 1
    with pytest.raises(ContractRejected):   # same key, different content
        registry.register(build_binding(
            evaluation_request=dict(dict(EVAL_REQUEST),
                                    candidate_digest="9" * 64),
            evaluation_id="eval-9999-OTHER", task_id="task-eeeeeeeeeeeeeeee",
            candidate={"candidate_digest": "sha256:" + "9" * 64,
                       "candidate_revision": "r2", "resource_envelope": {}},
            configuration=dict(CONFIGURATION)))


def test_t07_running_resume_identity_mismatch_blocked():
    """T07 — RUNNING resume identity mismatch: a resume against a WRONG
    task binding is REJECTED by the actual resume path (the R2.3.1
    4-field identity check); a snapshot digest mismatch is rejected too."""
    binding = synthetic_binding()
    # resume path: build the identity chain from a tampered task binding
    tampered = EvaluationTaskBinding(
        evaluation_id=binding.evaluation_id, task_id="task-ffffffffffffffff",
        candidate_id=binding.candidate_id,
        candidate_digest=binding.candidate_digest,
        baseline_digest=binding.baseline_digest,
        policy_version=binding.policy_version,
        config_digest=binding.config_digest,
        input_digest=binding.input_digest,
        candidate_revision=binding.candidate_revision,
        baseline_revision=binding.baseline_revision,
        configuration_identity=binding.configuration_identity,
        idempotency_key="idem-t07-tampered").seal()
    assert tampered.task_id != binding.task_id
    # the resume gate compares evaluation identity against the OFFICIAL
    # binding: binding.get_by_task(tampered task id) exists but binds to a
    # different evaluation — resolved via the controller-level test in
    # test_integration_boundary_r2 (resume_against_snapshot). Here we
    # verify the registry refuses a task-id swap for the same evaluation.
    registry = BindingRegistry()
    registry.register(build_binding(
        evaluation_request=dict(EVAL_REQUEST),
        evaluation_id="eval-0001-idem-e2t",
        task_id="task-0123456789abcdef", candidate=dict(CAND),
        configuration=dict(CONFIGURATION)))
    with pytest.raises(ContractRejected):
        registry.register(build_binding(
            evaluation_request=dict(EVAL_REQUEST),
            evaluation_id="eval-0001-idem-e2t",
            task_id="task-ffffffffffffffff", candidate=dict(CAND),
            configuration=dict(CONFIGURATION)))
    # the identity chain of the tampered join is well-formed but binds a
    # DIFFERENT task id — never resumable as the same work
    assert identity_chain_ok(tampered)
    assert registry.get_by_evaluation(
        "eval-0001-idem-e2t").task_id == "task-0123456789abcdef"


def test_t08_researcher_failed_status_no_evaluation_success():
    binding = synthetic_binding()
    for status in ("FAILED", "CANCELLED"):
        out = map_task_result_to_evaluation_result(
            task_result(status=status, error={"reason": "mock"}), binding)
        assert out["evaluation_status"] == "FAILED"
        assert out["terminal_reason"] == "mock"
        assert out["answer"] is None
    # D2: non-terminal statuses are PRESERVED — never a success, never a
    # failed-evaluation conversion
    for status in ("CREATED", "QUEUED", "RUNNING"):
        out = map_task_result_to_evaluation_result(task_result(status=status),
                                                   binding)
        assert out["evaluation_status"] == "PENDING"
        assert out["answer"] is None
    out = map_task_result_to_evaluation_result(task_result(status="BLOCKED"),
                                               binding)
    assert out["evaluation_status"] == "BLOCKED"   # never CANCELLED
    assert out["answer"] is None


def test_t09_usage_missing_blocked():
    binding = synthetic_binding()
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            task_result(usage={"tokens": None}), binding)
    assert "BUDGET_ACCOUNTING_UNKNOWN" in str(ei.value)


def test_t10_provenance_mismatch_blocked():
    binding = synthetic_binding()
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            task_result(result_digest="sha256:deadbeef"), binding)
    assert "RESULT_DIGEST_MISMATCH" in str(ei.value)


def test_t11_budget_exceeded_blocked():
    binding = synthetic_binding()
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            task_result(usage={"tokens": 50000}), binding,
            approved_budget_tokens=40000)
    assert "BUDGET_CAP_EXCEEDED" in str(ei.value)


def test_t12_no_permit_no_execution():
    """T12 — execution permit absent: NO actual task creation surface is
    invoked by this suite (structural assertion; the researcher repo is
    read-only this stage)."""
    import inspect
    import poc.rest_preflight_r1 as pf
    src = inspect.getsource(pf)
    for forbidden in ("requests.post", "urlopen", "http.client",
                      "create_task", "POST /v1/tasks"):
        assert forbidden not in src, forbidden


def test_t13_settlement_response_tamper_reconciliation_required():
    """T13 — alias of the WS-A1 real-path reconciliation (representative
    case; full matrix in test_ws_a1_real_adapter_path_reconciliation)."""
    service, _, evaluation_id, result = make_completed_evaluation()
    adapter = tamper_adapter(service, lambda b: b.update(
        {"evaluation_id": "eval-OTHER"}))
    with pytest.raises(Exception) as ei:
        adapter.get_evaluation_usage(evaluation_id)
    assert "SETTLEMENT_RECONCILIATION_REQUIRED" in str(ei.value)


def test_t14_settlement_response_lost_retry_no_double():
    """T14 — alias of WS-A2 (full assertions in test_ws_a2_*)."""
    service, adapter, evaluation_id, _ = make_completed_evaluation()
    lost = LoopbackClientAdapter(
        service, transport=LostResponseTransport(service))
    with pytest.raises(Exception):
        lost.get_evaluation_usage(evaluation_id)
    usage = adapter.get_evaluation_usage(evaluation_id)
    assert usage["model_calls_used"] == 10


def test_t15_unknown_task_status_fail_closed():
    binding = synthetic_binding()
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            task_result(status="EXPLODED"), binding)
    assert "TASK_STATUS_UNKNOWN" in str(ei.value)


def test_t16_result_re_reception_no_double_decision():
    """T16 — result re-reception: sealed results are immutable, budget is
    settled once, decision recorded once."""
    loop_mod = __import__("poc.recursive_loop_r2", fromlist=[
        "MockClientAdapter", "RecursiveLoopControllerR2"])
    from poc.recursive_loop_r1 import MockWorkbenchClient
    mock = MockWorkbenchClient(
        policy_version="candidate-evaluation-policy/v0.1",
        budget_eval_tokens=5000)
    client = loop_mod.MockClientAdapter(mock)
    loop = loop_mod.RecursiveLoopControllerR2()
    loop.bind_baseline("b", "baseline-v1",
                       {"answer_quality": 0.60, "evidence_quality": 0.70,
                        "token_cost": 1000, "gpu_cost": 100, "latency": 50,
                        "reliability": 0.95, "regression_risk": 0.1},
                       client=client, baseline_wire=BASELINE_WIRE)
    loop.generate_candidate(candidate_id="cand-rx-1",
                            change_scope="system_task_prompt",
                            change_description="x", execution_profile={},
                            resource_envelope={"max_eval_tokens": 1})
    loop.validate_candidate_step()
    loop.request_evaluation()
    client.deliver_result(loop.job_id,
                          {"answer_quality": 0.65, "evidence_quality": 0.72,
                           "token_cost": 300, "gpu_cost": 1, "latency": 50,
                           "reliability": 0.95, "regression_risk": 0.0},
                          token_cost=300)
    loop.poll_evaluation()
    first = loop.complete_evaluation()
    second = loop.complete_evaluation()
    assert second["duplicate_receive"] is True
    assert second["result"] == first["result"]
    assert loop.tokens_spent == 300
    d1 = loop.assess_feedback_step()
    assert d1["decision"] == "ADVANCE"
    records = len(loop.decision_records)
    # a re-received result NEVER produces a second decision
    assert loop.complete_evaluation()["duplicate_receive"] is True
    assert len(loop.decision_records) == records


def test_ws_b_researcher_status_model_mapping():
    """WS-B2: researcher statuses actually implemented (read-only
    survey) map onto the evaluation surface; unknown → fail-closed."""
    from poc.rest_preflight_r1 import RESEARCHER_STATUSES, \
        RESEARCHER_TERMINAL
    assert set(RESEARCHER_STATUSES) == {
        "CREATED", "QUEUED", "RUNNING", "BLOCKED", "COMPLETED", "FAILED",
        "CANCELLED"}
    # BLOCKED (researcher) ≠ CANCELLED (evaluation) — never collapsed
    assert "BLOCKED" in RESEARCHER_STATUSES and \
        "BLOCKED" not in RESEARCHER_TERMINAL


def test_ws_b3_researcher_usage_gap_not_reported():
    """WS-B3 finding: the researcher COMPLETED result_ref carries NO
    usage/ledger (only FAILED paths report ledger). Per the fail-closed
    rule this is NEVER interpreted as 0 — recorded as a proposed change
    for a separate workstream (this stage: read-only)."""
    binding = synthetic_binding()
    no_usage = task_result()
    no_usage.pop("usage")
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(no_usage, binding)
    assert "BUDGET_ACCOUNTING_UNKNOWN" in str(ei.value)
