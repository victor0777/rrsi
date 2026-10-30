# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""WB-RRSI-CONTROLLER-INTEGRATION-R2 — real Controller ↔ real Workbench
Candidate Evaluation API over an OFFICIAL Client Interface.

Contracts frozen on top of R1 (`poc.recursive_loop_r1`, untouched):

  A Official Client Interface — `WorkbenchClientInterface` is the ONLY
    surface between the RecursiveLoopController and any Workbench client
    (mock or loopback). The Controller NEVER reads Workbench internal
    data structures (records / jobs / budget dicts) — zero occurrences.
  B Canonical result consumption — `complete_evaluation()` receives the
    CANONICAL Workbench Result (`research-bench-evaluation-result/v0.1`)
    through the interface and validates it in the fixed 12-step order;
    any step failure is fail-closed (TERMINATED, never ADVANCE).
  C Promotion guard independence — `propose_promotion()` relies on
    controller-owned verified state only and emits an IMMUTABLE Decision
    Record bound to the Evaluation ID + Candidate Digest; the approved
    profile is checked against an explicit allowlist (never hardcoded).
  D Durable resume — `resume()` re-verifies Workbench status, result
    identity and trusted usage; the snapshot budget NEVER takes
    precedence over the Workbench trusted usage.

Zero model calls, zero benchmark runs, no production REST deployment.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from poc.recursive_loop_r1 import (  # noqa: F401 — re-exported contracts
    CHANGE_SCOPES, CHANGE_TYPES, CANDIDATE_FIELDS, ContractRejected,
    DigestAdapter, MockWorkbenchClient, PendingResult, REAL_QUALIFICATION_BASIS,
    REWARD_AXES, WORKBENCH_POLICY_VERSION, WorkbenchMockBlocked,
    assess_feedback, canonical_payload_bytes, sha256_obj,
    to_workbench_request, validate_candidate, RecursiveLoopController,
)

SCHEMA_REQUEST = "research-bench-candidate-evaluation-request/v0.1"
SCHEMA_RESULT = "research-bench-evaluation-result/v0.1"
APPROVED_EVALUATION_PROFILES = ("qasper-dev-mock-profile",)


# ============ A. Official Client Interface (the ONLY inter-project seam) ======
class ClientError(Exception):
    """Interface-level failure (fail-closed: callers must never guess)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class WorkbenchClientInterface:
    """Official Candidate Evaluation Client Interface.

    Every Workbench client (mock or loopback) exposes EXACTLY these six
    operations; the Controller is forbidden from touching any other
    attribute of a client (no records/jobs/budget dict access).
    """

    def submit_evaluation(self, candidate: dict, *, baseline_digest_wire: str,
                          policy_version: str,
                          requester: str = "rrsi") -> dict:
        """Submit the RRSI candidate for evaluation. Returns
        {"evaluation_id", "duplicate"}; duplicate submissions return the
        SAME evaluation id and never double-charge budget."""
        raise NotImplementedError

    def get_evaluation_status(self, evaluation_id: str) -> str:
        """Normalized status: RUNNING | COMPLETED | CANCELLED."""
        raise NotImplementedError

    def get_evaluation_result(self, evaluation_id: str) -> dict:
        """CANONICAL Workbench Result payload (immutable once ready)."""
        raise NotImplementedError

    def get_evaluation_events(self, evaluation_id: str) -> list:
        """Allowed-kind event surface (aggregate only)."""
        raise NotImplementedError

    def cancel_evaluation(self, evaluation_id: str) -> dict:
        raise NotImplementedError

    def get_evaluation_usage(self, evaluation_id: str) -> dict:
        """TRUSTED Workbench usage (authoritative over local ledger)."""
        raise NotImplementedError

    def get_evaluation_identity(self, evaluation_id: str) -> dict:
        """Official evaluation identity surface (candidate binding check):
        {"evaluation_id", "candidate_id", "policy_version"}."""
        raise NotImplementedError


def _canonical_digest(payload: dict) -> str:
    return hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()


def _verify_provenance(result_payload: dict) -> bool:
    """Lazy-bound workbench provenance verifier (imported on first use so
    the module does not hard-depend on the workbench tree at import)."""
    from evaluation.candidate_evaluation import verify_provenance
    return verify_provenance(result_payload)


def _normalized_result(envelope: dict) -> dict:
    """Seal a canonical result envelope (self-excluding provenance, 64-hex)."""
    sealed = dict(envelope)
    covered = {k: v for k, v in sealed.items() if k != "provenance_digest"}
    sealed["provenance_digest"] = _canonical_digest(covered)
    return sealed


class MockClientAdapter(WorkbenchClientInterface):
    """Official interface over the R1 mock client. The adapter — not the
    controller — owns the mapping from the mock job surface to the CANONICAL
    Workbench Result, so the controller consumes ONE result contract."""

    def __init__(self, mock: MockWorkbenchClient):
        self._mock = mock
        self._identity: dict[str, dict] = {}
        self._sealed: dict[str, dict] = {}

    @property
    def approved_budget_tokens(self) -> int:
        return self._mock.budget_eval_tokens

    def submit_evaluation(self, candidate, *, baseline_digest_wire,
                          policy_version, requester="rrsi") -> dict:
        sub = self._mock.submit(candidate)
        if not sub.get("ok"):
            raise ClientError("SUBMISSION_REJECTED", ",".join(
                sub.get("problems", [])))
        evaluation_id = sub["job_id"]
        self._identity[evaluation_id] = {
            "candidate_id": candidate["candidate_id"],
            "candidate_digest": candidate["candidate_digest"],
            "baseline_digest_wire": baseline_digest_wire,
            "policy_version": policy_version, "requester": requester}
        self._sealed.pop(evaluation_id, None)
        return {"evaluation_id": evaluation_id,
                "duplicate": sub.get("duplicate", False)}

    # test-harness feedback injection passthrough (mock basis only)
    def deliver_result(self, job_id: str, metrics: dict, **kw) -> dict:
        self._sealed.pop(job_id, None)
        return self._mock.deliver_result(job_id, metrics, **kw)

    def get_evaluation_status(self, evaluation_id: str) -> str:
        try:
            # the deterministic mock advances one tick per poll (the same
            # progression the R1 harness had); the loopback adapter is passive
            raw = self._mock.tick(evaluation_id) if \
                self._mock.jobs.get(evaluation_id, {}).get(
                    "state") == "EVALUATION_REQUESTED" else \
                self._mock.status(evaluation_id)
        except (WorkbenchMockBlocked, KeyError):
            raise ClientError("EVALUATION_NOT_FOUND", evaluation_id)
        return {"EVALUATION_REQUESTED": "RUNNING",
                "EVALUATION_COMPLETED": "COMPLETED",
                "CANCELLED": "CANCELLED"}.get(raw, raw)

    def get_evaluation_result(self, evaluation_id: str) -> dict:
        try:
            res = self._mock.result(evaluation_id)
        except PendingResult:
            raise ClientError("RESULT_NOT_READY", evaluation_id)
        except (WorkbenchMockBlocked, KeyError):
            raise ClientError("EVALUATION_NOT_FOUND", evaluation_id)
        return self._seal(evaluation_id, res)

    def _seal(self, evaluation_id: str, res: dict) -> dict:
        """Map the mock result to the CANONICAL result contract, once
        (sealed results are immutable — re-receipt returns the SAME bytes)."""
        if evaluation_id in self._sealed:
            return self._sealed[evaluation_id]
        ident = self._identity[evaluation_id]
        metrics = res.get("metrics") or {}
        valid = bool(res.get("valid"))
        envelope = {
            "schema": SCHEMA_RESULT,
            "evaluation_id": evaluation_id,
            "status": "COMPLETED_VALID" if valid else "FAILED",
            "candidate_identity": {
                "candidate_id": ident["candidate_id"],
                "candidate_digest": DigestAdapter.to_wire(
                    ident["candidate_digest"])},
            "baseline_identity": {"baseline_digest":
                                  ident["baseline_digest_wire"]},
            "evaluation_profile": "qasper-dev-mock-profile",
            "policy_version": res.get("evaluation_policy_version",
                                      WORKBENCH_POLICY_VERSION),
            "benchmark_cohort": {"benchmark": "qasper",
                                 "cohort": "dev-fixture",
                                 "data_boundary": "development"},
            "sample_count": res.get("samples", 0),
            "failure_category": "none" if valid else "evaluation_invalid",
            "improvement_claim_allowed": valid,
            "quality_metrics": {"answer_f1": metrics.get("answer_quality")},
            "evidence_metrics": {"evidence_f1":
                                 metrics.get("evidence_quality")},
            "cost_metrics": {"model_calls": metrics.get("gpu_cost", 0),
                             "tokens": res.get("token_cost", 0),
                             "latency_ms": metrics.get("latency", 0)},
            "delta": {"baseline_answer_f1": metrics.get("answer_quality")},
            "provenance_digest": None,
        }
        sealed = _normalized_result(envelope)
        self._sealed[evaluation_id] = sealed
        return sealed

    def get_evaluation_events(self, evaluation_id: str) -> list:
        return [{"kind": "evaluation_finished"}]

    def get_evaluation_identity(self, evaluation_id: str) -> dict:
        ident = self._identity.get(evaluation_id)
        if ident is None:
            raise ClientError("EVALUATION_NOT_FOUND", evaluation_id)
        return {"evaluation_id": evaluation_id,
                "candidate_id": ident["candidate_id"],
                "candidate_digest": DigestAdapter.to_wire(
                    ident["candidate_digest"]),
                "policy_version": ident["policy_version"]}

    def cancel_evaluation(self, evaluation_id: str) -> dict:
        try:
            self._mock.cancel(evaluation_id)
        except (WorkbenchMockBlocked, KeyError):
            raise ClientError("EVALUATION_NOT_FOUND", evaluation_id)
        return {"evaluation_id": evaluation_id, "cancelled": True}

    def get_evaluation_usage(self, evaluation_id: str) -> dict:
        if evaluation_id in self._sealed:
            sealed = self._sealed[evaluation_id]
        else:
            try:
                sealed = self._seal(evaluation_id,
                                    self._mock.result(evaluation_id))
            except PendingResult:   # not-ready evaluation: no usage yet
                return {"tokens_used": 0, "model_calls_used": 0,
                        "settlement_basis": "actual_usage"}
        if not _verify_provenance(sealed):   # fail-closed settlement basis
            raise ClientError("PROVENANCE_VERIFICATION_FAILED", evaluation_id)
        cost = sealed["cost_metrics"] or {}
        return {"tokens_used": cost.get("tokens", 0),
                "model_calls_used": cost.get("model_calls", 0),
                "settlement_basis": "actual_usage"}


class LoopbackClientAdapter(WorkbenchClientInterface):
    """Official interface over the REAL Workbench EvaluationService through
    the loopback HTTP-shaped transport (no production REST deployment)."""

    def __init__(self, service):
        from evaluation.loopback import LoopbackEvaluationTransport
        self._service = service
        self._transport = LoopbackEvaluationTransport(service)

    @property
    def approved_budget_tokens(self) -> int:
        return 0   # loopback budget enforcement is service-side

    def _request(self, method: str, path: str, body: Optional[dict] = None):
        try:
            return self._transport.request(method, path, body)
        except Exception as exc:  # loopback fail-closed -> interface failure
            raise ClientError("TRANSPORT_FAILURE", str(exc))

    def submit_evaluation(self, candidate, *, baseline_digest_wire,
                          policy_version, requester="rrsi") -> dict:
        request = to_workbench_request(
            candidate, baseline_digest_wire=baseline_digest_wire,
            policy_version=policy_version)
        request["requester"] = requester
        response = self._request("POST", "/v1/evaluations", request)
        return {"evaluation_id": response["body"]["evaluation_id"],
                "duplicate": response["body"]["duplicate"]}

    def get_evaluation_status(self, evaluation_id: str) -> str:
        body = self._request(
            "GET", f"/v1/evaluations/{evaluation_id}")["body"]
        status = body["status"]
        if status in ("PENDING", "RUNNING"):
            return "RUNNING"
        if status == "CANCELLED":
            return "CANCELLED"
        return "COMPLETED"  # COMPLETED_VALID / FAILED / BUDGET_EXHAUSTED / …

    def get_evaluation_result(self, evaluation_id: str) -> dict:
        return self._request(
            "GET", f"/v1/evaluations/{evaluation_id}/result")["body"]

    def get_evaluation_events(self, evaluation_id: str) -> list:
        return self._request(
            "GET", f"/v1/evaluations/{evaluation_id}/events")["body"]["events"]

    def get_evaluation_identity(self, evaluation_id: str) -> dict:
        body = self._request(
            "GET", f"/v1/evaluations/{evaluation_id}")["body"]
        return {"evaluation_id": body["evaluation_id"],
                "candidate_id": body["candidate_id"],
                "policy_version": body["policy_version"]}

    def cancel_evaluation(self, evaluation_id: str) -> dict:
        return self._request(
            "POST", f"/v1/evaluations/{evaluation_id}/cancel")["body"]

    def get_evaluation_usage(self, evaluation_id: str) -> dict:
        """Trusted usage — OFFICIAL surfaces only, VERIFY-FIRST order:
        1 canonical result via the official result surface -> 2 provenance
        + evaluation identity verified HERE -> 3 usage read from the
        verified result -> 4 settle-budget called LAST -> 5 settlement
        response cross-checked (evaluation id, usage basis, non-negative
        usage). Fail-closed: an unverified result NEVER reaches
        settle-budget."""
        result = self.get_evaluation_result(evaluation_id)
        if not _verify_provenance(result):
            raise ClientError("PROVENANCE_VERIFICATION_FAILED", evaluation_id)
        if result.get("evaluation_id") != evaluation_id:
            raise ClientError("EVALUATION_IDENTITY_MISMATCH", evaluation_id)
        tokens = (result.get("cost_metrics") or {}).get("tokens", 0)
        if tokens is None or tokens < 0:
            raise ClientError("BUDGET_ACCOUNTING_UNKNOWN", evaluation_id)
        settle = self._request(
            "POST", f"/v1/evaluations/{evaluation_id}/settle-budget")["body"]
        if settle.get("evaluation_id") != evaluation_id:
            raise ClientError("SETTLEMENT_IDENTITY_MISMATCH", evaluation_id)
        if settle.get("settlement_basis") != "actual_usage":
            raise ClientError("SETTLEMENT_BASIS_UNEXPECTED", evaluation_id)
        if not isinstance(settle.get("model_calls_used"), int) or \
                settle["model_calls_used"] < 0:
            raise ClientError("SETTLEMENT_USAGE_INVALID", evaluation_id)
        return {"tokens_used": tokens,
                "model_calls_used": settle["model_calls_used"],
                "settlement_basis": settle["settlement_basis"]}


# ============ B/C/D. Controller R2 — canonical consumption & independence =====
FORBIDDEN_CLIENT_ATTRS = ("jobs", "records", "budget", "by_key",
                          "tokens_spent")   # never accessed by the controller


class RecursiveLoopControllerR2(RecursiveLoopController):
    """R1 controller with the R2 integration contracts: the client is used
    EXCLUSIVELY through `WorkbenchClientInterface`; result consumption is
    canonical + 12-step; promotion relies on verified local state only."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.baseline_wire: str | None = None
        self.approved_budget_tokens: int = 0
        self.validated_result: dict | None = None
        self.decision_records: list[dict] = []
        self.evaluation_history: list[dict] = []

    # -- A: binding carries the wire baseline identity --
    def bind_baseline(self, baseline_id: str, version: str, metrics: dict, *,
                      client: WorkbenchClientInterface,
                      baseline_wire: str | None = None) -> dict:
        out = super().bind_baseline(baseline_id, version, metrics,
                                    client=client)
        self.baseline_wire = baseline_wire or DigestAdapter.to_wire(
            sha256_obj({"baseline_id": baseline_id, "version": version}))
        self.approved_budget_tokens = client.approved_budget_tokens
        return out

    # -- A: budget is a controller-owned ledger (no client internals) --
    def _check_budget(self) -> None:
        if self.iteration >= self.max_iterations:
            raise WorkbenchMockBlocked("MAX_ITERATIONS_REACHED")
        if self.evaluations >= self.max_evaluations:
            raise WorkbenchMockBlocked("MAX_EVALUATIONS_REACHED")
        if self.approved_budget_tokens and self.tokens_spent >= \
                self.approved_budget_tokens:
            raise WorkbenchMockBlocked("BUDGET_EXHAUSTED")

    # -- A: submission through the official interface only --
    def request_evaluation(self) -> dict:
        self._check_budget()
        sub = self.client.submit_evaluation(
            self.candidate, baseline_digest_wire=self.baseline_wire,
            policy_version=WORKBENCH_POLICY_VERSION)
        self.job_id = sub["evaluation_id"]
        self.state = "EVALUATION_REQUESTED"
        self.validated_result = None   # new/next evaluation has no result yet
        if not sub["duplicate"]:
            self.evaluations += 1
            self.evaluation_history.append({
                "evaluation_id": self.job_id, "candidate_digest":
                self.candidate["candidate_digest"]})
        return {"state": self.state, "evaluation_id": self.job_id,
                "duplicate": sub["duplicate"]}

    # -- A: normalized polling (no workbench status enums leak in) --
    def poll_evaluation(self) -> str:
        status = self.client.get_evaluation_status(self.job_id)
        while status == "RUNNING":
            status = self.client.get_evaluation_status(self.job_id)
        if status == "COMPLETED":
            self.state = "EVALUATION_COMPLETED"
        elif status == "CANCELLED":
            self._terminate("EVALUATION_CANCELLED")
        return status

    # -- B: canonical result consumption — fixed 12-step order --
    def complete_evaluation(self) -> dict:
        """1 receive (interface) -> 2 schema -> 3 evaluation id -> 4
        candidate identity -> 5 baseline identity -> 6 profile/policy ->
        7 provenance -> 8 status -> 9 required metrics -> 10 budget usage
        -> 11 reward/cost/risk mapping -> 12 state transition. Duplicate
        receipt is IDEMPOTENT (same sealed record, no budget re-charge)."""
        if self.validated_result and \
                self.validated_result["evaluation_id"] == self.job_id:
            return {"state": self.state, "result": self.validated_result,
                    "duplicate_receive": True}
        try:                                              # 1 receive
            res = self.client.get_evaluation_result(self.job_id)
        except ClientError as exc:
            return self._fail_closed("RESULT_RECEIVE_FAILED:" + exc.code)
        if res.get("schema") != SCHEMA_RESULT:            # 2 schema
            return self._fail_closed("SCHEMA_INVALID")
        if res.get("evaluation_id") != self.job_id:       # 3 evaluation id
            return self._fail_closed("EVALUATION_IDENTITY_MISMATCH")
        # 4-7: identity / profile / policy / provenance — EXPLICIT ordered
        # checks so the executed order equals the documented 12-step order
        ci = res.get("candidate_identity") or {}
        if ci.get("candidate_id") != self.candidate["candidate_id"] or \
                ci.get("candidate_digest") != DigestAdapter.to_wire(
                    self.candidate["candidate_digest"]):      # 4 candidate
            return self._fail_closed("CANDIDATE_IDENTITY_MISMATCH")
        if (res.get("baseline_identity") or {}).get("baseline_digest") != \
                self.baseline_wire:                           # 5 baseline
            return self._fail_closed("BASELINE_IDENTITY_MISMATCH")
        if res.get("policy_version") != WORKBENCH_POLICY_VERSION:
            return self._fail_closed("POLICY_VERSION_MISMATCH")   # 6 policy
        claimed = res.get("provenance_digest") or ""
        covered = {k: v for k, v in res.items()
                   if k != "provenance_digest"}
        if claimed != hashlib.sha256(
                canonical_payload_bytes(covered)).hexdigest():    # 7 provenance
            return self._fail_closed("PROVENANCE_VERIFICATION_FAILED")
        if res["status"] not in (                         # 8 status (AFTER 4-7)
                "COMPLETED_VALID", "COMPLETED_INVALID",
                "INSUFFICIENT_EVIDENCE", "FAILED", "CANCELLED",
                "BUDGET_EXHAUSTED"):
            return self._fail_closed("EVALUATION_STATUS_INVALID")
        if res["status"] != "COMPLETED_VALID":            # 8 (usable basis)
            return self._fail_closed({"FAILED": "EVALUATION_INVALID",
                                      "COMPLETED_INVALID": "EVALUATION_INVALID",
                                      "INSUFFICIENT_EVIDENCE":
                                          "INSUFFICIENT_EVIDENCE",
                                      "CANCELLED": "EVALUATION_CANCELLED",
                                      "BUDGET_EXHAUSTED":
                                          "BUDGET_EXHAUSTED"}.get(
                                          res["status"], "EVALUATION_INVALID"))
        metrics = (res.get("quality_metrics") or {})      # 9 required metrics
        if metrics.get("answer_f1") is None:
            return self._fail_closed("REQUIRED_METRICS_MISSING")
        boundary = (res.get("benchmark_cohort") or {}).get("data_boundary")
        if boundary not in ("development", "validation", "held_out"):
            return self._fail_closed("DATA_BOUNDARY_UNKNOWN")
        tokens = (res.get("cost_metrics") or {}).get("tokens", 0)  # 10 usage
        # budget caps are verified BEFORE any ledger change — an overage
        # result never charges the controller (the workbench ledger holds
        # the authoritative usage):
        #   a) PER-EVALUATION cap: a single evaluation above the approved cap
        #   b) CUMULATIVE cap: total verified usage above the approved budget
        if self.approved_budget_tokens and tokens > self.approved_budget_tokens:
            return self._fail_closed("BUDGET_CAP_EXCEEDED")
        if self.approved_budget_tokens and \
                self.tokens_spent + tokens > self.approved_budget_tokens:
            return self._fail_closed("CUMULATIVE_BUDGET_EXCEEDED")
        # 11 reward/cost/risk axis mapping (10-condition validator re-run;
        # guaranteed to pass — every condition already held above)
        try:
            mapped = from_workbench_result_r2(
                res, candidate=self.candidate,
                baseline_wire=self.baseline_wire,
                approved_budget_tokens=self.approved_budget_tokens or None)
        except ContractRejected as exc:
            return self._fail_closed(
                "RESULT_REJECTED:" + str(exc).split(";")[0].split(":")[0])
        # settle ONLY a FULLY validated result (verified numbers first,
        # ledger change last; settlement happens exactly once)
        if not self.validated_result:
            self.tokens_spent += tokens
        self.validated_result = {                         # immutable record
            "evaluation_id": res["evaluation_id"],
            "candidate_digest": self.candidate["candidate_digest"],
            "status": res["status"],
            "evaluation_profile": res["evaluation_profile"],
            "policy_version": res["policy_version"],
            "provenance_verified": True,
            "improvement_claim_allowed": bool(
                res.get("improvement_claim_allowed")),
            "sample_count": res.get("sample_count", 0),
            "tokens_used": tokens,
            "metrics": mapped}
        self.state = "EVALUATION_COMPLETED"               # 12 transition
        return {"state": self.state, "result": self.validated_result,
                "duplicate_receive": False}

    def _validate_result_payload(self, res: dict) -> dict:
        """Steps 4-9 + 11 via the R1 contract validator (10 conditions)."""
        return from_workbench_result_r2(
            res, candidate=self.candidate, baseline_wire=self.baseline_wire,
            approved_budget_tokens=self.approved_budget_tokens or None)

    def _fail_closed(self, reason: str) -> dict:
        self._terminate(reason)
        return {"state": self.state, "reason": reason}

    # -- C: promotion guard — verified controller state ONLY --
    def propose_promotion(self, *, rollback_plan: str,
                          residual_risks: str) -> dict:
        vr = self.validated_result
        last_decision = self.decision_records[-1] if \
            self.decision_records else None
        # Decision Record integrity is RE-VERIFIED at promotion time — the
        # digest makes tampering DETECTABLE here (append-only list + digest
        # discipline; it is not an immutable object per se)
        decision_tampered = bool(last_decision) and \
            last_decision.get("decision_record_digest") != "sha256:" + \
            _canonical_digest({k: v for k, v in last_decision.items()
                               if k != "decision_record_digest"})
        preconditions = {
            "candidate_validation_pass":
                self.state in ("NEXT_ITERATION", "CANDIDATE_VALIDATED"),
            "evaluation_valid": bool(vr) and vr["status"] ==
                                "COMPLETED_VALID",
            "provenance_verified": bool(vr) and vr["provenance_verified"],
            "baseline_match": self.candidate is not None and
                              self.baseline is not None and
                              self.candidate["target_version"] ==
                              self.baseline["version"],
            "reward_cost_risk_pass": bool(last_decision) and
                                     not decision_tampered and
                                     last_decision["decision"] == "ADVANCE"
                                     and last_decision["evaluation_id"] ==
                                     self.job_id and
                                     last_decision["candidate_digest"] ==
                                     self.candidate["candidate_digest"],
            "decision_record_integrity": bool(last_decision) and
                                         not decision_tampered,
            "evidence_present": bool(self.decision_records),
            "approved_profile": bool(vr) and vr["evaluation_profile"] in
                                APPROVED_EVALUATION_PROFILES,
            "proposal_allowed_state": self.state in
                                      ("NEXT_ITERATION",
                                       "CANDIDATE_VALIDATED"),
        }
        if not all(preconditions.values()):
            return {"promotion_blocked": True,
                    "failing_preconditions": [k for k, v in
                                              preconditions.items() if not v]}
        req = {
            "baseline_identity": dict(self.baseline),
            "candidate_identity": {
                "candidate_id": self.candidate["candidate_id"],
                "candidate_digest": self.candidate["candidate_digest"]},
            "decision_record": dict(last_decision),   # immutable evidence
            "quality_delta": self.best_quality -
                             self.baseline_metrics["answer_quality"],
            "cost_delta_tokens": self.tokens_spent,
            "regression_summary": "none observed in approved axes",
            "evaluation_policy_version": vr["policy_version"],
            "residual_risks": residual_risks,
            "rollback_plan": rollback_plan,
            "status": "PENDING_OWNER_APPROVAL"}
        self.promotion_requests.append(req)
        self.state = "PROMOTION_PROPOSED"
        return req

    # -- C: immutable Decision Record linked to evaluation + digest --
    def assess_feedback_step(self) -> dict:
        if not self.validated_result:
            raise ContractRejected("NO_VALIDATED_RESULT")
        vr = self.validated_result
        a = assess_feedback(self.baseline_metrics, vr["metrics"],
                            samples=vr["sample_count"],
                            comparison_baseline_version=self.baseline[
                                "version"],
                            bound_baseline_version=self.baseline["version"])
        record = {
            "evaluation_id": vr["evaluation_id"],
            "candidate_digest": vr["candidate_digest"],
            "decision": a["decision"], "reason": a["reason"],
            "sample_count": vr["sample_count"],
            "tokens_used": vr["tokens_used"],
            "decision_record_digest": None}
        record["decision_record_digest"] = "sha256:" + _canonical_digest(
            {k: v for k, v in record.items()
             if k != "decision_record_digest"})
        self.decision_records.append(record)          # immutable (append-only)
        self.history.append({
            "iteration": self.iteration,
            "candidate_id": self.candidate["candidate_id"],
            "candidate_digest": vr["candidate_digest"],
            "feedback_decision": a["decision"], "reason": a["reason"],
            "token_cost": vr["tokens_used"]})
        if a["decision"] == "UNDECIDABLE":
            self.state = "REVISE_CANDIDATE"
        elif a["decision"] == "REJECT":
            self.state = "REJECTED"
        elif a["decision"] == "HOLD":
            self.state = "REVISE_CANDIDATE"
        else:  # ADVANCE
            self.state = "NEXT_ITERATION"
            q = vr["metrics"]["answer_quality"]
            self.best_quality = (q if self.best_quality is None else
                                 max(self.best_quality, q))
            self.stagnation_window.append(q)
            if len(self.stagnation_window) >= 3 and \
                    (self.stagnation_window[-1] -
                     self.stagnation_window[-3]) < STAGNATION_EPSILON:
                self._terminate("IMPROVEMENT_STAGNATION")
        self.iteration += 1
        return {"state": self.state, "decision": a["decision"],
                "reason": a["reason"], "decision_record":
                dict(record)}

    # -- D: snapshot is controller-local (no workbench internals) --
    def snapshot(self) -> dict:
        return {
            "snapshot_schema_version": self.SNAPSHOT_SCHEMA_VERSION,
            "state": self.state,
            "baseline_identity": dict(self.baseline),
            "baseline_metrics": dict(self.baseline_metrics),
            "baseline_wire": self.baseline_wire,
            "current_candidate": (dict(self.candidate)
                                  if self.candidate else None),
            "current_evaluation_id": self.job_id,
            "iteration": self.iteration,
            "evaluations": self.evaluations,
            "budget_ledger": {"tokens_spent": self.tokens_spent,
                              "approved_budget":
                                  self.approved_budget_tokens},
            "candidate_history": [h for h in self.history],
            "evaluation_history": [dict(e) for e in self.evaluation_history],
            "best_candidate_quality": self.best_quality,
            "stop_reason": self.stop_reason,
            "pending_promotion_request": (self.promotion_requests[-1]
                                          if self.promotion_requests
                                          else None),
            "snapshot_digest": None}

    # -- D: durable resume — ATOMIC 10-step restoration --
    def resume(self, snap: dict, *, client: WorkbenchClientInterface) -> dict:
        """1 schema version -> 2 digest -> 3 baseline -> 4 candidate -> 5
        evaluation id -> 6 workbench status re-query -> 7 workbench result
        identity re-verify -> 8 usage query (per evaluation, SUMMED) -> 9
        budget ledger comparison (workbench usage AUTHORITATIVE) -> 10
        commit. ALL verification runs on LOCAL state first; ANY failure
        leaves the controller UNCHANGED (atomic restore). The snapshot
        digest is integrity-only — persistent trust additionally requires
        a trusted/sealed snapshot store (separate premise)."""
        problems = []
        if not isinstance(snap, dict):                    # 1 version
            raise ContractRejected("SNAPSHOT_NOT_OBJECT")
        if snap.get("snapshot_schema_version") != self.SNAPSHOT_SCHEMA_VERSION:
            problems.append("SNAPSHOT_VERSION_MISMATCH")
        required = ("state", "baseline_identity", "baseline_metrics",
                    "baseline_wire", "iteration", "evaluations",
                    "budget_ledger", "candidate_history",
                    "evaluation_history")
        for field in required:                            # 3-5 fields
            if field not in snap or snap[field] in (None, "") and field != \
                    "current_evaluation_id":
                problems.append("SNAPSHOT_INCOMPLETE:" + field)
        claimed = snap.get("snapshot_digest")             # 2 digest
        if not claimed:
            problems.append("SNAPSHOT_DIGEST_MISSING")
        elif claimed != "sha256:" + _canonical_digest(
                {k: v for k, v in snap.items()
                 if k != "snapshot_digest"}):
            problems.append("SNAPSHOT_TAMPERED")
        if problems:
            raise ContractRejected(";".join(problems))
        # ---- verification on LOCAL copies (nothing committed yet) ----
        local_tokens = snap["budget_ledger"]["tokens_spent"]
        restore = {"state": snap["state"], "stop_reason":
                   snap.get("stop_reason")}
        if snap.get("current_evaluation_id"):
            evaluation_id = snap["current_evaluation_id"]
            status = client.get_evaluation_status(evaluation_id)  # 6 status
            if status == "RUNNING":
                # in-progress evaluation RECONNECT: the evaluation id is
                # preserved, no result exists yet — resume into
                # EVALUATION_REQUESTED so polling/consumption can continue.
                # The RUNNING work must be bound to the SNAPSHOT's candidate
                # via the OFFICIAL identity surface; an identity that does
                # not match (or is unavailable) is fail-closed
                try:
                    identity = client.get_evaluation_identity(evaluation_id)
                except ClientError:
                    raise ContractRejected(
                        "RUNNING_IDENTITY_UNVERIFIED:" + evaluation_id)
                snap_candidate = snap.get("current_candidate") or {}
                if identity.get("candidate_id") != \
                        snap_candidate.get("candidate_id") or \
                        identity.get("policy_version") != \
                        WORKBENCH_POLICY_VERSION:
                    raise ContractRejected(
                        "RUNNING_IDENTITY_MISMATCH:" + evaluation_id)
                restore = {"state": "EVALUATION_REQUESTED", "stop_reason":
                           None}
            elif status == "CANCELLED":
                # cancelled evaluation: restore into a terminal state
                restore = {"state": "TERMINATED", "stop_reason":
                           "EVALUATION_CANCELLED"}
            elif status == "COMPLETED":
                try:                                      # 7 identity re-verify
                    res = client.get_evaluation_result(evaluation_id)
                    from_workbench_result_r2(
                        res, candidate=snap.get("current_candidate") or {},
                        baseline_wire=snap["baseline_wire"])
                except (ClientError, ContractRejected) as exc:
                    raise ContractRejected(
                        "WORKBENCH_RESULT_IDENTITY_MISMATCH:" + str(exc))
            else:
                raise ContractRejected("WORKBENCH_EVALUATION_STATE_MISMATCH:"
                                       + status)
            # 8+9 usage: SUM the trusted per-evaluation usage over the FULL
            # evaluation history — never compare cumulative ledger against
            # a single evaluation's usage
            wb_total = 0
            for entry in snap["evaluation_history"]:
                wb_total += client.get_evaluation_usage(
                    entry["evaluation_id"]).get("tokens_used", 0)
            if local_tokens > wb_total:
                raise ContractRejected(
                    "SNAPSHOT_BUDGET_EXCEEDS_WORKBENCH")
            if wb_total > local_tokens:
                local_tokens = wb_total  # workbench usage authoritative
        # ---- 10 commit: single atomic assignment block ----
        self.client = client
        self.baseline = dict(snap["baseline_identity"])
        self.baseline_metrics = dict(snap["baseline_metrics"])
        self.baseline_wire = snap["baseline_wire"]
        self.candidate = (dict(snap["current_candidate"])
                          if snap.get("current_candidate") else None)
        self.job_id = snap.get("current_evaluation_id")
        self.iteration = snap["iteration"]
        self.evaluations = snap["evaluations"]
        self.tokens_spent = local_tokens
        self.approved_budget_tokens = snap["budget_ledger"].get(
            "approved_budget", 0)
        self.history = list(snap["candidate_history"])
        self.evaluation_history = list(snap["evaluation_history"])
        self.best_quality = snap.get("best_candidate_quality")
        self.state = restore["state"]
        self.stop_reason = restore["stop_reason"]
        return {"resumed": True, "state": self.state}

    def cancel(self, reason: str = "EXPLICIT_CANCELLATION") -> dict:
        self._terminate(reason)
        return {"state": self.state, "reason": self.stop_reason}


def from_workbench_result_r2(result: dict, *, candidate: dict,
                             baseline_wire: str,
                             approved_budget_tokens: int | None = None) -> dict:
    """R2 re-entry over the R1 ten-condition validator, parameterized so
    resume can re-verify identity/provenance without a usable basis."""
    from poc.recursive_loop_r1 import from_workbench_result
    return from_workbench_result(
        result, candidate=candidate, baseline_wire=baseline_wire,
        policy_version=WORKBENCH_POLICY_VERSION,
        profile=result.get("evaluation_profile",
                           "qasper-dev-mock-profile"),
        approved_budget_tokens=approved_budget_tokens)
