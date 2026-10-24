# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Deterministic multi-file dataset manifest for R0-b calibration inputs.

Hash convention (pre-registered, directive section 2):

1. File path normalization: paths are relative to the dataset root, POSIX
   separators, no `.`/`..` components, no symlink traversal (files only).
2. Ordering: entries sorted by the normalized path byte string (codepoint
   order, matching UTF-8 byte order for these paths).
3. Per-file identity: SHA-256 of the raw file bytes, hex, lowercase.
4. Manifest serialization: canonical JSON — keys sorted, separators (",", ":"),
   UTF-8, no trailing newline — then SHA-256 of those bytes is the
   dataset manifest hash.

Usage: python3 -m poc.dataset_manifest --root DIR --paper-id ID --arxiv-version V \
           --pipeline-version P --out FILE
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath


def normalize_path(rel: PurePosixPath) -> str:
    parts = [p for p in rel.parts if p not in (".", "..", "")]
    return "/".join(parts)


def canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def file_entry(root: Path, path: Path) -> dict:
    b = path.read_bytes()
    rel = normalize_path(path.relative_to(root).as_posix() and
                         PurePosixPath(path.relative_to(root).as_posix()))
    return {"path": rel, "size": len(b),
            "sha256": hashlib.sha256(b).hexdigest()}


def build_manifest(root: Path, metadata: dict, exclude: set[str] | None = None) -> dict:
    exclude = exclude or set()
    files = [file_entry(root, p) for p in sorted(root.rglob("*"))
             if p.is_file() and not p.is_symlink()
             and normalize_path(PurePosixPath(p.relative_to(root).as_posix()))
             not in exclude]
    files.sort(key=lambda e: e["path"].encode("utf-8"))
    return {"schema": "rrsi-dataset-manifest/v0.1", **metadata,
            "file_count": len(files), "files": files}


def manifest_hash(manifest: dict) -> tuple[str, bytes]:
    b = canonical_bytes(manifest)
    return hashlib.sha256(b).hexdigest(), b


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--paper-id", required=True)
    ap.add_argument("--arxiv-version", required=True)
    ap.add_argument("--pipeline-version", required=True)
    ap.add_argument("--generated-at", default=None)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    generated_at = args.generated_at or dt.datetime.now(
        dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifest = build_manifest(args.root, {
        "paper_id": args.paper_id,
        "arxiv_version": args.arxiv_version,
        "pipeline_version": args.pipeline_version,
        "generated_at": generated_at,
        "provenance": {
            "acquisition": "ai_papers governed_arxiv_source_capture "
                           "(preexecution-receipt in source/)",
            "extraction": "ai_papers arxiv_html_bundle canonical bundle",
            "recorded_at": generated_at,
        },
    })
    digest, b = manifest_hash(manifest)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(b)
    print(json.dumps({"dataset_manifest_sha256": digest,
                      "file_count": manifest["file_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
