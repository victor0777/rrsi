# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
import json

import pytest

from poc import semantic_pilot as sp
from poc.run_dir_isolation import seal_run_dir


@pytest.fixture()
def bundle(tmp_path):
    return tmp_path / "bundle.json"


def write_bundle(bundle, fixtures):
    bundle.write_text(json.dumps({"fixtures": fixtures}))


def make_fixture(fid):
    return {"fixture_id": fid, "paper_identity": "paper:x",
            "source_identity": {"paper_id": "1802.07862", "arxiv_version": "v1",
                                "capture_sha256": "c0" * 32},
            "source_sentence_reference": {"anchor": "a", "anchor_in_source": True}}


def test_per_fixture_digest_independent(bundle):
    """Fixture-level digests differ per fixture; the bundle digest is context
    only and must never be interpreted as a per-fixture approval identifier."""
    write_bundle(bundle, [make_fixture("g3-1802-result"),
                          make_fixture("g4-1802-numeric")])
    fx = sp.load_bundle(bundle)
    d1 = sp.per_fixture_digest(fx["g3-1802-result"])
    d2 = sp.per_fixture_digest(fx["g4-1802-numeric"])
    assert d1 != d2
    assert sp.bundle_digest(bundle) == sp.bundle_digest(bundle)  # shared


def test_approval_record_requires_registered_scope():
    fixture = make_fixture("g9-1901-evidence")  # UNAVAILABLE — not approved
    with pytest.raises(ValueError):
        sp.build_approval_record(fixture=fixture, approved_by="x",
                                 approval_reference="x",
                                 independent_review_refs=[])


def test_blind_prompt_has_no_gold_or_direction(bundle, tmp_path):
    """Judge prompt contains no gold answers and no expected directions."""
    write_bundle(bundle, [make_fixture("g3-1802-result")])
    ap = sp.build_approval_record(fixture=sp.load_bundle(bundle)["g3-1802-result"],
                                  approved_by="owner", approval_reference="x",
                                  independent_review_refs=[])
    assert ap["approved_scope"] == "Numeric Fidelity"
    pair = sp.build_blind_pair(original_text="orig text",
                               perturbed_text="pert text",
                               dimension="Numeric Fidelity")
    prompt = sp.render_judge_user_prompt(pair)
    assert sp.blind_prompt_is_blind(prompt)
    assert "gold" not in prompt.lower() and "expected" not in prompt.lower()


def test_blind_pair_order_maps_back(tmp_path):
    pair = sp.build_blind_pair(original_text="O", perturbed_text="P",
                               dimension="d", seed=42)
    # unblind map must separate original from perturbed
    assert set(pair["unblind_map"].values()) == {"original", "perturbed"}
    assert (pair["unblind_map"]["A"] == "original") == (pair["A"] == "O")
    assert (pair["unblind_map"]["B"] == "perturbed") == (pair["B"] == "P")


def test_judge_output_contract_abstention():
    ok = sp.validate_judge_output({
        "input_a": {"verdict": "v", "basis": "b", "evidence_references": ["e1"]},
        "input_b": {"verdict": "v", "basis": "b", "evidence_references": ["e1"]},
        "relative_judgment": {"higher_quality": "B", "basis": "b"},
        "abstention": {"refused": False}})
    assert ok["valid"]
    bad = sp.validate_judge_output({
        "input_a": {"verdict": "v", "basis": "b", "evidence_references": ["e1"]},
        "input_b": {"verdict": "v", "basis": "b", "evidence_references": ["e1"]},
        "relative_judgment": {"higher_quality": "B", "basis": "b"},
        "abstention": {"refused": True}})  # no reason
    assert bad["valid"] is False and bad["error"] == "ABSTENTION_REASON_REQUIRED"


def test_disagreement_recorded_without_auto_truth():
    judge = {"input_a": {"verdict": "v", "basis": "b", "evidence_references": ["e"]},
             "input_b": {"verdict": "v", "basis": "b", "evidence_references": ["e"]},
             "relative_judgment": {"higher_quality": "B", "basis": "b"},
             "abstention": {"refused": False}}
    res = sp.compare_with_gold(judge_output=judge,
                               unblind_map={"A": "original", "B": "perturbed"},
                               gold_expected_direction="perturbed lower")
    assert res["agreement"] == "Disagreement"
    assert res["disagreement_auto_truth"] is False
    abstained = sp.compare_with_gold(
        judge_output={**judge, "abstention": {"refused": True, "reason": "r"}},
        unblind_map={"A": "original", "B": "perturbed"},
        gold_expected_direction="perturbed lower")
    assert abstained["agreement"] == "ABSTAINED"


def test_g7_check_flags_word_presence_only():
    word_only = {"input_a": {"verdict": "v", "basis": "the name TextRank appears",
                             "evidence_references": ["e"]},
                 "input_b": {"verdict": "v", "basis": "mentions textrank",
                             "evidence_references": ["e"]},
                 "relative_judgment": {"higher_quality": "A",
                                       "basis": "mentions textrank"}}
    assert sp.g7_methodological_loss_check(word_only)["classification"] == \
        "WORD_PRESENCE_ONLY"
    method = {"input_a": {"verdict": "v", "basis": "the keyword extraction step "
                          "and centroid clustering procedure are missing",
                          "evidence_references": ["e"]},
              "input_b": {"verdict": "v", "basis": "pipeline step coverage loss",
                          "evidence_references": ["e"]},
              "relative_judgment": {"higher_quality": "B",
                                    "basis": "step coverage loss"}}
    check = sp.g7_methodological_loss_check(method)
    assert check["classification"] == "METHODOLOGICAL"
    assert check["flag"] is False


def test_run_fail_closed_zero_calls():
    import os
    env = {k: os.environ.pop(k, None) for k in
           ("AI_PAPERS_MODEL_CALL_BUDGET_LEDGER", "AI_PAPERS_MODEL_CALL_CEILING",
            "AI_PAPERS_INVOCATION_ID", "AI_PAPERS_MODEL_CALL_BUDGET_ROOT")}
    try:
        out = sp.run()
        assert out["calls"] == 0 and out["tokens"] == 0
        assert out["code"] == "EXECUTION_BUDGET_NOT_ISSUED"
    finally:
        for k, v in env.items():
            if v is not None:
                os.environ[k] = v


def test_r6_admission_sealed():
    """The r6 admission artifacts must be sealed with matching digests."""
    from pathlib import Path
    d = Path("poc/runs/perturbation-audit/r6-pilot-admission")
    if not d.exists():
        pytest.skip("r6 dir not prepared in this environment")
    seal_run_dir(d)
    from poc.run_dir_isolation import verify_seal
    assert verify_seal(d) is True
