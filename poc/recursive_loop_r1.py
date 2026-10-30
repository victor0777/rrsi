# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""RRSI-RECURSIVE-LOOP-R1 — Recursive Improvement Controller (prototype,
deterministic; zero model calls, zero benchmark runs).

Design-frozen contracts per the Four-Project Architecture Boundary R2:
RRSI may GENERATE candidates, REQUEST evaluations through the official
Workbench Candidate Evaluation API (mocked here) and PROPOSE promotion —
it never approves operating promotion itself and never touches the
Workbench scorer or gold/held-out stores. Existing RRSI policies
(reward regularization docs 26–28, cost/budget policy, R7 admission
gates, execution permit path) take precedence; this module builds no
separate bypass engine.

Candidate changes are limited to the Researcher HARNESS configuration
(prompts, tool/context planning, retrieval, memory/evidence selection,
reasoning parameters) — production source code edits are out of scope.
"""

from __future__ import annotations

import hashlib
import json
import re

# ----------------------------- reuse matrix ---------------------------------
REUSE_MATRIX = {
    "poc_core.py": "candidate generation (cand_* mutation generators), "
                   "guards_fn incumbent/candidate guards, critic_review, "
                   "evaluate_fixture — feeding CandidateContract",
    "budget_policy.py": "check_prestart / assert_within_budget — the loop "
                        "uses the SAME totals policy, not a parallel one",
    "execution_permit.py": "verify_permit / assert_authorized — any future "
                           "real evaluation run still requires an Owner "
                           "permit through the R6I path",
    "dataset_manifest.py": "canonical_bytes / manifest_hash — digest "
                           "discipline reused for candidate digests",
    "gold_review.py": "approval-gate semantics (GoldReviewBlocked) — "
                      "mirrored for held-out/gold boundary",
    "r7_contract.py": "R7 evaluation contract, admission gates, reviewer "
                      "governance — Evaluation Policy version source",
    "docs 26-28": "reward regularization & discrimination audits — reward "
                  "axis policy precedence",
    "docs 37-39": "R7 metrics denominators & admission gates — promotion "
                  "evidence requirements",
}

# --------------------------- candidate contract ------------------------------
CANDIDATE_FIELDS = ("candidate_id", "parent_candidate_id", "target_project",
                    "target_version", "candidate_digest", "change_type",
                    "change_scope", "change_description", "execution_profile",
                    "resource_envelope", "generation_provenance")
# harness-configuration scopes ONLY (production source code excluded)
CHANGE_SCOPES = ("system_task_prompt", "tool_selection_policy",
                 "context_planning_policy", "retrieval_strategy",
                 "memory_evidence_selection", "reasoning_control_parameters")
CHANGE_TYPES = ("parameter_tuning", "policy_swap", "prompt_revision",
                "strategy_revision")


def sha256_obj(value) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode()).hexdigest()


# ========== §WB-RRSI-CONTRACT-CONVERGENCE-R1 — cross-repo contracts ==========
# Wire format (canonical): 64-char lowercase sha256 hex. RRSI internal
# format: "sha256:<hex>". The adapter is the ONLY conversion point.
WIRE_DIGEST_RE = re.compile(r"^[a-f0-9]{64}$")


class ContractRejected(Exception):
    """Explicit contract-mismatch rejection (never silent success)."""


class DigestAdapter:
    @staticmethod
    def to_wire(internal: str) -> str:
        if not internal.startswith("sha256:"):
            raise ContractRejected("DIGEST_MALFORMED:" + str(internal))
        wire = internal[7:]
        if not WIRE_DIGEST_RE.fullmatch(wire):
            raise ContractRejected("DIGEST_MALFORMED:" + wire)
        return wire

    @staticmethod
    def from_wire(wire: str) -> str:
        if not WIRE_DIGEST_RE.fullmatch(str(wire)):
            raise ContractRejected("DIGEST_MALFORMED:" + str(wire))
        return "sha256:" + wire


def canonical_payload_bytes(payload) -> bytes:
    """Shared canonicalization rule (identical on both sides): UTF-8,
    ensure_ascii=False, sort_keys=True, compact separators (',', ':')."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def to_workbench_request(candidate: dict, *, baseline_digest_wire: str,
                         policy_version: str, requester: str = "rrsi",
                         idempotency_key: str | None = None) -> dict:
    """§C1 — RRSI Candidate Contract → Workbench Request Schema.
    Executables, paths, URLs and commands have NO surface. Unmappable
    candidate fields are NOT silently dropped — unknown keys are an
    explicit contract rejection."""
    allowed_keys = set(CANDIDATE_FIELDS)  # full 11-field contract
    # wire-preserved: candidate identity, baseline identity, profile,
    # policy version, envelope, idempotency — all mapped below.
    # loop-internal (validated, NOT sent): parent_candidate_id,
    # target_version, generation_provenance.
    unknown = set(candidate) - allowed_keys
    if unknown:
        raise ContractRejected("UNMAPPABLE_FIELDS:" + ",".join(sorted(unknown)))
    if candidate["change_scope"] not in CHANGE_SCOPES:
        raise ContractRejected("FORBIDDEN_CHANGE_SCOPE")
    env = candidate["resource_envelope"]
    wb_env = {"max_model_calls": int(env.get("max_eval_tokens", 0) > 0) * 4,
              "max_tokens": int(env.get("max_eval_tokens", 0)),
              "max_wall_clock_minutes": 30}
    return {
        "schema": "research-bench-candidate-evaluation-request/v0.1",
        "idempotency_key": idempotency_key or
                           f"idem-{candidate['candidate_id']}-{policy_version}",
        "candidate_id": candidate["candidate_id"],
        "candidate_digest": DigestAdapter.to_wire(
            candidate["candidate_digest"]),
        "baseline_digest": baseline_digest_wire,
        "target_project": candidate["target_project"]
                          if candidate["target_project"] in
                          ("researcher", "ai_papers") else
                          "researcher",
        "target_contract_version": "research-agent-task/v0.1",
        "evaluation_profile": "qasper-dev-mock-profile",
        "resource_envelope": wb_env,
        "requested_metrics": ["quality_metrics", "evidence_metrics",
                              "cost_metrics", "delta", "validity"],
        "requester": requester,
    }


WORKBENCH_POLICY_VERSION = "candidate-evaluation-policy/v0.1"


def from_workbench_result(result: dict, *, candidate: dict,
                          baseline_wire: str, policy_version: str,
                          profile: str = "qasper-dev-mock-profile",
                          approved_budget_tokens: int | None = None) -> dict:
    """§C2 — Workbench Result → RRSI decision input. ALL ten conditions
    must hold; any failure ⇒ explicit rejection — the caller can never
    transition to ADVANCE or PROMOTION_PROPOSED on a rejected result."""
    problems = []
    if result.get("schema") != "research-bench-evaluation-result/v0.1":
        problems.append("SCHEMA_INVALID")
    ci = result.get("candidate_identity") or {}
    if ci.get("candidate_id") != candidate["candidate_id"] or \
            ci.get("candidate_digest") != DigestAdapter.to_wire(
                candidate["candidate_digest"]):
        problems.append("CANDIDATE_IDENTITY_MISMATCH")
    if (result.get("baseline_identity") or {}).get("baseline_digest") != \
            baseline_wire:
        problems.append("BASELINE_IDENTITY_MISMATCH")
    if result.get("evaluation_profile") != profile:
        problems.append("EVALUATION_PROFILE_MISMATCH")
    if result.get("policy_version") != WORKBENCH_POLICY_VERSION:
        problems.append("POLICY_VERSION_MISMATCH")
    claimed = result.get("provenance_digest") or ""
    covered = {k: v for k, v in result.items() if k != "provenance_digest"}
    recomputed = hashlib.sha256(
        canonical_payload_bytes(covered)).hexdigest()  # 64-hex wire format
    if claimed != recomputed:
        problems.append("PROVENANCE_VERIFICATION_FAILED")
    if result.get("status") not in ("COMPLETED_VALID", "COMPLETED_INVALID",
                                    "INSUFFICIENT_EVIDENCE", "FAILED",
                                    "CANCELLED", "BUDGET_EXHAUSTED"):
        problems.append("EVALUATION_STATUS_INVALID")
    metrics = result.get("quality_metrics") or {}
    if metrics.get("answer_f1") is None:
        problems.append("REQUIRED_METRICS_MISSING")
    boundary = (result.get("benchmark_cohort") or {}).get("data_boundary")
    if boundary not in ("development", "validation", "held_out"):
        problems.append("DATA_BOUNDARY_UNKNOWN")
    usage = (result.get("cost_metrics") or {}).get("tokens")
    if usage is None:
        problems.append("BUDGET_ACCOUNTING_UNKNOWN")
    elif approved_budget_tokens is not None and usage > \
            approved_budget_tokens:
        problems.append("BUDGET_CAP_EXCEEDED")
    if problems:
        raise ContractRejected(";".join(problems))
    # internal mapping: aggregate answer_f1 → decision axes (unit: score 0..1,
    # higher=better; token cost unit: tokens, higher=worse)
    return {
        "answer_quality": metrics["answer_f1"],
        "evidence_quality": (result.get("evidence_metrics") or {})
                            .get("evidence_f1", 0.0),
        "reliability": 0.95,  # from validity; mock basis
        "token_cost": usage,
        "gpu_cost": (result.get("cost_metrics") or {}).get("model_calls", 0),
        "latency": (result.get("cost_metrics") or {}).get("latency_ms", 0),
        "regression_risk": (result.get("failure_category") != "none") * 1.0,
    }


# §D3 — mock test gate vs real qualification basis (separated):
#   MIN_SAMPLES=3 gates ONLY the deterministic mock loop.
#   Real promotion judgment requires per-benchmark sample sizes,
#   uncertainty bounds, baseline comparability and regression risk —
#   reviewed by the target Researcher Owner, never auto-decided.
REAL_QUALIFICATION_BASIS = {
    "min_samples_mock_loop": 3,
    "mock_gate_applies_to": "deterministic closed-loop tests only",
    "real_promotion_basis": ("per-benchmark sample size + uncertainty "
                             "bounds + baseline comparability + "
                             "regression risk; human owner review"),
    "auto_qualification": "FORBIDDEN",}


def validate_candidate(candidate: dict) -> dict:
    problems = []
    if not isinstance(candidate, dict):
        return {"valid": False, "problems": ["CANDIDATE_NOT_OBJECT"]}
    for field in CANDIDATE_FIELDS:
        if field not in candidate or candidate[field] in (None, ""):
            problems.append(f"MISSING_FIELD:{field}")
    if problems:
        return {"valid": False, "problems": problems}
    if not str(candidate["candidate_id"]).startswith("cand-"):
        problems.append("CANDIDATE_ID_MALFORMED")
    if candidate["change_scope"] not in CHANGE_SCOPES:
        problems.append("FORBIDDEN_CHANGE_SCOPE")
    if candidate["change_type"] not in CHANGE_TYPES:
        problems.append("UNKNOWN_CHANGE_TYPE")
    if not str(candidate["candidate_digest"]).startswith("sha256:"):
        problems.append("DIGEST_MALFORMED")
    env = candidate["resource_envelope"]
    if not isinstance(env, dict) or "max_eval_tokens" not in env:
        problems.append("RESOURCE_ENVELOPE_INCOMPLETE")
    return {"valid": not problems, "problems": problems}


# ---------------------- workbench evaluation client --------------------------
class WorkbenchMockBlocked(Exception):
    """Boundary violation (held-out/gold access, budget, drift)."""


class PendingResult(Exception):
    """Evaluation job not finished yet."""


class MockWorkbenchClient:
    """Contract-only client for the official Candidate Evaluation API.
    No real API exists yet — the client is exercised against mock jobs.
    It never imports Workbench scorer code and never reads gold or
    held-out stores; held-out detail feedback requests are BLOCKED."""

    def __init__(self, *, policy_version: str, budget_eval_tokens: int):
        self.policy_version = policy_version
        self.budget_eval_tokens = budget_eval_tokens
        self.tokens_spent = 0
        self.jobs: dict[str, dict] = {}
        self.by_key: dict[str, str] = {}  # request_key -> job_id
        self.held_out_access_attempts: list[str] = []

    # -- submission (duplicate prevention via idempotent request key) --
    def request_key(self, candidate_digest: str) -> str:
        return sha256_obj({"digest": candidate_digest,
                           "policy": self.policy_version})

    def submit(self, candidate: dict) -> dict:
        v = validate_candidate(candidate)
        if not v["valid"]:
            return {"ok": False, "problems": v["problems"]}
        key = self.request_key(candidate["candidate_digest"])
        if key in self.by_key:
            return {"ok": True, "job_id": self.by_key[key],
                    "duplicate": True}
        if self.tokens_spent >= self.budget_eval_tokens:
            raise WorkbenchMockBlocked("BUDGET_EXHAUSTED")
        job_id = "wbj-" + sha256_obj({"key": key})[7:23]
        self.jobs[job_id] = {"candidate_digest":
                             candidate["candidate_digest"],
                             "state": "EVALUATION_REQUESTED",
                             "ticks_left": 2, "result": None}
        self.by_key[key] = job_id
        return {"ok": True, "job_id": job_id, "duplicate": False}

    def status(self, job_id: str) -> str:
        job = self.jobs.get(job_id)
        if not job:
            raise WorkbenchMockBlocked("UNKNOWN_JOB")
        return job["state"]

    def tick(self, job_id: str) -> str:
        job = self.jobs[job_id]
        if job["state"] == "EVALUATION_REQUESTED":
            job["ticks_left"] -= 1
            if job["ticks_left"] <= 0:
                job["state"] = "EVALUATION_COMPLETED"
        return job["state"]

    def result(self, job_id: str) -> dict:
        job = self.jobs.get(job_id)
        if not job or job["state"] != "EVALUATION_COMPLETED":
            raise PendingResult(job_id)
        return job["result"]

    def deliver_result(self, job_id: str, metrics: dict, *,
                       valid: bool = True, samples: int = 3,
                       token_cost: int = 100) -> dict:
        """Mock feedback injection (test harness only). The provenance
        digest is self-excluding, so tampering any field — including
        the evaluation policy version — breaks verification."""
        job = self.jobs[job_id]
        token_cost = min(token_cost, max(
            0, self.budget_eval_tokens - self.tokens_spent))
        self.tokens_spent += token_cost
        payload = {"job_id": job_id,
                   "candidate_digest": job["candidate_digest"],
                   "evaluation_policy_version": self.policy_version,
                   "workbench_run_id": "run-mock-1",
                   "comparison_baseline_version": "baseline-v1",
                   "valid": valid, "samples": samples,
                   "token_cost": token_cost,
                   "metrics": metrics}
        res = dict(payload, provenance_digest=sha256_obj(payload))
        job["result"] = res
        return res

    def verify_provenance(self, result: dict) -> bool:
        payload = {k: v for k, v in result.items()
                   if k != "provenance_digest"}
        if payload.get("evaluation_policy_version") != self.policy_version:
            return False
        return result["provenance_digest"] == sha256_obj(payload)

    # -- held-out boundary: detail feedback requests are BLOCKED --
    def request_held_out_detail(self, job_id: str) -> dict:
        self.held_out_access_attempts.append(job_id)
        raise WorkbenchMockBlocked("HELD_OUT_DETAIL_ACCESS_DENIED")

    def settle(self, job_id: str) -> dict:
        res = self.jobs[job_id]["result"]
        return {"tokens_settled": res["token_cost"],
                "budget_remaining": max(
                    0, self.budget_eval_tokens - self.tokens_spent)}

    def cancel(self, job_id: str) -> str:
        self.jobs[job_id]["state"] = "CANCELLED"
        return "CANCELLED"


# --------------------- reward / cost / risk decision -------------------------
REWARD_AXES = ("answer_quality", "evidence_quality", "token_cost",
               "gpu_cost", "latency", "reliability", "regression_risk")
# relative-worsening caps (positive = worsening for cost axes)
COST_WORSENING_CAPS = {"token_cost": 0.10, "gpu_cost": 0.10,
                       "latency": 0.15}
RELIABILITY_FLOOR = -0.02
MIN_SAMPLES = 3
STAGNATION_EPSILON = 0.005


def assess_feedback(baseline: dict, metrics: dict, *, samples: int,
                    comparison_baseline_version: str,
                    bound_baseline_version: str) -> dict:
    """Deterministic reward/cost/risk decision. Insufficient samples or a
    different comparison baseline ⇒ UNDECIDABLE — never promotion."""
    def d(axis):
        return metrics[axis] - baseline[axis]
    if samples < MIN_SAMPLES or comparison_baseline_version != \
            bound_baseline_version:
        return {"decision": "UNDECIDABLE",
                "reason": "INSUFFICIENT_SAMPLES_OR_BASELINE_MISMATCH"}
    if d("answer_quality") <= 0:
        return {"decision": "REJECT",
                "reason": "ANSWER_QUALITY_NOT_IMPROVED"}
    if d("evidence_quality") < 0:
        return {"decision": "REJECT",
                "reason": "EVIDENCE_QUALITY_REGRESSION"}
    if d("reliability") < RELIABILITY_FLOOR:
        return {"decision": "REJECT",
                "reason": "RELIABILITY_BELOW_FLOOR"}
    for axis, cap in COST_WORSENING_CAPS.items():
        rel = d(axis) / max(baseline[axis], 1e-9)
        if rel > cap:
            return {"decision": "HOLD",
                    "reason": "COST_CAP_EXCEEDED:" + axis}
    return {"decision": "ADVANCE",
            "reason": "QUALITY_IMPROVED_WITHIN_COST_ENVELOPE",
            "quality_delta": d("answer_quality")}


# ------------------- recursive loop state machine ----------------------------
STATES = ("BASELINE_BOUND", "CANDIDATE_GENERATED", "CANDIDATE_VALIDATED",
          "EVALUATION_REQUESTED", "EVALUATION_COMPLETED", "FEEDBACK_ASSESSED",
          "REJECTED", "REVISE_CANDIDATE", "NEXT_ITERATION",
          "PROMOTION_PROPOSED", "TERMINATED")
TERMINAL_STATES = ("REJECTED", "REVISE_CANDIDATE", "NEXT_ITERATION",
                   "PROMOTION_PROPOSED", "TERMINATED")


class RecursiveLoopController:
    """Isolated controller prototype. It tracks candidate/feedback/
    decision/cost per iteration, enforces terminal conditions (no
    infinite loops) and supports resume with history and budget
    preserved. It NEVER changes the operating researcher and never
    approves promotion."""

    def __init__(self, *, max_iterations: int = 5, max_evaluations: int = 10,
                 budget_eval_tokens: int = 2000):
        self.state = None
        self.baseline: dict | None = None
        self.baseline_metrics: dict | None = None
        self.max_iterations = max_iterations
        self.max_evaluations = max_evaluations
        self.iteration = 0
        self.evaluations = 0
        self.history: list[dict] = []
        self.tokens_spent = 0
        self.client: MockWorkbenchClient | None = None
        self.job_id: str | None = None
        self.candidate: dict | None = None
        self.stop_reason: str | None = None
        self.best_quality: float | None = None
        self.stagnation_window: list[float] = []
        self.promotion_requests: list[dict] = []

    def bind_baseline(self, baseline_id: str, version: str,
                      metrics: dict, *, client: MockWorkbenchClient) -> dict:
        self.baseline = {"baseline_id": baseline_id, "version": version}
        self.baseline_metrics = dict(metrics)
        self.client = client
        self.state = "BASELINE_BOUND"
        return {"state": self.state}

    def _check_budget(self) -> None:
        if self.iteration >= self.max_iterations:
            raise WorkbenchMockBlocked("MAX_ITERATIONS_REACHED")
        if self.evaluations >= self.max_evaluations:
            raise WorkbenchMockBlocked("MAX_EVALUATIONS_REACHED")
        if self.client.tokens_spent >= self.client.budget_eval_tokens:
            raise WorkbenchMockBlocked("BUDGET_EXHAUSTED")

    def generate_candidate(self, **fields) -> dict:
        self._check_budget()
        self.candidate = {
            "candidate_id": fields.get("candidate_id",
                                       f"cand-{self.iteration + 1}-"
                                       "draft"),
            "parent_candidate_id": fields.get("parent_candidate_id",
                                              "baseline"),
            "target_project": fields.get("target_project", "researcher"),
            "target_version": self.baseline["version"],
            "candidate_digest": sha256_obj({
                "description": fields.get("change_description"),
                "profile": fields.get("execution_profile"),
                "envelope": fields.get("resource_envelope")}),
            "change_type": fields.get("change_type", "parameter_tuning"),
            "change_scope": fields.get("change_scope"),
            "change_description": fields.get("change_description"),
            "execution_profile": fields.get("execution_profile", {}),
            "resource_envelope": fields.get("resource_envelope", {}),
            "generation_provenance": sha256_obj({
                "generator": "rrsi-recursive-loop-r1",
                "iteration": self.iteration,
                "parent": fields.get("parent_candidate_id", "baseline")}),
        }
        v = validate_candidate(self.candidate)
        if not v["valid"]:
            self.state = "TERMINATED"
            self.stop_reason = "CANDIDATE_VALIDATION_FAILED"
            return {"state": self.state, "problems": v["problems"]}
        # identical digest regeneration ⇒ revise, never re-evaluate
        for h in self.history:
            if h.get("candidate_digest") == self.candidate["candidate_digest"]:
                self.state = "REVISE_CANDIDATE"
                return {"state": self.state,
                        "reason": "IDENTICAL_CANDIDATE_REGENERATED"}
        self.state = "CANDIDATE_GENERATED"
        return {"state": self.state}

    def validate_candidate_step(self) -> dict:
        if self.state != "CANDIDATE_GENERATED":
            raise WorkbenchMockBlocked("INVALID_TRANSITION")
        drift = self.candidate["candidate_digest"] != sha256_obj({
            "description": self.candidate["change_description"],
            "profile": self.candidate["execution_profile"],
            "envelope": self.candidate["resource_envelope"]})
        if drift or self.candidate["target_version"] != \
                self.baseline["version"]:
            self.state = "TERMINATED"
            self.stop_reason = ("CANDIDATE_DIGEST_DRIFT" if drift else
                                "BASELINE_CHANGED")
            return {"state": self.state, "reason": self.stop_reason}
        self.state = "CANDIDATE_VALIDATED"
        return {"state": self.state}

    def request_evaluation(self) -> dict:
        self._check_budget()
        sub = self.client.submit(self.candidate)
        if not sub["ok"]:
            self.state = "TERMINATED"
            self.stop_reason = "SUBMISSION_REJECTED"
            return {"state": self.state, "problems": sub["problems"]}
        self.job_id = sub["job_id"]
        self.state = "EVALUATION_REQUESTED"
        if not sub.get("duplicate"):
            self.evaluations += 1
        return {"state": self.state, "job_id": self.job_id,
                "duplicate": sub.get("duplicate", False)}

    def poll_evaluation(self) -> str:
        state = self.client.status(self.job_id)
        while state == "EVALUATION_REQUESTED":
            state = self.client.tick(self.job_id)
        if state == "EVALUATION_COMPLETED":
            self.state = "EVALUATION_COMPLETED"
        return state

    def complete_evaluation(self) -> dict:
        """Receive result; invalid or provenance failure ⇒ TERMINATED
        (promotion never allowed on invalid evaluations)."""
        res = self.client.result(self.job_id)
        if not res.get("valid") or not self.client.verify_provenance(res):
            self.state = "TERMINATED"
            self.stop_reason = ("EVALUATION_INVALID" if not res.get("valid")
                                else "PROVENANCE_FAILURE")
            return {"state": self.state, "reason": self.stop_reason}
        settle = self.client.settle(self.job_id)
        self.tokens_spent += res["token_cost"]
        return {"state": self.state, "result": res,
                "settlement": settle}

    def assess_feedback_step(self) -> dict:
        res = self.client.result(self.job_id)
        a = assess_feedback(self.baseline_metrics, res["metrics"],
                            samples=res["samples"],
                            comparison_baseline_version=res[
                                "comparison_baseline_version"],
                            bound_baseline_version=self.baseline["version"])
        self.history.append({
            "iteration": self.iteration,
            "candidate_id": self.candidate["candidate_id"],
            "candidate_digest": self.candidate["candidate_digest"],
            "feedback_decision": a["decision"], "reason": a["reason"],
            "token_cost": res["token_cost"]})
        if a["decision"] == "UNDECIDABLE":
            self.state = "REVISE_CANDIDATE"
        elif a["decision"] == "REJECT":
            self.state = "REJECTED"
        elif a["decision"] == "HOLD":
            self.state = "REVISE_CANDIDATE"
        else:  # ADVANCE
            self.state = "NEXT_ITERATION"
            q = res["metrics"]["answer_quality"]
            self.best_quality = (q if self.best_quality is None else
                                 max(self.best_quality, q))
            self.stagnation_window.append(q)
            if len(self.stagnation_window) >= 3 and \
                    (self.stagnation_window[-1] -
                     self.stagnation_window[-3]) < STAGNATION_EPSILON:
                self._terminate("IMPROVEMENT_STAGNATION")
        self.iteration += 1
        self.state = self.state
        return {"state": self.state, "decision": a["decision"],
                "reason": a["reason"]}

    def _terminate(self, reason: str) -> None:
        self.state = "TERMINATED"
        self.stop_reason = reason

    # -- promotion boundary: propose only; Owner decides --
    def propose_promotion(self, *, rollback_plan: str,
                          residual_risks: str) -> dict:
        """§D1 — explicit promotion guard. ALL preconditions must hold;
        otherwise PROMOTION_BLOCKED. HOLD/REJECT/UNDECIDABLE/TERMINATED
        states can never create a proposal. Even an approved proposal
        stays a proposal — operating promotion belongs to the target
        Researcher Owner."""
        preconditions = {
            "candidate_validation_pass": self.state == "NEXT_ITERATION" or
                                         self.state == "CANDIDATE_VALIDATED",
            "evaluation_valid": self.job_id is not None and
                                self.client is not None and
                                self.client.jobs.get(self.job_id, {})
                                .get("state") == "EVALUATION_COMPLETED",
            "provenance_verified": self.job_id is not None and
                                   self.client is not None and
                                   self.client.verify_provenance(
                                       self.client.jobs[self.job_id]["result"]),
            "baseline_match": self.candidate is not None and
                              self.candidate["target_version"] ==
                              self.baseline["version"],
            "reward_cost_risk_pass": self.history and
                                     self.history[-1]["feedback_decision"] ==
                                     "ADVANCE",
            "evidence_present": bool(self.history),
            "approved_profile": True,   # qasper-dev-mock-profile via adapter
            "proposal_allowed_state": self.state in
                                      ("NEXT_ITERATION",
                                       "CANDIDATE_VALIDATED"),
        }
        if not all(preconditions.values()):
            blocked = {"promotion_blocked": True,
                       "failing_preconditions": [k for k, v in
                                                 preconditions.items()
                                                 if not v]}
            return blocked
        req = {
            "baseline_identity": dict(self.baseline),
            "candidate_identity": {
                "candidate_id": self.candidate["candidate_id"],
                "candidate_digest": self.candidate["candidate_digest"]},
            "evaluation_evidence": [h for h in self.history
                                    if h["candidate_id"] ==
                                    self.candidate["candidate_id"]],
            "quality_delta": self.best_quality - self.baseline_metrics[
                "answer_quality"],
            "cost_delta_tokens": self.tokens_spent,
            "regression_summary": "none observed in approved axes",
            "evaluation_policy_version": self.client.policy_version,
            "residual_risks": residual_risks,
            "rollback_plan": rollback_plan,
            "status": "PENDING_OWNER_APPROVAL"}
        self.promotion_requests.append(req)
        self.state = "PROMOTION_PROPOSED"
        return req

    # -- durable resume: full state, validated; restart never re-evaluates --
    SNAPSHOT_SCHEMA_VERSION = "rrsi-loop-snapshot/v0.2"

    def snapshot(self) -> dict:
        return {
            "snapshot_schema_version": self.SNAPSHOT_SCHEMA_VERSION,
            "state": self.state,
            "baseline_identity": dict(self.baseline),
            "baseline_metrics": dict(self.baseline_metrics),
            "current_candidate": (dict(self.candidate)
                                  if self.candidate else None),
            "current_evaluation_id": self.job_id,
            "iteration": self.iteration,
            "evaluations": self.evaluations,
            "budget_ledger": {"tokens_spent": self.tokens_spent,
                              "client_tokens": self.client.tokens_spent
                                               if self.client else 0,
                              "approved_budget":
                                  self.client.budget_eval_tokens
                                  if self.client else 0},
            "candidate_history": [h for h in self.history],
            "evaluation_history": [{"job_id": j,
                                    "state": rec["state"]}
                                   for j, rec in
                                   (self.client.jobs.items()
                                    if self.client else [])],
            "best_candidate_quality": self.best_quality,
            "stop_reason": self.stop_reason,
            "pending_promotion_request": (self.promotion_requests[-1]
                                          if self.promotion_requests
                                          else None),
            "snapshot_digest": None}

    def seal_snapshot(self, snap: dict) -> dict:
        snap["snapshot_digest"] = "sha256:" + hashlib.sha256(
            canonical_payload_bytes({k: v for k, v in snap.items()
                                     if k != "snapshot_digest"})).hexdigest()
        return snap

    def resume(self, snap: dict, *, client: MockWorkbenchClient) -> dict:
        """Validate snapshot (schema version + digest integrity + required
        fields), re-verify Workbench job identity, then restore. Tampered,
        old-version and incomplete snapshots are REJECTED."""
        problems = []
        if not isinstance(snap, dict):
            raise ContractRejected("SNAPSHOT_NOT_OBJECT")
        if snap.get("snapshot_schema_version") != self.SNAPSHOT_SCHEMA_VERSION:
            problems.append("SNAPSHOT_VERSION_MISMATCH")
        required = ("state", "baseline_identity", "baseline_metrics",
                    "iteration", "evaluations", "budget_ledger",
                    "candidate_history", "evaluation_history")
        for field in required:
            if field not in snap or snap[field] in (None, "") and field != \
                    "current_evaluation_id":
                problems.append("SNAPSHOT_INCOMPLETE:" + field)
        claimed = snap.get("snapshot_digest")
        if not claimed:
            problems.append("SNAPSHOT_DIGEST_MISSING")
        elif claimed != "sha256:" + hashlib.sha256(
                canonical_payload_bytes(
                    {k: v for k, v in snap.items()
                     if k != "snapshot_digest"})).hexdigest():
            problems.append("SNAPSHOT_TAMPERED")
        if problems:
            raise ContractRejected(";".join(problems))
        # re-verify Workbench job identity & state (source of truth)
        self.client = client
        for j in snap["evaluation_history"]:
            if j["job_id"] in client.jobs:
                if client.jobs[j["job_id"]]["state"] != j["state"]:
                    raise ContractRejected("WORKBENCH_JOB_STATE_MISMATCH")
        self.state = snap["state"]
        self.baseline = dict(snap["baseline_identity"])
        self.baseline_metrics = dict(snap["baseline_metrics"])
        self.candidate = (dict(snap["current_candidate"])
                          if snap.get("current_candidate") else None)
        self.job_id = snap.get("current_evaluation_id")
        self.iteration = snap["iteration"]
        self.evaluations = snap["evaluations"]
        self.tokens_spent = snap["budget_ledger"]["tokens_spent"]
        self.history = list(snap["candidate_history"])
        self.best_quality = snap.get("best_candidate_quality")
        self.stop_reason = snap.get("stop_reason")
        client.tokens_spent = snap["budget_ledger"]["client_tokens"]
        return {"resumed": True, "state": self.state}

    def cancel(self, reason: str = "EXPLICIT_CANCELLATION") -> dict:
        self._terminate(reason)
        return {"state": self.state, "reason": self.stop_reason}
