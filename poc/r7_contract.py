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
# info_loss: 3-anchor contract — each role is mandatory and distinct.
INFO_LOSS_ANCHOR_ROLES = {
    "original_note_anchor": "where the information existed in the ORIGINAL note",
    "absence_evidence": "adjacent context in the TARGET note proving deletion "
                        "(the deleted sentence itself is absent)",
    "importance_evidence": "source-paper evidence that the information was "
                           "actually important",
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
