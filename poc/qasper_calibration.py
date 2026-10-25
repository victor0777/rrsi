# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""QASPER calibration glue: collection packets -> consumer predictions.json.

Directive R0-b2 review, Workstream B item 5 (minimal record extraction). The
ai_papers collection CLI persists packets with verified evidence offsets whose
`surface` field is the evidence literal (verified substring of the abstract,
`external_qa_producer`). This glue only recovers that field into the frozen
WO-1 consumer prediction shape

    {"case_id", "paper_id", "intake_record", "evidence_literals"}

without touching ai_papers, the adapter, or the scorer contracts. It also
freezes the run environment (dataset digest, endpoint, invocation) and runs
the consumer + scorer unchanged.

Usage:
    python3 -m poc.qasper_calibration build   # packets -> predictions.json
    python3 -m poc.qasper_calibration score   # consumer + scorer, unchanged
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

RRSI_ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = RRSI_ROOT / "poc/runs/qasper-calibration"
RB_ROOT = RRSI_ROOT.parent / "research_benchmarks"
AI_PAPERS_ROOT = RRSI_ROOT.parent / "ai_papers"
CONSUMER = RB_ROOT / "adapters/ai_papers/reader_note/external_qa_consumer.py"
DATASET = RB_ROOT / "benchmarks/qasper/dataset/qasper-dev-v0.3.json"


def ai_papers_head() -> str:
    return subprocess.run(["git", "-C", str(AI_PAPERS_ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def build() -> int:
    predictions = []
    for p in sorted(RUN_DIR.glob("raw/packet-*.json")):
        packet = json.loads(p.read_bytes())
        record = packet["record"]
        # evidence literals recovered from verified offsets' surface field
        literals = []
        for span in packet.get("evidence_spans") or []:
            surface = str(span.get("surface") or "")
            if surface and surface not in literals:
                literals.append(surface)
        predictions.append({
            "case_id": packet["case_id"],
            "paper_id": record["source_identity"]["source_id"],
            "intake_record": record,
            "evidence_literals": literals,
        })
    manifest = {
        "schema": "rrsi-qasper-calibration-run/v0.1",
        "built_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ai_papers_commit": ai_papers_head(),
        "dataset_path": str(DATASET),
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "endpoint": "owner-provisioned LAN gateway (no paid external API)",
        "prediction_count": len(predictions),
        "contract_versions": {
            "intake": "ai-papers-external-qa-intake/v0.1",
            "consumer_record": "research-bench-adapter-qa-record/v0.1",
            "scorer": "qasper-answer-f1/v0.1",
        },
    }
    (RUN_DIR / "predictions.json").write_text(
        json.dumps({"manifest": manifest, "predictions": predictions},
                   ensure_ascii=False, indent=1))
    print(json.dumps({"built": len(predictions), "manifest_sha256":
                      hashlib.sha256(json.dumps(manifest, sort_keys=True,
                                                separators=(",", ":")).encode()).hexdigest()[:16]}))
    return 0


def score() -> int:
    data = json.loads((RUN_DIR / "predictions.json").read_text())
    expected_commit = data["manifest"]["ai_papers_commit"]
    sys.path.insert(0, str(RB_ROOT))
    from adapters.ai_papers.reader_note.external_qa_consumer import (  # noqa: E402
        score_predictions,
    )
    report = score_predictions(
        data["predictions"], split="dev",
        manifest_ref="r0b2-review-qasper-calibration",
        expected_commit=expected_commit,
    )
    (RUN_DIR / "score-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(json.dumps({k: report[k] for k in
                      ("case_count", "answer_f1", "evidence_f1", "evidence_measured_cases",
                       "unanswerable_confusion", "duplicate_predictions_excluded")}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["build", "score"])
    args = ap.parse_args()
    return build() if args.step == "build" else score()


if __name__ == "__main__":
    raise SystemExit(main())
