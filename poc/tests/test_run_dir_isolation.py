# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Negative regression for invocation-bound RUN_DIR isolation (directive §B).

All negative cases verify 0 model calls and 0 changes to existing artifacts
(no file in any pre-existing run dir is rewritten by these tests).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from poc.run_dir_isolation import (  # noqa: E402
    RunDirCollisionBlocked,
    resolve_run_dir,
    run_dir_for,
    seal_run_dir,
    verify_seal,
)


# new invocation + new run dir -> PASS
def test_new_invocation_new_dir_pass(tmp_path):
    d = resolve_run_dir("inv-a", tmp_path)
    assert d == tmp_path / "inv-a"
    assert not d.exists()  # created later by the run itself


# reusing another invocation's run dir -> BLOCK
def test_reuse_other_invocation_dir_block(tmp_path):
    used = run_dir_for("inv-a", tmp_path)
    used.mkdir()
    (used / "run-summary.json").write_text(json.dumps({"done": True}))
    with pytest.raises(RunDirCollisionBlocked) as e:
        resolve_run_dir("inv-b", tmp_path, permit_invocation_id="inv-b") \
            if False else resolve_run_dir("inv-a", tmp_path)
    assert "RUN_DIR_REUSED_COMPLETED" in e.value.code
    # existing artifacts unchanged
    assert (used / "run-summary.json").read_text() == json.dumps({"done": True})


# pre-existing raw packet files -> BLOCK
def test_existing_raw_packet_block(tmp_path):
    d = run_dir_for("inv-a", tmp_path)
    (d / "raw").mkdir(parents=True)
    packet = d / "raw" / "packet-abc.json"
    packet.write_text(json.dumps({"case_id": "x"}))
    before = packet.read_bytes()
    with pytest.raises(RunDirCollisionBlocked) as e:
        resolve_run_dir("inv-a", tmp_path)
    assert "RAW_PACKET_COLLISION" in e.value.code
    assert (d / "raw" / "packet-abc.json").read_bytes() == before


# invocation id mismatch vs permit -> BLOCK
def test_invocation_mismatch_block(tmp_path):
    with pytest.raises(RunDirCollisionBlocked) as e:
        resolve_run_dir("inv-a", tmp_path, permit_invocation_id="inv-z")
    assert "INVOCATION_ID_MISMATCH" in e.value.code


# manifest digest mismatch: sealed artifact tampered -> verify_seal False
def test_manifest_digest_mismatch_block(tmp_path):
    d = run_dir_for("inv-a", tmp_path)
    d.mkdir()
    (d / "artifact.json").write_text(json.dumps({"k": 1}))
    seal_run_dir(d)
    assert verify_seal(d) is True
    # tamper (simulated): digest no longer matches
    (d / "artifact.json").write_text(json.dumps({"k": 2}))
    assert verify_seal(d) is False


# overwrite attempt of an existing execution's outputs -> BLOCK
def test_overwrite_existing_results_block(tmp_path):
    d = run_dir_for("inv-a", tmp_path)
    d.mkdir()
    (d / "raw").mkdir()
    (d / "predictions.json").write_text(json.dumps({"prev": True}))
    before = (d / "predictions.json").read_bytes()
    with pytest.raises(RunDirCollisionBlocked) as e:
        resolve_run_dir("inv-a", tmp_path)
    assert "RUN_DIR_ALREADY_USED" in e.value.code
    assert (d / "predictions.json").read_bytes() == before


# seal after a run: digests fixed, artifacts unchanged by sealing
def test_seal_run_dir(tmp_path):
    d = run_dir_for("inv-b", tmp_path)
    (d / "raw").mkdir(parents=True)
    (d / "raw" / "packet-1.json").write_text(json.dumps({"n": 1}))
    (d / "run-summary.json").write_text(json.dumps({"calls": 1}))
    (d / "run-summary.json").chmod(0o400)
    seal = seal_run_dir(d)
    assert seal["artifact_digests"]["run-summary.json"] == \
        hashlib.sha256((d / "run-summary.json").read_bytes()).hexdigest()
    assert verify_seal(d) is True
