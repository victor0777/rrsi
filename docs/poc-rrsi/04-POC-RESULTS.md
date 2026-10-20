---
doc_id: poc-rrsi-04-poc-results
title: PoC Implementation and Test Results (R0, model-free)
status: final
updated: 2026-10-20
---

# PoC Implementation and Test Results (R0, model-free)

Location: `poc/` (this repo). Run:

```bash
python3 -m poc.run_poc --output poc/runs/r0     # full loop, ~10 s
python3 -m pytest -q poc/tests/                 # 7 tests
```

No LLM, no network, no API keys. The **rrsi core is imported unmodified** and
used as the method core (selection, schedule, history, calibrate, components,
critic's deterministic layer, evaluate); the PoC supplies a scripted environment
instead of benchmarks. Nothing outside `poc/` is touched, including the working
tree's git state: candidates live on branches of a **throwaway mini git repo**
created under `--output`.

## 1. What was built

| File | Role |
|---|---|
| `poc/fixture_seed/` | The editable fixture harness: `harness.py` (control flow), `prompts/instructions.md` (prompt), `config.json` (config), `skills/retry.md` (skill) |
| `poc/poc_core.py` | Scoring model (per-task latent p, Bernoulli trials seeded by (job, task, trial)), diff-driven critic screen with fixture denylist, scripted candidate catalog, guards |
| `poc/run_poc.py` | Driver: mini repo init, baseline ×4, calibrate δ, 4 rounds (worktree per candidate, annealed b_t, selection, prune set), holdout comparison, re-adjudication, restore check |
| `poc/tests/test_poc.py` | 7 tests: determinism, feature effects, critic screens, budget bounce, proposer decline on B_t, selection cost rule, full e2e |

The trial seed derives from the evaluation job salt, so two evaluations of the
SAME harness differ exactly as an evaluation null — the quantity δ is estimated
from (`calibrate`, "repeated base evaluations"). Determinism per (job, task,
trial) makes the scripted run stable for tests.

## 2. Round plan and observed outcome

| Round | b_t | Candidates (intent) | Observed decision |
|---|---|---|---|
| r0 | 3 | `prompt_checklist` (real prompt mechanism, +0.10 expected), `leak_task_id` (task-id leak), `noop_claim` (comment-only) | checklist **ACCEPTED** (in-band, shaped +7.43 > 0); both leaks **critic-rejected before any evaluation** |
| r1 | 3 | `retry_control_flow` (bounded retry, helps flaky tasks), `leak_answer_cache` (per-task answer cache), `unbounded_loop` | retry **ACCEPTED** (ΔS +0.167 > δ, L1: +0.17 ≤ budget 6.77); answer cache **critic-rejected** ("branch on task identity"); unbounded **critic-rejected** ("no exit path") |
| r2 | 2 | `cheap_guard` (+0.09 in-band, +4% cost), `budget_guard` (strict guard: downgrade on long drafts, +70% cost), `mega_bundle` (3 edits), `memory_journal` (structural memory) | cheap_guard **ACCEPTED** (in-band shaped +5.77); budget_guard **REJECTED** (shaped −18.9); mega_bundle **over_budget** (bounced under b_t=2, no eval); memory_journal **REJECTED** (shaped −7.8, ν=1 visible) |
| r3 | 2 | `memory_journal_v2` (redraw of pruned component), `prune_retry` (prune edit whose target is healthy) | both **proposer-declined by the Pruner** (B_t = {memory, prompt}: memory yield ≤ 0, retry yield > 0) → H_4 = H_3 |

Numbers: baseline S = 0.4375 (C = 1000), δ = 0.1215 (z = 1.0, 4 base evals),
final S* = 0.8958 (trajectory S = 0.8125), holdout ΔS = +0.4375 (H_final vs H_0
over 12 holdout tasks, two salts each), restore OK (tree hashes match both ways).

Why z = 1.0 rather than the default 2.0: with a 24-task fixture suite the
sd(null ΔS) is ~0.12, so z = 2 would set the band above every scripted gain and
selection would degenerate into "everything is noise". This is a documented
fixture-engineering knob (`CONFIG.notes`), not a method change.

## 3. Completion-criteria checklist

| Requirement | Result |
|---|---|
| Small harness change candidates generated | yes — 9 catalog candidates across 4 rounds |
| Same-condition before/after comparison | yes — identical (job, task, trial) seeds; incumbent re-evaluated per round |
| Evaluation vs holdout separation | yes — 24 evolve tasks decide; 12 holdout tasks measured post-hoc, never in any acceptance |
| Critic behavior | yes — 4 defect candidates rejected pre-evaluation with rubric reasons |
| Pruner behavior | yes — B_t computed from measured history; both decline paths verified |
| Adopt/reject rationale recorded | yes — per-edit JSONL history with hypothesis, ΔS, ΔC, outcome, reason |
| Restore-able structure | yes — trajectory commits + harness tree hashes; `restore.json` ok |
| ≥ 1 candidate independently evaluated, adopted or rejected | yes — 3 adopted, 2 measured-rejected, 4 critic-rejected, 1 over-budget, 2 declined |

Upstream rrsi tests still pass unmodified (8 passed), confirming no drift.

## 4. Honest notes

- The scoring model makes "generalization" hold by construction (mechanisms add
  uniform bonuses); the positive holdout verifies the measurement MACHINERY, not
  that RRSI prevents overfitting on a real suite.
- Candidate outcomes depend on the pinned trial salts (deterministic); r2
  `cheap_guard`'s in-band acceptance is a shaped-rule decision on a noisy
  realization — exactly how rrsi treats the band, but a different salt could
  measure it differently.
- The over-budget row appears 3× in the raw history: rrsi's per-EDIT recording
  (one record per bundled edit). The summary deduplicates by variant.
