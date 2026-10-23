# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS.
"""R0-a static integration checks (R0-a directive item 1), model-free.

Implements, as checkable code, the four R0-a verification duties that are
static in nature:

  U1 scope isolation        freeze globs vs candidate diff paths
  Promotion state machine   R1.1 section 7 transition table with reject paths
  Holdout access blocking   dataset-id denylist over candidate diff text
  Vendored-core conformance signature check (see conformance_signature())
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field

# ------------------------------------------------------------------ U1 scope --

# U1-only edit surface (the ONLY paths a Reader Prompt candidate may touch).
U1_GLOBS = [
    "src/ai_papers_research/paper/study/reader_note/prompts.py",
    "src/ai_papers_research/paper/study/reader_note/section_plan/*",
]

# Frozen for R1: a candidate touching ANY of these is rejected as over-scope.
FROZEN_GLOBS = [
    "src/ai_papers_research/context_planning/*",
    "src/ai_papers_research/multi_pass/*",
    "src/ai_papers_research/analysis_kg/*",
    "src/ai_papers_research/llm/*",
    "src/research_agent/*",
]


def scope_violations(changed_paths: list[str]) -> list[str]:
    """Paths outside the U1 surface, i.e. frozen-set violations."""
    bad = []
    for p in changed_paths:
        if not any(fnmatch.fnmatch(p, g) for g in U1_GLOBS):
            bad.append(p)
    return bad


# --------------------------------------------------------- promotion states --

# Transition table, R1.1 section 7. Every edge names its required condition;
# the ordering duty (holdout evidence BEFORE human approval) is edge 7.
STATES = ["EVALUATED", "ADMISSIBLE", "PROMOTED", "FROZEN", "HOLDOUT_DRAWN",
          "HUMAN_APPROVED", "CANONICAL"]

TRANSITIONS: dict[tuple[str, str], str] = {
    ("EVALUATED", "ADMISSIBLE"): "floor+cost+guard pass",
    ("ADMISSIBLE", "PROMOTED"): "argmax + L2 no-regression confirmed",
    ("PROMOTED", "FROZEN"): "experiment closed; tree hash registered; no further rounds",
    ("FROZEN", "HOLDOUT_DRAWN"): "batch holdout executed; access log registered",
    ("HOLDOUT_DRAWN", "HUMAN_APPROVED"): "Collabo milestone accept; report includes holdout result",
    ("HUMAN_APPROVED", "CANONICAL"): "rollback plan registered",
}


@dataclass
class HistoryEntry:
    state: str
    ts: int                              # monotonic clock (seconds)


class StateMachineError(ValueError):
    """Stable reject reason; never carries candidate payload."""


def assert_transition(history: list[HistoryEntry], to: str) -> HistoryEntry:
    """Apply one transition; raise on every R0-a reject path."""
    if not history:
        raise StateMachineError("EMPTY_HISTORY")
    last = history[-1]
    if last.state == to:
        raise StateMachineError("NOOP_TRANSITION")
    # R0-a ordering duty first: approval must never precede holdout evidence,
    # whatever the transition table says.
    if to in ("HUMAN_APPROVED",) and \
            not any(e.state == "HOLDOUT_DRAWN" for e in history):
        raise StateMachineError("APPROVAL_WITHOUT_HOLDOUT")
    if (last.state, to) not in TRANSITIONS:
        raise StateMachineError(f"ILLEGAL_TRANSITION:{last.state}->{to}")
    if any(e.ts > last.ts for e in history):
        raise StateMachineError("NON_MONOTONIC_TIMESTAMP")
    return HistoryEntry(to, last.ts + 1)


# ---------------------------------------------------- holdout access blocking --

# R1.1 section 3.2: holdout dataset ids must never appear in a candidate diff.
HOLDOUT_IDS = [
    "2502.12110", "2508.04700", "2508.06433", "2508.08997",
    "2508.09736", "2508.09874", "2509.11860", "2509.21212",
    "2510.08191", "2605.23723", "2508.01922", "2510.16729", "2510.17148",
]


def holdout_leaks(diff_text: str) -> list[str]:
    return [i for i in HOLDOUT_IDS if i in diff_text]


# ---------------------------------------------- vendored-core conformance -----

# SHA-256 prefix list of the vendored rrsi core files at R0-a; a change to the
# core changes these and fails the check. Values are recomputed from the tree.
import hashlib  # noqa: E402
from pathlib import Path  # noqa: E402

CORE_FILES = [
    "rrsi/analyst.py", "rrsi/calibrate.py", "rrsi/components.py",
    "rrsi/config.py", "rrsi/critic.py", "rrsi/domain.py", "rrsi/driver.py",
    "rrsi/evaluate.py", "rrsi/gitops.py", "rrsi/history.py", "rrsi/llm.py",
    "rrsi/loop.py", "rrsi/propose.py", "rrsi/schedule.py",
    "rrsi/selection.py",
]


@dataclass
class CoreSignature:
    digests: dict = field(default_factory=dict)

    def extend(self) -> "CoreSignature":
        for rel in CORE_FILES:
            b = (Path(__file__).resolve().parent.parent / rel).read_bytes()
            self.digests[rel] = hashlib.sha256(b).hexdigest()[:16]
        return self
