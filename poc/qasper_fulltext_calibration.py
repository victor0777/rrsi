# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Full-text QASPER calibration (approved scope: 2 papers / 10 cases, 1 run).

Directive R1 execution. Reuses the frozen QASPER dataset (embedded full_text),
the approved model/config of the abstract-only calibration (qwen3.8-flash-next-fp8,
temperature 0.0, max_output 1024, json_mode off, one documented attempt per
case), and the unchanged research_benchmarks consumer + scorer contracts.
No scorer changes; no ai_papers changes; no paid external API (LAN gateway).

Inference path: ai_papers `reader_note.llm.call_model` (same direct backend
the collection CLI used), so the call-budget ledger and provider-usage
telemetry are bound through the same environment variables. Fail-closed:
a pre-registered call cap (12) and wall-clock timeout stop the run.

Usage:
    python3 -m poc.qasper_fulltext_calibration run   # collect (bounded)
    python3 -m poc.qasper_fulltext_calibration build # packets -> predictions.json
    python3 -m poc.qasper_fulltext_calibration score # unchanged consumer+scorer
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

RRSI_ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = RRSI_ROOT / "poc/runs/qasper-fulltext-calibration"
RB_ROOT = RRSI_ROOT.parent / "research_benchmarks"
AI_PAPERS_ROOT = RRSI_ROOT.parent / "ai_papers"
DATASET = RB_ROOT / "benchmarks/qasper/dataset/qasper-dev-v0.3.json"

# Approved constants (identical to the abstract-only calibration).
APPROVED_MODEL = "qwen3.8-flash-next-fp8"
MAX_TOKENS = 1024
TEMPERATURE = 0.0
TIMEOUT = 600
MAX_CALLS = 12
MAX_WALL_SECONDS = 900

# Full-text request: same JSON contract and literal-quote rule as the
# abstract-only producer, with the input surface switched to paper text.
SYSTEM_PROMPT = (
    "You are a careful research-paper QA assistant. Answer the user's question "
    "using ONLY the provided paper text. Respond with a single JSON object "
    "and nothing else, with exactly these fields:\n"
    '  "answer_text": the answer (a concise span or phrase from the paper text, '
    "or a bare yes/no when the question is yes/no)\n"
    '  "answer_type": one of "extractive", "abstractive", "yes_no", "unanswerable"\n'
    '  "evidence_quotes": a list of VERBATIM substrings copied from the paper text '
    "that support the answer (empty list when unanswerable)\n"
    "If the paper text does not answer the question, set answer_type to "
    '"unanswerable", use an empty answer_text and an empty evidence_quotes list. '
    "Never invent text that is not a literal substring of the paper text."
)


def ai_papers_head() -> str:
    return subprocess.run(["git", "-C", str(AI_PAPERS_ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def flatten_full_text(sections) -> str:
    """Structured full_text sections -> flat text, preserving reading order."""
    parts = []
    for section in sections or []:
        if isinstance(section, dict):
            name = str(section.get("section_name") or "")
            if name:
                parts.append(name)
            for para in section.get("paragraphs") or []:
                parts.append(str(para))
        elif isinstance(section, str):
            parts.append(section)
    return "\n".join(p for p in parts if p.strip())


def normalized_find(text: str, needle: str):
    """Locate a quote allowing whitespace-run differences; return (start, end)."""
    if not needle:
        return None
    pattern = "".join("\\s+" if ch.isspace() else re.escape(ch) for ch in needle.strip())
    match = re.search(pattern, text)
    if match is None:
        return None
    start, end = match.span()
    # extend whitespace-only boundaries so surface == text[start:end] round-trips
    while start > 0 and text[start - 1].isspace():
        start -= 1
    while end < len(text) and text[end].isspace():
        end += 1
    return start, end


def parse_response(raw_text: str, *, document_text: str, case_id: str = "") -> dict:
    """Same rule as `external_qa_producer.parse_model_response`, full-text surface."""
    raw = str(raw_text or "").strip()
    if not raw:
        return {"failure": "PRODUCER_EMPTY_RESPONSE"}
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match is None:
        return {"failure": "PRODUCER_RESPONSE_PARSE_ERROR"}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"failure": "PRODUCER_RESPONSE_PARSE_ERROR"}
    if not isinstance(parsed, dict):
        return {"failure": "PRODUCER_RESPONSE_PARSE_ERROR"}
    answer_text = " ".join(str(parsed.get("answer_text") or "").split())
    answer_type = str(parsed.get("answer_type") or "").strip().lower()
    if answer_type not in ("extractive", "abstractive", "yes_no", "unanswerable"):
        return {"failure": f"PRODUCER_INVALID_ANSWER_TYPE:{answer_type}"}
    if answer_type == "unanswerable":
        return {"answer_text": "", "answer_type": "unanswerable",
                "evidence_literals": [], "spans": [],
                "abstention": {"status": "abstention_reported",
                               "reported_answer_type": "unanswerable"}}
    literals, spans = [], []
    for quote in parsed.get("evidence_quotes") or []:
        quote = " ".join(str(quote or "").split())
        if not quote:
            continue
        loc = normalized_find(document_text, quote)
        if loc is not None and quote not in literals:
            literals.append(quote)
            spans.append({"ref_id": f"ev_{len(spans):03d}",
                          "start": loc[0], "end": loc[1],
                          "surface": document_text[loc[0]:loc[1]]})
    if answer_type == "yes_no" and answer_text.lower() not in ("yes", "no"):
        return {"failure": "PRODUCER_INVALID_YES_NO_RESPONSE"}
    abstention = None
    if not literals:
        abstention = {"status": "evidence_missing", "downgraded_from_answer_type": answer_type}
    return {"answer_text": answer_text if literals else "", "answer_type": answer_type,
            "evidence_literals": literals, "spans": spans, "abstention": abstention}


def run() -> int:
    ds = json.loads(DATASET.read_bytes())
    cases = [json.loads(l) for l in
             (RUN_DIR.parent / "qasper-calibration/dev-cases-2papers.jsonl").open()
             if l.strip()]
    raw_dir = RUN_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    head = ai_papers_head()
    started_at = time.monotonic()
    calls = 0
    for case in cases:
        if calls >= MAX_CALLS:
            print(json.dumps({"status": "FAIL_CLOSED", "reason": "CALL_CAP"}))
            return 1
        if time.monotonic() - started_at > MAX_WALL_SECONDS:
            print(json.dumps({"status": "FAIL_CLOSED", "reason": "WALL_CLOCK_CAP"}))
            return 1
        paper_id = case["source_paper_ref"]["paper_id"]
        document = flatten_full_text(ds[paper_id]["full_text"])
        question = case["input_payload"]["question"]
        user = (f"Paper text:\n\"\"\"\n{document}\n\"\"\"\n\nQuestion: {question}\n\n"
                'Respond with the JSON object now (answer_text, answer_type, evidence_quotes).')
        sys.path.insert(0, str(AI_PAPERS_ROOT / "src"))
        from ai_papers_research.paper.study.reader_note.llm import call_model  # noqa: E402
        t0 = time.monotonic()
        try:
            raw, finish = call_model(
                base_url="http://192.168.0.199/v1", api_key="sk-1234",
                model=APPROVED_MODEL, system=SYSTEM_PROMPT, user=user,
                max_tokens=MAX_TOKENS, timeout=TIMEOUT, temperature=TEMPERATURE,
                retries=0, json_mode=False,
            )
        except Exception as exc:
            calls += 1
            packet = {"case_id": case["case_id"], "failure_type": "transport_error",
                      "error": str(exc)[:300], "record": None}
            slug = hashlib.sha256(case["case_id"].encode()).hexdigest()[:12]
            (raw_dir / f"packet-{slug}.json").write_text(json.dumps(packet))
            continue
        latency = round((time.monotonic() - t0) * 1000, 1)
        parsed = parse_response(raw, document_text=document)
        packet = {
            "case_id": case["case_id"],
            "paper_id": paper_id,
            "input_mode": "full_text",
            "ai_papers_commit": head,
            "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
            "failure_type": "none" if "failure" not in parsed else parsed["failure"],
            "latency_ms": latency,
            "record": parsed.get("failure") and None or {
                "case_id": case["case_id"],
                "schema": "ai-papers-external-qa-intake/v0.1",
                "question": question,
                "condition": {"input_mode": "full_text",
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
                    "source_id": paper_id,
                    "ai_papers_commit": head,
                    "extraction_bundle_digest": "sha256:"
                    + hashlib.sha256(DATASET.read_bytes()).hexdigest(),
                },
                "execution_metadata": {
                    "replay_cli": "poc.qasper_fulltext_calibration (rrsi glue)",
                    "artifact_ref": "poc/runs/qasper-fulltext-calibration/02_external_qa.json",
                    "run_id": f"qasper-fulltext-cal-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
                    "determinism": "single_run",
                },
            },
            "evidence_spans": parsed.get("spans") or [],
            "raw_output_digest": "sha256:" + hashlib.sha256(str(raw).encode()).hexdigest(),
        }
        slug = hashlib.sha256(case["case_id"].encode()).hexdigest()[:12]
        (raw_dir / f"packet-{slug}.json").write_text(json.dumps(packet, indent=1))
        calls += 1
        print(json.dumps({"case": case["case_id"][:45], "status": packet["failure_type"],
                          "answer_status": (packet["record"] or {}).get("answer", {}).get("answer_status"),
                          "latency_ms": latency}))
    summary = {"schema": "rrsi-qasper-fulltext-run/v0.1", "calls_used": calls,
               "wall_seconds": round(time.monotonic() - started_at, 1),
               "model": APPROVED_MODEL, "completed_at":
               datetime.now(UTC).isoformat()}
    (RUN_DIR / "run-summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary))
    return 0


def build() -> int:
    predictions = []
    for p in sorted((RUN_DIR / "raw").glob("packet-*.json")):
        packet = json.loads(p.read_text())
        record = packet.get("record")
        if record is None:
            continue
        literals = [s["surface"] for s in packet.get("evidence_spans") or []]
        predictions.append({
            "case_id": packet["case_id"], "paper_id": packet["paper_id"],
            "intake_record": record, "evidence_literals": literals,
        })
    manifest = {
        "schema": "rrsi-qasper-fulltext-calibration-run/v0.1",
        "built_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ai_papers_commit": ai_papers_head(),
        "dataset_path": str(DATASET),
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "input_mode": "full_text",
        "prediction_count": len(predictions),
    }
    (RUN_DIR / "predictions.json").write_text(
        json.dumps({"manifest": manifest, "predictions": predictions}, indent=1))
    print(json.dumps({"built": len(predictions)}))
    return 0


def score() -> int:
    data = json.loads((RUN_DIR / "predictions.json").read_text())
    sys.path.insert(0, str(RB_ROOT))
    from adapters.ai_papers.reader_note.external_qa_consumer import score_predictions  # noqa: E402
    report = score_predictions(
        data["predictions"], split="dev",
        manifest_ref="r1-fulltext-qasper-calibration",
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
