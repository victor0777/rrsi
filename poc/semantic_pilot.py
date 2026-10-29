# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Limited Semantic Judge Pilot — admission & preparation (directive R5, §B).

This module PREPARES the 3-fixture pilot; it executes nothing here:
run() is fail-closed on the budget environment, and no client is wired
in this step. Execution budget and call permission are issued ONLY after
the user's final approval (directive §C).

Blindness rule (§B): each fixture's Original and Perturbed note are
presented to the judge in a seed-fixed random order; the gold answers and
the expected evaluation direction are never included in the prompt. The
Gold Expected Direction is compared AFTER evaluation; a judge verdict that
differs from gold is recorded as Disagreement — neither side is promoted
to truth automatically (§D).
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from datetime import UTC, datetime
from pathlib import Path

PILOT_SCHEMA = "rrsi-semantic-judge-pilot/v0.1"
APPROVAL_SCHEMA = "rrsi-fixture-approval/v0.1"

# Directive §C — hard execution limits.
PILOT_LIMITS = {
    "max_eval_calls": 3,          # one per fixture
    "max_total_tokens": 6000,
    "max_wall_seconds": 300,
    "retry": 0,                   # automatic retry prohibited
    "endpoint": "http://127.0.0.1:8004/v1",
    "model": "qwen38-27b-fp8-vllm-tp1-ktl02",  # existing approved local profile
}

# Directive §A — per-fixture approval scopes (independently managed).
APPROVED_SCOPES = {
    "g3-1802-result": "Numeric Fidelity",
    "g4-1802-numeric": "Normalized Numeric Fidelity",
    "g7-1901-method": "Partial Required Information Coverage Loss",
}

PERTURBATION_BINDINGS = {
    "g3-1802-result": "poc/runs/perturbation-audit/r1/p2-1802-vocab.md",
    "g4-1802-numeric": "poc/runs/perturbation-audit/r1/p2-1802-size.md",
    "g7-1901-method": "poc/runs/perturbation-audit/r2-semantic/p5-1901-method-removed.md",
}

# Per-fixture content digest rule: sha256 of the canonical JSON serialization
# of the fixture record (sort_keys, ensure_ascii=False). This is a per-fixture
# value — it must NOT be confused with the shared gold bundle digest.
def per_fixture_digest(fixture: dict) -> str:
    return hashlib.sha256(
        json.dumps(fixture, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def load_bundle(bundle_path: Path) -> dict:
    """Return {fixture_id: fixture_record} from the gold bundle file."""
    data = json.loads(bundle_path.read_text())
    fixtures = data if isinstance(data, list) else data.get("fixtures", [])
    return {f["fixture_id"]: f for f in fixtures}


def bundle_digest(bundle_path: Path) -> str:
    return hashlib.sha256(bundle_path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- approval
def build_approval_record(*, fixture: dict, approved_by: str,
                          approval_reference: str,
                          independent_review_refs: list) -> dict:
    fid = fixture["fixture_id"]
    if fid not in APPROVED_SCOPES:
        raise ValueError(f"no approved scope registered for {fid}")
    return {
        "schema": APPROVAL_SCHEMA,
        "fixture_id": fid,
        "fixture_digest": per_fixture_digest(fixture),
        "approved_scope": APPROVED_SCOPES[fid],
        "approved_by": approved_by,
        "approval_reference": approval_reference,
        "independent_review_refs": independent_review_refs,
        # The bundle digest below is shared by all fixtures — it is recorded
        # for provenance only and is NOT interpreted as a per-fixture approval
        # identifier (directive §A).
        "bundle_digest_context_only": True,
        "approved_at": datetime.now(UTC).replace(microsecond=0)
            .isoformat().replace("+00:00", "Z"),
    }


# ---------------------------------------------------------------- blindness
def build_blind_pair(*, original_text: str, perturbed_text: str,
                     dimension: str, seed: int = 42) -> dict:
    """Blind presentation: seed-fixed random order; no gold, no direction."""
    rng = random.Random(seed)
    slots = ["A", "B"]
    kinds = ["original", "perturbed"]
    texts = [original_text, perturbed_text]
    if rng.random() < 0.5:  # seed-fixed order swap
        slots = slots[::-1]
    # position i gets slot slots[i] with kind kinds[i]
    return {
        "A": texts[kinds.index("original") if slots[0] == "A" else kinds.index("perturbed")],
        "B": texts[kinds.index("original") if slots[1] == "A" else kinds.index("perturbed")],
        "dimension": dimension,
        "unblind_map": {slots[0]: kinds[0], slots[1]: kinds[1]},
    }


SYSTEM_PROMPT_JUDGE = (
    "You are an independent evaluation judge. You will receive two paper "
    "reading notes labeled A and B, and one evaluation dimension. Assess "
    "each note on that dimension ONLY, from the text itself. Do not assume "
    "either note is the original. Return strict JSON with: per-input "
    "quality verdict, the basis grounded in the text, evidence references, "
    "a relative quality judgment of A vs B, and — if the dimension cannot "
    "be judged from the provided text — an abstention with the reason."
)


def render_judge_user_prompt(pair: dict) -> str:
    return (
        f"Evaluation dimension: {pair['dimension']}\n\n"
        f"--- Document A ---\n{pair['A']}\n\n"
        f"--- Document B ---\n{pair['B']}\n\n"
        "Return strict JSON only:\n"
        '{"input_a": {"verdict": "...", "basis": "...", "evidence_references": [...]},\n'
        ' "input_b": {"verdict": "...", "basis": "...", "evidence_references": [...]},\n'
        ' "relative_judgment": {"higher_quality": "A"|"B"|"equal", "basis": "..."},\n'
        ' "abstention": {"refused": true|false, "reason": "..."}}'
    )


def blind_prompt_is_blind(prompt: str) -> bool:
    """Guard: the prompt must not leak gold answers or expected directions."""
    forbidden = ("expected direction", "expected_direction", "gold",
                 "consistency ↓", "coverage ↓", "fidelity ↓", "↓")
    return not any(f in prompt.lower() or f in prompt for f in forbidden)


# ------------------------------------------------------------ output contract
REQUIRED_JUDGE_KEYS = ("input_a", "input_b", "relative_judgment")


def validate_judge_output(obj: dict) -> dict:
    """Directive §B output contract; abstention reason required if refused."""
    missing = [k for k in REQUIRED_JUDGE_KEYS if k not in obj]
    if missing:
        return {"valid": False, "error": f"MISSING_KEYS:{','.join(missing)}"}
    rel = obj["relative_judgment"]
    if rel.get("higher_quality") not in ("A", "B", "equal"):
        return {"valid": False, "error": "RELATIVE_JUDGMENT_INVALID"}
    ab = obj.get("abstention", {"refused": False})
    if ab.get("refused") and not ab.get("reason"):
        # §B-5: abstention requires a reason — without it the verdict is
        # invalid rather than silently scored.
        return {"valid": False, "error": "ABSTENTION_REASON_REQUIRED"}
    for side in ("input_a", "input_b"):
        entry = obj[side]
        if not entry.get("evidence_references"):
            return {"valid": False, "error": f"EVIDENCE_REFERENCES_REQUIRED:{side}"}
    return {"valid": True, "abstained": bool(ab.get("refused"))}


# ------------------------------------------------------------- post-hoc gold
def compare_with_gold(*, judge_output: dict, unblind_map: dict,
                      gold_expected_direction: str) -> dict:
    """Compare AFTER evaluation (§B). Disagreement is final — no auto-truth."""
    # unblind_map maps slot -> "original"/"perturbed" (build_blind_pair order)
    rel = judge_output["relative_judgment"]["higher_quality"]
    if judge_output.get("abstention", {}).get("refused"):
        return {"agreement": "ABSTAINED", "recorded_as": "Abstention",
                "reason": judge_output["abstention"]["reason"],
                "disagreement_auto_truth": False}
    # the perturbed note carries the intended defect → gold expects it lower;
    # agreement iff the judge rates the ORIGINAL slot higher. "equal" does not
    # establish the direction → Disagreement.
    perturbed_slot = next(s for s, k in unblind_map.items() if k == "perturbed")
    agreement = "Agreement" if rel not in (perturbed_slot, "equal") else "Disagreement"
    return {"agreement": agreement,
            "gold_expected_direction": gold_expected_direction,
            "judge_observed": rel,
            "disagreement_auto_truth": False,
            "note": "Disagreement recorded as-is — neither gold nor judge "
                    "is promoted to truth (directive §D)"}


def g7_methodological_loss_check(judge_output: dict) -> dict:
    """Directive §D — for g7 specifically: did the judge assess METHODOLOGICAL
    information loss, not mere word-presence?"""
    bases = [judge_output["input_a"]["basis"],
             judge_output["input_b"]["basis"],
             judge_output["relative_judgment"]["basis"]]
    joined = " ".join(bases).lower()
    import re as _re
    word_only_markers = (r"\bthe name\b", r"\bterm appears\b", r"\bword\b",
                         r"\bmentioned word\b", r"\bmentions textrank\b",
                         r"\btext appearance\b")
    methodological_markers = (r"\bstep\b", r"\bextraction\b", r"\bclustering\b",
                              r"\bcentroid\b", r"\bpipeline\b", r"\bprocedure\b",
                              r"information loss", r"\bcoverage\b")
    word_only = any(_re.search(m, joined) for m in word_only_markers)
    methodological = any(_re.search(m, joined) for m in methodological_markers)
    classification = ("AMBIGUOUS" if word_only and methodological else
                      "WORD_PRESENCE_ONLY" if word_only else
                      "METHODOLOGICAL" if methodological else "UNKNOWN")
    return {"classification": classification,
            "requirement": "judge must classify methodological information "
                           "loss, not word presence",
            "flag": classification not in ("METHODOLOGICAL",)}


# ------------------------------------------------------------------- run gate
def run() -> dict:
    """Fail-closed: no budget environment → zero calls, zero tokens."""
    required = ("AI_PAPERS_MODEL_CALL_BUDGET_LEDGER", "AI_PAPERS_MODEL_CALL_CEILING",
                "AI_PAPERS_INVOCATION_ID", "AI_PAPERS_MODEL_CALL_BUDGET_ROOT")
    if any(v not in os.environ for v in required):
        return {"status": "BLOCK", "code": "EXECUTION_BUDGET_NOT_ISSUED",
                "calls": 0, "tokens": 0,
                "reason": "execution budget and call permission are issued "
                          "only after the user's final approval (§C)"}
    return {"status": "BLOCK", "code": "PILOT_RUN_WIRING_PENDING_SEPARATE_ADMISSION",
            "calls": 0, "tokens": 0}


# ------------------------------------------------------------------ prepare
def prepare(out_dir: Path, bundle_path: Path, notes: dict) -> dict:
    """Build per-fixture approval records + blind pair manifest (no calls)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = load_bundle(bundle_path)
    approvals, pairs = [], []
    for fid, scope in APPROVED_SCOPES.items():
        fixture = bundle[fid]
        ap = build_approval_record(
            fixture=fixture,
            approved_by="owner-directive (R5 admission — fixture-level scope fix)",
            approval_reference="commit 9497c91 R5 results accepted by directive",
            independent_review_refs=[
                "r5-adjudication review-records.jsonl (R4 Recommend Approval, scope-limited)",
                "r4-revision review-records.jsonl (R1 verdicts)",
            ])
        ap_path = out_dir / f"approval-{fid}.json"
        ap_path.write_text(json.dumps(ap, indent=1, ensure_ascii=False))
        approvals.append(ap)
        pert_path = Path(PERTURBATION_BINDINGS[fid])
        original_text = Path(notes[fixture["source_identity"]["paper_id"]]).read_text()
        pair = build_blind_pair(
            original_text=original_text,
            perturbed_text=pert_path.read_text(),
            dimension=scope,
        )
        prompt = render_judge_user_prompt(pair)
        pair_manifest = {
            "schema": PILOT_SCHEMA, "fixture_id": fid,
            "fixture_digest": ap["fixture_digest"],
            "perturbed_path": str(pert_path),
            "perturbed_digest": hashlib.sha256(pert_path.read_bytes()).hexdigest(),
            "original_digest": hashlib.sha256(
                Path(notes[fixture["source_identity"]["paper_id"]]).read_bytes()).hexdigest(),
            "prompt_blind": blind_prompt_is_blind(prompt),
            "unblind_map_sealed": pair["unblind_map"],
            "system_prompt": SYSTEM_PROMPT_JUDGE,
            "user_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "limits": PILOT_LIMITS,
            "g7_special_check": fid == "g7-1901-method",
        }
        (out_dir / f"pair-{fid}.json").write_text(
            json.dumps(pair_manifest, indent=1, ensure_ascii=False))
        pairs.append(pair_manifest)
    summary = {
        "bundle_digest_context_only": bundle_digest(bundle_path),
        "approvals": len(approvals), "pairs": len(pairs),
        "all_prompts_blind": all(p["prompt_blind"] for p in pairs),
        "approved": len(approvals), "calls_executed": 0, "tokens_used": 0,
    }
    (out_dir / "admission-summary.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    NOTES = {
        "1802.07862": Path("poc/runs/qasper-reader-note-r1/reader/1802.07862/02_reading_chain/output/04_reader_note.en.md"),
        "1901.10133": Path("poc/runs/qasper-reader-note-r1/reader/1901.10133/02_reading_chain/output/04_reader_note.en.md"),
    }
    print(json.dumps(prepare(
        out_dir=Path("poc/runs/perturbation-audit/r6-pilot-admission"),
        bundle_path=Path("poc/runs/perturbation-audit/r2-semantic/semantic-gold-fixture.json"),
        notes=NOTES), indent=1))
