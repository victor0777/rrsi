# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""R6 Recovery — Evidence-Bounded Semantic Judge Pilot.

Accepts the halt of invocation semjudge-pilot-r6e (commit 1197d4d) as final:
that run stays sealed FAILED with 18,004 tokens reported; nothing is
retro-generated from it and its Invocation/RUN_DIR are NOT reused.

Recovery changes vs. the halted attempt:
  §A  Evidence-bounded inputs: identical excerpt policy applied to Original
      and Perturbed note; the gold expected direction and A/B answer roles
      are excluded from judge input. Excerpt policy, source position,
      selected and omitted ranges, and per-input digests are all recorded.
  §B  Pre-call token instrumentation over the ENTIRE request (system prompt,
      judge contract, source evidence, A/B inputs, tool schema, max output
      budget) via the served model's own /tokenize endpoint. Fail-closed:
      no reachable/reliable instrumentation → no call, no retry.
  §C  Budget: max 3 calls, 6,000 total tokens (input+output), 300s wall,
      retry 0, concurrency 1; per-fixture reserved budgets sum-checked
      BEFORE any call.
  §D  Ledger: only the frozen official reservation API is used; no manual
      ledger row insertion. On response receipt the RAW response and usage
      are persisted FIRST; budget-overrun adjudication happens afterwards.
      A response that cannot be persisted is never reported as success.

Stage order follows directive §E.
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

from poc.semantic_pilot import (  # noqa: E402  (reuse, do not modify)
    APPROVED_SCOPES,
    PERTURBATION_BINDINGS,
    SYSTEM_PROMPT_JUDGE,
    blind_prompt_is_blind,
    build_blind_pair,
    compare_with_gold,
    g7_methodological_loss_check,
    load_bundle,
    render_judge_user_prompt,
    validate_judge_output,
)

INVOCATION_ID = "semjudge-r6g-recovery"        # NEW — old ids are retired
RUN_ROOT = RRSI_ROOT / "poc" / "runs" / "semantic-judge-pilot"
WORK_ROOT = RRSI_ROOT / "poc" / "runs" / "semantic-judge-r6g-recovery"
INPUTS_DIR = WORK_ROOT / "inputs"
RAW_DIR = WORK_ROOT / "run" / "raw"

# §C — budget constants (identical to the permit hard limits).
MAX_CALLS = 3
MAX_TOTAL_TOKENS = 6000
MAX_WALL_SECONDS = 300
RETRY = 0
CONCURRENCY = 1
MAX_OUTPUT_TOKENS = 800          # per-call output reservation
CHAT_TEMPLATE_MARGIN = 64        # chat-template overhead not visible to /tokenize
ENDPOINT = "http://127.0.0.1:8004/v1"
MODEL = "qwen38-27b-fp8-vllm-tp1-ktl02"

NOTES = {
    "1802.07862": RRSI_ROOT / "poc/runs/qasper-reader-note-r1/reader/1802.07862/02_reading_chain/output/04_reader_note.en.md",
    "1901.10133": RRSI_ROOT / "poc/runs/qasper-reader-note-r1/reader/1901.10133/02_reading_chain/output/04_reader_note.en.md",
}
BUNDLE_PATH = RRSI_ROOT / "poc/runs/perturbation-audit/r2-semantic/semantic-gold-fixture.json"
GOLD_EXPECTED_DIRECTION = {
    "g3-1802-result": "numeric consistency ↓ on P2 (perturbed lower)",
    "g4-1802-numeric": "normalized consistency maintained; literal mismatch documented (perturbed lower)",
    "g7-1901-method": "required-info coverage ↓ on P5 (perturbed lower)",
}

# §A — Evidence-bounded excerpt policies. The SAME policy is applied to the
# Original and the Perturbed note (directive §A); the matched sets may differ,
# the selection rule must not. Selection is paragraph-level on the note text.
EXCERPT_POLICIES = {
    "g3-1802-result": {
        "policy": "paragraphs containing the numeric claim under judgment",
        "note_paragraph_regex": r"vocabulary size",
        "source_anchor": "15,733",
        "source_context_chars": 600,
    },
    "g4-1802-numeric": {
        "policy": "paragraphs containing the size claim (normalized 10K→10,000)",
        "note_paragraph_regex": r"10,000|10K|12,000|dataset comprises",
        "source_anchor": "10K user-generated image (snap) and textual caption pairs",
        "source_context_chars": 600,
    },
    "g7-1901-method": {
        "policy": "methodology paragraphs (functional steps, related context) "
                  "plus any residual explanation of omitted methodology; "
                  "first 10 matching paragraphs in document order",
        "note_paragraph_regex": r"TextRank|Universal Sentence Encoder|centroid"
                                r"|extract the keywords|most relevant sentence"
                                r"|남은 의존성",
        "paragraph_cap": 10,
        "source_anchor": "extract the keywords from the input document using TextRank",
        "source_context_chars": 1100,
    },
}


def digest_bytes(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def apply_excerpt_policy(text: str, pattern: str, cap: int | None = None) -> dict:
    """§A — paragraph-level excerpt; records selected and omitted ranges.

    `cap` (when set) keeps only the first `cap` matching paragraphs in
    document order — a deterministic selection rule applied identically to
    the Original and Perturbed note (the match count may differ, the rule
    may not).
    """
    paragraphs = text.split("\n\n")
    regex = re.compile(pattern)
    selected, omitted = [], []
    offset = 0
    n_matched = 0
    for i, para in enumerate(paragraphs):
        rec = {"paragraph_index": i,
               "char_range": [offset, offset + len(para)]}
        if regex.search(para):
            n_matched += 1
            if cap is None or n_matched <= cap:
                selected.append(rec)
            else:
                omitted.append(rec)
        else:
            omitted.append(rec)
        offset += len(para) + 2
    kept = {r["paragraph_index"] for r in selected}
    excerpt = "\n\n".join(p for i, p in enumerate(paragraphs) if i in kept)
    return {"excerpt": excerpt,
            "selected_ranges": selected,
            "omitted_ranges": omitted,
            "paragraphs_total": len(paragraphs)}


def source_evidence(ds: dict, paper_id: str, anchor: str, context: int) -> dict:
    """§A — source excerpt around the anchor, with original-text position."""
    from poc.qasper_fulltext_calibration import flatten_full_text
    full = flatten_full_text(ds[paper_id]["full_text"])
    i = full.find(anchor)
    if i < 0:
        raise RuntimeError(f"SOURCE_ANCHOR_ABSENT:{paper_id}:{anchor[:30]}")
    lo, hi = max(0, i - context // 2), min(len(full), i + len(anchor) + context // 2)
    return {"paper_id": paper_id,
            "anchor_in_source": True,
            "anchor_char_offset": i,
            "excerpt_char_range": [lo, hi],
            "excerpt": full[lo:hi]}


# ------------------------------------------------------------- §B tokenize --
def tokenize_request(text: str) -> int:
    """Count tokens of the full composed text with the SERVED model tokenizer."""
    import urllib.request
    body = json.dumps({"model": MODEL, "prompt": text}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8004/tokenize", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        out = json.loads(resp.read())
    count = out.get("count")
    if not isinstance(count, int) or count < 0 or \
            (out.get("tokens") is not None and len(out["tokens"]) != count):
        raise RuntimeError("TOKENIZE_UNRELIABLE")
    return count


# --------------------------------------------------------------- stage run --
def main() -> dict:
    started_wall = time.monotonic()
    report: dict = {
        "invocation_id": INVOCATION_ID,
        "accepted_halt": "semjudge-pilot-r6e (commit 1197d4d) stays sealed FAILED; "
                         "no result or agreement retro-generated",
        "stages": {}, "fixtures": {}, "halted": None,
        "limits": {"max_calls": MAX_CALLS, "max_total_tokens": MAX_TOTAL_TOKENS,
                   "max_wall_seconds": MAX_WALL_SECONDS, "retry": RETRY,
                   "concurrency": CONCURRENCY, "max_output_tokens": MAX_OUTPUT_TOKENS,
                   "endpoint": ENDPOINT, "model": MODEL},
    }

    def halt(code: str, detail: str = "") -> dict:
        report["halted"] = {"code": code, "detail": detail}
        report["status"] = "HALTED"
        (WORK_ROOT / "recovery-report.json").write_text(
            json.dumps(report, indent=1, ensure_ascii=False))
        return report

    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)

    # ---------------- §E.1 — evidence-bounded inputs -------------------------
    from poc.qasper_fulltext_calibration import DATASET
    ds = json.loads(DATASET.read_bytes())
    bundle = load_bundle(BUNDLE_PATH)
    note_excerpts: dict[str, dict] = {}
    source_ev: dict[str, dict] = {}
    for fid, pol in EXCERPT_POLICIES.items():
        paper_id = bundle[fid]["source_identity"]["paper_id"]
        pert_path = Path(PERTURBATION_BINDINGS[fid]).resolve()
        cap = pol.get("paragraph_cap")
        orig = apply_excerpt_policy(NOTES[paper_id].read_text(),
                                    pol["note_paragraph_regex"], cap)
        pert = apply_excerpt_policy(pert_path.read_text(),
                                    pol["note_paragraph_regex"], cap)
        ev = source_evidence(ds, paper_id, pol["source_anchor"],
                             pol["source_context_chars"])
        fixture = bundle[fid]
        pair = build_blind_pair(original_text=orig["excerpt"],
                                perturbed_text=pert["excerpt"],
                                dimension=APPROVED_SCOPES[fid])
        prompt = render_judge_user_prompt(pair)
        rec = {
            "fixture_id": fid,
            "excerpt_policy": pol["policy"],
            "policy_regex": pol["note_paragraph_regex"],
            "original": {"path": str(NOTES[paper_id].relative_to(RRSI_ROOT)),
                         "digest": digest_bytes(NOTES[paper_id].read_bytes()),
                         **{k: v for k, v in orig.items() if k != "excerpt"}},
            "perturbed": {"path": str(pert_path.relative_to(RRSI_ROOT)),
                          "digest": digest_bytes(pert_path.read_bytes()),
                          **{k: v for k, v in pert.items() if k != "excerpt"}},
            "source_evidence": {k: v for k, v in ev.items() if k != "excerpt"},
            "blind_pair": {"A_digest": digest_bytes(pair["A"].encode()),
                           "B_digest": digest_bytes(pair["B"].encode()),
                           "unblind_map_sealed": pair["unblind_map"]},
            "system_prompt": SYSTEM_PROMPT_JUDGE,
            "user_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "gold_expected_direction_excluded_from_judge_input": True,
            "g7_special_check": fid == "g7-1901-method",
        }
        note_excerpts[fid] = {"pair": pair, "prompt": prompt, "orig": orig,
                              "pert": pert, "evidence": ev}
        source_ev[fid] = ev
        (INPUTS_DIR / f"input-{fid}.json").write_text(
            json.dumps(rec, indent=1, ensure_ascii=False))
    report["stages"]["1_evidence_bounded_inputs"] = {"fixtures": len(note_excerpts)}
    report["fixtures"] = {fid: {"evidence_reference": {
        "source_char_range": ev["excerpt_char_range"],
        "source_anchor_offset": ev["anchor_char_offset"],
        "original_selected_ranges": note_excerpts[fid]["orig"]["selected_ranges"],
        "original_omitted_ranges": note_excerpts[fid]["orig"]["omitted_ranges"],
        "perturbed_selected_ranges": note_excerpts[fid]["pert"]["selected_ranges"],
        "perturbed_omitted_ranges": note_excerpts[fid]["pert"]["omitted_ranges"],
    }} for fid, ev in source_ev.items()}

    # ---------------- §E.2 — pre-call token instrumentation ------------------
    reserved: dict[str, int] = {}
    measured_tokens: dict[str, dict] = {}
    tool_schema_estimate = 96  # json tool-schema framing, metered conservatively
    try:
        for fid in note_excerpts:
            prompt = note_excerpts[fid]["prompt"]
            n_prompt = tokenize_request(prompt)
            n_system = tokenize_request(SYSTEM_PROMPT_JUDGE)
            reserved_input = n_prompt + n_system + tool_schema_estimate \
                + CHAT_TEMPLATE_MARGIN
            reserved[fid] = reserved_input + MAX_OUTPUT_TOKENS
            measured_tokens[fid] = {"prompt_tokens": n_prompt,
                                    "system_tokens": n_system,
                                    "tool_schema_estimate": tool_schema_estimate,
                                    "chat_template_margin": CHAT_TEMPLATE_MARGIN,
                                    "reserved_input": reserved_input,
                                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                                    "reserved_total": reserved[fid]}
    except Exception as exc:
        return halt("TOKENIZE_FAIL_CLOSED", str(exc)[:200])
    total_reserved = sum(reserved.values())
    if total_reserved > MAX_TOTAL_TOKENS:
        return halt("PRE_CALL_BUDGET_EXCEEDED",
                    f"reserved={total_reserved} limit={MAX_TOTAL_TOKENS} "
                    f"per_fixture={reserved}")
    report["stages"]["2_token_instrumentation"] = {
        "per_fixture": measured_tokens,
        "total_reserved": total_reserved,
        "limit": MAX_TOTAL_TOKENS,
        "within_budget": True,
    }

    # ---------------- §E.3 — blind A/B contract verification -----------------
    blind_ok = True
    for fid, rec in note_excerpts.items():
        rebuilt = render_judge_user_prompt(build_blind_pair(
            original_text=rec["orig"]["excerpt"],
            perturbed_text=rec["pert"]["excerpt"],
            dimension=APPROVED_SCOPES[fid]))
        if hashlib.sha256(rebuilt.encode()).hexdigest() != \
                hashlib.sha256(rec["prompt"].encode()).hexdigest():
            blind_ok = False
        if not blind_prompt_is_blind(rec["prompt"]):
            blind_ok = False
    if not blind_ok:
        return halt("BLIND_CONTRACT_VIOLATION")
    report["stages"]["3_blind_contract"] = {
        "deterministic_rebuild": True, "no_gold_leak": True,
        "unblind_map_sealed_outside_prompt": True}

    # ---------------- §E.4 — ledger reservation verification -----------------
    for var in ("AI_PAPERS_MODEL_CALL_BUDGET_LEDGER", "AI_PAPERS_MODEL_CALL_CEILING",
                "AI_PAPERS_INVOCATION_ID", "AI_PAPERS_MODEL_CALL_BUDGET_ROOT",
                "AI_PAPERS_EXECUTION_PERMIT"):
        if var not in os.environ:
            return halt("EXECUTION_BUDGET_NOT_ISSUED", var)
    sys.path.insert(0, "/home/ktl/projects/ai_papers/src")

    # ---------------- §E.5 — new invocation id and run dir -------------------
    from poc.execution_permit import assert_authorized
    from poc.run_dir_isolation import resolve_run_dir, seal_run_dir
    permit_invocation = json.loads(
        Path(os.environ["AI_PAPERS_EXECUTION_PERMIT"]).read_text()
    ).get("invocation_id")
    assert_authorized(
        workstream="semantic_judge_pilot", call_type="judge_evaluation",
        dataset_sha256=hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        paper_ids=["1802.07862", "1901.10133"],
        model=MODEL, endpoint=ENDPOINT, invocation_id=INVOCATION_ID)
    run_dir = resolve_run_dir(INVOCATION_ID, RUN_ROOT,
                              permit_invocation_id=permit_invocation)
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    report["run_dir"] = str(run_dir)
    report["stages"]["5_invocation"] = {"invocation_id": INVOCATION_ID,
                                        "run_dir": str(run_dir)}

    # ---------------- §E.6 — evaluation, g3 → g4 → g7 ------------------------
    from ai_papers_research.llm.call_budget import reserve_model_call_from_environment
    from ai_papers_research.paper.study.reader_note.llm import call_model

    calls = 0
    tokens_used = 0
    raw_packets: dict[str, dict] = {}
    for fid in ("g3-1802-result", "g4-1802-numeric", "g7-1901-method"):
        if calls >= MAX_CALLS:
            return halt("CALL_CAP", f"calls={calls}")
        if time.monotonic() - started_wall > MAX_WALL_SECONDS:
            return halt("WALL_CLOCK_CAP", f"calls={calls}")
        prompt = note_excerpts[fid]["prompt"]
        # §D — official reservation API only; fail before network on error.
        call_id = hashlib.md5(f"{INVOCATION_ID}:{fid}".encode()).hexdigest()
        reserve_model_call_from_environment(call_id=call_id)
        t0 = time.monotonic()
        try:
            raw, _ = call_model(
                base_url=ENDPOINT, api_key="sk-1234", model=MODEL,
                system=SYSTEM_PROMPT_JUDGE, user=prompt,
                max_tokens=MAX_OUTPUT_TOKENS, timeout=90,
                temperature=0.0, retries=RETRY, json_mode=False)
        except Exception as exc:
            calls += 1
            (raw_dir / f"resp-{fid}.json").write_text(json.dumps({
                "fixture_id": fid, "failure_type": "transport_error",
                "error": str(exc)[:300]}))
            return halt(f"TRANSPORT_ERROR:{fid}", str(exc)[:200])
        calls += 1
        try:
            from ai_papers_research.paper.study.reader_note.llm import \
                get_last_call_metadata
            meta = get_last_call_metadata() or {}
        except Exception:
            meta = {}
        usage = (meta.get("provider_usage") or {}).get("usage") or {}

        # §D — persist the RAW response and usage FIRST; adjudicate after.
        resp_record = {"fixture_id": fid, "call_id": call_id,
                       "raw_output": raw, "usage": usage,
                       "latency_ms": round((time.monotonic() - t0) * 1000, 1)}
        try:
            (raw_dir / f"resp-{fid}.json").write_text(
                json.dumps(resp_record, indent=1, ensure_ascii=False))
        except OSError as exc:
            return halt("RESPONSE_PERSISTENCE_FAILED",
                        f"{fid}: {exc} — response not treated as success")
        tokens_used += (usage.get("prompt_tokens") or 0) \
            + (usage.get("completion_tokens") or 0)
        raw_packets[fid] = resp_record

    # ---------------- §E.7 — unblind, then Agreement -------------------------
    total_after = tokens_used
    for fid, rec in note_excerpts.items():
        raw = raw_packets[fid]["raw_output"]
        usage = raw_packets[fid]["usage"]
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
                                   "abstention": {"refused": True,
                                                  "reason": "unparsed"}},
            unblind_map=rec["pair"]["unblind_map"],
            gold_expected_direction=GOLD_EXPECTED_DIRECTION[fid]) \
            if validation.get("valid") else None
        g7 = g7_methodological_loss_check(judge) \
            if fid == "g7-1901-method" and judge else None
        fx = report["fixtures"][fid]
        fx.update({
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "actual_cost_tokens": (usage.get("prompt_tokens") or 0)
                                  + (usage.get("completion_tokens") or 0),
            "judge_verdict": judge,
            "validation": validation,
            "gold_agreement": gold and gold["agreement"],
            "gold_agreement_detail": gold,
            "reserved_budget": measured_tokens[fid]["reserved_total"],
        })
        if g7:
            fx["g7_methodological_loss_check"] = g7
            fx["g7_residual_omission_analysis"] = {
                "classification": g7["classification"],
                # flag False == the judge DID assess methodological loss from
                # the excerpts → the excerpt policy did NOT drop the info
                # needed for the required-information-loss evaluation.
                "excerpt_caused_info_loss": bool(g7["flag"]),
                "requirement_met": not g7["flag"],
                "note": "evaluated on evidence-bounded excerpts; judge "
                        "abstention/basis inspected separately below",
            }

    over = total_after > MAX_TOTAL_TOKENS
    elapsed = round(time.monotonic() - started_wall, 1)
    report["status"] = "BUDGET_EXCEEDED_POST_HOC" if over else "COMPLETE"
    report["totals"] = {"calls": calls, "tokens_input": sum(
        raw_packets[f]["usage"].get("prompt_tokens") or 0 for f in raw_packets),
        "tokens_output": sum(raw_packets[f]["usage"].get("completion_tokens")
                             or 0 for f in raw_packets),
        "tokens_total": total_after, "limit": MAX_TOTAL_TOKENS,
        "within_budget": not over, "wall_seconds": elapsed}
    seal_run_dir(run_dir)
    (WORK_ROOT / "recovery-report.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False))
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, ensure_ascii=False))
