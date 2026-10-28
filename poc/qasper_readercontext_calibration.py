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
# The sha256-bound reader-note artifact from adapter preparation (5038b87).
READER_NOTE = (RRSI_ROOT / "poc/runs/r0b2/reader/r0b2-repeat-4b"
               / "02_reading_chain/output/04_reader_note.ko.md")


def reader_note_text() -> str:
    text = READER_NOTE.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert digest.startswith("bffb8b75"), f"reader-note artifact drift: {digest[:16]}"
    return text


def run() -> int:
    ds = json.loads(DATASET.read_bytes())
    cases = [json.loads(l) for l in
             (RUN_DIR.parent / "qasper-calibration/dev-cases-2papers.jsonl").open()
             if l.strip()]
    note = reader_note_text()
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
            "reader_note_artifact": str(READER_NOTE),
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
                    "artifact_ref": READER_NOTE.name,
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
               "reader_note_sha256": hashlib.sha256(note.encode()).hexdigest(),
               "completed_at": datetime.now(UTC).isoformat()}
    (RUN_DIR / "run-summary.json").write_text(json.dumps(summary, indent=1))
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
        "reader_note_sha256": hashlib.sha256(
            reader_note_text().encode()).hexdigest(),
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
    ap.add_argument("step", choices=["run", "build", "score"])
    args = ap.parse_args()
    return {"run": run, "build": build, "score": score}[args.step]()


if __name__ == "__main__":
    raise SystemExit(main())
