---
doc_id: poc-rrsi-07-proposals
title: research_agent / ai_papers Review and RRSI Integration Proposals
status: proposal
updated: 2026-10-20
---

# research_agent / ai_papers Review → RRSI Integration Proposals

This document reviews the two projects' harness surfaces and assets, and
proposes three concrete integration plans with the RRSI method core
(analyzed in `01–02`). Each proposal is independent; A is the recommended first
target. Actual implementation remains a separate decision.

## Part 1 — Review

### ai_papers (lower layer: paper reading → knowledge capture)

**Pipeline** (`docs/overview.md`): source capture → extraction bundle →
reader-note chain → Analysis/KG policy v2b candidates → graph preview + KCP
draft gate → cross-paper compatibility → cluster synthesis → relation/group
review → survey synthesis → canonical promotion gate.

**Harness surfaces that a self-improvement loop could edit:**
- reader-note chain prompts (reader instructions, must_explain expectations)
- `context_planning` (what context a reader pass receives)
- `multi_pass` policies; Analysis/KG policy v2b candidate thresholds/config

**Assets the loop can measure against (this is the key finding):**
- `docs/eval/reader-note-quality/gold/*.reader-note-quality-gt.json` — per-paper
  GT with per-item criteria: `must_explain`, `expected_reader_understanding`,
  `acceptable_term_groups`, `source_sentence_ids` (citation integrity)
- `docs/eval/analysis-kg-quality/gold/`, `artifact-interpretation-quality`,
  `loop-stability` (a 10-GT loop-stability review already exists)
- `quarantine/` beside `gold/` — a ready-made holdout source

**LLM layer** (`src/ai_papers_research/llm/`): `glm_adapter`, `qwen_client`,
`call_budget.py`, `circuit_admin.py`, `resilience.py`, `thinking.py` — bounded
calls with budget accounting already exist. RRSI's ΔC plugs onto `call_budget`
tokens; no new gateway code is needed.

### research_agent (upper layer: research decisions over KG artifacts)

**Mission** (`docs/overview.md`, `CLAUDE.md`): use GLM to read reviewable
KG-oriented artifacts and decide what research action happens next — review
automation (`cross_paper_review_*`), memory-guided decisions
(`research_state_memory_*`), admission/promotion gates, impact evaluation,
provenance tracing. Strong experiment discipline: frozen cohorts, exposure
manifests, experiment freeze/replay, promotion acceptance reviews.

**Harness surfaces:** review/triage prompts and thresholds, memory update
policies, admission contracts (`bounded_reasoning`, `epistemic_control_policy`).

**Assets to measure against:** frozen review cohorts, promotion acceptance
records, `coordination/milestones` acceptances/corrections.

### What RRSI contributes (from `poc/`)

A per-round loop with: noise band δ calibrated from repeat base evaluations;
gains that must pay their token cost; a critic that blocks suite-specific
leakage BEFORE evaluation; a prune set that removes machinery that stopped
helping; per-edit JSONL evidence; fast-forward-only acceptance with restorable
commits. The PoC verified these contracts model-free.

## Part 2 — Proposals

### Proposal A — Evolve the ai_papers reader-note harness (recommended first)

| Element | Definition |
|---|---|
| Domain adapter | one reader pipeline invocation = one trial; harness state = reader prompts + context_planning config + multi_pass settings (file-backed, editable in candidate worktrees) |
| Task set | evolve: reader-note gold papers minus holdout topics; holdout: quarantined papers + at least one topic cohort disjoint from the evolve set (e.g., hold out `e2e-*`, evolve on `agent-memory-*` — then reverse) |
| Reward | criteria passed / criteria total, weight = criteria total per item (rrsi's weighted estimator supports this directly — Harvey LAB-style) |
| Cost | ΔC = tokens per paper from `call_budget.py` |
| δ | repeat the baseline reader evaluation ×4 (papers fixed, LLM variance only); record sd(null ΔS) in the freeze doc |
| Critic denylist | gold paper titles/arxiv ids, GT item ids, grader paths; plus rrsi's 6-criterion LLM rubric |
| Domain guards (non-compensatory) | citation integrity (no `source_sentence_ids` fabrication), KCP draft-gate acceptance rate drop, evidence-authority violations — checked AFTER floor + cost rule |
| Acceptance | rrsi History JSONL per edit; adopt = fast-forward `evolve/reader`; Collabo milestone records the promotion; revert = `update-ref` to the prior trajectory entry |

Why first: the reward function already exists in GT form; the task set is file-
backed; the cost layer already exists; the harness state is text files — the
PoC's fixture matches this shape almost one-to-one. Risk: a reader pass has LLM
variance in the loop itself, so k≥2 and the δ floor do real work.

Estimated cost: one candidate round ≈ (4 baseline + 2 candidates × k trials) ×
(1 paper read each) reader runs; roughly 10–15 full paper reads per round.

### Proposal B — Evolve research_agent review triage

| Element | Definition |
|---|---|
| Domain | review decision automation on frozen review cohorts; harness = triage prompt + admission thresholds + memory update policy |
| Task set | evolve: frozen cohort A; holdout: frozen cohort B (their cohort-freeze discipline IS the evolve/holdout split) |
| Reward | agreement with human review outcomes / promotion acceptance results (binary per decision) |
| Guards | abstention contract, evidence authority; hallucination rate must not rise |
| δ | same repeat-baseline calibration; review decisions are high-variance → expect a wide band, which is honest |

Why second: reward definition needs care (agreement ≠ correctness), and review
quality regressions are costlier than reader-note regressions. But this is the
layer where self-improvement compounds most (it decides research actions).

### Proposal C — Audit-first adoption (zero-loop)

Adopt RRSI's pieces as instrumentation inside the EXISTING eval flows, no
evolution loop:
1. δ calibration for `docs/eval/loop-stability` — report "did the pipeline
   change by more than noise" instead of eyeballing the 10-GT review.
2. Critic denylist as a pre-merge check on prompt file changes in both repos
   (cheap CI step; no LLM needed for the deterministic layer).
3. Per-edit history JSONL for prompt/config changes (Collabo-linked), so prompt
   archaeology becomes evidence retrieval.

C is the lowest-risk start and produces the freeze/δ artifacts that A and B need
anyway.

### Sequencing and shared infrastructure

```
C (audit-first, ~2 days)  ->  δ artifacts, denylist CI, history convention
A (reader harness, ~1 wk) ->  first evolution loop, ai_papers only
B (review triage, later)  ->  second loop, research_agent, reuses everything
```

Shared components (built once, used by A and B): Domain adapter base, GLM
client behind rrsi's `generate` signature (via ai_papers `llm/` — no new
gateway), candidate worktree wrapper delegating to rrsi `gitops` (126 LOC),
History JSONL + Collabo milestone link by (round, variant).

Non-duplication guardrails (unchanged from `03-INTEGRATION-DESIGN`): no second
LLM gateway, no second retry engine, no second run-history store; rrsi core is
vendored as a package, not forked per project.

## Decision points

1. Confirm Proposal A's task split (which topic cohorts evolve vs holdout) in a
   freeze document before any run.
2. Confirm ΔC pricing (β0/β1) from `call_budget` token accounting.
3. Whether adoption is audit-first (C) or full loop (A): C's artifacts are
   prerequisites for A, so C is not a fork in the road but step one.
