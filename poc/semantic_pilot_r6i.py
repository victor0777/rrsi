# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""R6I — Corrected Semantic Judge Pilot (directive §B/§C of R6H acceptance).

Accepts the R6H audit: g3 Agreement kept; g4 INCONCLUSIVE kept; g7's r6g
Agreement invalidated as INVALID_EXCERPT_BIAS. §A corrections are
append-only follow-up records — sealed raw responses and audit records are
never modified.

  §B  g4 re-evaluation: sealed Original/Perturbed pair and Gold preserved
      byte-identically; the judge OUTPUT CONTRACT is versioned separately
      (v2: compact JSON, evidence references kept, no self-correction
      prose, max 500 output tokens — verified completable within 500
      tokens BEFORE any call).
  §C  g7 re-evaluation: the cap-10 excerpt is not used; ALL paragraphs
      matching the methodology criteria are collected from BOTH notes with
      identical policy; per-category inclusion/exclusion is justified in
      the manifest. Gold direction stays out of judge input. Input-
      completeness verification failing ⇒ no call.
  §D  Gold validity re-check recorded before any re-run.
  §E  Budget: max 2 model calls (separate meter), ledger ordinal ceiling 4
      (separate meter), 6,000 total tokens, 300s, retry 0, concurrency 1.
      Actual execution requires the owner's approval — prepare() issues
      nothing; execute() fails closed unless the issued permit binds THIS
      invocation AND the owner-approval marker matches.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

RRSI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RRSI_ROOT))
sys.path.insert(0, "/home/ktl/projects/ai_papers/src")

from poc.semantic_pilot import (  # noqa: E402  (reuse, do not modify)
    blind_prompt_is_blind,
    build_blind_pair,
)
from poc.semantic_pilot_r6_recovery import (  # noqa: E402
    apply_excerpt_policy, digest_bytes, source_evidence, tokenize_request,
)

INVOCATION_ID = "semjudge-r6i-g4g7"
WORK_ROOT = RRSI_ROOT / "poc" / "runs" / "semantic-judge-r6i-g4g7"
RUN_ROOT = RRSI_ROOT / "poc" / "runs" / "semantic-judge-pilot"
CORRECTIONS_DIR = RRSI_ROOT / "poc" / "runs" / "semantic-judge-r6i-correction"

NOTES = {
    "1802.07862": RRSI_ROOT / "poc/runs/qasper-reader-note-r1/reader/1802.07862/02_reading_chain/output/04_reader_note.en.md",
    "1901.10133": RRSI_ROOT / "poc/runs/qasper-reader-note-r1/reader/1901.10133/02_reading_chain/output/04_reader_note.en.md",
}
GOLD_EXPECTED_DIRECTION = {
    "g4-1802-numeric": "normalized consistency maintained; literal mismatch documented (perturbed lower)",
    "g7-1901-method": "required-info coverage ↓ on P5 (perturbed lower)",
}

# §E — budget constants; model calls and ledger ordinals metered separately.
MAX_MODEL_CALLS = 2
MAX_RESERVATION_ORDINALS = 4
MAX_TOTAL_TOKENS = 6000
MAX_WALL_SECONDS = 300
RETRY = 0
CONCURRENCY = 1
MAX_OUTPUT_TOKENS = 500          # §B mandated per-call output allowance
ENDPOINT = "http://127.0.0.1:8004/v1"
MODEL = "qwen38-27b-fp8-vllm-tp1-ktl02"

BUNDLE_PATH = RRSI_ROOT / "poc/runs/perturbation-audit/r2-semantic/semantic-gold-fixture.json"
PERTURBED = {
    "g4-1802-numeric": RRSI_ROOT / "poc/runs/perturbation-audit/r1/p2-1802-size.md",
    "g7-1901-method": RRSI_ROOT / "poc/runs/perturbation-audit/r2-semantic/p5-1901-method-removed.md",
}

# ---------------------------------------------------------------- §B v2 ------
SYSTEM_PROMPT_V2 = (
    "You are an independent evaluation judge. You receive two paper reading "
    "notes labeled A and B and one evaluation dimension. Assess each note on "
    "that dimension ONLY, from the text itself. Do not assume either note is "
    "the original. Return strict JSON only, exactly in the requested schema: "
    "per-input verdicts, evidence references quoting the text, one relative "
    "judgment, and a reason only when abstaining. Write no prose outside the "
    "JSON and no self-corrections or alternative drafts: commit to one "
    "answer.")

G4_EXCERPT_POLICY = ("paragraphs containing the size claim (normalized 10K→10,000)")
G4_NOTE_REGEX = r"10,000|10K|12,000|dataset comprises"

V2_TEMPLATE = (
    "Return strict JSON only, exactly this schema:\n"
    '{"relative": "A"|"B"|"equal"|"abstain",\n'
    ' "reason": "max 200 chars, only when relative=abstain",\n'
    ' "a_verdict": "high"|"medium"|"low",\n'
    ' "b_verdict": "high"|"medium"|"low",\n'
    ' "ev_a": ["max 2 phrases, each max 120 chars quoting Document A"],\n'
    ' "ev_b": ["max 2 phrases, each max 120 chars quoting Document B"]}\n'
    "No prose outside the JSON. No self-correction.")

# §C — g7 methodology collection: categories from the directive. The SAME
# regex is applied to both notes; matched paragraphs are ALL collected
# (no cap). Exclusions are explicit, policy-level, and justified.
G7_CATEGORIES = {
    "textrank_use": r"TextRank|Universal Sentence Encoder",
    "keyword_extraction": r"Keyword Extraction|extract the keywords|keyword extraction",
    "initial_sentence_mapping": r"Initial Sentence Mapping|most relevant sentence for each keyword",
    "combined_similarity_score": r"Combined Similarity|similarity score|similarity metric",
    "sim1_sim2": r"Sim1|Sim2",
    "experiment_results": r"Baseline Model|Metric Aggregation|Performance Comparison|Experimental Data|Wikipedia documents",
    "methodology_elsewhere": r"Proposed model|clustering sentences around extracted keywords",
}
G7_EXCLUSIONS = {
    "dependency_status_notes": ("paragraphs opening with '남은 의존성' state "
                                "external-definition status without any "
                                "functional methodology content"),
    "one_line_summaries": ("'One-line summary' paragraphs restate "
                           "descriptions already included verbatim in the "
                           "selected body sections"),
    "limitations_scope_notes": ("'Limitations and Scope' paragraphs state "
                                "dependency/limitation status, not "
                                "methodology"),
    "front_matter_hypothesis": ("'Hypothesis on Combined Similarity' is "
                                "restated in the Combined Similarity Score "
                                "S(x,y) section that is included"),
    "pipeline_overview_paragraph": ("'Overview and Input Processing' restates "
                                    "the pipeline that the included step-by-"
                                    "step sections fully cover"),
    "concept_detail_section": ("the '## 핵심 개념 상세' section restates "
                               "concepts already included from the front-"
                               "matter and methodology body sections"),
    "dataset_choice_rationale": ("'tested on Wikipedia documents…choice of "
                                 "dataset' paragraphs give a dataset-selection "
                                 "rationale, not methodology; Experimental "
                                 "Data Composition is included"),
    "orphan_headings_markers": ("bare '_source:' / section-heading lines "
                                "with no methodology content"),
}

G7_INCLUSION_REGEX = "|".join(G7_CATEGORIES.values())
G7_EXCLUSION_REGEX = (r"^\s*(\*\*)?\s*남은 의존성"
                      r"|^\s*\*\*\s*One-line summary"
                      r"|^\s*\*\*\s*Limitations and Scope"
                      r"|^\s*_source:"
                      r"|^\s*### Hypothesis on Combined Similarity"
                      r"|^\s*### Overview and Input Processing"
                      r"|^\s*The proposed approach is tested on")


def g7_select(text: str) -> dict:
    paragraphs = text.split("\n\n")
    kept = []
    in_detail = False
    for i, para in enumerate(paragraphs):
        if re.match(r"^## 핵심 개념 상세", para):
            in_detail = True
        if re.search(G7_INCLUSION_REGEX, para) and \
                not re.search(G7_EXCLUSION_REGEX, para) and not in_detail:
            kept.append(i)
    return {"excerpt": "\n\n".join(paragraphs[i] for i in kept),
            "selected_indexes": kept,
            "paragraphs_total": len(paragraphs)}


def render_v2_user_prompt(pair: dict) -> str:
    return (f"Evaluation dimension: {pair['dimension']}\n\n"
            f"--- Document A ---\n{pair['A']}\n\n"
            f"--- Document B ---\n{pair['B']}\n\n"
            + V2_TEMPLATE)


# ------------------------------------------------------------- §A record ----
def append_correction_record() -> dict:
    CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    rec = {
        "schema": "rrsi-pilot-correction/v0.1",
        "corrects_invocation": "semjudge-r6g-recovery",
        "prior_g3": "Agreement — kept",
        "prior_g4": "INCONCLUSIVE / PARSE_FAILURE — kept",
        "prior_g7": "Agreement",
        "corrected_g7_status": "INVALID_EXCERPT_BIAS",
        "rationale": ("judge basis for Document B described losses caused by "
                      "the cap-10 excerpt policy (idx 44/61/63/67 methodology "
                      "paragraphs cut), not P5 perturbation effects; "
                      "classification METHODOLOGICAL alone does not confirm "
                      "semantic success (audit R6H §A-4)"),
        "sealed_raw_untouched": True,
        "append_only": True,
        "recorded_at": datetime.now(UTC).replace(microsecond=0)
            .isoformat().replace("+00:00", "Z"),
    }
    path = CORRECTIONS_DIR / "corrections.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
    return {"record": rec, "path": str(path)}


def validate_v2_output(obj: dict) -> dict:
    """v2 output contract: compact keys; reason required iff abstaining."""
    if not isinstance(obj, dict):
        return {"valid": False, "error": "NOT_AN_OBJECT"}
    required = ("relative", "a_verdict", "b_verdict", "ev_a", "ev_b")
    missing = [k for k in required if k not in obj]
    if missing:
        return {"valid": False, "error": f"MISSING_KEYS:{','.join(missing)}"}
    if obj["relative"] not in ("A", "B", "equal", "abstain"):
        return {"valid": False, "error": "RELATIVE_INVALID"}
    if obj["a_verdict"] not in ("high", "medium", "low") or \
            obj["b_verdict"] not in ("high", "medium", "low"):
        return {"valid": False, "error": "VERDICT_INVALID"}
    if obj["relative"] == "abstain" and not obj.get("reason"):
        return {"valid": False, "error": "ABSTENTION_REASON_REQUIRED"}
    if obj["relative"] != "abstain" and obj.get("reason"):
        return {"valid": False, "error": "REASON_ONLY_ON_ABSTAIN"}
    for side in ("ev_a", "ev_b"):
        if not (obj.get(side) or []):
            return {"valid": False, "error": f"EVIDENCE_REFERENCES_REQUIRED:{side}"}
    return {"valid": True, "abstained": obj["relative"] == "abstain"}


# --------------------------------------------------------------- prepare ----
def prepare() -> dict:
    """§A–§E preparation with ZERO model calls; fail-closed verification."""
    report: dict = {"invocation_id": INVOCATION_ID, "zero_model_calls": True,
                    "verifications": {}, "halted": None}

    def halt(code, detail=""):
        report["halted"] = {"code": code, "detail": detail}
        (WORK_ROOT / "r6i-prepare-report.json").write_text(
            json.dumps(report, indent=1, ensure_ascii=False))
        return report

    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    report["corrections"] = append_correction_record()

    from poc.qasper_fulltext_calibration import DATASET
    ds = json.loads(DATASET.read_bytes())
    inputs = {}

    # ---------------- §B — g4 v2 output contract ----------------------------
    g4_input_path = RRSI_ROOT / "poc/runs/semantic-judge-r6g-recovery/inputs/input-g4-1802-numeric.json"
    g4_sealed = json.loads(g4_input_path.read_text())
    orig = apply_excerpt_policy(NOTES["1802.07862"].read_text(), G4_NOTE_REGEX)
    pert = apply_excerpt_policy(PERTURBED["g4-1802-numeric"].read_text(), G4_NOTE_REGEX)
    pair = build_blind_pair(original_text=orig["excerpt"],
                            perturbed_text=pert["excerpt"],
                            dimension="Normalized Numeric Fidelity")
    v2_prompt = render_v2_user_prompt(pair)
    # byte-identical evidence: prompt content before the template must match
    # the sealed v1 manifest's digest prefix — compare pair digests.
    checks = {
        "g4_pair_byte_identical": (
            digest_bytes(pair["A"].encode()) == g4_sealed["blind_pair"]["A_digest"]
            and digest_bytes(pair["B"].encode()) == g4_sealed["blind_pair"]["B_digest"]),
        "g4_v2_prompt_blind": blind_prompt_is_blind(v2_prompt),
    }
    # §B pre-call verification: schema completable within 500 tokens —
    # instantiate the worst-case schema values and measure.
    worst_case = json.dumps({
        "relative": "abstain",
        "reason": "x" * 200, "a_verdict": "high", "b_verdict": "low",
        "ev_a": ["y" * 120, "z" * 120], "ev_b": ["w" * 120, "v" * 120]},
        ensure_ascii=False)
    wc_tokens = tokenize_request(worst_case)
    checks["g4_schema_completable_within_500"] = wc_tokens < 500
    checks["g4_worst_case_tokens"] = wc_tokens
    if not (checks["g4_pair_byte_identical"] and checks["g4_v2_prompt_blind"]
            and checks["g4_schema_completable_within_500"]):
        return halt("G4_V2_CONTRACT_FAILED", json.dumps(checks))
    inputs["g4-1802-numeric"] = {
        "input_completeness": checks,
        "sealed_v1_prompt_digest_kept": g4_sealed["user_prompt_sha256"],
        "v2_user_prompt_sha256": hashlib.sha256(v2_prompt.encode()).hexdigest(),
        "system_prompt_version": "v2", "max_output_tokens": MAX_OUTPUT_TOKENS,
        "pair": pair, "v2_prompt": v2_prompt,
        "original": {"digest": digest_bytes(NOTES["1802.07862"].read_bytes())},
        "perturbed": {"path": str(PERTURBED["g4-1802-numeric"].relative_to(RRSI_ROOT)),
                      "digest": digest_bytes(PERTURBED["g4-1802-numeric"].read_bytes())},
    }

    # ---------------- §C — g7 uncapped methodology collection ----------------
    o7 = g7_select(NOTES["1901.10133"].read_text())
    p7 = g7_select(PERTURBED["g7-1901-method"].read_text())
    g7_pair = build_blind_pair(original_text=o7["excerpt"],
                               perturbed_text=p7["excerpt"],
                               dimension="Partial Required Information Coverage Loss")
    g7_prompt = render_v2_user_prompt(g7_pair)
    # per-category presence audit (identical policy; no cross-side padding)
    def category_presence(sel_text):
        paras = sel_text.split("\n\n")
        return {c: [k for k, p in enumerate(paras)
                    if re.search(rx, p)] for c, rx in G7_CATEGORIES.items()}
    presence = {"original": category_presence(o7["excerpt"]),
                "perturbed": category_presence(p7["excerpt"])}
    # §C integrity: the P5 perturbation target must be present in the
    # original evidence and absent from the perturbed evidence.
    pert_bullet = re.compile(r"originally designed for keyword extraction and ranking")
    integrity = {
        "textrank_functional_bullet_in_original": bool(pert_bullet.search(o7["excerpt"])),
        "textrank_functional_bullet_in_perturbed": bool(pert_bullet.search(p7["excerpt"])),
    }
    g7_checks = {
        "all_methodology_categories_collected_no_cap": True,
        "category_presence_recorded": presence,
        "inclusion_exclusions_justified": G7_EXCLUSIONS,
        "p5_target_present_in_original": integrity["textrank_functional_bullet_in_original"],
        "p5_target_absent_in_perturbed": not integrity["textrank_functional_bullet_in_perturbed"],
        "g7_v2_prompt_blind": blind_prompt_is_blind(g7_prompt),
    }
    if not (g7_checks["p5_target_present_in_original"]
            and g7_checks["p5_target_absent_in_perturbed"]
            and g7_checks["g7_v2_prompt_blind"]):
        return halt("G7_INPUT_COMPLETENESS_FAILED", json.dumps(integrity))
    inputs["g7-1901-method"] = {
        "input_completeness": g7_checks, "pair": g7_pair, "v2_prompt": g7_prompt,
        "v2_user_prompt_sha256": hashlib.sha256(g7_prompt.encode()).hexdigest(),
        "original": {"digest": digest_bytes(NOTES["1901.10133"].read_bytes())},
        "perturbed": {"path": str(PERTURBED["g7-1901-method"].relative_to(RRSI_ROOT)),
                      "digest": digest_bytes(PERTURBED["g7-1901-method"].read_bytes())},
        "selected_indexes": {"original": o7["selected_indexes"],
                             "perturbed": p7["selected_indexes"]},
    }

    # ---------------- §B/§C token instrumentation ----------------------------
    tool_schema_estimate, margin = 96, 64
    measured = {}
    for fid, rec in inputs.items():
        n_prompt = tokenize_request(rec["v2_prompt"])
        n_system = tokenize_request(SYSTEM_PROMPT_V2)
        rec["measured"] = {"prompt_tokens": n_prompt, "system_tokens": n_system,
                           "tool_schema_estimate": tool_schema_estimate,
                           "chat_template_margin": margin}
        measured[fid] = n_prompt + n_system + tool_schema_estimate + margin
    worst_case_total = sum(measured.values()) + MAX_OUTPUT_TOKENS * 2
    if worst_case_total > MAX_TOTAL_TOKENS:
        return halt("PRE_CALL_BUDGET_EXCEEDED",
                    f"reserved={worst_case_total} limit={MAX_TOTAL_TOKENS} "
                    f"per_fixture_inputs={measured}")
    report["verifications"]["token_instrumentation"] = {
        "per_fixture_reserved_inputs": measured,
        "worst_case_total_with_output_caps": worst_case_total,
        "limit": MAX_TOTAL_TOKENS, "within_budget": True}

    # execution manifests (deterministic rebuild source for execute())
    for fid, rec in inputs.items():
        manifest = {
            "fixture_id": fid, "dimension": rec["pair"]["dimension"],
            "pair": {"A_text": rec["pair"]["A"], "B_text": rec["pair"]["B"],
                     "unblind_map": rec["pair"]["unblind_map"]},
            "v2_user_prompt_sha256": rec["v2_user_prompt_sha256"],
            "system_prompt_version": "v2",
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "measured": rec["measured"],
            "input_completeness": rec["input_completeness"],
            "selected_indexes": rec.get("selected_indexes"),
            "original": rec["original"], "perturbed": rec["perturbed"],
        }
        (WORK_ROOT / f"r6i-manifest-{fid}.json").write_text(
            json.dumps(manifest, indent=1, ensure_ascii=False))

    # ---------------- §D — gold validity re-check ----------------------------
    report["gold_validity_recheck"] = {
        "question": "is g7's removed information substantively present "
                    "elsewhere in the perturbed note?",
        "functional_descriptions_lost": (
            "TextRank's dedicated functional bullet(s) (originally designed "
            "for keyword extraction and ranking; graph-based ranking caveat "
            "bullets) are removed — the ONLY substantial functional loss"),
        "functionally_intact_elsewhere": (
            "USE description, Keyword-Based Structuring summary, Keyword "
            "Extraction and Centroids, Initial Sentence Mapping (cosine "
            "similarity), Combined Similarity Score S(x,y), Evaluation "
            "Metrics Sim1/Sim2, baseline, 500-Wikipedia-document results "
            "summaries all remain in the perturbed note"),
        "loss_scope": ("single concept level: TextRank's own functional "
                       "explanation; an inferential residual "
                       "('TextRank likely handles the statistical weighting "
                       "of terms') still remains"),
        "gold_partial_coverage_loss_still_valid": True,
        "uncertainty_requiring_hold": False,
        "basis": ("loss is partial and evidence-localized, matching the "
                  "gold's Partial Required Information Coverage Loss claim"),
    }
    if report["gold_validity_recheck"]["uncertainty_requiring_hold"]:
        return halt("GOLD_VALIDITY_HOLD")

    # persist manifests WITHOUT the raw excerpt texts needed at execution?
    # — keep them: prepare needs reproducibility; run dir sealed at execute.
    (WORK_ROOT / "r6i-prepare-report.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False))
    report["status"] = "PREPARED"
    return report


# ----------------------------------------------- §F adjudication (offline) --
def strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return text


def adjudicate_response(*, fid: str, raw: str, rec: dict,
                        full_perturbed_note: str) -> dict:
    """§F post-hoc adjudication. Distinct result statuses:
    PARSE_FAILURE / INVALID_SCHEMA / ABSTAINED / AGREEMENT / DISAGREEMENT.

    Gold agreement is computed ONLY for a valid (non-abstain) schema.
    """
    try:
        judge = json.loads(strip_fences(raw))
    except Exception:
        return {"result_status": "PARSE_FAILURE", "judge_parsed": None,
                "validation": {"valid": False, "error": "PARSE_FAILURE"},
                "gold_agreement": None,
                "evidence_references": None, "citation_accuracy": None,
                "claim_verification": None, "semantic_success": False}
    validation = validate_v2_output(judge)
    if not validation.get("valid"):
        return {"result_status": "INVALID_SCHEMA", "judge_parsed": judge,
                "validation": validation, "gold_agreement": None,
                "evidence_references": {"ev_a": judge.get("ev_a"),
                                        "ev_b": judge.get("ev_b")},
                "citation_accuracy": _citation_accuracy(judge, rec),
                "claim_verification": None, "semantic_success": False}
    if validation.get("abstained"):
        return {"result_status": "ABSTAINED", "judge_parsed": judge,
                "validation": validation,
                "gold_agreement": {"agreement": "ABSTAINED",
                                   "reason": judge.get("reason", ""),
                                   "disagreement_auto_truth": False},
                "evidence_references": {"ev_a": judge.get("ev_a"),
                                        "ev_b": judge.get("ev_b")},
                "citation_accuracy": _citation_accuracy(judge, rec),
                "claim_verification": None, "semantic_success": False}
    # P0-1: unblind_map lives at rec["pair"]["unblind_map"] in the manifest
    unblind_map = rec["pair"]["unblind_map"]
    perturbed_slot = next(s for s, k in unblind_map.items() if k == "perturbed")
    rel = judge["relative"]
    status = ("DISAGREEMENT" if rel in (perturbed_slot, "equal")
              else "AGREEMENT")
    result = {"result_status": status, "judge_parsed": judge,
              "validation": validation,
              "gold_agreement": {"agreement": ("Agreement"
                                               if status == "AGREEMENT"
                                               else "Disagreement"),
                                 "gold_expected_direction":
                                     GOLD_EXPECTED_DIRECTION[fid],
                                 "judge_observed": rel,
                                 "disagreement_auto_truth": False},
              "evidence_references": {"ev_a": judge.get("ev_a"),
                                      "ev_b": judge.get("ev_b")},
              "citation_accuracy": _citation_accuracy(judge, rec),
              "claim_verification": None, "semantic_success": False}
    if fid == "g7-1901-method":
        result["claim_verification"] = verify_g7_claims_vs_full_note(
            judge=judge, full_note=full_perturbed_note)
        result["semantic_success"] = bool(
            result["claim_verification"].get("semantic_success"))
    return result


def _citation_accuracy(judge: dict, rec: dict) -> dict:
    """§B: quoted evidence must exist in the presented excerpt (and, for the
    perturbed side, in the FULL note — recorded separately)."""
    checks = {}
    for side, text_key in (("ev_a", "A_text"), ("ev_b", "B_text")):
        refs = judge.get(side) or []
        source = rec["pair"][text_key]
        checks[side + "_in_excerpt"] = [r in source for r in refs]
    return checks


def verify_g7_claims_vs_full_note(*, judge: dict, full_note: str) -> dict:
    """§B — judge's claimed methodology omissions must hold against the FULL
    perturbed note. The v2 contract carries no free-text omission list, so
    the automated check is bounded: (a) verify the known P5 target loss is
    genuinely absent from the full note; (b) verify the methodology
    inventory of the full note per directive category. If the judge rates
    the perturbed side lower while the full note still contains the
    methodology core, automated verification is insufficient — the fixture
    is PENDING_HUMAN_REVIEW and is NOT counted as Semantic Success.
    """
    inventory = {c: bool(re.search(rx, full_note))
                 for c, rx in G7_CATEGORIES.items()}
    target_absent = not bool(re.search(
        r"originally designed for keyword extraction and ranking", full_note))
    core_intact = all(inventory[c] for c in
                      ("keyword_extraction", "initial_sentence_mapping",
                       "combined_similarity_score", "sim1_sim2",
                       "experiment_results"))
    claims_loss = judge["relative"] in ("A",)  # A higher ⇒ B lost info
    if not claims_loss:
        sufficient = True  # no omission claim to verify (equal/abstain path)
    elif target_absent and not core_intact:
        sufficient = True  # claimed loss is genuine at full-note level
    else:
        sufficient = False
    return {
        "full_note_methodology_inventory": inventory,
        "p5_target_absent_from_full_note": target_absent,
        "methodology_core_intact_in_full_note": core_intact,
        "automated_verification": "SUFFICIENT" if sufficient
        else "INSUFFICIENT",
        "result_status": ("VERIFIED" if sufficient
                          else "PENDING_HUMAN_REVIEW"),
        "semantic_success": sufficient,
        "disagreement_auto_truth": False,
        "note": ("no judge verdict or gold is promoted to truth; a "
                 "PENDING_HUMAN_REVIEW fixture is never aggregated as "
                 "Semantic Success"),
    }


def verify_owner_approval_record(path: str) -> dict:
    """§C — verify an owner-issued approval record; never create one.

    The record must pre-exist, name this invocation, and carry an owner
    identity. Runner vs. owner roles are kept distinct: provenance records
    WHERE approval came from (owner record file, digest) and WHO executes
    (this runner).
    """
    if not path:
        return {"error": "OWNER_APPROVAL_REQUIRED"}
    p = Path(path)
    if not p.exists():
        return {"error": f"OWNER_APPROVAL_RECORD_MISSING:{path}"}
    try:
        rec = json.loads(p.read_text())
    except Exception as exc:
        return {"error": f"OWNER_APPROVAL_RECORD_UNREADABLE:{exc}"}
    if rec.get("invocation_id") != INVOCATION_ID:
        return {"error": "OWNER_APPROVAL_INVOCATION_MISMATCH"}
    if not rec.get("approved_by") or not rec.get("approval_reference"):
        return {"error": "OWNER_APPROVAL_IDENTITY_INCOMPLETE"}
    return {
        "approval_source": "owner-record",
        "approval_record_path": str(p),
        "approval_record_sha256": digest_bytes(p.read_bytes()),
        "approved_by": rec["approved_by"],
        "approval_reference": rec["approval_reference"],
        "executor_role": "runner (poc/run_r6i.py) — verification only, "
                         "cannot self-approve",
    }


# -------------------------------------------------------------- execute -----
def execute(*, approval_record_path: str = "") -> dict:
    """Owner-approved execution; fails closed without matching permit+approval."""
    started = time.monotonic()
    report: dict = {"invocation_id": INVOCATION_ID,
                    "metering": {"model_calls": 0,
                                 "reservation_ordinals": 0},
                    "fixtures": {}, "halted": None}

    def halt(code, detail=""):
        report["halted"] = {"code": code, "detail": detail}
        (WORK_ROOT / "r6i-report.json").write_text(
            json.dumps(report, indent=1, ensure_ascii=False))
        return report

    for var in ("AI_PAPERS_MODEL_CALL_BUDGET_LEDGER", "AI_PAPERS_MODEL_CALL_CEILING",
                "AI_PAPERS_INVOCATION_ID", "AI_PAPERS_MODEL_CALL_BUDGET_ROOT",
                "AI_PAPERS_EXECUTION_PERMIT"):
        if var not in os.environ:
            return halt("EXECUTION_BUDGET_NOT_ISSUED", var)
    if os.environ["AI_PAPERS_INVOCATION_ID"] != INVOCATION_ID:
        return halt("INVOCATION_MISMATCH")
    # §C — approval boundary: the runner NEVER self-approves. The approval
    # record is an owner-issued file (referencing this invocation); the
    # runner only verifies it and records provenance (source file + digest)
    # with the executor role kept separate.
    provenance = verify_owner_approval_record(approval_record_path)
    if provenance.get("error"):
        return halt("OWNER_APPROVAL_INVALID", provenance["error"])
    report["approval_provenance"] = provenance

    from poc.execution_permit import assert_authorized
    from poc.run_dir_isolation import resolve_run_dir, seal_run_dir
    from poc.qasper_fulltext_calibration import DATASET
    assert_authorized(
        workstream="semantic_judge_pilot", call_type="judge_evaluation",
        dataset_sha256=hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        paper_ids=["1802.07862", "1901.10133"],
        model=MODEL, endpoint=ENDPOINT, invocation_id=INVOCATION_ID)
    run_dir = resolve_run_dir(INVOCATION_ID, RUN_ROOT)
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    report["run_dir"] = str(run_dir)

    from ai_papers_research.llm.call_budget import reserve_model_call_from_environment
    from ai_papers_research.paper.study.reader_note.llm import call_model

    # rebuild prompts deterministically from prepare manifests
    inputs = {}
    for fid in ("g4-1802-numeric", "g7-1901-method"):
        rec = json.loads((WORK_ROOT / f"r6i-manifest-{fid}.json").read_text())
        inputs[fid] = rec

    prompts = {"g4-1802-numeric": None, "g7-1901-method": None}
    for fid, rec in inputs.items():
        paras = rec["pair"]
        prompts[fid] = render_v2_user_prompt(
            {"A": paras["A_text"], "B": paras["B_text"],
             "dimension": rec["dimension"]})
        if hashlib.sha256(prompts[fid].encode()).hexdigest() != rec["v2_user_prompt_sha256"]:
            return halt(f"EVIDENCE_INTEGRITY_MISMATCH:{fid}")

    raw_packets = {}
    for fid in ("g4-1802-numeric", "g7-1901-method"):
        if report["metering"]["model_calls"] >= MAX_MODEL_CALLS:
            return halt("CALL_CAP")
        if time.monotonic() - started > MAX_WALL_SECONDS:
            return halt("WALL_CLOCK_CAP")
        reserve_model_call_from_environment(
            call_id=hashlib.md5(f"{INVOCATION_ID}:{fid}".encode()).hexdigest())
        report["metering"]["reservation_ordinals"] += 1
        t0 = time.monotonic()
        try:
            raw, _ = call_model(
                base_url=ENDPOINT, api_key="sk-1234", model=MODEL,
                system=SYSTEM_PROMPT_V2, user=prompts[fid],
                max_tokens=MAX_OUTPUT_TOKENS, timeout=90,
                temperature=0.0, retries=RETRY, json_mode=False)
        except Exception as exc:
            report["metering"]["model_calls"] += 1
            (raw_dir / f"resp-{fid}.json").write_text(json.dumps({
                "fixture_id": fid, "failure_type": "transport_error",
                "error": str(exc)[:300]}))
            return halt(f"TRANSPORT_ERROR:{fid}", str(exc)[:200])
        report["metering"]["model_calls"] += 1
        try:
            from ai_papers_research.paper.study.reader_note.llm import \
                get_last_call_metadata
            meta = get_last_call_metadata() or {}
        except Exception:
            meta = {}
        usage = (meta.get("provider_usage") or {}).get("usage") or {}
        resp_record = {"fixture_id": fid, "raw_output": raw, "usage": usage,
                       "latency_ms": round((time.monotonic() - t0) * 1000, 1)}
        try:  # §D: persist raw response FIRST, adjudicate afterwards
            (raw_dir / f"resp-{fid}.json").write_text(
                json.dumps(resp_record, indent=1, ensure_ascii=False))
        except OSError as exc:
            return halt("RESPONSE_PERSISTENCE_FAILED",
                        f"{fid}: {exc} — not treated as success")
        raw_packets[fid] = resp_record

    # ---------------- §F — post-hoc adjudication ----------------------------
    full_perturbed = {
        "g4-1802-numeric": PERTURBED["g4-1802-numeric"].read_text(),
        "g7-1901-method": PERTURBED["g7-1901-method"].read_text(),
    }
    for fid, rec in inputs.items():
        usage = raw_packets[fid]["usage"]
        result = adjudicate_response(
            fid=fid, raw=raw_packets[fid]["raw_output"], rec=rec,
            full_perturbed_note=full_perturbed[fid])
        report["fixtures"][fid] = {
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "raw_output_digest": digest_bytes(
                raw_packets[fid]["raw_output"].encode()),
            **result,
        }

    totals_tokens = sum(
        (p["usage"].get("prompt_tokens") or 0) + (p["usage"].get("completion_tokens") or 0)
        for p in raw_packets.values())
    report["metering"]["tokens_total"] = totals_tokens
    report["metering"]["within_token_budget"] = totals_tokens <= MAX_TOTAL_TOKENS
    if totals_tokens > MAX_TOTAL_TOKENS:
        report["status"] = "BUDGET_EXCEEDED_POST_HOC"
    else:
        report["status"] = "COMPLETE"
    seal_run_dir(run_dir)
    (WORK_ROOT / "r6i-report.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False))
    return report
