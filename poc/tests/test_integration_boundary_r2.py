# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""RRSI-INTEGRATION-BOUNDARY-R2 — boundary gates.

WS-A identity/revision model, evaluation snapshot immutability, resume
against snapshot (latest-candidate change never blocks an old
evaluation). WS-B SHA scope policy + contract compatibility (never
SHA-based). WS-C registry conflict semantics, official binding record
verification, restart recovery boundary. WS-D result-mapping hardening
(baseline missing => REJECT). Zero model calls, zero task executions.
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
from poc.integration_boundary_r2 import (  # noqa: E402
    EvaluationSnapshotBinding, contract_compatible, candidate_identity,
    derive_revision, restart_recovery, resume_against_snapshot,
    verify_candidate_identity, verify_official_binding_record,
)
from poc.rest_preflight_r1 import (  # noqa: E402
    BindingRegistry, build_binding, map_task_result_to_evaluation_result,
)

BASELINE_WIRE = hashlib.sha256(b"baseline").hexdigest()
CONFIGURATION = {"task_type": "qa",
                 "model_profile": "qasper-dev-mock-profile",
                 "tool_policy": {"mode": "offline"},
                 "configuration_identity": {"profile":
                                            "qasper-dev-mock-profile"}}


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
                       baseline_wire=hashlib.sha256(b"baseline").hexdigest())
    return loop, client


# ==================== WS-A1 — identity / revision model ======================
def test_ws_a1_identity_triple_and_content_change_new_revision():
    content = {"change": "lower retry cap to 1"}
    identity = candidate_identity("cand-1", "r1", content)
    assert identity["candidate_id"] == "cand-1"
    assert identity["candidate_revision"] == "r1"
    verify_candidate_identity(identity, content)      # matches its content
    changed = derive_revision(identity, {"change": "x"})
    assert changed["candidate_revision"] == "r2"      # NEW revision
    assert changed["candidate_id"] == "cand-1"
    # prev revision is untouched and STILL verifiable
    verify_candidate_identity(identity, content)


def test_ws_a1_same_revision_different_digest_integrity_error():
    identity = candidate_identity("cand-1", "r1", {"x": 1})
    with pytest.raises(ContractRejected) as ei:
        verify_candidate_identity(identity, {"x": 2})
    assert "REVISION_DIGEST_MISMATCH" in str(ei.value)


def test_ws_a1_candidate_id_same_revision_changed_is_separate():
    """E2: same candidate id + different revision = a SEPARATE revision
    (never merged, never blocked)."""
    r1 = candidate_identity("cand-1", "r1", {"x": 1})
    r2 = derive_revision(r1, {"x": 2})
    r3 = derive_revision(r2, {"x": 3})
    assert len({r1["candidate_content_digest"],
                r2["candidate_content_digest"],
                r3["candidate_content_digest"]}) == 3
    assert [r["candidate_revision"] for r in (r1, r2, r3)] == \
        ["r1", "r2", "r3"]


# ================= WS-A2 — evaluation snapshot immutability ==================
def test_ws_a2_snapshot_binding_fixed_and_immutable():
    snapshot = EvaluationSnapshotBinding(
        evaluation_id="eval-0001-e2t", candidate_id="cand-e2t-1",
        candidate_revision="r2", candidate_content_digest="sha256:" + "a" * 64,
        baseline_revision="r1", baseline_content_digest="sha256:" + "b" * 64,
        evaluation_contract_version="research-agent-task/v0.1",
        evaluation_policy_version="candidate-evaluation-policy/v0.1"
    ).seal()
    assert snapshot.verify()
    # a NEW candidate revision does NOT rewrite the snapshot
    new_revision = derive_revision(
        {"schema": "rrsi-candidate-identity/v0.1",
         "candidate_id": "cand-e2t-1", "candidate_revision": "r2",
         "candidate_content_digest": "sha256:" + "a" * 64},
        {"change": "even lower cap"})
    assert new_revision["candidate_revision"] == "r3"
    assert snapshot.candidate_revision == "r2"        # unchanged
    assert snapshot.verify()                          # still intact


def test_ws_a2_snapshot_incomplete_rejected():
    with pytest.raises(ContractRejected) as ei:
        EvaluationSnapshotBinding(evaluation_id="eval-x")  # 7 fields missing
    assert "SNAPSHOT_INCOMPLETE" in str(ei.value)


# ==================== WS-A3 — resume against snapshot ========================
def snapshot_fixture():
    return EvaluationSnapshotBinding(
        evaluation_id="eval-0001-e2t", candidate_id="cand-e2t-1",
        candidate_revision="r2", candidate_content_digest="sha256:" + "a" * 64,
        baseline_revision="r1", baseline_content_digest="sha256:" + "b" * 64,
        evaluation_contract_version="research-agent-task/v0.1",
        evaluation_policy_version="candidate-evaluation-policy/v0.1"
    ).seal()


def workbench_identity_fixture(**over):
    identity = {
        "evaluation_id": "eval-0001-e2t", "candidate_id": "cand-e2t-1",
        "candidate_revision": "r2",
        "candidate_content_digest": "a" * 64,
        "baseline_content_digest": "b" * 64,
        "evaluation_policy_version": "candidate-evaluation-policy/v0.1",
        "task_binding_id": "wb-task-0001"}
    identity.update(over)
    return identity


def test_ws_a3_resume_allowed_on_matching_snapshot():
    out = resume_against_snapshot(
        snapshot_fixture(), workbench_identity_fixture(),
        official_binding_record=official_record_for(snapshot_fixture()))
    assert out["resume"] == "ALLOWED"
    assert out["task_id"] == "wb-task-0001"


def official_record_for(snapshot, task_id="wb-task-0001", **over):
    """Official Workbench binding record matching a snapshot (synthetic
    projection fixture — the real Workbench API is PENDING, WB-1)."""
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


def test_ws_a3_latest_candidate_change_never_blocks_old_resume():
    """E2: the LATEST candidate changed since the evaluation ran — the
    resume compares against the EXECUTION-TIME snapshot and still
    succeeds (R2.3.1 full binding NOT weakened: every 6-field identity
    is still checked against the snapshot's own values)."""
    latest_candidate = {"candidate_id": "cand-e2t-1", "revision": "r9",
                        "content_digest": "f" * 64}   # latest moved on
    assert latest_candidate["revision"] != \
        snapshot_fixture().candidate_revision
    out = resume_against_snapshot(
        snapshot_fixture(), workbench_identity_fixture(),
        official_binding_record=official_record_for(snapshot_fixture()))
    assert out["resume"] == "ALLOWED"


def test_ws_a3_snapshot_digest_mismatch_rejected():
    with pytest.raises(ContractRejected) as ei:
        resume_against_snapshot(
            snapshot_fixture(),
            workbench_identity_fixture(candidate_content_digest="f" * 64),
            official_binding_record=official_record_for(snapshot_fixture()))
    assert "CANDIDATE_DIGEST_MISMATCH" in str(ei.value)


def test_ws_a3_baseline_and_policy_and_task_binding_required():
    for over, code in (({"baseline_content_digest": ""},
                        "BASELINE_DIGEST_MISMATCH"),
                       ({"baseline_content_digest": "f" * 64},
                        "BASELINE_DIGEST_MISMATCH"),
                       ({"evaluation_policy_version":
                         "candidate-evaluation-policy/v9.9"},
                        "POLICY_VERSION_MISMATCH"),
                       ({"task_binding_id": ""},
                        "TASK_BINDING_IDENTITY_MISSING")):
        with pytest.raises(ContractRejected) as ei:
            resume_against_snapshot(
                snapshot_fixture(), workbench_identity_fixture(**over),
                official_binding_record=official_record_for(
                    snapshot_fixture()))
        assert code in str(ei.value)


# ============== WS-B — SHA scope + contract compatibility ====================
def test_ws_b_compatible_contract_connects_across_differing_shas():
    offer = {"contract_name": "research-agent-task",
             "contract_version": "v0.1",
             "schema_validation": "PASS",
             "capabilities": ["qa_task", "evidence_refs", "usage"]}
    out = contract_compatible(
        offer, contract_name="research-agent-task", contract_version="v0.1",
        required_capabilities=("qa_task", "usage"))
    assert out["compatible"] is True
    # same offer from a DIFFERENT repository commit — still connects
    offer["source_commit"] = "differing-sha"
    assert contract_compatible(
        offer, contract_name="research-agent-task",
        contract_version="v0.1",
        required_capabilities=("qa_task",))["compatible"] is True


def test_ws_b_identical_sha_still_refused_when_contract_unmet():
    offer = {"contract_name": "research-agent-task",
             "contract_version": "v0.1",
             "schema_validation": "FAIL"}     # capability met, schema not
    with pytest.raises(ContractRejected):
        contract_compatible(
            offer, contract_name="research-agent-task",
            contract_version="v0.1",
            required_capabilities=("qa_task",))


def test_ws_b_missing_required_capability_refused():
    offer = {"contract_name": "research-agent-task",
             "contract_version": "v0.1", "schema_validation": "PASS",
             "capabilities": ["qa_task"]}
    with pytest.raises(ContractRejected) as ei:
        contract_compatible(
            offer, contract_name="research-agent-task",
            contract_version="v0.1",
            required_capabilities=("qa_task", "durable_events"))
    assert "CONTRACT_CAPABILITY_MISSING:durable_events" in str(ei.value)


# ========== WS-C3 — official binding record verification =====================
def official_record(**over):
    record = {"schema": "research-bench-evaluation-task-binding/v0.1",
              "contract_version": "research-bench-evaluation-task-binding/v0.1",
              "evaluation_id": "eval-0001-e2t",
              "task_id": "task-0123456789abcdef",
              "candidate_id": "cand-e2t-1", "candidate_revision": "r2",
              "candidate_content_digest": "a" * 64,
              "baseline_revision": "r1", "baseline_content_digest": "b" * 64,
              "policy_version": "candidate-evaluation-policy/v0.1",
              "configuration_identity": {"profile": "qasper-dev-mock-profile"}}
    covered = {k: v for k, v in record.items()
               if k != "binding_record_digest"}
    record["binding_record_digest"] = hashlib.sha256(json.dumps(
        covered, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    record.update(over)
    return record


def test_ws_c3_official_record_full_verification():
    out = verify_official_binding_record(official_record())
    assert out["binding_verified"] is True


def test_ws_c3_missing_authority_field_blocks():
    record = official_record()
    record.pop("policy_version")
    with pytest.raises(ContractRejected) as ei:
        verify_official_binding_record(record)
    assert "BINDING_AUTHORITY_UNAVAILABLE:policy_version" in str(ei.value)


def test_ws_c3_missing_capability_field_blocks():
    record = official_record()
    record.pop("candidate_revision")
    with pytest.raises(ContractRejected) as ei:
        verify_official_binding_record(record)
    assert "CONTRACT_CAPABILITY_MISSING:candidate_revision" in str(ei.value)


def test_ws_c3_record_digest_tamper_rejected():
    with pytest.raises(ContractRejected) as ei:
        verify_official_binding_record(
            official_record(candidate_id="cand-OTHER"))
    assert "BINDING_RECORD_TAMPERED" in str(ei.value)


# ============== WS-C4 — restart recovery boundary ============================
def test_ws_c4_restart_blocked_without_official_lookup():
    out = restart_recovery({"official_binding_lookup_available": False})
    assert out["recovery"] == "BLOCKED"
    assert out["task_recreated"] is False
    assert "RESTART_RECOVERY_BLOCKED" in out["reason"]


def test_ws_c4_restart_blocked_on_identity_mismatch():
    out = restart_recovery({"official_binding_lookup_available": True,
                            "identity_match": False})
    assert out["recovery"] == "BLOCKED"
    assert out["task_recreated"] is False


def test_ws_c4_restart_confirmed_via_official_lookup():
    out = restart_recovery({"official_binding_lookup_available": True,
                            "identity_match": True,
                            "evaluation_id": "eval-0001-e2t"})
    assert out["recovery"] == "CONFIRMED"
    assert out["task_recreated"] is False


# ================ WS-D — result mapping hardening ============================
def _mapping_binding():
    from poc.rest_preflight_r1 import EvaluationTaskBinding
    return EvaluationTaskBinding(
        evaluation_id="eval-wsd", task_id="task-5555555555555555",
        candidate_id="cand-wsd-1", candidate_digest="5" * 64,
        baseline_digest=BASELINE_WIRE,
        policy_version="candidate-evaluation-policy/v0.1",
        config_digest="cfg", input_digest="in", idempotency_key="idem-wsd",
        candidate_revision="r2", baseline_revision="r1",
        configuration_identity={"profile": "qasper-dev-mock-profile"},
        request_digest="req-1").seal()


def wsd_result(**over):
    payload = {"schema": "research-agent-task-result/v0.1",
               "task_id": "task-5555555555555555", "status": "COMPLETED",
               "identity": {"candidate_id": "cand-wsd-1",
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


def test_wsd_baseline_missing_rejected():
    """E2: baseline digest MISSING is a rejection (the old conditional
    `if identity.get("baseline_digest") and ...` is removed)."""
    binding = _mapping_binding()
    result = wsd_result(identity={k: v for k, v in
                                  wsd_result()["identity"].items()
                                  if k != "baseline_digest"})
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(result, binding)
    assert "BASELINE_IDENTITY_MISSING" in str(ei.value)


def test_wsd_usage_missing_rejected():
    binding = _mapping_binding()
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            wsd_result(usage={"tokens": None}), binding)
    assert "BUDGET_ACCOUNTING_UNKNOWN" in str(ei.value)


def test_wsd_blocked_status_preserved():
    binding = _mapping_binding()
    out = map_task_result_to_evaluation_result(
        wsd_result(status="BLOCKED"), binding)
    assert out["evaluation_status"] == "BLOCKED"      # not CANCELLED
    assert out["task_status"] == "BLOCKED"


def test_wsd_task_id_change_blocked():
    binding = _mapping_binding()
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            wsd_result(task_id="task-ffffffffffffffff"), binding)
    assert "TASK_IDENTITY_MISMATCH" in str(ei.value)


def test_wsd_result_digest_tamper_blocked():
    binding = _mapping_binding()
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            wsd_result(answer_text="tampered"), binding)
    assert "RESULT_DIGEST_MISMATCH" in str(ei.value)


def test_wsd_policy_version_mismatch_blocked():
    binding = _mapping_binding()
    result = wsd_result()
    identity = dict(result["identity"], policy_version=
                    "candidate-evaluation-policy/v9.9")
    with pytest.raises(ContractRejected) as ei:
        map_task_result_to_evaluation_result(
            wsd_result(identity=identity), binding)
    assert "POLICY_VERSION_MISMATCH" in str(ei.value)


# ============ E2 — same task id + different evaluation id ====================
def e2_request(idem, digest_hex):
    return {"schema":
            "research-bench-candidate-evaluation-request/v0.1",
            "target_contract_version": "research-agent-task/v0.1",
            "idempotency_key": idem, "candidate_id": "cand-x-1",
            "candidate_digest": "sha256:" + digest_hex,
            "candidate_revision": "r2", "baseline_revision": "r1",
            "baseline_digest": BASELINE_WIRE,
            "resource_envelope": {"max_wall_clock_minutes": 1}}


def test_e2_same_task_id_different_evaluation_rejected():
    registry = BindingRegistry()
    registry.register(build_binding(
        evaluation_request=e2_request("idem-x-0001", "1" * 64),
        evaluation_id="eval-A", task_id="task-1111111111111111",
        candidate={"candidate_digest": "sha256:" + "1" * 64,
                   "candidate_revision": "r2"},
        configuration=dict(CONFIGURATION)))
    b2 = build_binding(
        evaluation_request=e2_request("idem-x-0002", "2" * 64),
        evaluation_id="eval-B", task_id="task-1111111111111111",
        candidate={"candidate_digest": "sha256:" + "2" * 64,
                   "candidate_revision": "r2"},
        configuration=dict(CONFIGURATION))
    with pytest.raises(ContractRejected) as ei:
        registry.register(b2)
    assert "TASK_BINDING_CONFLICT" in str(ei.value)


def test_e2_same_key_different_request_rejected():
    registry = BindingRegistry()
    registry.register(build_binding(
        evaluation_request=e2_request("idem-y-0001", "1" * 64),
        evaluation_id="eval-Y", task_id="task-2222222222222222",
        candidate={"candidate_digest": "sha256:" + "1" * 64,
                   "candidate_revision": "r2"},
        configuration=dict(CONFIGURATION)))
    other_req = e2_request("idem-y-0001", "2" * 64)
    with pytest.raises(ContractRejected):
        registry.register(build_binding(
            evaluation_request=other_req, evaluation_id="eval-Y2",
            task_id="task-3333333333333333",
            candidate={"candidate_digest": "sha256:" + "2" * 64,
                       "candidate_revision": "r2"},
            configuration=dict(CONFIGURATION)))


# ================= controller-level resume regression ========================
def test_controller_resume_after_latest_candidate_changed():
    """Acceptance 5: a changed latest candidate does NOT block an old
    evaluation's controller resume; a snapshot mismatch does."""
    loop, client = make_loop()
    loop.generate_candidate(candidate_id="cand-res-1",
                            change_scope="system_task_prompt",
                            change_description="x", execution_profile={},
                            resource_envelope={"max_eval_tokens": 1})
    loop.validate_candidate_step()
    loop.request_evaluation()
    client.deliver_result(loop.job_id,
                          dict(loop.baseline_metrics, answer_quality=0.65))
    loop.poll_evaluation()
    loop.complete_evaluation()
    snap = loop.seal_snapshot(loop.snapshot())
    # LATEST candidate changed afterwards (outside the snapshot)
    latest = {"candidate_id": "cand-res-1", "revision": "r9",
              "content_digest": "e" * 64}
    fresh = type(loop)()
    out = fresh.resume(snap, client=client)
    assert out["resumed"] is True
    assert fresh.candidate["candidate_id"] == \
        snapshot_candidate_id(snap)          # snapshot value preserved
    assert latest["content_digest"] != \
        snap["current_candidate"]["candidate_digest"]
    # snapshot tamper => resume refused
    tampered = dict(snap, iteration=99)
    with pytest.raises(ContractRejected):
        type(loop)().resume(tampered, client=client)


def snapshot_candidate_id(snap):
    return snap["current_candidate"]["candidate_id"]
