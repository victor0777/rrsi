# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""RRSI-INTEGRATION-BOUNDARY-R2 — identity / revision / contract boundary.

Scope frozen to the RRSI repository (directive §1). Zero model calls,
zero task executions; every rule is deterministic and tested.

WS-A Identity / Revision model
    A candidate is identified by the TRIPLE (candidate_id,
    candidate_revision, candidate_content_digest): the id names the
    logically-same improvement target, the revision pins one immutable
    point in time, the content digest carries that revision's
    integrity. Content changes ⇒ NEW revision — an existing revision's
    digest is never overwritten (C2 integrity rule).

WS-A Evaluation Snapshot Binding
    An evaluation fixes the 8-field snapshot at creation; the snapshot
    is IMMUTABLE. New revisions never rewrite an existing evaluation's
    snapshot.

WS-A Resume policy
    Resume compares against the EXECUTION-TIME snapshot (evaluation id,
    candidate revision/digest, baseline revision/digest, policy
    version, workbench task binding identity) — NEVER against the
    latest candidate. A changed latest candidate does NOT block an old
    evaluation's resume; a snapshot content/digest mismatch DOES.
    The R2.3.1 full identity binding is preserved (5-field check).

WS-B SHA binding scope
    SHA-256 carries INTEGRITY ONLY (revisions, snapshots, binding
    records, results/evidence, execution provenance). It is NOT a
    repository-HEAD pin and NOT an API-compatibility decision.
    Cross-service compatibility is decided by
    (contract_name, contract_version, required_capabilities,
    schema_validation) — compatible contracts connect regardless of
    commit SHAs; incompatible ones are refused even with identical
    SHAs.

WS-C Authority separation
    Workbench owns the PERSISTENT evaluation↔task binding authority;
    RRSI VERIFIES official binding records and holds only a read-only
    projection; Researcher owns task identity and execution results.
    RRSI-internal registries stay TEST/PROTOTYPE-only and never
    declare durable authority.
"""

from __future__ import annotations

import json

from poc.recursive_loop_r1 import ContractRejected, WIRE_DIGEST_RE

SCHEMA_CANDIDATE_IDENTITY = "rrsi-candidate-identity/v0.1"
SCHEMA_EVALUATION_SNAPSHOT = "rrsi-evaluation-snapshot-binding/v0.1"
SCHEMA_CONTRACT_COMPATIBILITY = "rrsi-contract-compatibility/v0.1"


def _sha256(payload) -> str:
    return "sha256:" + hashlib_sha256_hex(json.dumps(
        payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8"))


def hashlib_sha256_hex(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _canonical_digest(payload: dict) -> str:
    return "sha256:" + hashlib_sha256_hex(json.dumps(
        payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8"))


# ==================== WS-A1 — identity / revision model ======================
def candidate_identity(candidate_id: str, revision: str,
                       content) -> dict:
    """Identity triple for one immutable revision. The content digest is
    computed over the revision CONTENT (canonical JSON)."""
    identity = {
        "schema": SCHEMA_CANDIDATE_IDENTITY,
        "candidate_id": candidate_id,
        "candidate_revision": revision,
        "candidate_content_digest": _sha256(content),
    }
    return identity


def verify_candidate_identity(identity: dict, content) -> None:
    """Integrity check: the declared content digest must match the
    actual revision content. Same revision + different digest is an
    INTEGRITY ERROR (never a new version)."""
    if identity.get("schema") != SCHEMA_CANDIDATE_IDENTITY:
        raise ContractRejected("SCHEMA_INVALID")
    for field in ("candidate_id", "candidate_revision",
                  "candidate_content_digest"):
        if not identity.get(field):
            raise ContractRejected("IDENTITY_INCOMPLETE:" + field)
    actual = _sha256(content)
    if identity["candidate_content_digest"] != actual:
        raise ContractRejected(
            f"REVISION_DIGEST_MISMATCH: revision "
            f"{identity['candidate_revision']!r} content changed")


def derive_revision(prev_identity: dict | None, content) -> dict:
    """Content changed ⇒ NEW revision (monotonic). An existing
    revision's digest is never rewritten — prev stays untouched and
    verifiable against ITS OWN content. prev None ⇒ revision r1."""
    if prev_identity is None:
        return candidate_identity(
            _pending_id(content), "r1", content)
    n = int(prev_identity["candidate_revision"][1:])
    return candidate_identity(
        prev_identity["candidate_id"], f"r{n + 1}", content)


def _pending_id(content) -> str:
    return "cand-" + hashlib_sha256_hex(
        json.dumps(content, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8"))[:16]


# ================= WS-A2 — evaluation snapshot binding =======================
class EvaluationSnapshotBinding:
    """Immutable 8-field execution-time snapshot. New candidate
    revisions NEVER rewrite an existing evaluation's snapshot."""

    FIELDS = ("evaluation_id", "candidate_id", "candidate_revision",
              "candidate_content_digest", "baseline_revision",
              "baseline_content_digest", "evaluation_contract_version",
              "evaluation_policy_version")

    def __init__(self, **fields):
        missing = [f for f in self.FIELDS
                   if not fields.get(f)]
        if missing:
            raise ContractRejected(
                "SNAPSHOT_INCOMPLETE:" + ",".join(missing))
        for f in self.FIELDS:
            setattr(self, f, fields[f])
        self.record_digest = None

    def seal(self) -> "EvaluationSnapshotBinding":
        self.record_digest = _canonical_digest(
            {k: v for k, v in vars(self).items()
             if k != "record_digest"})
        return self

    def verify(self) -> bool:
        return self.record_digest == _canonical_digest(
            {k: v for k, v in vars(self).items()
             if k != "record_digest"})


# ==================== WS-A3 — resume against snapshot ========================
def resume_against_snapshot(snapshot: EvaluationSnapshotBinding,
                            workbench_identity: dict) -> dict:
    """Resume policy (WS-A3): compare ONLY against the execution-time
    snapshot. ``workbench_identity`` = the OFFICIAL workbench identity
    surface for this evaluation (evaluation id, candidate id/revision/
    digest, baseline digest, policy version, task binding id).
    The LATEST candidate is never consulted here — a changed latest
    candidate does NOT block an old evaluation's resume. Snapshot
    content/digest mismatch IS rejected (full R2.3.1 binding kept)."""
    if not snapshot.verify():
        raise ContractRejected("SNAPSHOT_TAMPERED")
    problems = []
    if workbench_identity.get("evaluation_id") != snapshot.evaluation_id:
        problems.append("EVALUATION_ID_MISMATCH")
    if workbench_identity.get("candidate_id") != snapshot.candidate_id:
        problems.append("CANDIDATE_ID_MISMATCH")
    if workbench_identity.get("candidate_revision") != \
            snapshot.candidate_revision:
        problems.append("CANDIDATE_REVISION_MISMATCH")
    wb_digest = workbench_identity.get("candidate_content_digest") or ""
    if not WIRE_DIGEST_RE.fullmatch(wb_digest.replace("sha256:", "")):
        problems.append("CANDIDATE_DIGEST_MISSING")
    elif wb_digest.replace("sha256:", "") != \
            snapshot.candidate_content_digest.replace("sha256:", ""):
        problems.append("CANDIDATE_DIGEST_MISMATCH")
    wb_baseline = (workbench_identity.get("baseline_content_digest")
                   or "").replace("sha256:", "")
    if wb_baseline != snapshot.baseline_content_digest.replace(
            "sha256:", ""):
        problems.append("BASELINE_DIGEST_MISMATCH")
    if workbench_identity.get("evaluation_policy_version") != \
            snapshot.evaluation_policy_version:
        problems.append("POLICY_VERSION_MISMATCH")
    if not workbench_identity.get("task_binding_id"):
        # workbench task binding identity is REQUIRED for resume
        problems.append("TASK_BINDING_IDENTITY_MISSING")
    if problems:
        raise ContractRejected(";".join(problems))
    return {"resume": "ALLOWED", "evaluation_id": snapshot.evaluation_id,
            "candidate_revision": snapshot.candidate_revision}


# ================ WS-B2 — contract compatibility (not SHA) ===================
def contract_compatible(offer: dict, *, contract_name: str,
                        contract_version: str,
                        required_capabilities: tuple) -> dict:
    """Cross-service compatibility decision. Git commit SHAs are NEVER
    consulted: a compatible contract connects across differing SHAs,
    an incompatible one is refused even with identical SHAs.
    Missing required capabilities are an explicit refusal."""
    problems = []
    if offer.get("contract_name") != contract_name:
        problems.append("CONTRACT_NAME_MISMATCH")
    if offer.get("contract_version") != contract_version:
        problems.append("CONTRACT_VERSION_MISMATCH")
    if offer.get("schema_validation") != "PASS":
        problems.append("SCHEMA_VALIDATION_MISSING")
    offered = set(offer.get("capabilities") or ())
    missing = sorted(set(required_capabilities) - offered)
    if missing:
        raise ContractRejected("CONTRACT_CAPABILITY_MISSING:" +
                               ",".join(missing))
    if problems:
        raise ContractRejected(";".join(problems))
    return {"compatible": True, "contract": f"{contract_name}/"
                                            f"{contract_version}"}


# ========== WS-C3 — official binding record verification (read-only) =========
OFFICIAL_BINDING_FIELDS = (
    "contract_version", "evaluation_id", "task_id", "candidate_id",
    "candidate_revision", "candidate_content_digest", "baseline_revision",
    "baseline_content_digest", "policy_version", "configuration_identity",
    "binding_record_digest",
)


def verify_official_binding_record(record: dict) -> dict:
    """Verify a Workbench OFFICIAL binding record (read-only
    projection). Fields the workbench does not yet provide are NEVER
    assumed or invented — a missing REQUIRED field blocks with
    BINDING_AUTHORITY_UNAVAILABLE (authority cannot be proven) or
    CONTRACT_CAPABILITY_MISSING (the surface lacks the field)."""
    if record.get("schema") != "research-bench-evaluation-task-binding/v0.1":
        raise ContractRejected("BINDING_SCHEMA_INVALID")
    provided = set(record)
    for field in ("contract_version", "evaluation_id", "task_id",
                  "candidate_id", "candidate_content_digest",
                  "baseline_content_digest", "policy_version",
                  "binding_record_digest"):
        if field not in provided:
            raise ContractRejected(
                f"BINDING_AUTHORITY_UNAVAILABLE:{field}")
    for field in ("candidate_revision", "baseline_revision",
                  "configuration_identity"):
        if field not in provided:
            raise ContractRejected(
                f"CONTRACT_CAPABILITY_MISSING:{field}")
    claimed = record.get("binding_record_digest") or ""
    covered = {k: v for k, v in record.items()
               if k != "binding_record_digest"}
    if claimed != _canonical_digest(covered).replace("sha256:", ""):
        raise ContractRejected("BINDING_RECORD_TAMPERED")
    return {"binding_verified": True, "evaluation_id":
            record["evaluation_id"], "task_id": record["task_id"]}


# ============== WS-C4 — restart recovery boundary (fail-closed) ==============
def restart_recovery(plan: dict) -> dict:
    """Restart handling: an RRSI-internal in-memory registry NEVER
    declares recovery by itself — the official workbench binding lookup
    must re-confirm the identity. Lookup unavailable ⇒
    RESTART_RECOVERY_BLOCKED; tasks are NEVER recreated from local
    state."""
    if not plan.get("official_binding_lookup_available"):
        return {"recovery": "BLOCKED",
                "reason": "RESTART_RECOVERY_BLOCKED:"
                          "official binding lookup unavailable",
                "task_recreated": False}
    if not plan.get("identity_match"):
        return {"recovery": "BLOCKED",
                "reason": "WORKBENCH_IDENTITY_MISMATCH",
                "task_recreated": False}
    return {"recovery": "CONFIRMED", "evaluation_id":
            plan["evaluation_id"], "task_recreated": False}
