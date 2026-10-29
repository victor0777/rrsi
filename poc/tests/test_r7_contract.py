# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""R7-D2 static contract tests (§A3) — zero model calls; approved
Development Fixtures only (R6I g4/g7 texts as synthetic basis)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RRSI_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RRSI_ROOT))
sys.path.insert(0, "/home/ktl/projects/ai_papers/src")

from poc.r7_contract import (  # noqa: E402
    JUDGE_SCHEMA_VERSION, PIPELINE_ROLES, VERIFICATION_EVIDENCE_FIELDS,
    INFO_LOSS_ANCHOR_ROLES, markdown_normalize, resolve_claim_evidence,
    sha256, validate_anchor, validate_claim, validate_judge_output,
    verify_absence, verify_info_loss,
)

# synthetic development texts (from approved R6I fixture content)
ORIGINAL = ("The SnapCaptions dataset comprises 10,000 user-generated "
            "image-caption pairs. Captions average 30.7 characters in "
            "length, with a vocabulary size of **15,733** tokens. The "
            "first algorithmic step involves extracting keywords from "
            "the input document using the TextRank algorithm.")
PERTURBED = ("The SnapCaptions dataset comprises 12,000 user-generated "
             "image-caption pairs. Captions average 30.7 characters in "
             "length, with a vocabulary size of **15,733** tokens.")
SOURCE = ("This paper presents the SnapCaptions dataset and a modality "
          "attention model. TextRank keyword extraction is a mandatory "
          "pipeline step of the proposed method.")
DOCS = {"orig": ORIGINAL, "pert": PERTURBED, "source": SOURCE}


def d(doc_id: str, text: str, role: str, quote: str,
      policy: str = "byte_exact", **kw) -> dict:
    return {"document_id": doc_id, "document_digest": sha256(text),
            "document_role": role, "locator": "para:0",
            "quote": quote, "match_policy": policy, **kw}


def info_loss_claim(**anchor_overrides) -> dict:
    anchors = [
        d("orig", ORIGINAL, "original_note",
          "The first algorithmic step involves extracting keywords from "
          "the input document using the TextRank algorithm.",
          "markdown_normalized", anchor_role="original_note_anchor"),
        d("pert", PERTURBED, "perturbed_note",
          "Captions average 30.7 characters in length,",
          "byte_exact", anchor_role="absence_evidence"),
        d("source", SOURCE, "source_paper",
          "TextRank keyword extraction is a mandatory pipeline step",
          "semantic_review",
          anchor_role="importance_evidence"),
    ]
    for i, ov in enumerate(anchor_overrides.pop("replace", [])):
        anchors[i] = ov
    for role in anchor_overrides.pop("drop_roles", []):
        anchors = [a for a in anchors if a["anchor_role"] != role]
    return {"claim_id": "c-loss-1", "kind": "info_loss",
            "target_note": "pert", "anchors": anchors}


# ------------------------- §A3 static test matrix ---------------------------
def test_valid_numeric_error_claim():
    c = {"claim_id": "c-num-1", "kind": "numeric_error", "target_note": "pert",
         "anchors": [d("pert", PERTURBED, "perturbed_note",
                       "comprises 12,000 user-generated image-caption pairs")]}
    r = validate_claim(c, DOCS)
    assert r["valid"] and r["verification_status"] == "VERIFIED"


def test_valid_partial_info_loss_claim():
    r = validate_claim(info_loss_claim(), DOCS)
    assert r["valid"], r["problems"]
    # the importance anchor is semantic_review — never machine-decided
    assert r["verification_status"] == "PENDING_HUMAN_REVIEW"


def test_fabricated_loss_claim_fails():
    # info quoted nowhere: original note does not contain it
    bad = info_loss_claim(replace=[
        d("orig", ORIGINAL, "original_note",
          "The model was trained for 300 epochs on the full corpus.",
          "byte_exact", anchor_role="original_note_anchor")])
    r = validate_claim(bad, DOCS)
    assert not r["valid"]
    assert r["verification_status"] == "FAILED"
    assert any("QUOTE_ABSENT" in p for a in r["anchor_results"]
               for p in a["problems"])


def test_info_still_present_elsewhere_pending_human_review():
    # original info lexically present elsewhere in the perturbed note
    pert = PERTURBED + " TextRank supplies the keyword centroids."
    r = verify_absence(claim=info_loss_claim(), original_note=ORIGINAL,
                       perturbed_note=pert)
    assert r["local_evidence"]["verified"] is True
    assert r["verification_status"] == "PENDING_HUMAN_REVIEW"
    assert any(v > 0 for v in
               r["global_absence"]["lexical_hits"].values())


def test_wrong_locator_quote_absent():
    c = {"claim_id": "c-num-2", "kind": "numeric_error", "target_note": "orig",
         "anchors": [d("orig", ORIGINAL, "original_note",
                       "vocabulary size of 99,999 tokens")]}
    r = validate_claim(c, DOCS)
    assert not r["valid"]


def test_document_digest_mismatch_fail_closed():
    a = d("orig", "DIFFERENT TEXT", "original_note",
          "10,000 user-generated image-caption pairs")
    r = validate_anchor(a, DOCS)
    assert r["verification_status"] == "FAILED"
    assert any("DOCUMENT_DIGEST_MISMATCH" in p for p in r["problems"])


def test_markdown_normalized_quote_match():
    a = d("orig", ORIGINAL, "original_note",
          "vocabulary size of 15,733 tokens", "markdown_normalized")
    r = validate_anchor(a, DOCS)
    assert r["verification_status"] == "VERIFIED"  # '**15,733**' matched


def test_missing_required_anchor_fail_closed():
    # drop importance_evidence anchor
    c = info_loss_claim(drop_roles=["importance_evidence"])
    r = validate_claim(c, DOCS)
    assert not r["valid"]
    assert any("REQUIRED_ANCHOR_MISSING:importance_evidence" in p
               for p in r["problems"])
    # roles documented
    assert set(INFO_LOSS_ANCHOR_ROLES) == {"original_note_anchor",
                                           "absence_evidence",
                                           "importance_evidence"}


def test_absence_never_verified_by_string_absence_alone():
    r = verify_absence(claim=info_loss_claim(), original_note=ORIGINAL,
                       perturbed_note=PERTURBED)
    assert r["local_evidence"]["verified"] is True  # local pass
    # global absence still requires human review even with zero lexical hits
    assert all(v == 0 for v in
               r["global_absence"]["lexical_hits"].values())
    assert r["global_absence"]["conclusion"] == "PENDING_HUMAN_REVIEW"
    assert r["verification_status"] == "PENDING_HUMAN_REVIEW"


# ---------------- §A/B pipeline separation tests (staged architecture) -------
def judge_output(**overrides) -> dict:
    out = {
        "relative": "A", "a_verdict": "VALID", "b_verdict": "INVALID",
        "claims": [{
            "claim_id": "c-1", "kind": "numeric_error",
            "target_side": "B", "claim_text": "12,000 should be 10,000",
            "observed_evidence_refs": ["e-1"]}],
        "evidence_refs": ["e-1"], "abstention": False,
        "schema_version": JUDGE_SCHEMA_VERSION,
    }
    out.update(overrides)
    return out


def test_judge_output_v03_valid():
    r = validate_judge_output(judge_output())
    assert r["valid"], r["problems"]
    assert len(r["claims"]) == 1


def test_judge_output_forbidden_fields_rejected():
    # judge must not assert source importance or verification status
    out = judge_output(claims=[{
        "claim_id": "c-1", "kind": "numeric_error", "target_side": "B",
        "claim_text": "x", "observed_evidence_refs": ["e-1"],
        "importance_evidence": "from source paper",
        "verification_status": "VERIFIED"}])
    r = validate_judge_output(out)
    assert not r["valid"]
    assert any("JUDGE_FORBIDDEN_FIELD" in p for p in r["problems"])


def test_judge_abstention_requires_undecidable():
    r = validate_judge_output(judge_output(abstention=True))
    assert not r["valid"]
    assert any("ABSTENTION_REQUIRES_UNDECIDABLE" in p for p in r["problems"])


def test_pipeline_role_permission_matrix():
    # judge denied source/gold/truth; resolver locator-only; adjudicator all
    assert PIPELINE_ROLES["SemanticJudge"]["source_paper"] == "denied"
    assert PIPELINE_ROLES["SemanticJudge"]["gold"] == "denied"
    assert PIPELINE_ROLES["SemanticJudge"]["perturbation_truth"] == "denied"
    assert PIPELINE_ROLES["EvidenceResolver"]["source_paper"] == \
        "locator-check only"
    assert PIPELINE_ROLES["ClaimVerifier"]["source_paper"] == "allowed"
    assert PIPELINE_ROLES["ClaimVerifier"]["gold"] == "denied"
    assert PIPELINE_ROLES["GoldAdjudicator"]["gold"] == "allowed"


def test_resolver_unresolved_ref_fail_closed():
    claim = judge_output()["claims"][0]
    r = resolve_claim_evidence(claim, {"c-1": {}}, DOCS)  # empty ref table
    assert any("UNRESOLVED_REF" in p for p in r["problems"])
    assert r["verification_evidence"] == []


def test_resolver_digest_bound_record():
    claim = judge_output()["claims"][0]
    refs = {"c-1": {"e-1": d("pert", PERTURBED, "perturbed_note",
                              "comprises 12,000 user-generated")}}
    r = resolve_claim_evidence(claim, refs, DOCS)
    assert r["problems"] == []
    rec = r["verification_evidence"][0]
    assert set(VERIFICATION_EVIDENCE_FIELDS) <= set(rec)
    assert rec["verification_status"] == "VERIFIED"


def test_info_loss_three_evidence_full_chain():
    r = verify_info_loss(
        claim_id="c-loss-1",
        original_note_anchor=d("orig", ORIGINAL, "original_note",
                               "The first algorithmic step involves "
                               "extracting keywords from the input "
                               "document using the TextRank algorithm.",
                               "markdown_normalized"),
        absence_evidence=d("pert", PERTURBED, "perturbed_note",
                           "Captions average 30.7 characters in length,"),
        source_importance=d("source", SOURCE, "source_paper",
                            "TextRank keyword extraction is a mandatory "
                            "pipeline step", "semantic_review"),
        documents=DOCS, original_note=ORIGINAL, perturbed_note=PERTURBED,
        human_review=False)
    assert r["evidence_original_note"]["verification_status"] == "VERIFIED"
    assert r["evidence_perturbed_absence"]["local_absence"] is True
    assert r["verification_status"] == "PENDING_HUMAN_REVIEW"  # no review


def test_info_loss_verified_with_recorded_human_review():
    r = verify_info_loss(
        claim_id="c-loss-1",
        original_note_anchor=d("orig", ORIGINAL, "original_note",
                               "The first algorithmic step involves "
                               "extracting keywords from the input "
                               "document using the TextRank algorithm.",
                               "markdown_normalized"),
        absence_evidence=d("pert", PERTURBED, "perturbed_note",
                           "Captions average 30.7 characters in length,"),
        source_importance=d("source", SOURCE, "source_paper",
                            "TextRank keyword extraction is a mandatory "
                            "pipeline step", "semantic_review"),
        documents=DOCS, original_note=ORIGINAL, perturbed_note=PERTURBED,
        human_review=True)
    assert r["verification_status"] == "VERIFIED"
    assert r["record"]["human_review_recorded"] is True


def test_info_loss_info_present_elsewhere_never_machine_verified():
    # same info remains elsewhere in the perturbed note → even with a
    # recorded human review, VERIFIED is forbidden (global absence fails)
    pert = PERTURBED + " TextRank supplies the keyword centroids."
    r = verify_info_loss(
        claim_id="c-loss-1",
        original_note_anchor=d("orig", ORIGINAL, "original_note",
                               "The first algorithmic step involves "
                               "extracting keywords from the input "
                               "document using the TextRank algorithm.",
                               "markdown_normalized"),
        absence_evidence=d("pert", PERTURBED, "perturbed_note",
                           "Captions average 30.7 characters in length,"),
        source_importance=d("source", SOURCE, "source_paper",
                            "TextRank keyword extraction is a mandatory "
                            "pipeline step", "semantic_review"),
        documents=DOCS, original_note=ORIGINAL, perturbed_note=pert,
        human_review=True)
    assert r["evidence_perturbed_absence"][
        "global_absence_machine_confirmed"] is False
    assert r["verification_status"] == "PENDING_HUMAN_REVIEW"


def test_info_loss_fabricated_anchor_fail_closed():
    r = verify_info_loss(
        claim_id="c-fab",
        original_note_anchor=d("orig", ORIGINAL, "original_note",
                               "The model was trained for 300 epochs.",
                               "byte_exact"),
        absence_evidence=d("pert", PERTURBED, "perturbed_note",
                           "Captions average 30.7 characters in length,"),
        source_importance=d("source", SOURCE, "source_paper",
                            "TextRank keyword extraction", "semantic_review"),
        documents=DOCS, original_note=ORIGINAL, perturbed_note=PERTURBED,
        human_review=True)
    assert r["verification_status"] == "FAILED"  # QUOTE_ABSENT fail-closed
