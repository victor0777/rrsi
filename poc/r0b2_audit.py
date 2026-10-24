# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""R0-b2 ledger↔telemetry reconciliation audit (fail-closed reporting).

Directive R0-b2 item 1: distinguish, per call,
  - reserved        (ledger `model_call_budget_reserved`, before network)
  - rejected        (ledger `model_call_budget_rejected`, before network)
  - terminal        (telemetry `model_call_terminal`, after network)
  - success / fail  (telemetry status, http_status, e.g. 404)
  - usage recorded  (telemetry availability_status == "reported")

A call reserved without a terminal record, or a terminal without recorded
usage, is a contract violation -> the audit exits 1 (fail-closed) even though
the trial itself may have succeeded. Summarizes token totals and per-call
latency. No rrsi core changes.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--telemetry", required=True)
    ap.add_argument("--invocation-id", default=None,
                    help="restrict audit to one invocation (default: all)")
    args = ap.parse_args()

    ledger = [json.loads(l) for l in open(args.ledger) if l.strip()]
    tele = [json.loads(l) for l in open(args.telemetry) if l.strip()]
    if args.invocation_id:
        tele = [e for e in tele if e.get("invocation_id") == args.invocation_id]

    reserved_all = [e for e in ledger if e.get("event_type") == "model_call_budget_reserved"]
    rejected_all = [e for e in ledger if e.get("event_type") == "model_call_budget_rejected"]
    if args.invocation_id:
        reserved = [e for e in reserved_all if e.get("invocation_id") == args.invocation_id]
        rejected = [e for e in rejected_all if e.get("invocation_id") == args.invocation_id]
    else:
        reserved, rejected = reserved_all, rejected_all
    terminals = [e for e in tele if e.get("event_type") == "model_call_terminal"]

    res_ids = {e["call_id"] for e in reserved}
    tele_ids = {e["call_id"] for e in terminals}
    by_id = {e["call_id"]: e for e in terminals}

    no_terminal = sorted(res_ids - tele_ids)
    no_reservation = sorted(tele_ids - res_ids)

    status_counts: dict[str, int] = {}
    usage_counts: dict[str, int] = {}
    http_counts: dict[str, int] = {}
    tokens_in = tokens_out = 0
    latencies = []
    for e in terminals:
        status_counts[e.get("status", "?")] = status_counts.get(e.get("status", "?"), 0) + 1
        avail = ((e.get("token_usage") or {}).get("availability_status")
                 or (e.get("usage") or {}).get("availability_status")
                 or "absent")
        usage_counts[avail] = usage_counts.get(avail, 0) + 1
        http = e.get("http_status")
        http_counts[str(http)] = http_counts.get(str(http), 0) + 1
        u = e.get("token_usage") or e.get("usage") or {}
        tokens_in += (u.get("prompt_tokens") or 0)
        tokens_out += (u.get("completion_tokens") or 0)
        if e.get("latency_ms") is not None:
            latencies.append(e["latency_ms"])

    violations = []
    if no_terminal:
        violations.append(f"RESERVED_WITHOUT_TERMINAL:{len(no_terminal)}")
    if no_reservation:
        violations.append(f"TERMINAL_WITHOUT_RESERVATION:{len(no_reservation)}")
    if usage_counts.get("reported", 0) + usage_counts.get("partial", 0) != len(terminals):
        violations.append("TERMINAL_WITHOUT_REPORTED_USAGE")

    summary = {
        "schema": "r0b2-ledger-telemetry-audit/v0.1",
        "ledger_reserved": len(reserved),
        "ledger_rejected": len(rejected),
        "telemetry_terminals": len(terminals),
        "status_counts": status_counts,
        "http_status_counts": http_counts,
        "usage_availability_counts": usage_counts,
        "tokens_input": tokens_in,
        "tokens_output": tokens_out,
        "latency_ms_mean": round(statistics.mean(latencies), 1) if latencies else None,
        "latency_ms_max": round(max(latencies), 1) if latencies else None,
        "violations": violations,
        "reserved_without_terminal_sample": no_terminal[:5],
        "ok": not violations,
    }
    print(json.dumps(summary, indent=1))
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
