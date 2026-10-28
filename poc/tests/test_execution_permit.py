# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Negative regression tests for the Execution Permit contract (directive §C).

Every blocking condition must refuse with 0 model calls and 0 ledger
reservations. No test in this file touches the network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from poc.execution_permit import (  # noqa: E402
    ExecutionPermitBlocked,
    assert_authorized,
    load_permit,
)

BASE = {
    "schema": "rrsi-execution-permit/v0.1",
    "invocation_id": "inv-1",
    "workstream": "reader_context_qa",
    "call_type": "qa_inference",
    "dataset_sha256": "2ae7ee62a65b1c4225791c70de80c2aad4e8998cf1fd4f09a53103db4f21af93",
    "paper_ids": ["1802.07862", "1901.10133"],
    "model_factors": {"model": "qwen3.8-flash-next-fp8",
                      "endpoint": "http://192.168.0.199/v1"},
    "budget": {"max_calls": 12, "max_wall_seconds": 900},
    "ledger_reservation": {"ledger_path": "/tmp/ledger-rn1/model-call-budget-reservations.jsonl"},
}


def actual_kwargs(**over):
    kw = dict(workstream="reader_context_qa", call_type="qa_inference",
              dataset_sha256="2ae7ee62a65b1c4225791c70de80c2aad4e8998cf1fd4f09a53103db4f21af93",
              paper_ids=("1802.07862", "1901.10133"),
              model="qwen3.8-flash-next-fp8", endpoint="http://192.168.0.199/v1",
              invocation_id="inv-1")
    kw.update(over)
    return kw


@pytest.fixture()
def bound(tmp_path, monkeypatch):
    ledger = tmp_path / "model-call-budget-reservations.jsonl"
    ledger.write_text("")
    permit = dict(BASE)
    permit["ledger_reservation"] = {"ledger_path": str(ledger)}
    pfile = tmp_path / "permit.json"
    pfile.write_text(json.dumps(permit))
    from poc.execution_permit import register_permit
    register_permit(pfile, issued_by="test-fixture")
    monkeypatch.setenv("AI_PAPERS_EXECUTION_PERMIT", str(pfile))
    monkeypatch.setenv("AI_PAPERS_MODEL_CALL_BUDGET_LEDGER", str(ledger))
    monkeypatch.delenv("AI_PAPERS_MODEL_CALL_CEILING", raising=False)
    return permit


def assert_no_reservation(tmp_path):
    for f in tmp_path.rglob("model-call-budget-reservations.jsonl"):
        assert f.read_text().strip() == ""


# no permit -> BLOCK (bound budget environment does NOT authorize)
def test_no_permit_block(tmp_path, monkeypatch):
    monkeypatch.delenv("AI_PAPERS_EXECUTION_PERMIT", raising=False)
    monkeypatch.setenv("AI_PAPERS_MODEL_CALL_BUDGET_LEDGER",
                       str(tmp_path / "l.jsonl"))
    with pytest.raises(ExecutionPermitBlocked) as e:
        assert_authorized(**actual_kwargs())
    assert "PERMIT_REQUIRED" in e.value.code
    assert_no_reservation(tmp_path)


# no budget environment -> BLOCK
def test_no_budget_env_block(tmp_path, monkeypatch):
    pfile = tmp_path / "permit.json"
    pfile.write_text(json.dumps(BASE))
    monkeypatch.setenv("AI_PAPERS_EXECUTION_PERMIT", str(pfile))
    monkeypatch.delenv("AI_PAPERS_MODEL_CALL_BUDGET_LEDGER", raising=False)
    with pytest.raises(ExecutionPermitBlocked):
        assert_authorized(**actual_kwargs())


# unauthorized QA execution: permit for reader workstream, QA attempted -> BLOCK
def test_reader_permit_qa_attempt_block(bound, monkeypatch):
    bound["workstream"] = "reader_note_generation"
    bound["call_type"] = "reader_chain"
    pfile = Path(monkeypatch.__dict__.get("_src", "") or "/dev/null")  # noqa
    import os
    # rewrite permit file (scope change must come from the issuer, re-issued)
    permit_path = os.environ["AI_PAPERS_EXECUTION_PERMIT"]
    Path(permit_path).write_text(json.dumps(bound))
    from poc.execution_permit import register_permit
    register_permit(Path(permit_path), issued_by="test-fixture")
    with pytest.raises(ExecutionPermitBlocked) as e:
        assert_authorized(**actual_kwargs())
    assert "PERMIT_WORKSTREAM_MISMATCH" in e.value.code


# QA attempted under a reader-authorized invocation (invocation-bound permit)
def test_qa_under_reader_invocation_block(bound, monkeypatch):
    bound["call_type"] = "reader_chain"
    import os
    Path(os.environ["AI_PAPERS_EXECUTION_PERMIT"]).write_text(json.dumps(bound))
    from poc.execution_permit import register_permit
    register_permit(Path(os.environ["AI_PAPERS_EXECUTION_PERMIT"]), issued_by="test-fixture")
    with pytest.raises(ExecutionPermitBlocked) as e:
        assert_authorized(**actual_kwargs())
    assert "PERMIT_CALL_TYPE_MISMATCH" in e.value.code


# dataset mismatch -> BLOCK
def test_dataset_mismatch_block(bound):
    with pytest.raises(ExecutionPermitBlocked) as e:
        assert_authorized(**actual_kwargs(dataset_sha256="0" * 64))
    assert "PERMIT_DATASET_MISMATCH" in e.value.code


# paper identity mismatch -> BLOCK
def test_paper_mismatch_block(bound):
    with pytest.raises(ExecutionPermitBlocked) as e:
        assert_authorized(**actual_kwargs(paper_ids=("1802.07862", "9999.99999")))
    assert "PERMIT_PAPERS_MISMATCH" in e.value.code


# budget exceeded -> BLOCK
def test_budget_exceeded_block(bound, monkeypatch):
    monkeypatch.setenv("AI_PAPERS_MODEL_CALL_CEILING", "12")
    bound["budget"]["max_calls"] = 56
    import os
    Path(os.environ["AI_PAPERS_EXECUTION_PERMIT"]).write_text(json.dumps(bound))
    from poc.execution_permit import register_permit
    register_permit(Path(os.environ["AI_PAPERS_EXECUTION_PERMIT"]), issued_by="test-fixture")
    with pytest.raises(ExecutionPermitBlocked) as e:
        assert_authorized(**actual_kwargs())
    assert "PERMIT_BUDGET_EXCEEDED" in e.value.code


# final holdout input -> BLOCK
def test_final_holdout_block(bound):
    with pytest.raises(ExecutionPermitBlocked) as e:
        assert_authorized(**actual_kwargs(paper_ids=("2609.24972",)))
    assert "PERMIT_PAPERS_MISMATCH" in e.value.code


# model endpoint mismatch -> BLOCK
def test_endpoint_mismatch_block(bound):
    with pytest.raises(ExecutionPermitBlocked) as e:
        assert_authorized(**actual_kwargs(endpoint="http://127.0.0.1:8004/v1"))
    assert "PERMIT_ENDPOINT_MISMATCH" in e.value.code


# model profile mismatch -> BLOCK
def test_model_mismatch_block(bound):
    with pytest.raises(ExecutionPermitBlocked) as e:
        assert_authorized(**actual_kwargs(model="qwen38-27b-fp8-vllm-tp1-ktl02"))
    assert "PERMIT_MODEL_MISMATCH" in e.value.code


# positive: permit + environment + scope all agree -> PASS
def test_authorized_pass(bound):
    result = assert_authorized(**actual_kwargs())
    assert result["checks"][-1] == "PERMIT_LEDGER"
    assert_no_reservation(Path(result["invocation_id"]).parent if False else
                          Path(__import__("os").environ["AI_PAPERS_MODEL_CALL_BUDGET_LEDGER"]).parent)


# permit file missing on disk -> BLOCK
def test_permit_file_missing_block(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PAPERS_EXECUTION_PERMIT", str(tmp_path / "absent.json"))
    with pytest.raises(ExecutionPermitBlocked) as e:
        load_permit()
    assert "PERMIT_FILE_MISSING" in e.value.code


# ---- permit issuance boundary (directive §B) and integration regression ----

# runner cannot self-issue: a permit absent from the issuance ledger -> BLOCK
def test_permit_not_issued_block(bound):
    # rewrite WITHOUT re-registering: the runner consumed a permit the issuer
    # never issued (tamper / self-issuance attempt)
    import os
    bound["invocation_id"] = "self-issued"
    Path(os.environ["AI_PAPERS_EXECUTION_PERMIT"]).write_text(json.dumps(bound))
    with pytest.raises(ExecutionPermitBlocked) as e:
        assert_authorized(**actual_kwargs(invocation_id="self-issued"))
    assert "PERMIT_NOT_ISSUED" in e.value.code


# tamper: post-issuance byte modification -> BLOCK
def test_permit_tamper_block(bound):
    import os
    path = Path(os.environ["AI_PAPERS_EXECUTION_PERMIT"])
    permit = json.loads(path.read_text())
    permit["budget"]["max_calls"] = 999  # privilege escalation in the file
    path.write_text(json.dumps(permit))
    with pytest.raises(ExecutionPermitBlocked) as e:
        assert_authorized(**actual_kwargs())
    assert "PERMIT_NOT_ISSUED" in e.value.code


# ledger reservation capability failure -> BLOCK (0 reservations, 0 calls)
def test_ledger_reservation_failure_block(bound, monkeypatch):
    import os
    ledger = Path(os.environ["AI_PAPERS_MODEL_CALL_BUDGET_LEDGER"])
    ledger.parent.chmod(0o500)  # read-only parent: write probe must fail
    try:
        with pytest.raises(ExecutionPermitBlocked) as e:
            assert_authorized(**actual_kwargs())
        assert "PERMIT_LEDGER_UNWRITABLE" in e.value.code
        assert ledger.parent.read_text is not None  # dir exists, no probe left
        assert not list(ledger.parent.glob(".reservation-probe"))
        assert ledger.read_text() == ""  # 0 successful reservations
    finally:
        ledger.parent.chmod(0o700)


# preflight path may not execute QA: the runner-level preflight refuses QA
# without a permit even when identity would PASS.
def test_preflight_qa_attempt_block(tmp_path, monkeypatch):
    import os
    # identity+registry all in place (same-paper note registry exists), but no
    # permit: preflight must report PERMIT_REQUIRED, 0 calls, 0 reservations
    monkeypatch.delenv("AI_PAPERS_EXECUTION_PERMIT", raising=False)
    monkeypatch.delenv("AI_PAPERS_MODEL_CALL_BUDGET_LEDGER", raising=False)
    for env in ("AI_PAPERS_EXECUTION_PERMIT", "AI_PAPERS_MODEL_CALL_BUDGET_LEDGER"):
        assert env not in os.environ
    # the runner CLI refuses before identity: invoke the preflight helper
    from poc.qasper_readercontext_calibration import preflight
    result = preflight()
    assert result["status"] == "BLOCK"
    assert result["calls"] == 0
    assert result["reservations"] == 0
