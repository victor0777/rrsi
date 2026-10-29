# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Offline regression tests for the R6I corrected semantic pilot (model-free:
no network model calls; the ledger tests use the official API on a temp
budget root only)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

RRSI_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RRSI_ROOT))
sys.path.insert(0, "/home/ktl/projects/ai_papers/src")

from poc.semantic_pilot_r6i import (  # noqa: E402
    G7_CATEGORIES, MAX_MODEL_CALLS, MAX_OUTPUT_TOKENS, MAX_RESERVATION_ORDINALS,
    MAX_TOTAL_TOKENS, SYSTEM_PROMPT_V2, WORK_ROOT, adjudicate_response,
    render_v2_user_prompt, validate_v2_output, verify_g7_claims_vs_full_note,
    verify_owner_approval_record,
)
from poc.semantic_pilot_r6_recovery import (  # noqa: E402
    apply_excerpt_policy,
)
from poc.semantic_pilot import build_blind_pair  # noqa: E402

PERTURBED_G7 = RRSI_ROOT / "poc/runs/perturbation-audit/r2-semantic/p5-1901-method-removed.md"
PERTURBED_G4 = RRSI_ROOT / "poc/runs/perturbation-audit/r1/p2-1802-size.md"
NOTES_1802 = RRSI_ROOT / "poc/runs/qasper-reader-note-r1/reader/1802.07862/02_reading_chain/output/04_reader_note.en.md"
G4_NOTE_REGEX = r"10,000|10K|12,000|dataset comprises"


def g4_manifest() -> dict:
    orig = apply_excerpt_policy(NOTES_1802.read_text(), G4_NOTE_REGEX)
    pert = apply_excerpt_policy(PERTURBED_G4.read_text(), G4_NOTE_REGEX)
    pair = build_blind_pair(original_text=orig["excerpt"],
                            perturbed_text=pert["excerpt"],
                            dimension="Normalized Numeric Fidelity")
    return {"fixture_id": "g4-1802-numeric",
            "dimension": "Normalized Numeric Fidelity",
            "pair": {"A_text": pair["A"], "B_text": pair["B"],
                     "unblind_map": pair["unblind_map"]}}


VALID = json.dumps({
    "relative": "B", "reason": "", "a_verdict": "high", "b_verdict": "low",
    "ev_a": ["10,000 user-generated image-caption pairs"],
    "ev_b": ["comprises 12,000 pairs"]})


# ------------------------------- §A.2/§A.3 — statuses -----------------------
def test_valid_agreement_and_disagreement():
    rec = g4_manifest()
    perturbed_slot = next(s for s, k in
                          rec["pair"]["unblind_map"].items() if k == "perturbed")
    losing = json.loads(VALID.replace('"relative": "B"',
                                      f'"relative": "{perturbed_slot}"'))
    res = adjudicate_response(fid="g4-1802-numeric",
                              raw=json.dumps(losing), rec=rec,
                              full_perturbed_note=PERTURBED_G4.read_text())
    assert res["result_status"] == "DISAGREEMENT"
    assert res["gold_agreement"]["agreement"] == "Disagreement"
    other = next(s for s in ("A", "B") if s != perturbed_slot)
    winning = json.loads(VALID.replace('"relative": "B"',
                                       f'"relative": "{other}"'))
    res = adjudicate_response(fid="g4-1802-numeric",
                              raw=json.dumps(winning), rec=rec,
                              full_perturbed_note=PERTURBED_G4.read_text())
    assert res["result_status"] == "AGREEMENT"
    assert res["gold_agreement"]["agreement"] == "Agreement"


def test_equal_is_disagreement_not_agreement():
    rec = g4_manifest()
    obj = json.loads(VALID.replace('"relative": "B"', '"relative": "equal"'))
    res = adjudicate_response(fid="g4-1802-numeric", raw=json.dumps(obj),
                              rec=rec, full_perturbed_note=PERTURBED_G4.read_text())
    assert res["result_status"] == "DISAGREEMENT"


def test_abstained_status():
    rec = g4_manifest()
    obj = json.loads(VALID)
    obj["relative"] = "abstain"
    obj["reason"] = "source not provided"
    res = adjudicate_response(fid="g4-1802-numeric", raw=json.dumps(obj),
                              rec=rec, full_perturbed_note=PERTURBED_G4.read_text())
    assert res["result_status"] == "ABSTAINED"
    assert res["gold_agreement"]["agreement"] == "ABSTAINED"


def test_parse_failure_and_invalid_schema_forbid_gold():
    rec = g4_manifest()
    res = adjudicate_response(fid="g4-1802-numeric", raw="not json at all {",
                              rec=rec, full_perturbed_note=PERTURBED_G4.read_text())
    assert res["result_status"] == "PARSE_FAILURE"
    assert res["gold_agreement"] is None
    bad = json.loads(VALID)
    bad.pop("ev_a")
    res = adjudicate_response(fid="g4-1802-numeric", raw=json.dumps(bad),
                              rec=rec, full_perturbed_note=PERTURBED_G4.read_text())
    assert res["result_status"] == "INVALID_SCHEMA"
    assert res["gold_agreement"] is None
    bad = json.loads(VALID)
    bad["relative"] = "maybe"
    res = adjudicate_response(fid="g4-1802-numeric", raw=json.dumps(bad),
                              rec=rec, full_perturbed_note=PERTURBED_G4.read_text())
    assert res["result_status"] == "INVALID_SCHEMA"
    bad = json.loads(VALID)
    bad["relative"] = "abstain"  # missing reason
    res = adjudicate_response(fid="g4-1802-numeric", raw=json.dumps(bad),
                              rec=rec, full_perturbed_note=PERTURBED_G4.read_text())
    assert res["result_status"] == "INVALID_SCHEMA"


def test_validate_v2_edges():
    ok = {"relative": "equal", "a_verdict": "medium", "b_verdict": "medium",
          "ev_a": ["x"], "ev_b": ["y"]}
    assert validate_v2_output(ok)["valid"]
    reason = dict(ok, relative="abstain", reason="cannot judge")
    assert validate_v2_output(reason)["valid"]
    assert not validate_v2_output(dict(ok, reason="stray"))["valid"]
    assert not validate_v2_output({"relative": "A"})["valid"]


def test_unblind_map_manifest_reference_matches():
    rec = g4_manifest()
    assert set(rec["pair"]["unblind_map"].items()) >= \
        {next(iter(rec["pair"]["unblind_map"].items()))}
    # the adjudicator must read unblind_map from rec["pair"] (manifest shape)
    res = adjudicate_response(fid="g4-1802-numeric", raw=VALID, rec=rec,
                              full_perturbed_note=PERTURBED_G4.read_text())
    assert res["result_status"] in ("AGREEMENT", "DISAGREEMENT")


# ------------------------------- §B — g7 full-note path ---------------------
def test_g7_claim_verification_pending_human_review():
    res = verify_g7_claims_vs_full_note(judge={"relative": "A"},
                                        full_note=PERTURBED_G7.read_text(),
                                        unblind_map={"A": "original",
                                                     "B": "perturbed"})
    # a loss claim with NO specific omission items stays pending; the P5
    # item (textrank_functional) is genuinely absent while other items
    # (use_functional, mapping, combined score, Sim1/Sim2, results)
    # remain in the full note — partial loss is the true state.
    assert res["claims_loss"] is True
    assert res["missing_items_claimed"] == []
    item_verification = res["item_verification"]
    assert item_verification["textrank_functional"][
        "content_absent_from_full_note"] is True
    assert item_verification["use_functional"][
        "content_absent_from_full_note"] is False
    assert item_verification["initial_sentence_mapping"][
        "content_absent_from_full_note"] is False
    assert res["result_status"] == "PENDING_HUMAN_REVIEW"
    assert res["semantic_success"] is False
    assert res["disagreement_auto_truth"] is False


def test_g7_verification_sufficient_when_core_gone():
    # a loss claim with cited items, none present in the full note
    res = verify_g7_claims_vs_full_note(
        judge={"relative": "A",
               "missing": ["textrank_functional", "use_functional"]},
        full_note="nothing here",
        unblind_map={"A": "original", "B": "perturbed"})
    assert res["result_status"] == "VERIFIED"
    assert res["semantic_success"] is True


def test_g7_no_loss_claim_when_equal():
    res = verify_g7_claims_vs_full_note(judge={"relative": "equal"},
                                        full_note=PERTURBED_G7.read_text(),
                                        unblind_map={"A": "original",
                                                     "B": "perturbed"})
    # equal makes no loss claim: nothing verified as success
    assert res["claims_loss"] is False
    assert res["result_status"] == "PENDING_HUMAN_REVIEW"
    assert res["semantic_success"] is False


def test_g7_adjudication_carries_claim_verification():
    rec = {"fixture_id": "g7-1901-method",
           "dimension": "Partial Required Information Coverage Loss",
           "pair": {"A_text": "A", "B_text": "B",
                    "unblind_map": {"A": "original", "B": "perturbed"}}}
    obj = {"relative": "A", "a_verdict": "high", "b_verdict": "low",
           "ev_a": ["step"], "ev_b": ["tool named"]}
    res = adjudicate_response(fid="g7-1901-method", raw=json.dumps(obj),
                              rec=rec, full_perturbed_note=PERTURBED_G7.read_text())
    assert res["result_status"] == "AGREEMENT"
    assert res["claim_verification"]["result_status"] == "PENDING_HUMAN_REVIEW"
    assert res["semantic_success"] is False


# ------------------------------- §C — approval boundary ---------------------
def test_runner_cannot_self_approve():
    assert verify_owner_approval_record("")["error"] == \
        "OWNER_APPROVAL_REQUIRED"
    assert verify_owner_approval_record("/nonexistent/path.json")[
        "error"].startswith("OWNER_APPROVAL_RECORD_MISSING")
    import poc.run_r6i as run_r6i
    src = Path(run_r6i.__file__).read_text()
    # the launcher must not accept a bare --approve flag
    assert "--approve" not in src.replace("--owner-approval", "")


def test_owner_approval_record_verification(tmp_path, monkeypatch):
    from poc.semantic_pilot_r6i import INVOCATION_ID, OWNER_REGISTRY
    monkeypatch.setattr("poc.semantic_pilot_r6i.OWNER_REGISTRY",
                        tmp_path / "registry.json")
    (tmp_path / "registry.json").write_text(json.dumps(
        {"owners": [{"identity": "owner", "authority": True}]}))
    rec = {"invocation_id": INVOCATION_ID, "approved_by": "owner",
           "approval_reference": "r6i directive"}
    good = tmp_path / "approval.json"
    good.write_text(json.dumps(rec))
    prov = verify_owner_approval_record(str(good))
    assert prov["approval_source"] == "owner-record"
    assert prov["executor_role"].startswith("runner")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({**rec, "invocation_id": "other"}))
    assert verify_owner_approval_record(str(bad))[
        "error"] == "OWNER_APPROVAL_INVOCATION_MISMATCH"


# ------------------------------- §D — budget boundaries ---------------------
def test_budget_constants_and_formula():
    from poc.semantic_pilot_r6_recovery import CHAT_TEMPLATE_MARGIN, \
        MAX_OUTPUT_TOKENS as RES_OUT
    tool_schema_estimate = 96
    formula = lambda p, s: p + s + tool_schema_estimate + CHAT_TEMPLATE_MARGIN
    # manifest-measured inputs (frozen at prepare time)
    for fid in ("g4-1802-numeric", "g7-1901-method"):
        mpath = WORK_ROOT / f"r6i-manifest-{fid}.json"
        if not mpath.exists():
            continue
        measured = json.loads(mpath.read_text())["measured"]
        reserved = formula(measured["prompt_tokens"], measured["system_tokens"])
        assert reserved == sum(measured[k] for k in
                               ("prompt_tokens", "system_tokens",
                                "tool_schema_estimate", "chat_template_margin"))
    assert MAX_OUTPUT_TOKENS == 500  # r6i's own §B constant
    assert RES_OUT == 800            # r6-recovery's separate contract
    assert MAX_MODEL_CALLS * 2 == MAX_RESERVATION_ORDINALS


def test_ledger_official_api_ceiling_boundary(tmp_path, monkeypatch):
    from ai_papers_research.llm.call_budget import (
        model_call_budget_environment, reserve_model_call_from_environment,
        ModelCallBudgetExceededError,
    )
    budget_root = tmp_path / "budget"
    budget_root.mkdir()
    env = model_call_budget_environment(budget_root, invocation_id="t-ceiling",
                                        ceiling=4)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert reserve_model_call_from_environment(call_id="c1") == 1
    assert reserve_model_call_from_environment(call_id="c2") == 2
    assert reserve_model_call_from_environment(call_id="c3") == 3
    assert reserve_model_call_from_environment(call_id="c4") == 4
    with pytest.raises(ModelCallBudgetExceededError):
        reserve_model_call_from_environment(call_id="c5")
    with pytest.raises(ModelCallBudgetExceededError):
        reserve_model_call_from_environment(call_id="c5")  # rejected row keeps ordinal


# ---------------- R6I pre-execution audit P0 (fail-first tests) -------------
def test_issued_permit_passes_assert_authorized(monkeypatch, tmp_path):
    """P0-1: a permit issued by the owner issuer must verify against the
    EXISTING execution_permit contract (no schema weakening)."""
    import poc.owner_issue_permit as issuer
    monkeypatch.setattr("poc.execution_permit.issuance_ledger_path",
                        lambda: tmp_path / "issuance.jsonl")
    issued = issuer.issue_test_only(tmp_root=tmp_path)
    permit_path = Path(issued["permit"])
    # the runner-side check requires the exact bytes to have been issued:
    from poc.execution_permit import register_permit
    register_permit(permit_path, issued_by="test-only registration")
    monkeypatch.setenv("AI_PAPERS_EXECUTION_PERMIT", str(permit_path))
    for k, v in issued["budget_env"].items():
        monkeypatch.setenv(k, v)
    from poc.execution_permit import assert_authorized
    from poc.qasper_fulltext_calibration import DATASET
    verified = assert_authorized(
        workstream="semantic_judge_pilot", call_type="judge_evaluation",
        dataset_sha256=__import__("hashlib")
            .sha256(DATASET.read_bytes()).hexdigest(),
        paper_ids=["1802.07862", "1901.10133"],
        model="qwen38-27b-fp8-vllm-tp1-ktl02",
        endpoint="http://127.0.0.1:8004/v1",
        invocation_id="semjudge-r6i-g4g7")
    assert "PERMIT_BUDGET" in verified["checks"]


def test_issuance_requires_valid_approval_record(monkeypatch, tmp_path):
    """§1 — permit issuance without a valid approval record is refused;
    the record-free path exists only as the isolated test-only function."""
    import poc.owner_issue_permit as issuer
    with pytest.raises(PermissionError):
        issuer.issue(approval_record_path="")
    with pytest.raises(PermissionError):
        issuer.issue(approval_record_path="/nonexistent/record.json")
    # forged approver identity: record exists, authority does not
    from poc.semantic_pilot_r6i import INVOCATION_ID
    monkeypatch.setattr("poc.semantic_pilot_r6i.OWNER_REGISTRY",
                        tmp_path / "registry.json")
    (tmp_path / "registry.json").write_text(json.dumps(
        {"owners": [{"identity": "Hongseok Lee", "authority": True}]}))
    forged = tmp_path / "forged.json"
    forged.write_text(json.dumps({
        "invocation_id": INVOCATION_ID, "approved_by": "mystery-user",
        "approval_reference": "x",
        "scope": issuer.PERMIT_SCOPE, "workstream": "semantic_judge_pilot"}))
    with pytest.raises(PermissionError) as exc:
        issuer.issue(approval_record_path=str(forged))
    assert "OWNER_APPROVAL_AUTHORITY_UNVERIFIED" in str(exc.value)
    # scope mismatch: valid authority, wrong scope
    from poc.owner_issue_permit import PERMIT_SCOPE
    mismatched = tmp_path / "scope.json"
    mismatched.write_text(json.dumps({
        "invocation_id": INVOCATION_ID, "approved_by": "Hongseok Lee",
        "approval_reference": "x",
        "scope": {**PERMIT_SCOPE, "paper_ids": ["0000.00000"]},
        "workstream": "semantic_judge_pilot"}))
    with pytest.raises(PermissionError) as exc:
        issuer.issue(approval_record_path=str(mismatched))
    assert "RECORD_SCOPE_MISMATCH" in str(exc.value)
    # a fully valid record issues
    good = tmp_path / "good.json"
    good.write_text(json.dumps({
        "invocation_id": INVOCATION_ID, "approved_by": "Hongseok Lee",
        "approval_reference": "r6i directive",
        "scope": PERMIT_SCOPE, "workstream": "semantic_judge_pilot"}))
    monkeypatch.setattr("poc.execution_permit.issuance_ledger_path",
                        lambda: tmp_path / "issuance.jsonl")
    monkeypatch.setattr(issuer, "BUDGET_ROOT", tmp_path / "wbudget")
    monkeypatch.setattr(issuer, "PERMIT_PATH", tmp_path / "wpermit.json")
    issued = issuer.issue(approval_record_path=str(good))
    assert Path(issued["permit"]).exists()
    assert issued["issuance"]["event"] == "execution_permit_issued"


def test_g7_partial_loss_claim_verified():
    """§3 — a judge that correctly identifies the PARTIAL loss (TextRank's
    own functional explanation + keyword-extraction body) succeeds even
    though other methodology explanations remain in the full note."""
    rec = {"fixture_id": "g7-1901-method",
           "dimension": "Partial Required Information Coverage Loss",
           "pair": {"A_text": "A", "B_text": "B",
                    "unblind_map": {"A": "original", "B": "perturbed"}}}
    raw = json.dumps({"relative": "A", "a_verdict": "high",
                      "b_verdict": "low",
                      "ev_a": ["step"], "ev_b": ["tool named"],
                      "missing": ["textrank_functional",
                                  "keyword_extraction_body"]})
    res = adjudicate_response(fid="g7-1901-method", raw=raw, rec=rec,
                              full_perturbed_note=PERTURBED_G7.read_text())
    cv = res["claim_verification"]
    assert cv["claims_loss"] is True
    assert cv["result_status"] == "VERIFIED"
    assert cv["semantic_success"] is True
    assert res["result_status"] == "AGREEMENT"  # separate from success
    assert res["semantic_success"] is True


def test_g7_over_claim_rejected():
    """§3 — a judge claiming intact methodology items are also missing is
    never a success."""
    rec = {"fixture_id": "g7-1901-method",
           "dimension": "Partial Required Information Coverage Loss",
           "pair": {"A_text": "A", "B_text": "B",
                    "unblind_map": {"A": "original", "B": "perturbed"}}}
    raw = json.dumps({"relative": "A", "a_verdict": "high",
                      "b_verdict": "low",
                      "ev_a": ["step"], "ev_b": ["tool named"],
                      "missing": ["textrank_functional", "sim1_sim2",
                                  "combined_similarity_score"]})
    res = adjudicate_response(fid="g7-1901-method", raw=raw, rec=rec,
                              full_perturbed_note=PERTURBED_G7.read_text())
    cv = res["claim_verification"]
    assert cv["result_status"] == "OVER_CLAIM_REJECTED"
    assert "sim1_sim2" in cv["over_claimed_items"]
    assert cv["semantic_success"] is False


def test_runner_does_not_issue_permit_itself():
    """P0-2: the execute path must not self-issue/register permits."""
    import poc.run_r6i as run_r6i
    src = Path(run_r6i.__file__).read_text()
    assert "register_permit" not in src, "runner must not register permits"
    import poc.owner_issue_permit as issuer
    isrc = Path(issuer.__file__).read_text()
    assert "register_permit" in isrc, "issuance belongs to the owner issuer"


def test_approval_record_presence_vs_authority(tmp_path):
    """P0-2: a present record with an unregistered approver must be refused:
    existence is not authority."""
    from poc.semantic_pilot_r6i import INVOCATION_ID
    rec = {"invocation_id": INVOCATION_ID, "approved_by": "mystery-user",
           "approval_reference": "x"}
    p = tmp_path / "approval.json"
    p.write_text(json.dumps(rec))
    prov = verify_owner_approval_record(str(p))
    assert prov["record_present"] is True
    assert prov["authority_verified"] is False
    assert prov["error"] == "OWNER_APPROVAL_AUTHORITY_UNVERIFIED"


def test_g7_claims_loss_uses_unblind_map_both_orders():
    """P0-3: no fixed A/B assumption — both blind placements tested.
    A loss claim = the judge rates the ORIGINAL slot higher."""
    full = PERTURBED_G7.read_text()
    for unblind in ({"A": "original", "B": "perturbed"},
                    {"A": "perturbed", "B": "original"}):
        perturbed_slot = next(s for s, k in unblind.items() if k == "perturbed")
        original_slot = next(s for s, k in unblind.items() if k == "original")
        res = verify_g7_claims_vs_full_note(
            judge={"relative": original_slot}, full_note=full,
            unblind_map=unblind)
        assert res["claims_loss"] is True
        res = verify_g7_claims_vs_full_note(
            judge={"relative": perturbed_slot}, full_note=full,
            unblind_map=unblind)
        assert res["claims_loss"] is False


def test_semantic_success_separate_from_verified_status():
    """P0-4: VERIFIED / AGREEMENT / semantic_success are distinct; equal,
    abstain, or no-claim-only never records success."""
    rec = {"fixture_id": "g7-1901-method",
           "dimension": "Partial Required Information Coverage Loss",
           "pair": {"A_text": "A", "B_text": "B",
                    "unblind_map": {"A": "original", "B": "perturbed"}}}
    # equal: no omission claim to verify — never success
    res = adjudicate_response(
        fid="g7-1901-method",
        raw=json.dumps({"relative": "equal", "a_verdict": "high",
                        "b_verdict": "high", "ev_a": ["x"], "ev_b": ["y"]}),
        rec=rec, full_perturbed_note=PERTURBED_G7.read_text())
    assert res["claim_verification"]["result_status"] == "PENDING_HUMAN_REVIEW"
    assert res["claim_verification"]["claims_loss"] is False
    assert res["semantic_success"] is False
    # abstain: never success
    res = adjudicate_response(
        fid="g7-1901-method",
        raw=json.dumps({"relative": "abstain", "reason": "cannot judge",
                        "a_verdict": "low", "b_verdict": "low",
                        "ev_a": ["x"], "ev_b": ["y"]}),
        rec=rec, full_perturbed_note=PERTURBED_G7.read_text())
    assert res["result_status"] == "ABSTAINED"
    assert res["semantic_success"] is False
    # a loss claim that survives full-note verification is the ONLY success
    no_core = "\n\n".join(["plain text without any methodology"]) * 5
    res = adjudicate_response(
        fid="g7-1901-method",
        raw=json.dumps({"relative": "A", "a_verdict": "high",
                        "b_verdict": "low", "ev_a": ["x"], "ev_b": ["y"],
                        "missing": ["textrank_functional"]}),
        rec=rec, full_perturbed_note=no_core)
    assert res["claim_verification"]["result_status"] == "VERIFIED"
    assert res["claim_verification"]["claims_loss"] is True
    assert res["semantic_success"] is True
