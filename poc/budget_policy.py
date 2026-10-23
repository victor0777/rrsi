# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""R0-b calibration budget policy (directive: token hard ceiling abolished).

Machine-checkable form of the budget policy change. The ledger (`call_budget`)
is retained unchanged; only its token-ceiling blocking is disabled. Tokens stay
a metering/optimization metric. Fail-closed stops remain on wall-clock time,
model calls, and GPU-hours. Model-free, like r0a_checks.
"""

from __future__ import annotations

# ------------------------------------------------------------ policy constants --

# Version: R0-b calibration scope = 1 paper-trial (initial calibration).
BUDGET_POLICY: dict = {
    "version": "r0b-calibration-budget-v2",
    "supersedes": "R1.1 section 5.2 token cap as applied to R0-b (3M)",
    "token_ceiling": None,          # abolished; metering only
    "paper_trials": 1,              # initial calibration run
    "model_calls": 50,
    "wall_clock_minutes": 30,
    "gpu_hours": 0.5,               # sum across GPUs
    "auto_retries": 0,
    "concurrency": 1,
}

# Dimensions that still fail-closed on overrun (kept per directive items 9, 2-5).
BLOCKING_DIMENSIONS = ("wall_clock_minutes", "model_calls", "gpu_hours")

# Token fields are recorded on every call but never block (directive item 1).
METERED_TOKEN_FIELDS = ("tokens_input", "tokens_output", "tokens_total")

# The ledger survives; only the token hard ceiling is disabled (directive item 8).
LEDGER = {
    "retained": True,
    "blocking_disabled": ["token_ceiling"],
    "blocking_kept": list(BLOCKING_DIMENSIONS),
}


class BudgetExceeded(RuntimeError):
    """Stable fail-closed stop reason; carries the dimension, never a payload."""


# ---------------------------------------------------------------- prestart gate --

def check_prestart(estimates: dict) -> tuple[bool, list[str]]:
    """Pre-start usage check under the new policy.

    Token estimates are recorded only (never a reason to block a trial).
    Every blocking dimension must have an estimate within its cap; missing
    estimates for blocking dimensions still block the start.
    """
    reasons = []
    for dim in BLOCKING_DIMENSIONS:
        if dim not in estimates:
            reasons.append(f"MISSING_ESTIMATE:{dim}")
        elif estimates[dim] > BUDGET_POLICY[dim]:
            reasons.append(f"OVER_CAP:{dim}")
    for field in METERED_TOKEN_FIELDS:
        if field in estimates and estimates[field] < 0:
            reasons.append(f"NEGATIVE_METER:{field}")
    return (not reasons), reasons


# ------------------------------------------------------------- fail-closed stop --

def assert_within_budget(record: dict) -> None:
    """Enforce one completed (or in-flight) call/run against the policy.

    Raises BudgetExceeded on wall-clock, model-call, or GPU-hour overrun.
    Absent token metering is a contract error: usage must keep being recorded.
    """
    for dim in BLOCKING_DIMENSIONS:
        if dim in record and record[dim] > BUDGET_POLICY[dim]:
            raise BudgetExceeded(f"FAIL_CLOSED:{dim}")
    if "tokens_total" not in record:
        raise BudgetExceeded("FAIL_CLOSED:TOKEN_METERING_ABSENT")


def assert_no_retry(attempts: int) -> None:
    """Auto-retry count must stay 0; the first failure is final and reported."""
    if attempts > BUDGET_POLICY["auto_retries"]:
        raise BudgetExceeded("FAIL_CLOSED:AUTO_RETRY")


def assert_concurrency(running: int) -> None:
    if running > BUDGET_POLICY["concurrency"]:
        raise BudgetExceeded("FAIL_CLOSED:CONCURRENCY")


# ------------------------------------------- GPU-hours vs wall-clock separation --

def gpu_hours_sum(per_gpu_seconds: list[float]) -> float:
    """GPU-hours summed across GPUs (multi-GPU runs add, not max).

    GPU-hours measure accelerator occupancy per GPU; wall-clock measures
    elapsed session time. They are recorded as separate fields and never
    derived from each other.
    """
    return sum(per_gpu_seconds) / 3600.0


# ---------------------------------------------------------- external paid API --

# Paid external APIs keep a separate monetary cap (directive item 10). It is
# mandatory whenever a non-local provider is bound; otherwise the policy check
# itself fails closed.
PAID_API_POLICY = {"separate_cost_cap_required": True, "cap_registered": None}


def assert_paid_api_cap(provider: str, cost_cap: float | None) -> None:
    if provider != "local" and cost_cap is None:
        raise BudgetExceeded("FAIL_CLOSED:PAID_API_CAP_UNREGISTERED")
