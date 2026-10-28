# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Reader-context QASPER calibration (approved scope: 2 papers / 10 cases, 1 run).

Directive R1 execution. Input is the FIXED reader-note artifact
(`04_reader_note.ko.md`, sha256-bound at adapter preparation) — full-text
injection is prohibited by the directive. Model/config fixed
(qwen3.8-flash-next-fp8, temperature 0.0, max_output 1024, one documented
attempt per case), scorer and dataset freeze unchanged, no paid external API.

Usage:
    python3 -m poc.qasper_readercontext_calibration run   # collect (bounded)
    python3 -m poc.qasper_readercontext_calibration build # packets -> predictions
    python3 -m poc.qasper_readercontext_calibration score # unchanged consumer

Evaluation-integrity amendment (post a6cd3b1): every case's paper identity
binding is verified fail-closed BEFORE the first model call; a mismatch or
missing provenance refuses the run with 0 calls and 0 ledger reservations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from poc.qasper_fulltext_calibration import (
    AI_PAPERS_ROOT,
    APPROVED_MODEL,
    DATASET,
    MAX_CALLS,
    MAX_TOKENS,
    MAX_WALL_SECONDS,
    TEMPERATURE,
    TIMEOUT,
    ai_papers_head,
    parse_response,
)

RRSI_ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = RRSI_ROOT / "poc/runs/qasper-readercontext-calibration"
# Legacy single artifact (a6cd3b1 run; INVALID_CONTEXT_MISMATCH — see 21).
READER_NOTE = (RRSI_ROOT / "poc/runs/r0b2/reader/r0b2-repeat-4b"
               / "02_reading_chain/output/04_reader_note.ko.md")
# Per-paper note registry (R1 generation; identity-bound per paper).
READER_NOTE_REGISTRY = (RRSI_ROOT
                        / "poc/runs/qasper-reader-note-r1/source-registration-rrsi.json")


def reader_notes() -> dict:
    """paper_id -> {"artifact": Path, "sha256": str} from the rrsi registry."""
    reg = json.loads(READER_NOTE_REGISTRY.read_text())
    return {
        paper_id: {
            "artifact": RRSI_ROOT / entry["reader_note_artifact"],
            "sha256": entry["reader_note_sha256"],
            "source_version": entry["canonical_arxiv_version_id"],
        }
        for paper_id, entry in reg["sources"].items()
    }


def reader_note_text() -> str:
    text = READER_NOTE.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert digest.startswith("bffb8b75"), f"reader-note artifact drift: {digest[:16]}"
    return text


def cases_file() -> list:
    return [json.loads(l) for l in
            (RUN_DIR.parent / "qasper-calibration/dev-cases-2papers.jsonl").open()
            if l.strip()]


def preflight() -> dict:
    """Ordered, non-executing execution-path gate (directive §A 1–6).

    Returns {"status": "READY"|"BLOCK", "calls": 0, "reservations": 0, ...}.
    Never imports or touches the model client. Order is mandatory:
    permit -> identity -> split/holdout -> model/endpoint -> budget -> ledger.
    """
    import os
    calls = 0
    reservations = 0
    checks = []
    # 1. Execution Permit (includes workstream/call-type/model/endpoint/budget/
    #    ledger reservation capability — environment alone authorizes nothing).
    from poc.execution_permit import ExecutionPermitBlocked, assert_authorized
    try:
        permit_result = assert_authorized(
            workstream="reader_context_qa", call_type="qa_inference",
            dataset_sha256=hashlib.sha256(DATASET.read_bytes()).hexdigest(),
            paper_ids=[c["source_paper_ref"]["paper_id"] for c in cases_file()],
            model=APPROVED_MODEL, endpoint="http://192.168.0.199/v1",
            invocation_id=os.environ.get("AI_PAPERS_PROCESS_TELEMETRY_INVOCATION_ID", ""))
    except ExecutionPermitBlocked as blocked:
        return {"status": "BLOCK", "code": blocked.code, "calls": calls,
                "reservations": reservations}
    checks.append("EXECUTION_PERMIT")
    # 2. Paper Identity + 3. Split/Holdout (resolve_binding verifies both,
    #    fail-closed, per case, against the per-paper note registry).
    from poc.paper_identity_binding import IdentityBindingBlocked, resolve_binding
    notes = reader_notes()
    for case in cases_file():
        paper_id = case["source_paper_ref"]["paper_id"]
        binding_note = notes.get(paper_id)
        if binding_note is None:
            return {"status": "BLOCK", "code": "READER_NOTE_REGISTRY_ENTRY_ABSENT",
                    "calls": calls, "reservations": reservations}
        try:
            resolve_binding(
                question_paper_id=paper_id,
                question_source_version="v0.3",
                reader_run_dir=binding_note["artifact"].parents[2],
                note_artifact_path=binding_note["artifact"],
                expected_note_digest=binding_note["sha256"],
                expected_note_source_version=binding_note["source_version"],
                registry_path=READER_NOTE_REGISTRY,
                split="dev",
            )
        except IdentityBindingBlocked as blocked:
            return {"status": "BLOCK", "code": blocked.code, "calls": calls,
                    "reservations": reservations}
    checks.append("PAPER_IDENTITY_AND_SPLIT")
    # 5. Budget: ceiling env must exist and cover the permitted call count.
    ceiling = os.environ.get("AI_PAPERS_MODEL_CALL_CEILING")
    if not ceiling or int(ceiling) < len(cases_file()):
        return {"status": "BLOCK", "code": "BUDGET_CEILING_INSUFFICIENT",
                "calls": calls, "reservations": reservations}
    checks.append("BUDGET")
    # 4. Model/Endpoint validated inside the permit; 6. ledger reservation
    # capability probe ran inside the permit (PERMIT_LEDGER).
    checks.append("MODEL_ENDPOINT")
    checks.append("LEDGER_RESERVATION_CAPABLE")
    return {"status": "READY", "calls": calls, "reservations": reservations,
            "checks": checks,
            "permit_checks": permit_result["checks"]}


def run() -> int:
    import os
    # Fail-closed: model calls must go through the ledger/telemetry bindings.
    # An unbound invocation is refused BEFORE identity checks (0 calls).
    for env in ("AI_PAPERS_MODEL_CALL_BUDGET_LEDGER",
                "AI_PAPERS_MODEL_CALL_CEILING",
                "AI_PAPERS_PROCESS_TELEMETRY_EVENTS",
                "AI_PAPERS_PROCESS_TELEMETRY_INVOCATION_ID"):
        if not os.environ.get(env):
            print(json.dumps({"status": "FAIL_CLOSED",
                              "reason": "CALL_BUDGET_ENV_ABSENT", "env": env}))
            return 1
    gate = preflight()
    if gate["status"] != "READY":
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "PREFLIGHT_BLOCKED",
                          "code": gate["code"], "calls": 0,
                          "reservations": 0}))
        return 1
    # Artifact immutability: invocation-bound, collision-checked run dir.
    from poc.run_dir_isolation import resolve_run_dir, seal_run_dir
    permit_invocation = json.loads(
        Path(os.environ["AI_PAPERS_EXECUTION_PERMIT"]).read_text()
    ).get("invocation_id") or ""
    run_dir = resolve_run_dir(
        os.environ["AI_PAPERS_PROCESS_TELEMETRY_INVOCATION_ID"],
        RUN_DIR.parent, permit_invocation_id=permit_invocation)
    RUN_DIR = run_dir  # all raw/summary writes go to the invocation-bound dir
    ds = json.loads(DATASET.read_bytes())
    cases = cases_file()
    # Identity/split verified by preflight; raw collection begins.
    notes = reader_notes()
    raw_dir = RUN_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    head = ai_papers_head()
    started = time.monotonic()
    calls = 0
    for case in cases:
        if calls >= MAX_CALLS:
            print(json.dumps({"status": "FAIL_CLOSED", "reason": "CALL_CAP"}))
            return 1
        if time.monotonic() - started > MAX_WALL_SECONDS:
            print(json.dumps({"status": "FAIL_CLOSED", "reason": "WALL_CLOCK_CAP"}))
            return 1
        paper_id = case["source_paper_ref"]["paper_id"]
        question = case["input_payload"]["question"]
        binding_note = notes[paper_id]
        note_path = binding_note["artifact"]
        note = note_path.read_text(encoding="utf-8")
        user = (f"Paper reading note:\n\"\"\"\n{note}\n\"\"\"\n\nQuestion: {question}\n\n"
                'Respond with the JSON object now (answer_text, answer_type, evidence_quotes).')
        sys.path.insert(0, str(AI_PAPERS_ROOT / "src"))
        from ai_papers_research.paper.study.reader_note.llm import call_model  # noqa: E402
        t0 = time.monotonic()
        try:
            raw, _ = call_model(
                base_url="http://192.168.0.199/v1", api_key="sk-1234",
                model=APPROVED_MODEL, system=SYSTEM_PROMPT_RC, user=user,
                max_tokens=MAX_TOKENS, timeout=TIMEOUT, temperature=TEMPERATURE,
                retries=0, json_mode=False,
            )
        except Exception as exc:
            calls += 1
            slug = hashlib.sha256(case["case_id"].encode()).hexdigest()[:12]
            (raw_dir / f"packet-{slug}.json").write_text(json.dumps(
                {"case_id": case["case_id"], "failure_type": "transport_error",
                 "error": str(exc)[:300], "record": None}))
            continue
        latency = round((time.monotonic() - t0) * 1000, 1)
        parsed = parse_response(raw, document_text=note)
        packet = {
            "case_id": case["case_id"], "paper_id": paper_id,
            "input_mode": "reader_context",
            "reader_note_artifact": str(note_path),
            "reader_note_sha256": hashlib.sha256(note.encode()).hexdigest(),
            "ai_papers_commit": head,
            "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
            "failure_type": "none" if "failure" not in parsed else parsed["failure"],
            "latency_ms": latency,
            "record": parsed.get("failure") and None or {
                "case_id": case["case_id"],
                "schema": "ai-papers-external-qa-intake/v0.1",
                "question": question,
                "condition": {"input_mode": "selected_sections",
                              "evidence_policy": "evidence_span_allowed",
                              "retrieval_disabled": True},
                "answer": {"text": parsed["answer_text"],
                           "answer_type": parsed["answer_type"],
                           "evidence_refs": [
                               {"ref_id": s["ref_id"], "ref_kind": "sentence_id"}
                               for s in parsed["spans"]],
                           "answer_status": "answered" if parsed["evidence_literals"]
                           else "unanswerable_claimed"},
                "source_identity": {
                    "source_id": paper_id, "ai_papers_commit": head,
                    "extraction_bundle_digest": "sha256:"
                    + hashlib.sha256(note.encode()).hexdigest(),
                },
                "execution_metadata": {
                    "replay_cli": "poc.qasper_readercontext_calibration (rrsi glue)",
                    "artifact_ref": note_path.name,
                    "run_id": f"qasper-rc-cal-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
                    "determinism": "single_run",
                },
            },
            "evidence_spans": parsed.get("spans") or [],
            "raw_output_digest": "sha256:" + hashlib.sha256(str(raw).encode()).hexdigest(),
        }
        slug = hashlib.sha256(case["case_id"].encode()).hexdigest()[:12]
        (raw_dir / f"packet-{slug}.json").write_text(json.dumps(packet, indent=1))
        calls += 1
        print(json.dumps({"case": case["case_id"][:45],
                          "status": packet["failure_type"],
                          "answer_status": (packet["record"] or {}).get("answer", {}).get("answer_status"),
                          "latency_ms": latency}))
    summary = {"schema": "rrsi-qasper-readercontext-run/v0.1", "calls_used": calls,
               "wall_seconds": round(time.monotonic() - started, 1),
               "model": APPROVED_MODEL,
               "reader_note_registry_sha256": hashlib.sha256(
                   READER_NOTE_REGISTRY.read_bytes()).hexdigest(),
               "completed_at": datetime.now(UTC).isoformat()}
    (RUN_DIR / "run-summary.json").write_text(json.dumps(summary, indent=1))
    seal_run_dir(RUN_DIR)  # fix manifest + artifact digests after execution
    print(json.dumps(summary))
    return 0


SYSTEM_PROMPT_RC = (
    "You are a careful research-paper QA assistant. Answer the user's question "
    "using ONLY the provided paper reading note. Respond with a single JSON "
    "object and nothing else, with exactly these fields:\n"
    '  "answer_text": the answer (a concise span or phrase from the reading note, '
    "or a bare yes/no when the question is yes/no)\n"
    '  "answer_type": one of "extractive", "abstractive", "yes_no", "unanswerable"\n'
    '  "evidence_quotes": a list of VERBATIM substrings copied from the reading note '
    "that support the answer (empty list when unanswerable)\n"
    "If the reading note does not answer the question, set answer_type to "
    '"unanswerable", use an empty answer_text and an empty evidence_quotes list. '
    "Never invent text that is not a literal substring of the reading note."
)


def build() -> int:
    predictions = []
    for p in sorted((RUN_DIR / "raw").glob("packet-*.json")):
        packet = json.loads(p.read_text())
        record = packet.get("record")
        if record is None:
            continue
        predictions.append({
            "case_id": packet["case_id"], "paper_id": packet["paper_id"],
            "intake_record": record,
            "evidence_literals": [s["surface"] for s in packet.get("evidence_spans") or []],
        })
    manifest = {
        "schema": "rrsi-qasper-readercontext-calibration-run/v0.1",
        "built_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ai_papers_commit": ai_papers_head(),
        "dataset_path": str(DATASET),
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "input_mode": "reader_context",
        "reader_note_registry_sha256": hashlib.sha256(
            READER_NOTE_REGISTRY.read_bytes()).hexdigest(),
        "prediction_count": len(predictions),
    }
    (RUN_DIR / "predictions.json").write_text(
        json.dumps({"manifest": manifest, "predictions": predictions}, indent=1))
    print(json.dumps({"built": len(predictions)}))
    return 0


def score() -> int:
    data = json.loads((RUN_DIR / "predictions.json").read_text())
    sys.path.insert(0, str(RRSI_ROOT.parent / "research_benchmarks"))
    from adapters.ai_papers.reader_note.external_qa_consumer import score_predictions  # noqa: E402
    report = score_predictions(
        data["predictions"], split="dev",
        manifest_ref="r1-readercontext-qasper-calibration",
        expected_commit=data["manifest"]["ai_papers_commit"],
    )
    (RUN_DIR / "score-report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: report[k] for k in
                      ("case_count", "answer_f1", "evidence_f1", "evidence_measured_cases",
                       "unanswerable_confusion")}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["preflight", "run", "build", "score"])
    args = ap.parse_args()
    if args.step == "preflight":
        print(json.dumps(preflight()))
        return 0 if preflight()["status"] == "READY" else 1
    return {"run": run, "build": build, "score": score}[args.step]()


if __name__ == "__main__":
    raise SystemExit(main())
