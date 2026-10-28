# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Unit tests for the deterministic perturbation evaluators."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from poc.perturbation_eval import (  # noqa: E402
    designated_numeric_consistency,
    extract_numbers,
    reference_integrity,
)


# unit-aware normalization: "10K" == "10000" (QASPER gold "10000" case)
def test_unit_aware_number_match():
    assert designated_numeric_consistency(
        "the dataset is 10K pairs", "the dataset is 10K pairs", "10,000"
    )["consistent"] is True


# perturbed value absent from source -> inconsistent
def test_perturbed_value_detected():
    r = designated_numeric_consistency(
        "vocab size of 15,733 tokens", "vocab size of 15,733 tokens", "15,800"
    )
    assert r["consistent"] is False
    assert r["literal_in_source"] is False


# strict-literal would false-positive the original: documented limitation
def test_literal_false_positive_avoided():
    r = designated_numeric_consistency(
        "comprising 10,000 pairs", "composed of 10K pairs", "10,000"
    )
    assert r["literal_in_source"] is False and r["consistent"] is True


# reference integrity: dangling artifact id detected
def test_dangling_reference_detected():
    r = reference_integrity("see artifact: `fig0009`", {"fig0001", "tbl0001"})
    assert r["intact"] is False and "fig0009" in r["broken_references"]


# intact references pass
def test_intact_reference_pass():
    r = reference_integrity("artifact: `fig0001`, `tbl0001`", {"fig0001", "tbl0001"})
    assert r["intact"] is True and r["broken_references"] == []


# extract_numbers: years and values normalize deterministically
def test_extract_numbers():
    assert 10000 in extract_numbers("10K and 10,000 pairs")
    assert 15733 in extract_numbers("15,733 tokens")
