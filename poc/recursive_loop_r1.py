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
        req = {
            "baseline_identity": dict(self.baseline),
            "candidate_identity": {
                "candidate_id": self.candidate["candidate_id"],
                "candidate_digest": self.candidate["candidate_digest"]},
            "evaluation_evidence": [h for h in self.history
                                    if h["candidate_id"] ==
                                    self.candidate["candidate_id"]],
            "quality_delta": self.history[-1]["token_cost"] * 0 + (
                self.best_quality - self.baseline_metrics["answer_quality"]),
            "cost_delta_tokens": self.tokens_spent,
            "regression_summary": "none observed in approved axes",
            "evaluation_policy_version": self.client.policy_version,
            "residual_risks": residual_risks,
            "rollback_plan": rollback_plan,
            "status": "PENDING_OWNER_APPROVAL"}
        self.promotion_requests.append(req)
        self.state = "PROMOTION_PROPOSED"
        return req

    # -- resume: state, history and budget preserved --
    def snapshot(self) -> dict:
        return {"state": self.state, "iteration": self.iteration,
                "evaluations": self.evaluations,
                "tokens_spent": self.tokens_spent,
                "client_tokens": (self.client.tokens_spent if self.client
                                  else 0),
                "history": self.history,
                "baseline": self.baseline,
                "best_quality": self.best_quality,
                "stop_reason": self.stop_reason}

    def resume(self, snap: dict, *, client: MockWorkbenchClient) -> dict:
        self.state = snap["state"]
        self.iteration = snap["iteration"]
        self.evaluations = snap["evaluations"]
        self.tokens_spent = snap["tokens_spent"]
        self.history = list(snap["history"])
        self.baseline = snap["baseline"]
        self.best_quality = snap["best_quality"]
        self.stop_reason = snap["stop_reason"]
        self.baseline_metrics = self.baseline_metrics  # rebound by owner
        self.client = client
        client.tokens_spent = snap["client_tokens"]
        return {"resumed": True, "state": self.state}

    def cancel(self, reason: str = "EXPLICIT_CANCELLATION") -> dict:
        self._terminate(reason)
        return {"state": self.state, "reason": self.stop_reason}
