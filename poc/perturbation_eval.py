# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
"""Deterministic minimal evaluators for the perturbation discrimination audit.

Reuse-first policy: only functions needed by the P2/P3/P6 experiment and not
already implemented elsewhere are added here. Known limitations are part of
the contract — no semantic judgment is ever produced.

    numeric_source_consistency(note, source)
        Every explicit numeral in the note must occur in the source after
        unit-aware normalization ("10K" == "10000", commas stripped).
        LIMITATION: detects literal/normalized presence only — a numerically
        correct paraphrase whose value the source states differently is
        flagged as inconsistent even when semantically correct, and vice
        versa no meaning check is performed on the surrounding claim.
    reference_integrity(note, valid_refs)
        Every note reference of a known artifact shape must be in the valid
        set. LIMITATION: existence only — whether a reference actually
        supports the surrounding claim (semantic grounding) is NOT judged.
    literal_evidence(quote, document)
        Whitespace-tolerant substring presence (reuses the producer rule).
    length_stats(text)
        Chars + whitespace tokens. LIMITATION: whitespace tokens are a
        proxy, not the provider tokenizer.
"""

from __future__ import annotations

import re


def _norm_number(token: str) -> int | None:
    t = token.strip().replace(",", "").lower()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(k|m|b)?", t)
    if m is None:
        return None
    value = float(m.group(1))
    scale = {"k": 1e3, "m": 1e6, "b": 1e9}.get(m.group(2) or "", 1)
    out = value * scale
    return int(out) if out == int(out) else None


NUM_TOKEN = re.compile(r"\b\d[\d,.]*(?:\s*[kmb])?\b", re.IGNORECASE)
REF_TOKEN = re.compile(r"\b((?:fig|tbl|eq)\d{3,4})\b", re.IGNORECASE)


def extract_numbers(text: str) -> list[int]:
    out = []
    for m in NUM_TOKEN.finditer(text):
        value = _norm_number(m.group(0))
        if value is not None and value not in out:
            out.append(value)
    return out


def numeric_source_consistency(note_text: str, source_text: str) -> dict:
    note_nums = extract_numbers(note_text)
    source_nums = set(extract_numbers(source_text))
    missing = [n for n in note_nums if n not in source_nums]
    return {
        "schema": "rrsi-numeric-source-consistency/v0.1",
        "consistent": not missing,
        "note_numbers": note_nums,
        "missing_from_source": missing,
        "limitation": "normalized presence only; no semantic claim judgment",
    }


def reference_integrity(note_text: str, valid_refs: set) -> dict:
    refs = [r.lower() for r in REF_TOKEN.findall(note_text)]
    unique = sorted(set(refs))
    broken = sorted(set(r for r in unique if r not in {v.lower() for v in valid_refs}))
    return {
        "schema": "rrsi-reference-integrity/v0.1",
        "intact": not broken,
        "references": unique,
        "broken_references": broken,
        "limitation": "existence only; semantic grounding not judged",
    }


def literal_evidence(quote: str, document: str) -> bool:
    from poc.qasper_fulltext_calibration import normalized_find
    return normalized_find(document, quote) is not None


def length_stats(text: str) -> dict:
    return {
        "schema": "rrsi-length-stats/v0.1",
        "chars": len(text),
        "whitespace_tokens": len(text.split()),
        "limitation": "whitespace tokens are a proxy, not the provider tokenizer",
    }


def designated_numeric_consistency(note_text: str, source_text: str,
                                   value: str) -> dict:
    """Check ONE designated numeric claim (experiment-scoped, noise-free).

    Global numeric consistency is NOT a valid signal here — citation years
    and section numbers exist in notes but not in full_text. This checks a
    single designated experimental/statistical value with unit-aware
    normalization and reports strict-literal vs normalized results.
    """
    value_norm = _norm_number(value)
    source_norm = extract_numbers(source_text)
    literal = value.strip().lower() in source_text.strip().lower()
    normalized = value_norm in source_norm if value_norm is not None else None
    perturbed_ok = literal or bool(normalized)
    return {
        "schema": "rrsi-designated-numeric-consistency/v0.1",
        "value": value,
        "literal_in_source": literal,
        "normalized_in_source": normalized,
        "consistent": perturbed_ok,
        "limitation": "designated value only; semantic judgment of the "
                      "surrounding claim not performed",
    }
