# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Tests for the independent gold-review approval gate."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from poc.gold_review import (  # noqa: E402
    GoldReviewBlocked,
    approval_state,
    record_review,
)

COND = ("source_identity_match", "source_context_sufficient",
        "claim_evidence_relation_verified", "perturbation_semantic_defect_confirmed",
        "expected_direction_verified")
FULL = {c: True for c in COND}


def _fixture(tmp_path):
    f = tmp_path / "fixture.json"
    f.write_text('{"fixture_id": "g1"}')
    return f


# author path can never approve
def test_self_approval_refused(tmp_path):
    with pytest.raises(GoldReviewBlocked) as e:
        record_review(fixture_path=_fixture(tmp_path), reviewer="gen",
                      reviewer_role="author", decision="Approve", comment="",
                      conditions=FULL, out_path=tmp_path / "r.jsonl")
    assert "SELF_APPROVAL_REFUSED" in e.value.code


# approval requires all five conditions
def test_incomplete_conditions_refused(tmp_path):
    with pytest.raises(GoldReviewBlocked) as e:
        record_review(fixture_path=_fixture(tmp_path), reviewer="ind",
                      reviewer_role="independent", decision="Approve", comment="",
                      conditions={"source_identity_match": True},
                      out_path=tmp_path / "r.jsonl")
    assert "APPROVAL_CONDITIONS_INCOMPLETE" in e.value.code


# needs revision records are allowed with partial conditions
def test_needs_revision_allowed(tmp_path):
    record_review(fixture_path=_fixture(tmp_path), reviewer="ind",
                  reviewer_role="independent", decision="Needs Revision",
                  comment="context too short", conditions={}, out_path=tmp_path / "r.jsonl")
    assert approval_state(_fixture(tmp_path), tmp_path / "r.jsonl")["state"] == "NEEDS_REVISION"


# valid independent approval -> APPROVED
def test_valid_approval(tmp_path):
    record_review(fixture_path=_fixture(tmp_path), reviewer="independent-reviewer-1",
                  reviewer_role="independent", decision="Approve", comment="ok",
                  conditions=FULL, out_path=tmp_path / "r.jsonl")
    assert approval_state(_fixture(tmp_path), tmp_path / "r.jsonl")["state"] == "APPROVED"


# no records -> HUMAN_REVIEW_REQUIRED
def test_no_records_state(tmp_path):
    assert approval_state(_fixture(tmp_path), tmp_path / "absent.jsonl")["state"] == \
        "HUMAN_REVIEW_REQUIRED"
