# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Paper Identity Binding contract for Reader-context QA (fail-closed preflight).

Evaluation-integrity amendment: the `a6cd3b1` reader-context run executed model
calls with a mismatched paper identity (QASPER questions vs an unrelated
reader note) and is registered INVALID_CONTEXT_MISMATCH. Every reader-context
execution must therefore resolve a full identity binding BEFORE the first
model call; any missing or inconsistent identifier fails closed.

Identity is resolved from structured provenance only — the reader run
manifest's source_id, the extraction bundle's source records, and the source
registry / artifact manifests. Markdown titles, headings, or file names are
never used as identity evidence.

Binding checks (in evaluation order):
    1. QUESTION_PAPER_ID_PRESENT        QASPER question paper id present/well-formed
    2. NOTE_SOURCE_PAPER_ID_RESOLVED    structured provenance resolves the note's paper id
    3. SOURCE_VERSION_CONSISTENT        note (and question) source versions present and consistent
    4. NOTE_ARTIFACT_DIGEST_VERIFIED    note bytes match the sha256 bound in the artifact manifest
    5. REGISTRY_LINK_PRESENT            source registry entry exists and agrees with resolved identity
    6. IDENTITY_AND_SPLIT_POLICY        note paper == question paper; dev split; holdout refused
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ARXIV_ID = re.compile(r"^\d{4}\.\d{4,5}$")
SOURCE_ID = re.compile(r"^e2e-arxiv-(\d{4})[.-](\d{4,5})$")

ALLOWED_SPLITS = ("dev",)


class IdentityBindingBlocked(Exception):
    """Fail-closed identity binding refusal (never reaches a model call)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"BLOCKED:{code}" + (f" ({detail})" if detail else ""))
        self.code = code
        self.detail = detail


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class IdentityBinding:
    """Resolved, structured paper identity for one reader-context execution."""

    question_paper_id: str
    question_source_version: str
    note_source_paper_id: str
    note_source_version: str
    note_artifact_path: Path
    note_artifact_sha256: str
    registry_path: Path
    expected_note_source_version: str = ""
    registry_entry: dict = field(default_factory=dict)
    split: str = "dev"
    holdout_paper_ids: frozenset = frozenset()
    checks: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema": "rrsi-paper-identity-binding/v0.1",
            "question_paper_id": self.question_paper_id,
            "question_source_version": self.question_source_version,
            "note_source_paper_id": self.note_source_paper_id,
            "note_source_version": self.note_source_version,
            "expected_note_source_version": self.expected_note_source_version,
            "note_artifact_path": str(self.note_artifact_path),
            "note_artifact_sha256": self.note_artifact_sha256,
            "registry_path": str(self.registry_path),
            "split": self.split,
            "checks": self.checks,
        }


def _require(check: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise IdentityBindingBlocked(check, detail)


def resolve_reader_run_identity(reader_run_dir: Path) -> dict:
    """Resolve the note's paper identity from structured provenance only.

    Chain: reader run-manifest.source_id -> extraction source.json (same
    source_id) -> source identity record (canonical arxiv base id + version).
    No markdown title, heading, or filename is consulted.
    """
    manifest = reader_run_dir / "run-manifest.json"
    _require("READER_RUN_MANIFEST_MISSING", manifest.exists(), str(manifest))
    data = json.loads(manifest.read_text(encoding="utf-8"))
    source_id = str(data.get("source_id") or "")
    match = SOURCE_ID.match(source_id)
    _require("READER_SOURCE_ID_MALFORMED", match is not None, source_id)
    paper_id = f"{match.group(1)}.{match.group(2)}"

    paper_md = Path(str(data.get("paper_md") or ""))
    _require("EXTRACTION_REF_MISSING", bool(str(data.get("paper_md"))), "paper_md absent")
    source_json = paper_md.parent / "source.json"
    _require("EXTRACTION_SOURCE_RECORD_MISSING", source_json.exists(), str(source_json))
    extraction = json.loads(source_json.read_text(encoding="utf-8"))
    _require("EXTRACTION_IDENTITY_MISMATCH",
             str(extraction.get("source_id") or "") == source_id,
             f"extraction={extraction.get('source_id')} run={source_id}")

    source_html = Path(str(extraction.get("source_html") or ""))
    _require("SOURCE_RECORD_REF_MISSING", bool(str(extraction.get("source_html"))),
             "source_html absent")
    identity_path = source_html.parent / "source-identity-v0.1.json"
    _require("SOURCE_IDENTITY_RECORD_MISSING", identity_path.exists(), str(identity_path))
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    _require("SOURCE_IDENTITY_MISMATCH",
             str(identity.get("canonical_arxiv_base_id") or "") == paper_id,
             str(identity.get("canonical_arxiv_base_id")))
    version = str(identity.get("canonical_arxiv_version_id") or "")
    _require("SOURCE_VERSION_ABSENT", bool(version))
    return {"paper_id": paper_id, "source_version": version,
            "source_sha256": str(identity.get("sha256") or ""),
            "reader_run_dir": str(reader_run_dir)}


def resolve_binding(
    *,
    question_paper_id: str,
    question_source_version: str,
    reader_run_dir: Path,
    note_artifact_path: Path,
    expected_note_digest: str,
    expected_note_source_version: str,
    registry_path: Path,
    split: str,
    holdout_paper_ids: frozenset = frozenset(),
) -> IdentityBinding:
    """Resolve and verify the full binding; raise before any model call on failure."""
    checks: list = []

    _require("QUESTION_PAPER_ID_PRESENT", bool(str(question_paper_id or "").strip()))
    _require("QUESTION_PAPER_ID_MALFORMED", ARXIV_ID.match(question_paper_id) is not None,
             question_paper_id)
    checks.append("QUESTION_PAPER_ID_PRESENT")

    resolved = resolve_reader_run_identity(reader_run_dir)
    checks.append("NOTE_SOURCE_PAPER_ID_RESOLVED")

    # question_source_version is the question-side source identity (e.g. the
    # frozen QASPER fixture snapshot); it must be present and is recorded but
    # never compared across different version schemes.
    _require("QUESTION_SOURCE_VERSION_ABSENT",
             bool(str(question_source_version or "").strip()))
    _require("SOURCE_VERSION_MISMATCH",
             resolved["source_version"] == expected_note_source_version,
             f"note={resolved['source_version']} expected={expected_note_source_version}")
    checks.append("SOURCE_VERSION_CONSISTENT")

    _require("NOTE_ARTIFACT_MISSING", note_artifact_path.exists(), str(note_artifact_path))
    digest = sha256_file(note_artifact_path)
    _require("NOTE_ARTIFACT_DIGEST_MISMATCH", digest == expected_note_digest,
             f"actual={digest[:16]} expected={expected_note_digest[:16]}")
    checks.append("NOTE_ARTIFACT_DIGEST_VERIFIED")

    _require("SOURCE_REGISTRY_MISSING", registry_path.exists(), str(registry_path))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    entry = (registry.get("sources") or {}).get(resolved["paper_id"])
    _require("REGISTRY_LINK_ABSENT", isinstance(entry, dict), resolved["paper_id"])
    _require("REGISTRY_VERSION_MISMATCH",
             str(entry.get("source_version") or "") == resolved["source_version"].rsplit("v", 1)[-1]
             or str(entry.get("source_version") or "") in resolved["source_version"],
             f"registry={entry.get('source_version')} resolved={resolved['source_version']}")
    if entry.get("sha256"):
        _require("REGISTRY_DIGEST_MISMATCH",
                 str(entry["sha256"]) == resolved["source_sha256"],
                 f"registry={entry['sha256'][:16]} resolved={resolved['source_sha256'][:16]}")
    checks.append("REGISTRY_LINK_PRESENT")

    _require("SPLIT_NOT_ALLOWED", split in ALLOWED_SPLITS, split)
    _require("FINAL_HOLDOUT_REFUSED",
             resolved["paper_id"] not in holdout_paper_ids, resolved["paper_id"])
    _require("PAPER_IDENTITY_MISMATCH",
             resolved["paper_id"] == question_paper_id,
             f"note={resolved['paper_id']} question={question_paper_id}")
    checks.append("IDENTITY_AND_SPLIT_POLICY")

    return IdentityBinding(
        question_paper_id=question_paper_id,
        question_source_version=question_source_version,
        note_source_paper_id=resolved["paper_id"],
        note_source_version=resolved["source_version"],
        note_artifact_path=note_artifact_path,
        note_artifact_sha256=digest,
        registry_path=registry_path,
        expected_note_source_version=expected_note_source_version,
        registry_entry=dict(entry),
        split=split,
        holdout_paper_ids=frozenset(holdout_paper_ids),
        checks=checks,
    )


def to_prediction(binding: IdentityBinding) -> dict:
    """Projection attached to every prediction so the consumer can audit identity."""
    return binding.to_dict()
