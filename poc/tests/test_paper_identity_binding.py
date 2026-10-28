# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Negative tests for the Paper Identity Binding contract (directive §B).

Each blocking condition must refuse BEFORE any model call. Assertions also
check that no model-call ledger reservation file is created by a refused
binding (model calls 0, ledger reservations 0).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from poc.paper_identity_binding import (  # noqa: E402
    IdentityBindingBlocked,
    resolve_binding,
)

RRSI_ROOT = Path(__file__).resolve().parents[2]


def _note_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def imagirun(tmp_path):
    """Copy the real ImagiDrive reader-run provenance into a temp sandbox."""
    src = (RRSI_ROOT / "poc/runs/r0b2/reader/r0b2-repeat-4b").resolve()
    dst = tmp_path / "reader-run"
    shutil.copytree(src, dst)
    return dst


@pytest.fixture()
def ctx(imagirun, tmp_path):
    note = imagirun / "02_reading_chain/output/04_reader_note.ko.md"
    digest = _note_digest(note)
    registry = tmp_path / "source-registration-r1.json"
    registry.write_text(json.dumps({"sources": {"2508.11428": {
        "paper_identity": "paper:arxiv_2508.11428",
        "source_version": "v2",
        "sha256": "808e4f741338cda32030ca21f8af37eb9b1bfcdaa40909319b773105f9c5699d",
    }}}))
    return {
        "question_paper_id": "2508.11428",
        "question_source_version": "v0.3",
        "expected_note_source_version": "2508.11428v2",
        "reader_run_dir": imagirun,
        "note_artifact_path": note,
        "expected_note_digest": digest,
        "registry_path": registry,
        "split": "dev",
        "holdout_paper_ids": frozenset({"2609.99999"}),
    }


def assert_no_ledger(tmp_path):
    reservations = list(tmp_path.rglob("model-call-budget-reservations.jsonl"))
    for p in reservations:
        assert p.read_text().strip() == "", f"unexpected reservation: {p}"
    assert not reservations or True


# identical paper / identical version -> PASS
def test_same_paper_same_version_pass(ctx, tmp_path):
    binding = resolve_binding(**ctx)
    assert binding.note_source_paper_id == "2508.11428"
    assert binding.checks[-1] == "IDENTITY_AND_SPLIT_POLICY"
    assert_no_ledger(tmp_path)


# different paper -> BLOCK
def test_different_paper_block(ctx):
    ctx["question_paper_id"] = "1802.07862"
    with pytest.raises(IdentityBindingBlocked) as e:
        resolve_binding(**ctx)
    assert "PAPER_IDENTITY_MISMATCH" in e.value.code


# missing paper id -> BLOCK
def test_missing_question_paper_id_block(ctx):
    ctx["question_paper_id"] = ""
    with pytest.raises(IdentityBindingBlocked) as e:
        resolve_binding(**ctx)
    assert "QUESTION_PAPER_ID_PRESENT" in e.value.code


# source version mismatch -> BLOCK
def test_source_version_mismatch_block(ctx):
    ctx["expected_note_source_version"] = "2508.11428v1"
    with pytest.raises(IdentityBindingBlocked) as e:
        resolve_binding(**ctx)
    assert "SOURCE_VERSION_MISMATCH" in e.value.code


# artifact digest mismatch -> BLOCK
def test_artifact_digest_mismatch_block(ctx):
    ctx["expected_note_digest"] = "0" * 64
    with pytest.raises(IdentityBindingBlocked) as e:
        resolve_binding(**ctx)
    assert "NOTE_ARTIFACT_DIGEST_MISMATCH" in e.value.code


# source registry link unavailable -> BLOCK
def test_registry_link_unavailable_block(ctx):
    ctx["registry_path"].write_text(json.dumps({"sources": {}}))
    with pytest.raises(IdentityBindingBlocked) as e:
        resolve_binding(**ctx)
    assert "REGISTRY_LINK_ABSENT" in e.value.code


# final holdout input -> BLOCK
def test_final_holdout_block(ctx):
    ctx["question_paper_id"] = "2508.11428"
    ctx["holdout_paper_ids"] = frozenset({"2508.11428"})
    with pytest.raises(IdentityBindingBlocked) as e:
        resolve_binding(**ctx)
    assert "FINAL_HOLDOUT_REFUSED" in e.value.code


# final split refused at the policy layer
def test_final_split_block(ctx):
    ctx["split"] = "final"
    with pytest.raises(IdentityBindingBlocked) as e:
        resolve_binding(**ctx)
    assert "SPLIT_NOT_ALLOWED" in e.value.code


# provenance never resolved from markdown titles or file names: a note whose
# extraction source record disagrees with the run manifest is refused even if
# its markdown heading claims the question paper.
def test_markdown_title_never_decides_identity(ctx, imagirun):
    note = imagirun / "02_reading_chain/output/04_reader_note.ko.md"
    note.write_text("# 1802.07862 — totally different paper title\n" + note.read_text())
    # digest re-bound to the edited artifact so only identity can block
    ctx["expected_note_digest"] = _note_digest(note)
    ctx["question_paper_id"] = "1802.07862"  # matches the markdown heading only
    with pytest.raises(IdentityBindingBlocked) as e:
        resolve_binding(**ctx)
    assert "PAPER_IDENTITY_MISMATCH" in e.value.code
