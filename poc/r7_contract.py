# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""R7-D2 Claim Anchor & Semantic Verification contract (design-frozen,
statically testable — zero model calls).

This contract is INDEPENDENT of the R6I judge; it does not modify any
R6I operating code. Claims carry typed anchors; verification is
fail-closed on digest mismatch and missing required anchors. Absence
evidence is separated into Local Evidence (deletion-site context and
Original/Perturbed correspondence) and Global Absence (semantic
presence of the same information elsewhere in the perturbed note —
never string-absence alone; unresolvable ⇒ PENDING_HUMAN_REVIEW).
"""

from __future__ import annotations

import hashlib
import json
import re

DOCUMENT_ROLES = ("source_paper", "original_note", "perturbed_note")
MATCH_POLICIES = ("byte_exact", "markdown_normalized", "semantic_review")
VERIFICATION_STATUSES = ("UNVERIFIED", "VERIFIED", "FAILED",
                         "PENDING_HUMAN_REVIEW")
CLAIM_KINDS = ("numeric_error", "info_loss", "missing_evidence",
               "contradiction")

# §A1/A2 — pipeline component separation with explicit input permissions.
# The Semantic Judge sees ONLY the A/B notes (blind contract, R6I-sustained);
# source paper and gold are denied to judge/resolver/verifier; only the
# Gold Adjudicator may touch gold and perturbation ground truth.
PIPELINE_ROLES = {
    "SemanticJudge": {
        "ab_note": "allowed", "source_paper": "denied",
        "gold": "denied", "perturbation_truth": "denied",
        "responsibility": "relative quality judgment, error/loss claims, "
                          "observed evidence, abstain when undecidable",
    },
    "EvidenceResolver": {
        "ab_note": "allowed", "source_paper": "locator-check only",
        "gold": "denied", "perturbation_truth": "denied",
        "responsibility": "resolve judge citations to actual positions, "
                          "verify document digests, byte/markdown match",
    },
    "ClaimVerifier": {
        "ab_note": "allowed", "source_paper": "allowed",
        "gold": "denied", "perturbation_truth": "denied",
        "responsibility": "verify claims against source paper and FULL "
                          "reader notes; partial vs total loss; semantic "
                          "uncertainty → human review",
    },
    "GoldAdjudicator": {
        "ab_note": "allowed", "source_paper": "allowed",
        "gold": "allowed", "perturbation_truth": "allowed",
        "responsibility": "compare verified claims with independent gold; "
                          "agreement / FP / FN; gold uncertainty control",
    },
    "EvaluationReporter": {
        "ab_note": "verdicts", "source_paper": "verification results",
        "gold": "aggregation only", "perturbation_truth": "aggregation only",
        "responsibility": "independent metric aggregation (e2e/conditional "
                          "agreement, precision/recall, FPR, abstention, "
                          "grounding, cost)",
    },
}
JUDGE_SCHEMA_VERSION = "r7-judge-output/v0.3"
JUDGE_CLAIM_FIELDS = ("claim_id", "kind", "target_side", "claim_text",
                      "observed_evidence_refs")
JUDGE_OUTPUT_FIELDS = ("relative", "a_verdict", "b_verdict", "claims",
                       "evidence_refs", "abstention", "schema_version")
VERIFICATION_EVIDENCE_FIELDS = ("claim_id", "document_id",
                                "document_digest", "document_role",
                                "locator", "quote", "match_policy",
                                "verification_status", "verification_method",
                                "verification_evidence")
# §D2A-A — structured Human Review Record. Existence of a record is never
# sufficient for VERIFIED: the recorded verdicts decide (negative → FAILED,
# uncertain/unrecorded → PENDING_HUMAN_REVIEW).
# §D2A.1-C1 — provenance-hardened record (11 fields). Compatibility
# policy: legacy `document_digests` is accepted as an alias for
# `reviewed_document_digests` (7-field v1 records); all new records MUST
# use the v2 names. Schema version of the judge output is unchanged.
REVIEW_RECORD_FIELDS = ("review_id", "reviewer_id", "claim_id",
                        "reviewed_document_digests", "review_timestamp",
                        "review_scope", "global_absence_verdict",
                        "source_importance_verdict", "rationale",
                        "evidence_refs", "review_record_digest")
REVIEW_RECORD_LEGACY_ALIASES = {"document_digests":
                                "reviewed_document_digests"}
REVIEW_ABSENCE_VERDICTS = ("CONFIRMED", "REFUTED", "UNCERTAIN")
REVIEW_IMPORTANCE_VERDICTS = ("IMPORTANT", "NOT_IMPORTANT", "UNCERTAIN")
CLAIM_TEXT_MAX_CHARS = 200
CLAIM_ID_MAX_CHARS = 32
CLAIM_ID_PATTERN = re.compile(r"c-[A-Za-z0-9][A-Za-z0-9._-]*")
# §D2A.1-C3 — Reviewer Registry. The registry starts EMPTY: no reviewer
# is ever invented. Until the Owner assigns real reviewers, no evaluation
# claim may be promoted to VERIFIED. Synthetic test fixtures must be
# registered with synthetic=True and are statically distinct from any
# real reviewer approval record.
REVIEWER_REGISTRY_STATUSES = ("REGISTERED", "UNREGISTERED", "REVOKED",
                              "PENDING_ASSIGNMENT")
_REVIEWER_REGISTRY: dict[str, dict] = {}


def register_reviewer(reviewer_id: str, status: str, *,
                      synthetic: bool = False) -> None:
    if status not in REVIEWER_REGISTRY_STATUSES:
        raise ValueError("UNKNOWN_REVIEWER_STATUS:" + status)
    _REVIEWER_REGISTRY[reviewer_id] = {"status": status,
                                       "synthetic": synthetic}


def reviewer_status(reviewer_id: str) -> str:
    entry = _REVIEWER_REGISTRY.get(reviewer_id)
    return entry["status"] if entry else "UNREGISTERED"
# info_loss: 3-anchor contract — each role is mandatory and distinct.
INFO_LOSS_ANCHOR_ROLES = {
    "original_note_anchor": "where the information existed in the ORIGINAL note",
    "absence_evidence": "adjacent context in the TARGET note proving deletion "
                        "(the deleted sentence itself is absent)",
    "importance_evidence": "source-paper evidence that the information was "
                           "actually important",
}


def validate_judge_output(output) -> dict:
    """§A3 + §D2A-C + §D2A.1-A — Judge output schema
    (r7-judge-output/v0.3) with STRICT allow-list validation and
    FAIL-CLOSED type guards: any malformed input yields an explicit
    failure result — the validator never raises and never performs
    follow-up operations that presuppose a type it has not verified."""
    problems = []
    def claim_prob(i, p):
        problems.append(f"CLAIM[{i}]:{p}")
    if not isinstance(output, dict):  # None / list / int / str / ...
        return {"schema_version": "?", "valid": False,
                "problems": ["INVALID_OUTPUT_TYPE"], "claims": []}
    # allow-list: reject extra top-level fields
    for field in output:
        if field not in JUDGE_OUTPUT_FIELDS:
            problems.append("EXTRA_FIELD_FORBIDDEN:" + field)
    for field in JUDGE_OUTPUT_FIELDS:
        if field not in output:
            problems.append(f"MISSING_FIELD:{field}")
    if problems:
        return {"schema_version": output.get("schema_version", "?"),
                "valid": False, "problems": problems, "claims": []}
    # exact types — verdicts decided per field, gates recorded up-front
    claims_is_list = isinstance(output["claims"], list)
    evidence_refs_is_list = isinstance(output["evidence_refs"], list) and \
        all(isinstance(r, str) and r for r in output["evidence_refs"])
    if not isinstance(output["schema_version"], str) or \
            output["schema_version"] != JUDGE_SCHEMA_VERSION:
        problems.append("UNKNOWN_SCHEMA_VERSION")
    if not isinstance(output["relative"], str) or \
            output["relative"] not in ("A", "B", "EQUAL", "UNDECIDABLE"):
        problems.append("UNKNOWN_RELATIVE")
    for v in (output["a_verdict"], output["b_verdict"]):
        if not isinstance(v, str) or v not in ("VALID", "INVALID",
                                               "ABSTAINED"):
            problems.append("UNKNOWN_VERDICT")
    if not isinstance(output["abstention"], bool):  # exact bool, not int
        problems.append("ABSTENTION_NOT_BOOLEAN")
    if not claims_is_list:  # e.g. None / int / str — no claim iteration
        problems.append("CLAIMS_NOT_LIST")
    if not evidence_refs_is_list:
        problems.append("EVIDENCE_REFS_NOT_LIST_OF_STR")
    # abstention / verdict consistency (both directions)
    abstention = output["abstention"]
    if isinstance(abstention, bool):
        if abstention:
            if output["relative"] != "UNDECIDABLE":
                problems.append("ABSTENTION_REQUIRES_UNDECIDABLE")
            if output["a_verdict"] != "ABSTAINED" or \
                    output["b_verdict"] != "ABSTAINED":
                problems.append("ABSTENTION_REQUIRES_ABSTAINED_VERDICTS")
        elif output["relative"] == "UNDECIDABLE":
            problems.append("UNDECIDABLE_REQUIRES_ABSTENTION")
    # claims: strict allow-list per claim (only when the list type holds)
    seen_ids = set()
    if claims_is_list:
        for i, c in enumerate(output["claims"]):
            if not isinstance(c, dict):
                claim_prob(i, "CLAIM_NOT_OBJECT")
                continue
            for field in c:
                if field not in JUDGE_CLAIM_FIELDS:
                    claim_prob(i, "EXTRA_FIELD_FORBIDDEN:" + field)
            for field in JUDGE_CLAIM_FIELDS:
                if field not in c:
                    claim_prob(i, f"MISSING_FIELD:{field}")
            cid = c.get("claim_id")
            if not isinstance(cid, str) or not cid:
                claim_prob(i, "CLAIM_ID_NOT_STRING")
            elif len(cid) > CLAIM_ID_MAX_CHARS:
                claim_prob(i, "CLAIM_ID_TOO_LONG")
            elif not CLAIM_ID_PATTERN.fullmatch(cid):
                claim_prob(i, "CLAIM_ID_MALFORMED")
            elif cid in seen_ids:
                claim_prob(i, "DUPLICATE_CLAIM_ID")
            else:
                seen_ids.add(cid)
            if c.get("kind") not in CLAIM_KINDS:
                claim_prob(i, "UNKNOWN_CLAIM_KIND")
            if c.get("target_side") not in ("A", "B"):
                claim_prob(i, "UNKNOWN_TARGET_SIDE")
            text = c.get("claim_text")
            if not isinstance(text, str) or not text:
                claim_prob(i, "CLAIM_TEXT_NOT_STRING")
            elif len(text) > CLAIM_TEXT_MAX_CHARS:
                claim_prob(i, "CLAIM_TEXT_TOO_LONG")
            refs = c.get("observed_evidence_refs")
            if not isinstance(refs, list) or not refs or not all(
                    isinstance(r, str) and r for r in refs):
                # evidence reference integrity: refs required, well-typed,
                # unique, and every ref must appear in the judge-level list
                claim_prob(i, "OBSERVED_EVIDENCE_REFS_REQUIRED")
            else:
                if len(set(refs)) != len(refs):
                    claim_prob(i, "DUPLICATE_EVIDENCE_REF")
                if evidence_refs_is_list and any(
                        r not in output["evidence_refs"] for r in refs):
                    claim_prob(i, "UNKNOWN_EVIDENCE_REF")
    if evidence_refs_is_list and \
            len(set(output["evidence_refs"])) != len(output["evidence_refs"]):
        problems.append("DUPLICATE_EVIDENCE_REF")
    return {"schema_version": output.get("schema_version", "?"),
            "valid": not problems, "problems": problems,
            "claims": [{"claim_id": c.get("claim_id", "?") if isinstance(c, dict) else "?",
                        "index": i} for i, c in enumerate(
                            output["claims"] if claims_is_list else [])]}


def check_component_inputs(role: str, inputs: dict) -> dict:
    """§D2A-D — static input-permission boundary check. At component
    input-assembly time, verify no denied material reaches the component.
    `inputs` maps input kind → content (or None if not provided)."""
    if role not in PIPELINE_ROLES:
        return {"role": role, "boundary_ok": False,
                "violations": ["UNKNOWN_ROLE:" + role]}
    perm = PIPELINE_ROLES[role]
    violations = []
    for kind, content in inputs.items():
        policy = perm.get(kind)
        if policy is None:
            violations.append("UNKNOWN_INPUT_KIND:" + kind)
        elif policy == "denied":
            if content is not None:
                violations.append("FORBIDDEN_INPUT:" + kind)
        elif policy == "locator-check only":
            # source paper: locator/digest metadata only — full text
            # (or any other key) is a boundary violation
            if not isinstance(content, dict):
                violations.append("FORBIDDEN_FULL_TEXT:" + kind)
            elif set(content) - {"locator", "digest"}:
                violations.append("FORBIDDEN_FULL_TEXT:" + kind)
            elif not content.get("locator") or not content.get("digest"):
                violations.append("INCOMPLETE_LOCATOR_CHECK:" + kind)
    return {"role": role, "boundary_ok": not violations,
            "violations": violations}


def finalize_review_record(record: dict) -> dict:
    """§D2A.1-C2 — attach review_record_digest: self-excluded canonical
    payload digest. The digest is an INTEGRITY check on the record data,
    NOT an authentication of the reviewer's identity — reviewer identity
    is verified only against a Reviewer Registry entry or an approved
    review record (trusted local execution environment premise)."""
    payload = {k: v for k, v in record.items()
               if k != "review_record_digest"}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
    out = dict(record)
    out["review_record_digest"] = sha256(canonical)
    return out


def _review_scope_sufficient(record) -> bool:
    """§D2A.1-C2 — review scope must cover the FULL perturbed note and
    the source-importance review. Accepts a structured dict (canonical)
    or a legacy string mentioning both."""
    scope = record.get("review_scope")
    if isinstance(scope, dict):
        return bool(scope.get("full_perturbed_note")) and \
            bool(scope.get("source_importance_review"))
    if isinstance(scope, str):
        low = scope.lower()
        return "perturbed" in low and ("source" in low or
                                       "importance" in low)
    return False


def validate_human_review(record, *, claim_id: str, documents: dict,
                          anchor_doc_ids: list) -> dict:
    """§D2A.1-C1/C2 — provenance-hardened Human Review Record
    validation (11 v2 fields; legacy `document_digests` alias accepted
    per compatibility policy). All mandatory: review id, reviewer id,
    claim binding, document digest binding, timestamp, scope coverage,
    verdicts, rationale, evidence references that exist in the actual
    documents, and record digest self-integrity. Any integrity failure
    means the record can never produce VERIFIED."""
    problems = []
    if not isinstance(record, dict):
        return {"valid": False,
                "problems": ["REVIEW_RECORD_NOT_OBJECT"]}
    # normalize legacy alias before field checks
    if "reviewed_document_digests" not in record and \
            "document_digests" in record:
        record = dict(record)
        record["reviewed_document_digests"] = \
            record["document_digests"]
    for field in REVIEW_RECORD_FIELDS:
        if field not in record or record[field] in (None, ""):
            problems.append(f"MISSING_FIELD:{field}")
    if record.get("claim_id") != claim_id:
        problems.append("CLAIM_ID_MISMATCH")
    reviewer = record.get("reviewer_id")
    if not isinstance(reviewer, str) or not reviewer.strip():
        problems.append("REVIEWER_ID_INVALID")
    review_id = record.get("review_id")
    if not isinstance(review_id, str) or not review_id.strip():
        problems.append("REVIEW_ID_INVALID")
    ts = record.get("review_timestamp")
    if not isinstance(ts, str) or len(ts) < 10:
        problems.append("REVIEW_TIMESTAMP_INVALID")
    if not isinstance(record.get("rationale"), str) or \
            len(record.get("rationale", "")) < 10:
        problems.append("RATIONALE_INSUFFICIENT")
    if not _review_scope_sufficient(record):
        problems.append("REVIEW_SCOPE_INSUFFICIENT")
    digests = record.get("reviewed_document_digests")
    if not isinstance(digests, dict) or not digests:
        problems.append("REVIEW_DIGESTS_MISSING")
    elif isinstance(digests, dict):
        for doc_id in anchor_doc_ids:
            if doc_id not in digests:
                problems.append("REVIEW_DIGEST_MISSING:" + doc_id)
            elif digests[doc_id] != sha256(documents[doc_id]):
                problems.append("REVIEW_DIGEST_MISMATCH:" + doc_id)
    # record evidence refs must exist in the actual documents
    refs = record.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        problems.append("REVIEW_EVIDENCE_REFS_MISSING")
    elif isinstance(refs, list):
        for ref in refs:
            if not isinstance(ref, dict) or \
                    not isinstance(ref.get("document_id"), str) or \
                    not isinstance(ref.get("quote"), str):
                problems.append("REVIEW_EVIDENCE_REF_MALFORMED")
            elif ref["document_id"] not in documents or \
                    ref["quote"] not in documents[ref["document_id"]]:
                problems.append("REVIEW_EVIDENCE_REF_ABSENT:" +
                                ref["document_id"])
    if record.get("global_absence_verdict") not in REVIEW_ABSENCE_VERDICTS:
        problems.append("UNKNOWN_ABSENCE_VERDICT")
    if record.get("source_importance_verdict") not in \
            REVIEW_IMPORTANCE_VERDICTS:
        problems.append("UNKNOWN_IMPORTANCE_VERDICT")
    # record digest self-integrity (self-excluded canonical payload)
    if "review_record_digest" in record and \
            record["review_record_digest"] not in (None, ""):
        recomputed = finalize_review_record(record)["review_record_digest"]
        if recomputed != record["review_record_digest"]:
            problems.append("REVIEW_RECORD_DIGEST_INVALID")
    return {"valid": not problems, "problems": problems}


def resolve_claim_evidence(claim: dict, judge_evidence_refs: dict,
                           documents: dict) -> dict:
    """§B1 — EvidenceResolver step. Judge `observed_evidence_refs` keys are
    resolved to VerificationEvidence records: digest-bound, fail-closed on
    mismatch or unresolvable reference. Source paper is touched for
    locator confirmation only."""
    records = []
    unresolved = []
    refs = judge_evidence_refs.get(claim["claim_id"], {})
    for ref_key in claim.get("observed_evidence_refs") or []:
        rec = refs.get(ref_key)
        if not isinstance(rec, dict):
            unresolved.append("UNRESOLVED_REF:" + ref_key)
            continue
        record = {f: rec.get(f) for f in VERIFICATION_EVIDENCE_FIELDS}
        result = validate_anchor(rec, documents)
        record["verification_status"] = result["verification_status"]
        record["verification_method"] = rec.get("match_policy")
        record["verification_evidence"] = {
            "problems": result["problems"],
            "quote_present": result["quote_present"],
        }
        records.append(record)
    return {"claim_id": claim["claim_id"],
            "verification_evidence": records, "problems": unresolved}


def verify_info_loss(*, claim_id: str, original_note_anchor: dict,
                     absence_evidence: dict, source_importance: dict,
                     documents: dict, original_note: str,
                     perturbed_note: str, source_paper: str,
                     human_review_record: dict | None = None) -> dict:
    """§B2 + §D2A.1-B — ClaimVerifier: information-loss verification from
    THREE evidences, with the SEMANTIC / LEXICAL layer separation.
    Lexical probe role (§D2A.1-B1 — policy corrected): the probe is a
    REVIEW AID only — it locates residual occurrences of the same terms
    in the perturbed note so the human reviewer can confirm whether the
    important relations/conditions/numerics/procedures are still present
    or gone. Lexical results are NEVER the final semantic presence /
    absence verdict and are NEVER an acceptance precondition: residual
    keyword presence alone does NOT fail a loss claim (partial-loss
    support, §D2A.1-B3), and lexical absence alone does NOT confirm one.
    Document binding (§D2A-B): probed texts must byte-equal the
    registered document texts; version mixing is fail-closed.
    Decision rules (fail-closed):
    - any FAILED evidence or binding conflict ⇒ FAILED
    - negative verdicts (absence REFUTED, importance NOT_IMPORTANT) ⇒
      FAILED
    - missing/invalid record, uncertain verdicts, UNREGISTERED or
      non-REGISTERED reviewer, insufficient rationale/scope, unreviewed
      residual probe locations ⇒ PENDING_HUMAN_REVIEW
    - VERIFIED only when ALL hold: original anchor valid; perturbed-note
      and source-paper binding valid; record bound to THIS claim and the
      CURRENT document versions; global_absence_verdict CONFIRMED;
      source_importance_verdict IMPORTANT; rationale + scope sufficient;
      record digest integrity holds; no FAILED evidence; and every
      residual probe location has been reviewed (lexical_probe_reviewed)
      when residual keyword hits exist."""
    binding_problems = []
    for anchor, text, label in ((original_note_anchor, original_note,
                                 "original_note"),
                                (absence_evidence, perturbed_note,
                                 "perturbed_note"),
                                (source_importance, source_paper,
                                 "source_paper")):
        doc_id = anchor.get("document_id")
        if doc_id in documents and documents[doc_id] != text:
            binding_problems.append("DOCUMENT_VERSION_CONFLICT:" + label)
    ev_original = validate_anchor(original_note_anchor, documents)
    ev_absence = validate_anchor(absence_evidence, documents)
    ev_importance = validate_anchor(source_importance, documents)
    if ev_original["verification_status"] == "VERIFIED" and \
            not binding_problems:
        in_perturbed = quote_match(original_note_anchor["quote"],
                                   perturbed_note, "markdown_normalized")
        local_absence = not in_perturbed
    else:
        local_absence = None
    # lexical probe: residual occurrences = candidate review locations
    keywords = [w.lower() for w in
                re.findall(r"[a-zA-Z]{6,}", original_note_anchor["quote"])]
    keywords = list(dict.fromkeys(keywords))[:8]
    lexical_hits = {k: len(re.findall(r"\b" + re.escape(k) + r"\b",
                                      perturbed_note, re.IGNORECASE))
                    for k in keywords}
    residual_probe_locations = any(v > 0 for v in lexical_hits.values())
    statuses = [ev_original["verification_status"],
                ev_absence["verification_status"],
                ev_importance["verification_status"]]
    review = validate_human_review(
        human_review_record, claim_id=claim_id, documents=documents,
        anchor_doc_ids=[original_note_anchor["document_id"],
                        absence_evidence["document_id"],
                        source_importance["document_id"]])
    record_reviewer = (human_review_record or {}).get("reviewer_id") \
        if isinstance(human_review_record, dict) else None
    if "FAILED" in statuses or binding_problems or \
            any(r["problems"] for r in
                (ev_original, ev_absence, ev_importance)):
        status = "FAILED"
    elif not review["valid"]:
        # record existence alone is never sufficient; unclear ⇒ PENDING
        status = "PENDING_HUMAN_REVIEW"
    elif human_review_record.get("global_absence_verdict") == "REFUTED" or \
            human_review_record.get("source_importance_verdict") == \
            "NOT_IMPORTANT":
        status = "FAILED"
    elif reviewer_status(record_reviewer) != "REGISTERED":
        # §D2A.1-C3 — no reviewer assigned ⇒ never promote to VERIFIED
        status = "PENDING_HUMAN_REVIEW"
    elif human_review_record.get("global_absence_verdict") == "CONFIRMED" \
            and human_review_record.get("source_importance_verdict") == \
            "IMPORTANT":
        if residual_probe_locations and not \
                human_review_record.get("lexical_probe_reviewed"):
            # §D2A.1-B4 — residual locations exist but were not reviewed
            status = "PENDING_HUMAN_REVIEW"
        else:
            status = "VERIFIED"
    else:
        status = "PENDING_HUMAN_REVIEW"
    return {
        "claim_id": claim_id,
        "evidence_original_note": ev_original,
        "evidence_perturbed_absence": {
            **ev_absence, "local_absence": local_absence,
            "probe_role": "review aid: locates residual occurrences of "
                          "the probed terms; neither semantic presence "
                          "nor semantic absence is decided by this probe",
            "keywords_probed": keywords, "lexical_hits": lexical_hits,
            "residual_probe_locations": residual_probe_locations,
            "residual_reviewed": human_review_record.get(
                "lexical_probe_reviewed") if isinstance(
                    human_review_record, dict) else None,
        },
        "evidence_source_importance": {
            **ev_importance, "note": "semantic judgment; decided by the "
                                     "recorded human review verdict",
        },
        "review_record_validation": review,
        "verification_status": status,
        "record": {"claim_id": claim_id,
                   "scope_digest": {"original_note": sha256(original_note),
                                    "perturbed_note": sha256(perturbed_note),
                                    "source_paper": sha256(source_paper)},
                   "document_binding_problems": binding_problems,
                   "reviewer_status": reviewer_status(record_reviewer),
                   "human_review_recorded": review["valid"]},
    }


def sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def markdown_normalize(text: str) -> str:
    return text.replace("**", "").replace("   *   ", "* ") \
               .replace("*   ", "* ").strip()


def quote_match(quote: str, text: str, policy: str) -> bool:
    if policy == "byte_exact":
        return quote in text
    if policy == "markdown_normalized":
        return markdown_normalize(quote) in markdown_normalize(text)
    return False  # semantic_review is never machine-resolvable here


def validate_anchor(anchor: dict, documents: dict) -> dict:
    """Fail-closed anchor validation. `documents` maps document_id → text
    (raw bytes-as-str). Digest binding is mandatory."""
    problems = []
    for field in ("document_id", "document_digest", "document_role",
                  "locator", "quote", "match_policy"):
        if field not in anchor or anchor[field] in (None, ""):
            problems.append(f"MISSING_FIELD:{field}")
    if anchor.get("document_role") not in DOCUMENT_ROLES:
        problems.append("UNKNOWN_DOCUMENT_ROLE")
    if anchor.get("match_policy") not in MATCH_POLICIES:
        problems.append("UNKNOWN_MATCH_POLICY")
    if problems:
        return {"verification_status": "FAILED", "problems": problems,
                "quote_present": False}
    doc_id = anchor["document_id"]
    if doc_id not in documents:
        return {"verification_status": "FAILED",
                "problems": ["DOCUMENT_ABSENT:" + doc_id],
                "quote_present": False}
    text = documents[doc_id]
    if anchor["document_digest"] != sha256(text):
        return {"verification_status": "FAILED",
                "problems": ["DOCUMENT_DIGEST_MISMATCH:" + doc_id],
                "quote_present": False}
    if anchor["match_policy"] == "semantic_review":
        # never machine-resolvable — human review, not FAILED
        return {"verification_status": "PENDING_HUMAN_REVIEW",
                "problems": [], "quote_present": None}
    present = quote_match(anchor["quote"], text, anchor["match_policy"])
    return {"verification_status": ("VERIFIED" if present else "FAILED"),
            "problems": ([] if present else ["QUOTE_ABSENT:" + doc_id]),
            "quote_present": present}


def validate_claim(claim: dict, documents: dict) -> dict:
    """Static claim-contract validation (schema + anchors). Independent of
    any judge output parser."""
    problems = []
    for field in ("claim_id", "kind", "target_note", "anchors"):
        if field not in claim:
            problems.append(f"MISSING_FIELD:{field}")
    if problems:
        return {"claim_id": claim.get("claim_id", "?"), "valid": False,
                "verification_status": "FAILED", "problems": problems,
                "anchor_results": []}
    if claim["kind"] not in CLAIM_KINDS:
        return {"claim_id": claim["claim_id"], "valid": False,
                "verification_status": "FAILED",
                "problems": ["UNKNOWN_CLAIM_KIND"],
                "anchor_results": []}
    anchors = claim.get("anchors") or []
    if not anchors:
        return {"claim_id": claim["claim_id"], "valid": False,
                "verification_status": "FAILED",
                "problems": ["REQUIRED_ANCHORS_MISSING"],
                "anchor_results": []}
    anchor_results = [validate_anchor(a, documents) for a in anchors]
    failed = [a for a in anchor_results
              if a["verification_status"] == "FAILED"]
    pending = [a for a in anchor_results
               if a["verification_status"] == "PENDING_HUMAN_REVIEW"]
    # kind-specific required-anchor presence (fail-closed)
    if claim["kind"] == "info_loss":
        roles = {a.get("anchor_role") for a in anchors}
        missing_roles = [r for r in INFO_LOSS_ANCHOR_ROLES
                         if r not in roles]
        if missing_roles:
            problems.extend("REQUIRED_ANCHOR_MISSING:" + r
                            for r in missing_roles)
    if claim["kind"] == "contradiction" and len(anchors) < 2:
        problems.append("CONTRADICTION_REQUIRES_2_QUOTES")
    valid = not failed and not problems  # contract-satisfying claim
    if not valid:
        status = "FAILED"
    elif pending:
        status = "PENDING_HUMAN_REVIEW"
    else:
        status = "VERIFIED"
    return {"claim_id": claim["claim_id"], "valid": valid,
            "verification_status": status,
            "problems": problems, "anchor_results": anchor_results}


def verify_absence(*, claim: dict, original_note: str,
                   perturbed_note: str) -> dict:
    """§A2 — absence evidence with LOCAL vs GLOBAL separation. Fail-closed:
    Global Absence confirmed only by structured search + human review; a
    mere string-absence is never VERIFIED. Unresolvable ⇒
    PENDING_HUMAN_REVIEW."""
    local = {
        "check": "deletion-site context and Original/Perturbed correspondence",
        "method": "compare the quoted original_note_anchor against the "
                  "perturbed note with markdown normalization",
        "original_quote_bound": claim.get("anchors") is not None,
        "found_in_perturbed": None,
    }
    if claim.get("anchors"):
        for a in claim["anchors"]:
            if a.get("anchor_role") == "original_note_anchor":
                local["found_in_perturbed"] = quote_match(
                    a["quote"], perturbed_note, a.get("match_policy",
                                                     "markdown_normalized"))
    local["verified"] = local["found_in_perturbed"] is False
    # Global Absence: semantic search of the same information elsewhere —
    # statically limited to lexical heuristics; a lexical miss is NOT a
    # semantic confirmation ⇒ human review required.
    keywords = []
    for a in claim.get("anchors") or []:
        if a.get("anchor_role") == "original_note_anchor":
            words = re.findall(r"[a-zA-Z]{6,}", a["quote"])
            keywords = list(dict.fromkeys(w.lower() for w in words))[:8]
    global_absence = {
        "check": "same information present elsewhere in the perturbed note",
        "scope_digest": {"original_note": sha256(original_note),
                         "perturbed_note": sha256(perturbed_note)},
        "method": "lexical keyword probe over the full perturbed note; "
                  "lexical absence is NOT semantic confirmation",
        "keywords_probed": keywords,
        "lexical_hits": {},
        "conclusion": None,
    }
    if keywords:
        global_absence["lexical_hits"] = {
            k: len(re.findall(r"\b" + re.escape(k) + r"\b",
                              perturbed_note, re.IGNORECASE))
            for k in keywords}
        if all(v == 0 for v in global_absence["lexical_hits"].values()):
            # all keywords lexically absent — still not semantically decided
            global_absence["conclusion"] = "PENDING_HUMAN_REVIEW"
        else:
            global_absence["conclusion"] = "PENDING_HUMAN_REVIEW"
    else:
        global_absence["conclusion"] = "PENDING_HUMAN_REVIEW"
    status = "VERIFIED" if (local["verified"] and
                            global_absence["conclusion"] == "VERIFIED") \
        else "PENDING_HUMAN_REVIEW"
    return {"local_evidence": local, "global_absence": global_absence,
            "verification_status": status,
            "record": {"scope_digest": global_absence["scope_digest"],
                       "note": "verification scope, compared digests, "
                               "method and review outcome are all recorded "
                               "in this structure; semantic absence not "
                               "machine-decidable here ⇒ human review"}}
