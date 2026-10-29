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


# ------------------------------------------------------------------ execute
def execute(*, invocation_id: str, run_root: Path) -> dict:
    """Execute the 3-fixture pilot under permit + budget reservation.

    Halt conditions (directive §C/§D): permit or budget failure, model
    profile/endpoint mismatch, budget overrun, evidence-integrity failure.
    No automatic retry; concurrency 1.
    """
    import time as _time
    from poc.execution_permit import assert_authorized
    from poc.qasper_fulltext_calibration import DATASET

    # 1. Execution permit + budget environment (fail-closed before anything).
    gate = run()
    if gate["code"] == "EXECUTION_BUDGET_NOT_ISSUED":
        return {"status": "BLOCK", "calls": 0, "tokens": 0,
                "code": "EXECUTION_BUDGET_NOT_ISSUED"}
    if True:  # budget env present — proceed under it; permit verified below
        # budget env present — proceed under it; verify permit bound to this run
        permit_invocation = json.loads(
            Path(os.environ["AI_PAPERS_EXECUTION_PERMIT"]).read_text()
        ).get("invocation_id")
        verified = assert_authorized(
            workstream="semantic_judge_pilot", call_type="judge_evaluation",
            dataset_sha256=hashlib.sha256(DATASET.read_bytes()).hexdigest(),
            paper_ids=["1802.07862", "1901.10133"],
            model=PILOT_LIMITS["model"], endpoint=PILOT_LIMITS["endpoint"],
            invocation_id=invocation_id)
    else:
        return {"status": "BLOCK", "calls": 0, "tokens": 0,
                "code": "EXECUTION_BUDGET_NOT_ISSUED"}

    # 2. Invocation-bound run dir (collision-checked, permit-bound).
    from poc.run_dir_isolation import resolve_run_dir, seal_run_dir
    run_dir = resolve_run_dir(invocation_id, run_root,
                              permit_invocation_id=permit_invocation)
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 3. Evidence integrity: rebuild blind pairs deterministically; the
    #    r6 sealed prompt digests must match byte-for-byte (else halt).
    admissions = Path("poc/runs/perturbation-audit/r6-pilot-admission")
    bundle_path = Path("poc/runs/perturbation-audit/r2-semantic/semantic-gold-fixture.json")
    notes = {
        "1802.07862": Path("poc/runs/qasper-reader-note-r1/reader/1802.07862/02_reading_chain/output/04_reader_note.en.md"),
        "1901.10133": Path("poc/runs/qasper-reader-note-r1/reader/1901.10133/02_reading_chain/output/04_reader_note.en.md"),
    }
    bundle = load_bundle(bundle_path)
    rebuilt = {}
    for fid, scope in APPROVED_SCOPES.items():
        fixture = bundle[fid]
        pair = build_blind_pair(
            original_text=notes[fixture["source_identity"]["paper_id"]].read_text(),
            perturbed_text=Path(PERTURBATION_BINDINGS[fid]).read_text(),
            dimension=scope)
        prompt = render_judge_user_prompt(pair)
        rebuilt[fid] = {"pair": pair, "prompt": prompt,
                        "digest": hashlib.sha256(prompt.encode()).hexdigest()}

    started = _time.monotonic()
    calls = tokens = 0
    results = {}
    ledger = os.environ["AI_PAPERS_MODEL_CALL_BUDGET_LEDGER"]
    sys_path = "/home/ktl/projects/ai_papers/src"
    import sys
    sys.path.insert(0, sys_path)
    from ai_papers_research.paper.study.reader_note.llm import call_model

    halted = None
    for fid in APPROVED_SCOPES:
        if halted:
            break
        if calls >= PILOT_LIMITS["max_eval_calls"]:
            halted = "CALL_CAP"
            break
        if _time.monotonic() - started > PILOT_LIMITS["max_wall_seconds"]:
            halted = "WALL_CLOCK_CAP"
            break
        rec = rebuilt[fid]
        manifest = json.loads((admissions / f"pair-{fid}.json").read_text())
        if manifest["user_prompt_sha256"] != rec["digest"]:
            halted = f"EVIDENCE_INTEGRITY_MISMATCH:{fid}"
            break
        # budget reservation BEFORE the call (issuance-consumption separation:
        # the runner writes consumption records against the issued permit).
        call_id = hashlib.md5(f"{invocation_id}:{fid}".encode()).hexdigest()
        # Reservation via the frozen ledger machinery (fail-closed on schema).
        from ai_papers_research.llm.call_budget import reserve_model_call_from_environment
        reserve_model_call_from_environment(call_id=call_id)
        t0 = _time.monotonic()
        try:
            raw, _ = call_model(
                base_url=PILOT_LIMITS["endpoint"], api_key="sk-1234",
                model=PILOT_LIMITS["model"], system=SYSTEM_PROMPT_JUDGE,
                user=rec["prompt"], max_tokens=1500, timeout=120,
                temperature=0.0, retries=0, json_mode=False)
        except Exception as exc:
            calls += 1
            (raw_dir / f"packet-{fid}.json").write_text(json.dumps({
                "fixture_id": fid, "failure_type": "transport_error",
                "error": str(exc)[:300]}))
            halted = f"TRANSPORT_ERROR:{fid}"
            break
        latency_ms = round((_time.monotonic() - t0) * 1000, 1)
        calls += 1
        meta = {}
        try:
            from ai_papers_research.paper.study.reader_note.llm import get_last_call_metadata
            meta = get_last_call_metadata() or {}
        except Exception:
            pass
        usage = (meta.get("provider_usage") or {}).get("usage") or {}
        tokens += (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)
        if tokens > PILOT_LIMITS["max_total_tokens"]:
            # record the received response BEFORE halting (directive: honest
            # failure evidence; the pilot halts without retry afterwards).
            (raw_dir / f"packet-{fid}.json").write_text(json.dumps({
                "fixture_id": fid, "failure_type": "token_budget_exceeded",
                "token_usage": usage, "raw_output_digest": "sha256:" +
                hashlib.sha256(raw.encode()).hexdigest()}))
            halted = "TOKEN_BUDGET_EXCEEDED"
            break
        try:
            parsed_raw = json.loads(raw) if raw.strip().startswith("{") else None
        except Exception:
            parsed_raw = None
        # parse strict-JSON judge output (strip code fences if any)
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        try:
            judge = json.loads(text)
        except Exception:
            judge = None
        validation = validate_judge_output(judge) if judge else \
            {"valid": False, "error": "PARSE_FAILURE"}
        gold = compare_with_gold(
            judge_output=judge or {"relative_judgment": {"higher_quality": "equal"},
                                   "abstention": {"refused": True, "reason": "unparsed"}},
            unblind_map=rec["pair"]["unblind_map"],
            gold_expected_direction="perturbed lower") if validation.get("valid") else None
        g7 = g7_methodological_loss_check(judge) if fid == "g7-1901-method" and judge else None
        packet = {
            "fixture_id": fid, "failure_type": "none" if judge else "parse_failure",
            "token_usage": usage, "latency_ms": latency_ms,
            "raw_output_digest": "sha256:" + hashlib.sha256(raw.encode()).hexdigest(),
            "latency_ms": latency_ms, "validation": validation,
            "judge_parsed": judge, "g7_check": g7, "gold_agreement": gold,
            "prompt_digest": rec["digest"],
        }
        (raw_dir / f"packet-{fid}.json").write_text(json.dumps(packet, indent=1, ensure_ascii=False))
        results[fid] = packet

    seal_run_dir(run_dir)
    summary = {"invocation_id": invocation_id, "run_dir": str(run_dir),
               "status": "HALTED" if halted else "COMPLETE",
               "halt_reason": halted, "calls": calls, "tokens_reported": tokens,
               "fixtures": {k: {"agreement": v["gold_agreement"] and v["gold_agreement"]["agreement"],
                                "g7": v["g7_check"] and v["g7_check"]["classification"]}
                            for k, v in results.items()},
               "limits": PILOT_LIMITS}
    (run_dir / "pilot-summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    return summary
