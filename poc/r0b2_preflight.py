# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""R0-b2 preflight: move model-config validation to a pre-network stage.

Directive R0-b2 item 1: the R0-b1 404 (`qwen-coder` in the writer/polish path)
happened mid-trial because model identity was only checked implicitly per call.
This preflight validates, BEFORE any model call:

  1. every reader-chain model id (writer, polish, vision, embedding) is
     registered on the provider (`GET /v1/models`);
  2. the token telemetry sink path is writable (so provider usage recording
     cannot silently drop, `append_process_event_from_environment`);
  3. the call-budget ledger env binding is complete and the ledger file is
     writable.

Exit 0 = preflight PASS (safe to run); exit 1 = BLOCKED with reasons.
Model-free network probing only; no rrsi core changes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path


def provider_models(base_url: str) -> tuple[set[str] | None, str]:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/models",
                                    timeout=10) as r:
            payload = json.loads(r.read())
        return {m["id"] for m in payload.get("data", [])}, ""
    except Exception as exc:  # network/parse failure is itself a preflight fail
        return None, f"{type(exc).__name__}: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True, help="writer model id")
    ap.add_argument("--polish-model", default=None, help="polish model id")
    ap.add_argument("--vision-model", default=None)
    ap.add_argument("--embedding-model", default=None)
    ap.add_argument("--use-vision", action="store_true")
    ap.add_argument("--use-embeddings", action="store_true")
    ap.add_argument("--telemetry-path", required=True, type=Path)
    ap.add_argument("--ledger-path", required=True, type=Path)
    ap.add_argument("--ceiling", required=True, type=int)
    ap.add_argument("--invocation-id", required=True)
    args = ap.parse_args()

    reasons: list[str] = []

    # --- 1. model identity pre-network (was previously implicit per call) ---
    models, err = provider_models(args.base_url)
    if models is None:
        reasons.append(f"PROVIDER_UNREACHABLE:{args.base_url}:{err}")
    wanted = {"writer": args.model, "polish": args.polish_model,
              "vision": args.vision_model if args.use_vision else None,
              "embedding": args.embedding_model if args.use_embeddings else None}
    for path, mid in wanted.items():
        if not mid:
            continue  # path disabled for this run
        if mid == "unregistered-by-default":
            reasons.append(f"DEFAULT_PLACEHOLDER_MODEL:{path}")
        elif models is not None and mid not in models:
            # stable R0-b1-class failure, now raised before the trial starts
            reasons.append(f"MODEL_NOT_REGISTERED:{path}:{mid}")

    # --- 2. telemetry sink must accept a write (usage cannot silently drop) ---
    args.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile("w", dir=args.telemetry_path.parent,
                                         prefix=".preflight-", delete=False) as t:
            t.write(json.dumps({"preflight": "telemetry_sink_probe"}))
            probe = Path(t.name)
        probe.unlink()
    except OSError as exc:
        reasons.append(f"TELEMETRY_SINK_UNWRITABLE:{exc}")

    # --- 3. ledger binding complete + writable ---
    if args.ceiling < 1:
        reasons.append("INVALID_CEILING")
    args.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile("a", dir=args.ledger_path.parent,
                                         prefix=".preflight-", delete=False):
            pass
    except OSError as exc:
        reasons.append(f"LEDGER_UNWRITABLE:{exc}")

    print(json.dumps({
        "preflight": "r0b2",
        "invocation_id": args.invocation_id,
        "ceiling": args.ceiling,
        "checked_models": {k: v for k, v in wanted.items() if v},
        "telemetry_path": str(args.telemetry_path),
        "ledger_path": str(args.ledger_path),
        "ok": not reasons,
        "reasons": reasons,
    }))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
