# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Tests for the R0-b calibration budget policy change (model-free)."""

from __future__ import annotations

import pytest

from poc.budget_policy import (
    BLOCKING_DIMENSIONS,
    BUDGET_POLICY,
    BudgetExceeded,
    LEDGER,
    METERED_TOKEN_FIELDS,
    assert_concurrency,
    assert_no_retry,
    assert_paid_api_cap,
    assert_within_budget,
    check_prestart,
    gpu_hours_sum,
)


def test_token_ceiling_is_abolished_but_metering_kept():
    assert BUDGET_POLICY["token_ceiling"] is None
    assert METERED_TOKEN_FIELDS == ("tokens_input", "tokens_output", "tokens_total")


def test_ledger_retained_with_token_blocking_disabled_only():
    assert LEDGER["retained"] is True
    assert LEDGER["blocking_disabled"] == ["token_ceiling"]
    assert set(LEDGER["blocking_kept"]) == set(BLOCKING_DIMENSIONS)


def test_prestart_token_estimate_never_blocks():
    # 5M tokens would have blocked under the old 3M ceiling; now it is metering only.
    ok, reasons = check_prestart({"tokens_total": 5_000_000, "model_calls": 20,
                                  "wall_clock_minutes": 25, "gpu_hours": 0.3})
    assert ok and reasons == []


def test_prestart_blocking_dimensions_still_block():
    ok, reasons = check_prestart({"model_calls": 51, "wall_clock_minutes": 10,
                                  "gpu_hours": 0.1})
    assert not ok and reasons == ["OVER_CAP:model_calls"]

    ok, reasons = check_prestart({"wall_clock_minutes": 10, "gpu_hours": 0.1})
    assert not ok and reasons == ["MISSING_ESTIMATE:model_calls"]


def test_fail_closed_kept_on_time_calls_gpu():
    for dim, value in [("wall_clock_minutes", 31), ("model_calls", 51),
                       ("gpu_hours", 0.51)]:
        record = {"tokens_total": 1000, dim: value}
        with pytest.raises(BudgetExceeded, match=dim):
            assert_within_budget(record)


def test_fail_closed_on_missing_token_metering():
    with pytest.raises(BudgetExceeded, match="TOKEN_METERING_ABSENT"):
        assert_within_budget({"model_calls": 1, "wall_clock_minutes": 1,
                              "gpu_hours": 0.01})


def test_no_auto_retry_and_single_concurrency():
    with pytest.raises(BudgetExceeded, match="AUTO_RETRY"):
        assert_no_retry(1)
    with pytest.raises(BudgetExceeded, match="CONCURRENCY"):
        assert_concurrency(2)


def test_gpu_hours_sums_across_gpus_and_separate_from_wall_clock():
    # Two GPUs, 20 min each, concurrent: 0.667 GPU-h but 20 min wall-clock.
    assert gpu_hours_sum([1200.0, 1200.0]) == pytest.approx(2 / 3)
    assert BUDGET_POLICY["gpu_hours"] != BUDGET_POLICY["wall_clock_minutes"]


def test_paid_api_requires_separate_cost_cap():
    assert_paid_api_cap("local", None)                       # free: no cap needed
    assert_paid_api_cap("remote-paid", cost_cap=5.0)         # registered: fine
    with pytest.raises(BudgetExceeded, match="PAID_API_CAP_UNREGISTERED"):
        assert_paid_api_cap("remote-paid", None)
