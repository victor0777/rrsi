# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""RRSI-INTEGRATION-BOUNDARY-R2.1 — revision enforcement on REAL paths.

F01–F18 negative suite + the end-to-end chain Controller → Evaluation
Snapshot → Binding Projection → Synthetic Researcher Result → Result
Verification → Controller Decision. Zero model calls, zero task
executions; the Workbench official binding API is PENDING (WB-1) so
binding records here are SYNTHETIC PROJECTIONS (marked, never claimed
as real API results).
"""

from __future__ import annotations

import copy
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
from poc.integration_boundary_r2 import (  # noqa: E402
    CandidateRevisionRegistry, candidate_identity,
    contract_compatible, derive_revision, resume_against_snapshot,
    verify_candidate_identity, verify_official_binding_record,
)
from poc.rest_preflight_r1 import (  # noqa: E402
    BindingRegistry, EvaluationTaskBinding, build_binding,
    build_legacy_binding, map_task_result_to_evaluation_result,
)

BASELINE_WIRE = hashlib.sha256(b"baseline").hexdigest()
CONFIGURATION = {"task_type": "qa",
                 "model_profile": "qasper-dev-mock-profile",
                 "tool_policy": {"mode": "offline"},
                 "configuration_identity": {"profile":
                                            "qasper-dev-mock-profile"}}
EVAL_REQUEST = {
    "schema": "research-bench-candidate-evaluation-request/v0.1",
    "idempotency_key": "idem-r21-0001", "candidate_id": "cand-r21-1",
    "candidate_digest": "sha256:" + "5" * 64,
    "candidate_revision": "r2", "baseline_revision": "r1",
    "baseline_digest": BASELINE_WIRE,
    "target_contract_version": "research-agent-task/v0.1",
    "resource_envelope": {"max_wall_clock_minutes": 1},
    "input": {"question": "q"}}


def r21_binding(**over):
    fields = dict(
        evaluation_request=dict(EVAL_REQUEST),
        evaluation_id="eval-r21", task_id="task-5555555555555555",
        candidate={"candidate_digest": "sha256:" + "5" * 64,
                   "candidate_revision": "r2"},
        configuration=dict(CONFIGURATION))
    fields.update(over)
    return build_binding(**fields).seal()


def r21_result(**over):
    payload = {"schema": "research-agent-task-result/v0.1",
               "task_id": "task-5555555555555555", "status": "COMPLETED",
               "identity": {"candidate_id": "cand-r21-1",
                            "candidate_revision": "r2",
                            "baseline_revision": "r1",
                            "candidate_digest": "5" * 64,
                            "baseline_digest": BASELINE_WIRE,
                            "policy_version":
                                "candidate-evaluation-policy/v0.1"},
               "answer_text": "a", "evidence_refs": [{"s": "ev-1"}],
               "abstained": False, "usage": {"tokens": 100}}
    covered = {k: v for k, v in payload.items() if k != "result_digest"}
    payload["result_digest"] = "sha256:" + hashlib.sha256(json.dumps(
        covered, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    payload.update(over)
    return payload


# ============== WS-A — candidate revision on real paths (F01, F02) ===========
def make_loop(**kw):
    from poc.recursive_loop_r1 import MockWorkbenchClient
    from poc.recursive_loop_r2 import MockClientAdapter, \
        RecursiveLoopControllerR2
    params = dict(policy_version="candidate-evaluation-policy/v0.1",
                  budget_eval_tokens=5000)
    params.update(kw)
    client = MockClientAdapter(MockWorkbenchClient(**params))
    loop = RecursiveLoopControllerR2()
    loop.bind_baseline("researcher-baseline", "baseline-v1",
                       {"answer_quality": 0.60, "evidence_quality": 0.70,
                        "token_cost": 1000, "gpu_cost": 100, "latency": 50,
                        "reliability": 0.95, "regression_risk": 0.1},
                       client=client,
                       baseline_wire=BASELINE_WIRE)
    return loop, client


def test_f01_same_candidate_id_new_revision_preserves_evaluation():
    """F01: same candidate id + CHANGED content issues a NEW revision
    while the past evaluation/revision stays verifiable."""
    loop, client = make_loop()
    loop.generate_candidate(candidate_id="cand-f01",
                            change_scope="system_task_prompt",
                            change_description="cap=2", execution_profile={},
                            resource_envelope={"max_eval_tokens": 1})
    assert loop.candidate_revision == "r1"
    verify_candidate_identity(
        candidate_identity("cand-f01", "r1", {
            "description": "cap=2", "profile": {}, "envelope":
            {"max_eval_tokens": 1}}), {
            "description": "cap=2", "profile": {}, "envelope":
            {"max_eval_tokens": 1}})
    # changed content, SAME candidate id -> NEW revision, old intact
    loop.generate_candidate(candidate_id="cand-f01",
                            change_scope="system_task_prompt",
                            change_description="cap=1", execution_profile={},
                            resource_envelope={"max_eval_tokens": 1})
    assert loop.candidate_revision == "r2"
    loop2, _ = make_loop()
    loop2.generate_candidate(candidate_id="cand-f01",
                             change_scope="system_task_prompt",
                             change_description="cap=2", execution_profile={},
                             resource_envelope={"max_eval_tokens": 1})
    assert loop2.candidate_revision == "r1"          # same content => r1


def test_f02_same_revision_different_digest_rejected():
    """F02: a recorded revision re-presented with a DIFFERENT content
    digest is an integrity error (never a new version, never merged)."""
    registry = CandidateRevisionRegistry()
    identity = registry.issue("cand-f02", {"x": 1})
    assert identity["candidate_revision"] == "r1"
    with pytest.raises(ContractRejected) as ei:
        registry.restore("cand-f02", "r1",
                         "sha256:" + "f" * 64)
    assert "REVISION_DIGEST_MISMATCH" in str(ei.value)
    # past revision stays verifiable against ITS OWN content
    verify_candidate_identity(identity, {"x": 1})
    with pytest.raises(ContractRejected):
        verify_candidate_identity(identity, {"x": 2})


def test_f02_controller_revision_digest_tamper_rejected():
    """Controller path: a resume whose snapshot candidate content was
    modified under the SAME revision is rejected on the REAL resume
    path (digest re-computed over the candidate content)."""
    loop, client = make_loop()
    loop.generate_candidate(candidate_id="cand-f02c",
                            change_scope="system_task_prompt",
                            change_description="cap=2", execution_profile={},
                            resource_envelope={"max_eval_tokens": 1})
    loop.validate_candidate_step()
    loop.request_evaluation()
    snap = loop.seal_snapshot(loop.snapshot())
    tampered = copy.deepcopy(snap)
    tampered["current_candidate"]["change_description"] = "TAMPERED"
    covered = {k: v for k, v in tampered.items()
               if k != "snapshot_digest"}
    tampered["snapshot_digest"] = "sha256:" + hashlib.sha256(json.dumps(
        covered, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    with pytest.raises(ContractRejected) as ei:
        type(loop)().resume(tampered, client=client)
    assert "REVISION_DIGEST_MISMATCH" in str(ei.value)


# ============ WS-B — result mapping revision enforcement (F03–F07) ===========
def test_f03_result_candidate_revision_missing_rejected():
    """F03: the current researcher result contract provides NO revision
    — blocked with CONTRACT_CAPABILITY_MISSING, never assumed, never
    invented into the result payload."""
    binding = r21_binding()
    identity = {k: v for k, v in r21_result()["identity"].items()
                if k != "candidate_revision"}
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            r21_result(identity=identity), binding)
    assert "CONTRACT_CAPABILITY_MISSING:candidate_revision_in_result" \
        in str(ei.value)


def test_f04_result_candidate_revision_mismatch_rejected():
    binding = r21_binding()
    identity = dict(r21_result()["identity"], candidate_revision="r9")
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            r21_result(identity=identity), binding)
    assert "CANDIDATE_REVISION_MISMATCH" in str(ei.value)


def test_f05_result_baseline_revision_missing_rejected():
    binding = r21_binding()
    identity = {k: v for k, v in r21_result()["identity"].items()
                if k != "baseline_revision"}
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            r21_result(identity=identity), binding)
    assert "CONTRACT_CAPABILITY_MISSING:baseline_revision_in_result" \
        in str(ei.value)


def test_f06_result_baseline_revision_mismatch_rejected():
    binding = r21_binding()
    identity = dict(r21_result()["identity"], baseline_revision="r9")
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            r21_result(identity=identity), binding)
    assert "BASELINE_REVISION_MISMATCH" in str(ei.value)


def test_f07_binding_record_digest_tamper_rejected():
    binding = r21_binding()
    binding.candidate_digest = "f" * 64                  # any tamper
    assert not binding.verify()
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(r21_result(), binding)
    assert "BINDING_RECORD_TAMPERED" in str(ei.value)


# ============== WS-C — resume task binding closure (F08–F10, F15) ============
def snapshot_fixture():
    from poc.integration_boundary_r2 import EvaluationSnapshotBinding
    return EvaluationSnapshotBinding(
        evaluation_id="eval-r21", candidate_id="cand-r21-1",
        candidate_revision="r2", candidate_content_digest="sha256:" + "5" * 64,
        baseline_revision="r1", baseline_content_digest="sha256:" +
        BASELINE_WIRE,
        evaluation_contract_version="research-agent-task/v0.1",
        evaluation_policy_version="candidate-evaluation-policy/v0.1"
    ).seal()


def official_record_for(snapshot, task_id="wb-task-0001", **over):
    record = {"schema": "research-bench-evaluation-task-binding/v0.1",
              "contract_version":
                  "research-bench-evaluation-task-binding/v0.1",
              "evaluation_id": snapshot.evaluation_id,
              "task_id": task_id,
              "candidate_id": snapshot.candidate_id,
              "candidate_revision": snapshot.candidate_revision,
              "candidate_content_digest":
                  snapshot.candidate_content_digest.replace("sha256:", ""),
              "baseline_revision": snapshot.baseline_revision,
              "baseline_content_digest":
                  snapshot.baseline_content_digest.replace("sha256:", ""),
              "policy_version": snapshot.evaluation_policy_version,
              "configuration_identity": {"profile": "qasper-dev-mock-profile"}}
    covered = {k: v for k, v in record.items()
               if k != "binding_record_digest"}
    record["binding_record_digest"] = hashlib.sha256(json.dumps(
        covered, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    record.update(over)
    return record


def identity_fixture(task_id="wb-task-0001", **over):
    identity = {"evaluation_id": "eval-r21", "candidate_id": "cand-r21-1",
                "candidate_revision": "r2",
                "candidate_content_digest": "5" * 64,
                "baseline_content_digest": BASELINE_WIRE,
                "evaluation_policy_version":
                    "candidate-evaluation-policy/v0.1",
                "task_binding_id": task_id}
    identity.update(over)
    return identity


def test_f08_resume_task_id_change_rejected():
    """F08: the official record now binds a DIFFERENT task than the
    previous execution used — the resume is rejected (never resumed
    across task bindings)."""
    with pytest.raises(ContractRejected) as ei:
        resume_against_snapshot(
            snapshot_fixture(), identity_fixture(task_id="wb-task-0001"),
            official_binding_record=official_record_for(
                snapshot_fixture(), task_id="wb-task-9999"))
    assert "TASK_BINDING_IDENTITY_MISMATCH" in str(ei.value)


def test_f09_official_binding_lookup_unavailable_blocked():
    """F09: workbench binding lookup unavailable — BLOCKED with
    BINDING_AUTHORITY_UNAVAILABLE (never assumed or invented)."""
    with pytest.raises(ContractRejected) as ei:
        resume_against_snapshot(snapshot_fixture(), identity_fixture())
    assert "BINDING_AUTHORITY_UNAVAILABLE" in str(ei.value)
    with pytest.raises(ContractRejected) as ei2:
        resume_against_snapshot(snapshot_fixture(), identity_fixture(),
                                official_binding_record={})
    assert "BINDING_AUTHORITY_UNAVAILABLE" in str(ei2.value)


def test_f10_latest_candidate_changed_old_resume_allowed():
    """F10: the LATEST candidate moved on — the resume compares against
    the execution-time snapshot + the OFFICIAL binding and still
    succeeds."""
    latest = derive_revision(None, {"desc": "totally-new-latest"})
    out = resume_against_snapshot(
        snapshot_fixture(), identity_fixture(),
        official_binding_record=official_record_for(snapshot_fixture()))
    assert out["resume"] == "ALLOWED"
    assert latest["candidate_revision"] == "r1"          # latest is separate


def test_f15_failed_resume_leaves_controller_unchanged():
    """F15: a FAILED resume (official binding verification) leaves the
    controller state UNCHANGED (atomic restore boundary)."""
    loop, client = make_loop()
    loop.generate_candidate(candidate_id="cand-f15",
                            change_scope="system_task_prompt",
                            change_description="cap=2", execution_profile={},
                            resource_envelope={"max_eval_tokens": 1})
    loop.validate_candidate_step()
    loop.request_evaluation()
    snap = loop.seal_snapshot(loop.snapshot())
    fresh = type(loop)()
    before = copy.deepcopy(vars(fresh))
    before_revisions = copy.deepcopy(fresh._revisions.issued)

    orig_record = client.get_official_binding_record

    def tampered_record(evaluation_id):                  # tampered binding
        record = orig_record(evaluation_id)
        record["evaluation_id"] = "eval-OTHER"
        covered = {k: v for k, v in record.items()
                   if k != "binding_record_digest"}
        record["binding_record_digest"] = hashlib.sha256(json.dumps(
            covered, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        return record            # re-signed: passes integrity, fails match

    client.get_official_binding_record = tampered_record
    with pytest.raises(ContractRejected) as ei:
        fresh.resume(snap, client=client)
    assert "BINDING_EVALUATION_ID_MISMATCH" in str(ei.value)
    assert {k: v for k, v in vars(fresh).items() if k != "_revisions"} == \
        {k: v for k, v in before.items() if k != "_revisions"}
    assert fresh._revisions.issued == before_revisions    # UNCHANGED


# =============== WS-D — status-specific validation (F11–F13) =================
def test_f11_non_terminal_status_no_result_digest_required():
    """F11: non-terminal statuses never require a terminal result
    digest — the state is PRESERVED and no usage is verified-settled."""
    binding = r21_binding()
    no_digest = {k: v for k, v in r21_result().items()
                 if k != "result_digest"}
    for status, expected in (("CREATED", "PENDING"), ("QUEUED", "PENDING"),
                             ("RUNNING", "PENDING"), ("BLOCKED", "BLOCKED")):
        out = map_task_result_to_evaluation_result(
            dict(no_digest, status=status), binding)
        assert out["evaluation_status"] == expected
        assert out["verified_usage"] is False
        assert out["revision_enforced"] is True


def test_f12_completed_result_digest_missing_rejected():
    binding = r21_binding()
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            {k: v for k, v in r21_result().items() if k != "result_digest"},
            binding)
    assert "RESULT_DIGEST_MISSING" in str(ei.value)


def test_f13_completed_usage_missing_rejected():
    binding = r21_binding()
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            r21_result(usage={"tokens": None}), binding)
    assert "BUDGET_ACCOUNTING_UNKNOWN" in str(ei.value)
    with pytest.raises(ContractRejected):
        map_task_result_to_evaluation_result(
            {k: v for k, v in r21_result().items() if k != "usage"}, binding)


# ================= WS-E — configuration binding (F14, F18) ===================
def test_f14_same_key_different_configuration_rejected():
    """F14: the SAME idempotency key with a DIFFERENT configuration is
    an explicit conflict — configuration changes never ride an existing
    key."""
    registry = BindingRegistry()
    registry.register(r21_binding())
    other_cfg = dict(CONFIGURATION, model_profile="other-profile",
                     configuration_identity={"profile": "other-profile"})
    with pytest.raises(ContractRejected) as ei:
        registry.register(r21_binding(configuration=dict(other_cfg)))
    assert "IDEMPOTENCY_CONFLICT:configuration" in str(ei.value)


def test_f18_revision_not_provided_blocked_and_legacy_explicit():
    """F18: a candidate WITHOUT a revision is blocked on the
    revision-aware contract (never silently r1). The explicit LEGACY
    adapter is isolated: its records are marked legacy and its result
    mapping NEVER claims a verified revision."""
    with pytest.raises(ContractRejected) as ei:
        r21_binding(candidate={                                 # no revision
            "candidate_digest": "sha256:" + "5" * 64})
    assert "CANDIDATE_REVISION_REQUIRED" in str(ei.value)
    with pytest.raises(ContractRejected) as ei2:
        r21_binding(evaluation_request=dict(
            EVAL_REQUEST, baseline_revision=""))                # no baseline rev
    assert "BASELINE_REVISION_REQUIRED" in str(ei2.value)
    legacy = build_legacy_binding(
        evaluation_request=dict(EVAL_REQUEST),
        evaluation_id="eval-r21-legacy", task_id="task-5555555555555555",
        candidate={"candidate_digest": "sha256:" + "5" * 64},
        configuration=dict(CONFIGURATION))
    assert legacy["legacy"] is True and legacy["revision_provided"] is False


# ================= WS-B2 — SHA scope (F16, F17) ==============================
def test_f16_differing_commit_sha_compatible_contract_connects():
    offer = {"contract_name": "research-agent-task",
             "contract_version": "v0.1", "schema_validation": "PASS",
             "capabilities": ["qa_task", "usage"], "source_commit": "aaa"}
    offer["source_commit"] = "completely-different-sha"
    out = contract_compatible(
        offer, contract_name="research-agent-task", contract_version="v0.1",
        required_capabilities=("qa_task",))
    assert out["compatible"] is True


def test_f17_identical_sha_capability_missing_refused():
    offer = {"contract_name": "research-agent-task",
             "contract_version": "v0.1", "schema_validation": "PASS",
             "capabilities": ["qa_task"], "source_commit": "identical-sha"}
    with pytest.raises(ContractRejected) as ei:
        contract_compatible(
            offer, contract_name="research-agent-task",
            contract_version="v0.1",
            required_capabilities=("qa_task", "durable_events"))
    assert "CONTRACT_CAPABILITY_MISSING:durable_events" in str(ei.value)


# ========== F2 — REAL PATH chain (synthetic projection marked) ===============
def test_real_path_controller_to_decision_chain():
    """Controller Candidate → Evaluation Snapshot → Binding Projection →
    Synthetic Researcher Result → Result Verification → Controller
    Decision. The binding record is a SYNTHETIC MOCK PROJECTION (real
    Workbench API PENDING, WB-1) — asserted, not hidden."""
    loop, client = make_loop()
    loop.generate_candidate(candidate_id="cand-chain-1",
                            change_scope="system_task_prompt",
                            change_description="cap=1", execution_profile={},
                            resource_envelope={"max_eval_tokens": 1})
    loop.validate_candidate_step()
    loop.request_evaluation()
    assert loop.candidate_revision == "r1"
    # evaluation snapshot
    snap = loop.seal_snapshot(loop.snapshot())
    # binding projection from the adapter (synthetic, marked)
    record = client.get_official_binding_record(loop.job_id)
    verified = verify_official_binding_record(record)
    assert verified["binding_verified"] is True
    assert record["candidate_revision"] == loop.candidate_revision
    assert record["configuration_identity"]["projection"] == \
        "synthetic-mock-adapter"          # projection MARKED
    # synthetic researcher result + result verification against the
    # binding projected from THIS evaluation
    binding = build_binding(
        evaluation_request=dict(
            EVAL_REQUEST, candidate_id=loop.candidate["candidate_id"],
            candidate_digest=loop.candidate["candidate_digest"],
            candidate_revision=loop.candidate_revision,
            baseline_revision=loop.baseline_revision),
        evaluation_id=loop.job_id, task_id=record["task_id"],
        candidate=dict(loop.candidate,
                       candidate_revision=loop.candidate_revision),
        configuration=dict(CONFIGURATION)).seal()
    wire_digest = hashlib.sha256(b"5").hexdigest() if False else \
        record["candidate_content_digest"]
    chain_result = dict(
        r21_result(), task_id=record["task_id"],
        identity=dict(r21_result()["identity"],
                      candidate_id=loop.candidate["candidate_id"],
                      candidate_revision=loop.candidate_revision,
                      candidate_digest=wire_digest,
                      baseline_revision=loop.baseline_revision))
    covered = {k: v for k, v in chain_result.items() if k != "result_digest"}
    chain_result["result_digest"] = "sha256:" + hashlib.sha256(json.dumps(
        covered, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    result = map_task_result_to_evaluation_result(chain_result, binding)
    assert result["evaluation_status"] == "COMPLETED_VALID"
    assert result["revision_enforced"] is True
    # controller decision
    client.deliver_result(loop.job_id,
                          dict(loop.baseline_metrics, answer_quality=0.65))
    assert loop.poll_evaluation() == "COMPLETED"
    out = loop.complete_evaluation()
    assert out["state"] == "EVALUATION_COMPLETED"
    decision = loop.assess_feedback_step()
    assert decision["decision"] == "ADVANCE"
    # resume across restart: snapshot restores atomically, revision kept
    fresh = type(loop)()
    resumed = fresh.resume(snap, client=client)
    assert resumed["resumed"] is True
    assert fresh.candidate_revision == "r1"
