---
doc_id: poc-rrsi-05-harness2-comparison
title: RRSI vs Harness² — mechanism comparison
status: final
updated: 2026-10-20
---

# RRSI vs Harness² Comparison

Harness² (`../harness2`, arXiv:2610.14224) does **task-level recursion**
(Propose–Probe–Compose contrastive editing per task) plus **harnessing-level
recursion** (a persistent improvement harness adopting adopted harnesses and
evidence-backed lessons). RRSI does **suite-level evolution with regularized
selection** across rounds. This document compares mechanisms only; it changes
nothing in `harness2`.

## 1. Side-by-side

| Dimension | RRSI | Harness² |
|---|---|---|
| Improvement unit | candidate harness vs incumbent, per round | per-task refinement step (k recursion budget) |
| Candidate generation | proposer agent conditioned on full edit history L_t; independent variants (m) drafted in parallel worktrees | editor proposes invariant + domain edits; candidate probes execute the SAME task (contrastive, no ground truth); composer composes behavioral contrasts |
| Evaluation | full evolve set × k trials, parallel, resume-safe | per-task probe runs; benchmark judged after selection by a separate rubric judge |
| Promotion condition | noise-adjusted floor S' ≥ S* − δ + cost rule (L1 for real gains, shaped within the band) + domain guards + critic pre-screen | no suite-level noise band: a step composes what helped the current task; gains asserted via behavioral contrast, no statistical floor |
| Experience reuse | L_t (all measured edits incl. rejected) conditions the proposer; prune set removes stopped machinery | harnessing-level recursion persists adopted harnesses + lessons; per-task |
| Cost control | ΔC budget: tokens must be paid by measured gain; missing trials count 0 under full denominator | probe count = recursion budget k; rubric pass, no token rule |
| Failure regime it targets | overfitting to the evolve SUITE across rounds | cold-start on a NEW task with an open world |

## 2. The structural difference that matters

RRSI regularizes the **search trajectory across rounds**: a falsified hypothesis
is not redrawn, gains must clear measured noise, stopped components are pruned.
Harness² regularizes the **step on a single task**: behavioral contrasts between
probes decide what composes. They attack different failure modes and compose
naturally:

```
Harness² step (task level, cheap, contrastive)
   -> adopted task harnesses become the "evolve set" artifacts
   -> RRSI-style round (suite level: floor + cost rule + prune) decides promotion
   -> persistent improvement harness stores what cleared the band
```

## 3. Reusable common interface

- Candidate = (declared edits [(component, hypothesis, diff)], mechanism, targets).
  Both sides use essentially this shape; the PoC's catalog is a concrete fixture.
- History JSONL per edit with measured outcome — harness2's evidence directory and
  rrsi's `History` fill the same slot; unifying the schema (~20 fields) is a
  paper exercise, not a rewrite.
- Worktree-per-candidate isolation — rrsi `gitops` (126 LOC, Apache-2.0) can
  serve both; harness2 currently has its own runtime paths.
- GLM client — harness2's `optimizer/glm_client.py` and an rrsi backend should
  share llm-proxy-runtime bindings.

## 4. Cost and generalization

RRSI pays per candidate a full suite evaluation (expensive, statistically
founded); Harness² pays k probes per task (cheap per step, no OOD guarantee).
Measured consequence in the papers: RRSI reports large in-distribution gains
that would otherwise vanish OOD; Harness² reports open-world gains up to ~11.5
points on WorkBuddy-Bench with a single step. For our stack: use Harness²-style
steps for task execution and keep RRSI's floor + cost rule + prune at any layer
where we promote harness state across tasks. No mechanism duplication found: the
PoC's pieces (δ calibration, cost rule, B_t) do not exist in `harness2/optimizer`.
