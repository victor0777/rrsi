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
# info_loss: 3-anchor contract — each role is mandatory and distinct.
INFO_LOSS_ANCHOR_ROLES = {
    "original_note_anchor": "where the information existed in the ORIGINAL note",
    "absence_evidence": "adjacent context in the TARGET note proving deletion "
                        "(the deleted sentence itself is absent)",
    "importance_evidence": "source-paper evidence that the information was "
                           "actually important",
}


def validate_judge_output(output: dict) -> dict:
    """§A3 — Judge output schema (r7-judge-output/v0.3). The Judge emits
    only observable-level fields: it is NOT asked for source-paper
    importance judgments or gold information. Claims carry
    observed_evidence_refs (resolver-facing), not verified anchors."""
    problems = []
    for field in JUDGE_OUTPUT_FIELDS:
        if field not in output:
            problems.append(f"MISSING_FIELD:{field}")
    if problems:
        return {"schema_version": output.get("schema_version", "?"),
                "valid": False, "problems": problems, "claims": []}
    if output["schema_version"] != JUDGE_SCHEMA_VERSION:
        problems.append("UNKNOWN_SCHEMA_VERSION")
    if output["relative"] not in ("A", "B", "EQUAL", "UNDECIDABLE"):
        problems.append("UNKNOWN_RELATIVE")
    for v in (output["a_verdict"], output["b_verdict"]):
        if v not in ("VALID", "INVALID", "ABSTAINED"):
            problems.append("UNKNOWN_VERDICT")
    if not isinstance(output["abstention"], bool):
        problems.append("ABSTENTION_NOT_BOOLEAN")
    if output["abstention"] and output["relative"] != "UNDECIDABLE":
        problems.append("ABSTENTION_REQUIRES_UNDECIDABLE")
    parsed_claims = []
    for i, c in enumerate(output.get("claims") or []):
        cprobs = []
        for field in JUDGE_CLAIM_FIELDS:
            if field not in c or c[field] in (None, ""):
                cprobs.append(f"MISSING_FIELD:{field}")
        if c.get("kind") not in CLAIM_KINDS:
            cprobs.append("UNKNOWN_CLAIM_KIND")
        if c.get("target_side") not in ("A", "B"):
            cprobs.append("UNKNOWN_TARGET_SIDE")
        refs = c.get("observed_evidence_refs")
        if not isinstance(refs, list) or not refs:
            cprobs.append("OBSERVED_EVIDENCE_REFS_REQUIRED")
        # judge must not assert verification it cannot perform
        for forbidden in ("importance_evidence", "verification_status"):
            if forbidden in c:
                cprobs.append(f"JUDGE_FORBIDDEN_FIELD:{forbidden}")
        parsed_claims.append({"index": i, "problems": cprobs,
                              "claim_id": c.get("claim_id", "?")})
    for c in parsed_claims:
        problems.extend(f"CLAIM[{c['index']}]:{p}" for p in c["problems"])
    return {"schema_version": output["schema_version"],
            "valid": not problems, "problems": problems,
            "claims": parsed_claims}


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
                     perturbed_note: str, human_review: bool = False) -> dict:
    """§B2 — ClaimVerifier: information-loss verification from THREE
    evidences.
    1. Original Note Evidence — anchor quote must exist in the original
       note (digest-bound, fail-closed).
    2. Perturbed Note Absence — local: anchor quote absent from the
       perturbed note (markdown-normalized); global: no equivalent info
       elsewhere — machine layer is a lexical probe only, never
       confirming ⇒ human review unless a recorded human review exists.
    3. Source Paper Importance — semantic judgment against the source
       paper ⇒ machine-decidable only with a recorded human review;
       otherwise PENDING_HUMAN_REVIEW.
    Fail-closed: any FAILED evidence ⇒ FAILED; any undecided ⇒
    PENDING_HUMAN_REVIEW; VERIFIED only when all three are confirmed."""
    ev_original = validate_anchor(original_note_anchor, documents)
    ev_absence = validate_anchor(absence_evidence, documents)
    ev_importance = validate_anchor(source_importance, documents)
    if ev_original["verification_status"] == "VERIFIED":
        in_perturbed = quote_match(original_note_anchor["quote"],
                                   perturbed_note, "markdown_normalized")
        local_absence = not in_perturbed
    else:
        local_absence = None
    # global absence: lexical probe — a miss is not semantic confirmation
    keywords = [w.lower() for w in
                re.findall(r"[a-zA-Z]{6,}", original_note_anchor["quote"])]
    keywords = list(dict.fromkeys(keywords))[:8]
    lexical_hits = {k: len(re.findall(r"\b" + re.escape(k) + r"\b",
                                      perturbed_note, re.IGNORECASE))
                    for k in keywords}
    global_absence_machine = (bool(lexical_hits)
                              and all(v == 0
                                      for v in lexical_hits.values()))
    statuses = [ev_original["verification_status"],
                ev_absence["verification_status"],
                ev_importance["verification_status"]]
    if "FAILED" in statuses or any(
            r["problems"] for r in (ev_original, ev_absence, ev_importance)):
        status = "FAILED"
    elif human_review and global_absence_machine:
        # recorded human review + machine-confirmed global lexical absence
        status = "VERIFIED"
    else:
        status = "PENDING_HUMAN_REVIEW"
    return {
        "claim_id": claim_id,
        "evidence_original_note": ev_original,
        "evidence_perturbed_absence": {
            **ev_absence, "local_absence": local_absence,
            "global_absence_method": "lexical keyword probe; lexical "
                                     "absence is NOT semantic confirmation",
            "keywords_probed": keywords, "lexical_hits": lexical_hits,
            "global_absence_machine_confirmed": global_absence_machine,
        },
        "evidence_source_importance": {
            **ev_importance, "note": "semantic judgment; machine layer "
                                     "requires recorded human review",
        },
        "verification_status": status,
        "record": {"claim_id": claim_id,
                   "scope_digest": {"original_note": sha256(original_note),
                                    "perturbed_note": sha256(perturbed_note)},
                   "human_review_recorded": human_review},
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
