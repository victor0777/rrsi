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
    INFO_LOSS_ANCHOR_ROLES, markdown_normalize, check_component_inputs,
    resolve_claim_evidence, sha256, validate_anchor, validate_claim,
    validate_human_review, validate_judge_output, verify_absence,
    verify_info_loss,
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
    # strict allow-list: judge must not assert source importance or
    # verification status — extra fields are rejected outright
    out = judge_output(claims=[{
        "claim_id": "c-1", "kind": "numeric_error", "target_side": "B",
        "claim_text": "x", "observed_evidence_refs": ["e-1"],
        "importance_evidence": "from source paper",
        "verification_status": "VERIFIED"}])
    r = validate_judge_output(out)
    assert not r["valid"]
    assert any("EXTRA_FIELD_FORBIDDEN" in p for p in r["problems"])


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


LOSS_ANCHORS = dict(
    original_note_anchor=d("orig", ORIGINAL, "original_note",
                           "The first algorithmic step involves extracting "
                           "keywords from the input document using the "
                           "TextRank algorithm.", "markdown_normalized"),
    absence_evidence=d("pert", PERTURBED, "perturbed_note",
                       "Captions average 30.7 characters in length,"),
    source_importance=d("source", SOURCE, "source_paper",
                        "TextRank keyword extraction is a mandatory "
                        "pipeline step", "semantic_review"),
)


def loss_call(**kw):
    base = dict(claim_id="c-loss-1", documents=DOCS,
                original_note=ORIGINAL, perturbed_note=PERTURBED,
                source_paper=SOURCE, **LOSS_ANCHORS)
    base.update(kw)
    return verify_info_loss(**base)


def review_record(gav="CONFIRMED", siv="IMPORTANT", digests=None,
                  claim_id="c-loss-1", **overrides):
    rec = {"reviewer_id": "reviewer-1", "claim_id": claim_id,
           "document_digests": digests or {
               "orig": sha256(ORIGINAL), "pert": sha256(PERTURBED),
               "source": sha256(SOURCE)},
           "global_absence_verdict": gav,
           "source_importance_verdict": siv,
           "rationale": "deletion confirmed at mapped position; importance "
                        "confirmed against the source paper",
           "review_scope": "full original + perturbed notes + source paper"}
    rec.update(overrides)
    return rec


def test_info_loss_three_evidence_full_chain():
    r = loss_call()  # no review record → uncertain, never VERIFIED
    assert r["evidence_original_note"]["verification_status"] == "VERIFIED"
    assert r["evidence_perturbed_absence"]["local_absence"] is True
    assert r["verification_status"] == "PENDING_HUMAN_REVIEW"


def test_info_loss_verified_with_structured_review_record():
    r = loss_call(human_review_record=review_record())
    assert r["verification_status"] == "VERIFIED"
    assert r["review_record_validation"]["valid"] is True
    assert r["record"]["human_review_recorded"] is True


# ------------------- §D2A-E negative regression matrix ----------------------
def test_neg1_record_without_verdicts_is_pending():
    # record exists but verdicts missing → PENDING, never VERIFIED
    rec = review_record(gav=None, siv=None)
    assert not validate_human_review(
        rec, claim_id="c-loss-1", documents=DOCS,
        anchor_doc_ids=["orig", "pert", "source"])["valid"]
    r = loss_call(human_review_record=rec)
    assert r["verification_status"] == "PENDING_HUMAN_REVIEW"


def test_neg2_negative_global_absence_verdict_fails():
    r = loss_call(human_review_record=review_record(gav="REFUTED"))
    assert r["verification_status"] == "FAILED"


def test_neg3_uncertain_source_importance_is_pending():
    r = loss_call(human_review_record=review_record(siv="UNCERTAIN"))
    assert r["verification_status"] == "PENDING_HUMAN_REVIEW"


def test_neg4_review_record_digest_mismatch():
    bad_digests = review_record().get("document_digests").copy()
    bad_digests["pert"] = "sha256:deadbeef"
    rec = review_record(digests=bad_digests)
    v = validate_human_review(rec, claim_id="c-loss-1", documents=DOCS,
                              anchor_doc_ids=["orig", "pert", "source"])
    assert any("REVIEW_DIGEST_MISMATCH:pert" in p for p in v["problems"])
    # integrity failure → cannot VERIFY
    r = loss_call(human_review_record=rec)
    assert r["verification_status"] == "PENDING_HUMAN_REVIEW"


def test_neg5_registered_document_text_mismatch_fail_closed():
    # documents registry built from a different perturbed-note version
    docs2 = dict(DOCS, pert=PERTURBED.replace("12,000", "13,000"))
    r = verify_info_loss(claim_id="c-loss-1",
                         **{k: v for k, v in LOSS_ANCHORS.items()},
                         documents=docs2, original_note=ORIGINAL,
                         perturbed_note=PERTURBED, source_paper=SOURCE,
                         human_review_record=review_record())
    assert any("DOCUMENT_VERSION_CONFLICT:perturbed_note" in p
               for p in r["record"]["document_binding_problems"])
    assert r["verification_status"] == "FAILED"


def test_neg6_judge_extra_top_level_field_rejected():
    out = judge_output(gold_verdict="VALID")  # non-allow-list field
    r = validate_judge_output(out)
    assert not r["valid"]
    assert any("EXTRA_FIELD_FORBIDDEN:gold_verdict" in p
               for p in r["problems"])


def test_neg7_evidence_ref_not_in_judge_evidence_list():
    out = judge_output(evidence_refs=[])  # claim refs e-1, list empty
    r = validate_judge_output(out)
    assert not r["valid"]
    assert any("UNKNOWN_EVIDENCE_REF" in p or
               "OBSERVED_EVIDENCE_REFS_REQUIRED" in p
               for p in r["problems"])
    out2 = judge_output(evidence_refs=["e-other"])
    r2 = validate_judge_output(out2)
    assert not r2["valid"]
    assert any("UNKNOWN_EVIDENCE_REF" in p for p in r2["problems"])


def test_neg8_gold_passed_to_judge_boundary_violation():
    r = check_component_inputs("SemanticJudge",
                               {"ab_note": "A/B notes", "gold": "leak!"})
    assert not r["boundary_ok"]
    assert "FORBIDDEN_INPUT:gold" in r["violations"]
    # clean judge input passes
    ok = check_component_inputs("SemanticJudge", {"ab_note": "A/B notes"})
    assert ok["boundary_ok"]
    # resolver source access: locator/digest metadata only
    ok2 = check_component_inputs(
        "EvidenceResolver",
        {"source_paper": {"locator": "para:3", "digest": sha256(SOURCE)}})
    assert ok2["boundary_ok"]
    full = check_component_inputs("EvidenceResolver",
                                  {"source_paper": SOURCE})
    assert not full["boundary_ok"]
    assert any("FORBIDDEN_FULL_TEXT" in v for v in full["violations"])


def test_info_loss_info_present_elsewhere_never_machine_verified():
    # same info remains elsewhere in the perturbed note → even a valid
    # review record cannot VERIFY (machine global absence fails)
    pert = PERTURBED + " TextRank supplies the keyword centroids."
    docs = dict(DOCS, pert=pert)  # registry must match the probed text
    anchors = dict(LOSS_ANCHORS,
                   absence_evidence=d("pert", pert, "perturbed_note",
                                      "Captions average 30.7 characters "
                                      "in length,"))
    rec = review_record(digests={"orig": sha256(ORIGINAL),
                                 "pert": sha256(pert),
                                 "source": sha256(SOURCE)})
    r = loss_call(perturbed_note=pert, documents=docs,
                  human_review_record=rec, **anchors)
    assert r["evidence_perturbed_absence"][
        "global_absence_machine_confirmed"] is False
    assert r["verification_status"] == "PENDING_HUMAN_REVIEW"


def test_info_loss_fabricated_anchor_fail_closed():
    r = loss_call(
        claim_id="c-fab",
        original_note_anchor=d("orig", ORIGINAL, "original_note",
                               "The model was trained for 300 epochs.",
                               "byte_exact"),
        human_review_record=review_record(claim_id="c-fab"))
    assert r["verification_status"] == "FAILED"  # QUOTE_ABSENT fail-closed


def test_judge_strict_validation_types_and_duplicates():
    # duplicate claim ids rejected
    dup = {"claim_id": "c-1", "kind": "numeric_error", "target_side": "B",
           "claim_text": "x", "observed_evidence_refs": ["e-1"]}
    r = validate_judge_output(judge_output(claims=[dup, dict(dup)]))
    assert not r["valid"]
    assert any("DUPLICATE_CLAIM_ID" in p for p in r["problems"])
    # wrong types rejected
    r2 = validate_judge_output(judge_output(abstention=1))
    assert not r2["valid"]
    assert any("ABSTENTION_NOT_BOOLEAN" in p for p in r2["problems"])
    # length limit enforced
    long_c = dict(dup, claim_text="x" * 201)
    r3 = validate_judge_output(judge_output(claims=[long_c]))
    assert not r3["valid"]
    assert any("CLAIM_TEXT_TOO_LONG" in p for p in r3["problems"])
    # abstention requires abstained verdicts
    r4 = validate_judge_output(judge_output(abstention=True,
                                            relative="UNDECIDABLE"))
    assert not r4["valid"]
    assert any("ABSTENTION_REQUIRES_ABSTAINED_VERDICTS" in p
               for p in r4["problems"])
