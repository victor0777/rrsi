---
doc_id: poc-rrsi-08-kb-proposals
title: research_agent / ai_papers Review and RRSI Integration Proposals (KB)
status: proposal
updated: 2026-10-20
---

# research_agent / ai_papers Review → RRSI Integration Proposals (KB edition)

Companion to `07-RESEARCH-AGENT-AI-PAPERS-PROPOSALS.md`, which reviews the two
projects and proposes three sequenced integration plans with the RRSI method
core: **C audit-first instrumentation → A ai_papers reader-note harness
evolution → B research_agent review triage evolution**. That document holds the
authoritative proposal tables (task/reward/δ/critic/guard definitions per
proposal). This file records the review's supporting detail and the reasoning
summary for the KB layer.

## Review detail (why these proposals)

- **ai_papers gold fixtures are the missing reward function.** The
  reader-note-quality GT files carry per-item criteria (`must_explain`,
  `expected_reader_understanding`, `acceptable_term_groups`,
  `source_sentence_ids`) — exactly the criteria-passed reward model rrsi's
  weighted estimator consumes, with citation integrity available as a
  non-compensatory guard.
- **Holdout exists already.** `quarantine/` sits beside `gold/` in the eval
  directories; topic-cohort disjointness gives a second holdout axis.
- **Cost accounting exists.** `src/ai_papers_research/llm/call_budget.py` gives
  tokens per run; rrsi's relative cost change and L1 rule plug directly onto it.
- **research_agent's experiment discipline IS the task-split machinery.** Frozen
  cohorts and exposure manifests map one-to-one onto rrsi's evolve/holdout
  slots; its coordination milestones become the human promotion gate.
- **Nothing in `harness2/optimizer` duplicates rrsi's δ / cost rule / prune
  logic** (verified in `05`), and nothing in the two projects duplicates the
  loop either — the proposed additions are new, thin wrappers (~600 LOC) over a
  vendored Apache-2.0 core, not parallel implementations.

## Sequencing (from `07`)

```
C (audit-first, ~2 days)  ->  δ calibration for loop-stability, critic denylist
                              as prompt-change pre-merge check, per-edit JSONL
                              history convention linked to Collabo
A (reader harness, ~1 wk) ->  first evolution loop on ai_papers reader
                              prompts / context planning / multi_pass
B (review triage, later)  ->  second loop on research_agent review triage /
                              admission thresholds / memory policy
```

Cost estimate for one candidate round of A: roughly 10–15 full paper reads
(4 baseline + 2 candidates × k trials).

## Decision points

1. Freeze the evolve/holdout topic split before any run (which cohort evolves).
2. Set β0/β1 pricing from real `call_budget` token accounting.
3. Confirm audit-first (C) is step one, not an alternative fork — its artifacts
   are prerequisites for A.
