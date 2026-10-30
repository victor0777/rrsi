# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""WB-RRSI-RESEARCHER-REST-PREFLIGHT-R1 — no-model contract prototype.

Fixture-based prototype of the Workbench ↔ Researcher adapter contracts
(directive WS-C / WS-F "필요시 무모델 Fixture 기반 Adapter Prototype").
ZERO model calls, ZERO task executions — every mapping is verified
against fully synthetic or existing shared fixtures.

Contracts (read-only survey of ``research_agent`` HEAD, recorded in doc
53; the survey repository is NOT modified here):

  C1 Request Mapping — RRSI Candidate → Workbench Evaluation Request →
     Researcher Task Request, with a PERSISTENT EvaluationTaskBinding
     joining the two identifier spaces (Evaluation ID ≠ Task ID).
  C2 Result Mapping — Researcher Task Result → Workbench Canonical
     Result → RRSI verification, fail-closed: researcher success alone
     NEVER declares evaluation success, missing usage is NEVER 0, a
     failed task is NEVER converted into a valid evaluation result.
  C3 Responsibility split — Researcher executes, Workbench owns
     lifecycle/budget/canonical results, RRSI verifies and decides.
"""

from __future__ import annotations

import hashlib
import json

from poc.recursive_loop_r1 import ContractRejected, DigestAdapter

SCHEMA_TASK_REQUEST = "research-agent-task-request/v0.1"
SCHEMA_TASK_RESULT = "research-agent-task-result/v0.1"
# Researcher task statuses actually implemented (task_store HEAD):
RESEARCHER_STATUSES = ("CREATED", "QUEUED", "RUNNING", "BLOCKED",
                       "COMPLETED", "FAILED", "CANCELLED")
RESEARCHER_TERMINAL = ("COMPLETED", "FAILED", "CANCELLED")


def _sha256(payload) -> str:
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()


# ======================= C1 — Request mapping / binding ======================
def map_evaluation_to_task_request(evaluation_request: dict,
                                   candidate: dict) -> dict:
    """Workbench Evaluation Request → Researcher Task Request.

    Bindings carried forward: evaluation id (as request_id — the
    researcher idempotency key, so an evaluation retries to the SAME
    task), candidate digest + baseline digest + policy version ride in
    the input payload (the researcher validates only as opaque identity
    — it never scores against them). Gold/evaluation content has NO
    surface: FORBIDDEN_BODY_KEYS of the researcher rejects it."""
    input_payload = {
        "task_contract": evaluation_request["target_contract_version"],
        "candidate_id": evaluation_request["candidate_id"],
        "candidate_digest": evaluation_request["candidate_digest"],
        "baseline_digest": evaluation_request["baseline_digest"],
        "evaluation_policy_version": WORKBENCH_POLICY_VERSION_R2,
        "question": (evaluation_request.get("input")
                     or {"question": ""}).get("question", ""),
    }
    envelope = candidate.get("resource_envelope") or {}
    return {
        "schema": SCHEMA_TASK_REQUEST,
        "request_id": "eval-" + evaluation_request["idempotency_key"],
        "task_type": "qa",
        "input": input_payload,
        "model_profile": "qasper-dev-mock-profile",
        "data_snapshot_digest": _sha256(input_payload),
        "budget": {"wall_clock_s": 60 * evaluation_request[
            "resource_envelope"].get("max_wall_clock_minutes", 30)},
        "tool_policy": {"mode": "offline"},
    }


WORKBENCH_POLICY_VERSION_R2 = "candidate-evaluation-policy/v0.1"


class EvaluationTaskBinding:
    """PERSISTENT join between the two identifier spaces. A binding is
    immutable once created; retries MUST return the existing task id."""

    def __init__(self, *, evaluation_id: str, task_id: str, candidate_id: str,
                 candidate_digest: str, baseline_digest: str,
                 policy_version: str, config_digest: str,
                 input_digest: str, idempotency_key: str):
        self.evaluation_id = evaluation_id
        self.task_id = task_id
        self.candidate_id = candidate_id
        self.candidate_digest = candidate_digest       # wire 64-hex
        self.baseline_digest = baseline_digest         # wire 64-hex
        self.policy_version = policy_version
        self.config_digest = config_digest
        self.input_digest = input_digest
        self.idempotency_key = idempotency_key
        self.record_digest = None

    def seal(self) -> "EvaluationTaskBinding":
        covered = {k: v for k, v in vars(self).items()
                   if k != "record_digest"}
        self.record_digest = "sha256:" + _sha256(covered)
        return self

    def verify(self) -> bool:
        covered = {k: v for k, v in vars(self).items()
                   if k != "record_digest"}
        return self.record_digest == "sha256:" + _sha256(covered)


class BindingRegistry:
    """In-memory persistent registry: evaluation id ↔ task id, plus the
    full identity chain. Idempotent join and fail-closed lookups."""

    def __init__(self):
        self.by_evaluation: dict[str, EvaluationTaskBinding] = {}
        self.by_task: dict[str, EvaluationTaskBinding] = {}
        self.by_idempotency: dict[str, str] = {}   # key -> evaluation id

    def register(self, binding: EvaluationTaskBinding) -> EvaluationTaskBinding:
        if binding.idempotency_key in self.by_idempotency:
            existing = self.by_evaluation[self.by_idempotency[
                binding.idempotency_key]]
            if existing.evaluation_id != binding.evaluation_id:
                raise ContractRejected("IDEMPOTENCY_CONFLICT")
            return existing                       # idempotent join
        if binding.evaluation_id in self.by_evaluation:
            # fail-closed: one evaluation can NEVER be re-joined to a
            # different task id (no task-id change / binding inversion)
            raise ContractRejected("EVALUATION_BINDING_CONFLICT")
        binding.seal()
        self.by_evaluation[binding.evaluation_id] = binding
        self.by_task[binding.task_id] = binding
        self.by_idempotency[binding.idempotency_key] = binding.evaluation_id
        return binding

    def get_by_evaluation(self, evaluation_id: str) -> EvaluationTaskBinding:
        if evaluation_id not in self.by_evaluation:
            raise ContractRejected(
                "BINDING_NOT_FOUND:" + evaluation_id)
        return self.by_evaluation[evaluation_id]

    def get_by_task(self, task_id: str) -> EvaluationTaskBinding:
        if task_id not in self.by_task:
            raise ContractRejected("BINDING_NOT_FOUND:" + task_id)
        return self.by_task[task_id]


def build_binding(*, evaluation_request: dict, evaluation_id: str,
                  task_id: str, candidate: dict) -> EvaluationTaskBinding:
    """Create the identity chain for one evaluation ↔ task pair."""
    task_request = map_evaluation_to_task_request(evaluation_request,
                                                  candidate)
    return EvaluationTaskBinding(
        evaluation_id=evaluation_id, task_id=task_id,
        candidate_id=evaluation_request["candidate_id"],
        candidate_digest=DigestAdapter.to_wire(
            candidate["candidate_digest"]),
        baseline_digest=evaluation_request["baseline_digest"],
        policy_version=WORKBENCH_POLICY_VERSION_R2,
        config_digest=_sha256({"model_profile": task_request["model_profile"],
                               "tool_policy": task_request["tool_policy"]}),
        input_digest=task_request["data_snapshot_digest"],
        idempotency_key=evaluation_request["idempotency_key"])


# ================== C2 — Result mapping (fail-closed) ========================
def map_task_result_to_evaluation_result(task_result: dict,
                                         binding: EvaluationTaskBinding,
                                         *,
                                         approved_budget_tokens=None) -> dict:
    """Researcher Task Result → Workbench-shaped evaluation inputs.

    Fail-closed rules (WS-C C2, directive-enforced):
      - COMPLETED status alone NEVER yields a valid evaluation basis —
        a usable basis additionally requires answer + usage + digest.
      - missing usage is BUDGET_ACCOUNTING_UNKNOWN (never 0).
      - a FAILED / CANCELLED / BLOCKED task maps to a FAILED evaluation
        (never converted into a valid evaluation result).
      - identity mismatches against the binding are rejected.
    """
    problems = []
    if task_result.get("schema") != SCHEMA_TASK_RESULT:
        problems.append("SCHEMA_INVALID")
    status = task_result.get("status")
    if status not in RESEARCHER_STATUSES:
        problems.append("TASK_STATUS_UNKNOWN")   # unknown ≠ success
    identity = task_result.get("identity") or {}
    if identity.get("candidate_id") != binding.candidate_id or \
            identity.get("candidate_digest") != binding.candidate_digest:
        problems.append("CANDIDATE_IDENTITY_MISMATCH")
    if identity.get("baseline_digest") and \
            identity["baseline_digest"] != binding.baseline_digest:
        problems.append("BASELINE_IDENTITY_MISMATCH")
    if problems:
        raise ContractRejected(";".join(problems))
    usage = task_result.get("usage") or {}
    tokens = usage.get("tokens")
    if isinstance(tokens, bool) or not isinstance(tokens, int) or \
            tokens < 0:
        raise ContractRejected("BUDGET_ACCOUNTING_UNKNOWN")
    if approved_budget_tokens is not None and tokens > \
            approved_budget_tokens:
        raise ContractRejected("BUDGET_CAP_EXCEEDED")
    if status != "COMPLETED":
        # failed task → failed evaluation basis (never a success)
        return {"evaluation_status": "FAILED",
                "failure_category": "researcher_task_" + status.lower(),
                "answer": None, "evidence_refs": [], "tokens_used": tokens}
    result_digest = task_result.get("result_digest")
    if not result_digest or result_digest != "sha256:" + _sha256(
            {k: v for k, v in task_result.items()
             if k != "result_digest"}):
        raise ContractRejected("RESULT_DIGEST_MISMATCH")
    if not task_result.get("answer_text") and not \
            task_result.get("abstained"):
        raise ContractRejected("ANSWER_MISSING")   # success without answer
    evidence = task_result.get("evidence_refs") or []
    if not evidence and not task_result.get("abstained"):
        # evidence absence is NEVER treated as passed evidence verification
        raise ContractRejected("EVIDENCE_MISSING")
    return {"evaluation_status": "COMPLETED_VALID" if not
            task_result.get("abstained") else "INSUFFICIENT_EVIDENCE",
            "failure_category": "none",
            "answer": task_result["answer_text"],
            "evidence_refs": evidence,
            "tokens_used": tokens}


def identity_chain_ok(binding: EvaluationTaskBinding) -> bool:
    """D1 identity gate: the persisted join itself must be
    tamper-evident and complete (wire digests are 64-hex)."""
    from poc.recursive_loop_r1 import WIRE_DIGEST_RE
    return binding.record_digest is not None and binding.verify() and \
        bool(WIRE_DIGEST_RE.fullmatch(binding.candidate_digest or ""))
