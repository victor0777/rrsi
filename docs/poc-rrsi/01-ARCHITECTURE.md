---
doc_id: poc-rrsi-01-architecture
title: RRSI Architecture Analysis
status: final
updated: 2026-10-20
---

# RRSI Architecture Analysis

Repository: `google-research/rrsi` — *Regularized Recursive Self-Improvement of
Agent Harnesses* (arXiv:2609.24972). Apache-2.0 (Google LLC). Core is 2,964
lines of pure Python with a single hard dependency (`anthropic[vertex]`); the
benchmark runners are optional extras.

## 1. What the system does

RRSI evolves an agent's **harness** — the prompts, control flow, tools, memory
and context management around a frozen policy model — against a fixed task
suite. Its central claim is that harness evolution overfits unless the
**search trajectory** is regularized, not the harness contents. Both the edit
space (what a candidate may contain) and the search constraints (how many
independent edits one candidate may bundle, what evidence blocks a redraw of a
falsified hypothesis) stay open; the regularizers act on movement through the
space.

## 2. Module map

```
rrsi/
  loop.py       Run: paths, frontier state, one round (Algorithm 1 + 2), resume
  domain.py     Domain interface: the ONLY thing RRSI needs from a benchmark
  driver.py     CLI: baseline / calibrate / round / heldout / readjudicate
  propose.py    The proposer agent P_reg (strict-JSON action protocol, done())
  analyst.py    Analyze(H_t, D): three-lens report over failure traces
  digester.py   Per-task digest dispatch (evidence anchors for prompts)
  critic.py     Critic(H_t, H'): deterministic precheck + LLM review, bounded repair
  evaluate.py   Evaluate(H', D, k): S_hat, C_hat; missing trials count 0
  selection.py  Algorithm 2: cost rule, noise-adjusted floor, argmax (pure fns)
  history.py    L_t, tried set, yield g_t, prune set B_t, stall flag, directives
  schedule.py   Annealed edit budget b_t (cosine, Eq. anneal)
  components.py Component vocabulary K, diff-driven tag normalization, novelty nu
  gitops.py     Worktree/branch plumbing for candidate isolation
  calibrate.py  Noise band delta: z * sd(null ΔS) from repeated base evals
  llm.py        Claude on Vertex, round-robin over projects, ephemeral caching
  config.py     RRSIConfig hyperparameters (paper Appendix)
```

## 3. Execution flow of one round (`Run.round`, loop.py:231)

```
1.  F_t  <- Analyze(H_t, D_evolve)         analyst over incumbent's worst/best traces
2.  b_t  <- schedule.edit_budget(t)        cosine-annealed, ||z_t||_0 <= b_t
3.  sigma_t, T_t, U_t, E_t, B_t            history.stall_flag / History / directives.json
4.  for v in m variants (each on its OWN worktree + branch off evolve/<domain>):
        C_t^(v) ~ propose.propose          agent edits harness IN PLACE, done(edits=[...])
        tags validated against the diff    components.normalize (re-tag on mismatch)
        Critic(H_t, C) with repair         critic.review; bounded repair rounds
        liveness smoke                     domain.smoke (NOT a selection rule)
5.  Evaluate(H', D_evolve, k)              in parallel over variants, resume-safe
6.  select.select_round                    floor + cost rule + guards + argmax
7.  fast-forward evolve/<domain>           H_{t+1} is always a commit; worktrees pruned
```

Resume-safety is structural: every phase writes before it mutates, a round that
crashed after evaluating variant A reuses A's `eval.json`, and `history.has(t,
variant)` makes re-run idempotent. `Run.readjudicate` re-runs Algorithm 2 on
stored measurements after a delta change with **zero new evaluations**;
`Run.reevaluate` re-measures only infra-corrupted candidates.

## 4. Candidate generation and verification (worktrees)

`domains/<name>` evolves on branch `evolve/<name>`. Each candidate of round t is
drafted in its own worktree on branch `<domain>/r<t><variant>` created from the
incumbent (gitops.py:80): variants cannot see each other's edits and can be
evaluated concurrently. Acceptance is `git merge-base --is-ancestor` +
`update-ref` (a strict fast-forward), so the incumbent is always a commit and
restore is `update-ref` back to any trajectory entry. The frontier records the
**harness subtree hash** (`rev-parse <commit>:<harness path>`), so commits
outside the harness never count as a harness change (loop.py:235 checks this
explicitly at round entry).

## 5. The six regularizers, traced to code

| Regularizer | Side | Implementation |
|---|---|---|
| Annealed edit budget b_t | proposal | `schedule.edit_budget` (cosine b_max→b_min), enforced in `propose.done()`: over-budget submissions are bounced, never accepted |
| History-conditioned proposer | proposal | `propose.propose` receives L_t rendered by `History.render`: "a falsified hypothesis is not redrawn"; measured outcomes dominate, a wall of aborts is truncated |
| Reserved exploration slots | proposal | `stall_flag` + `exploration`: when stalled and U_t ≠ ∅, the last m_draft variants MUST edit an untried component, judged by the DIFF (propose.done + loop.py:524) |
| Critic leakage screen | selection-side pre-check | `critic.precheck` (generic denylist + domain regexes) + LLM review with a 6-criterion rubric (leakage, degenerate, grader gaming, undeclared bundling, runtime-memory leakage, unbounded work); bounded repair |
| Noise-adjusted floor + cost rule | selection | `selection.judge`: admissible iff S' ≥ S* − δ and c (L1 branch for gains above the band; shaped w_s ΔS − w_c ΔC + w_n ν > 0 inside the band) |
| Prune set B_t | selection-side memory | `History.prune_set`: components whose most recent measured gain within window n_prune is ≤ 0 (stale ⇒ −inf ⇒ pruned) are handed to the proposer with the accepted machinery to remove |

## 6. Normalization, overfitting control, noise, cost

- **Tag normalization.** A declared component survives only if the diff carries
  evidence (`has_evidence`); otherwise the edit is re-tagged from what the diff
  reads as. An unverified tag would corrupt T_t, U_t and the novelty term, so
  the PoC treats this as a hard gate, matching loop.py's behavior.
- **Overfitting control.** Three layers: the critic's pre-evaluation screen;
  the domain denylist (grader paths, task ids); K_str novelty counting over
  `client_tool, skill, memory, subagent` so selection can see structural
  exploration. Non-compensatory domain criteria (`Domain.guards`) run AFTER the
  floor and cost rule.
- **Evaluation noise.** δ is either fixed per instance (0.017 / 0.004 / 0.020 in
  `rrsi.json`s) or estimated by `calibrate`: with R ≥ 2 base evaluations the
  null difference is observed directly; otherwise bootstrap over trials within
  each task, δ = z·sd(null ΔS), z default 2.0.
- **Cost control.** Missing trials contribute r = 0 under the FULL denominator
  (a candidate cannot look better by destroying trials it finds hard). ΔC is
  RELATIVE; a gaining candidate needs ΔC ≤ β0 + β1·ΔS — a true gain pays for
  tokens, tokens without gain are rejected by the shaped branch.

## 7. Paper claims vs. actual implementation

What IS faithfully implemented (and unit-tested upstream in `tests/test_core.py`,
which needs no API): the estimator and weighting, anneal equation, bootstrap and
repeated-eval calibration, both cost-rule branches, floor/argmax/S*, prune set,
tag normalization, stall/exploration logic, worktree plumbing.

What the code asserts but upstream tests do NOT cover: `Domain.guards`
(engineering only), `critic.review`'s LLM layer (needs Vertex), the analyst/digester
LLM loop, and the three benchmark adapters under `domains/` (coding uses harbor
in its own venv; workspace/eng use `RRSI_AGENT_PYTHON`). The paper's headline
results are produced by those adapters plus Claude Opus 4.8 as all three search
roles; none of that is part of the method core. When reusing RRSI, the reusable
part is the loop + regularizers; the environment adapters are per-instance work.

## 8. License and dependencies

- `LICENSE`: Apache-2.0 (Google LLC); `third_party/archipelago` and
  `third_party/harbor_terminus2`: Apache-2.0.
- Runtime deps: `anthropic[vertex]` only. `agentic` extra (fastmcp, litellm,
  pydantic, pymupdf, ...) belongs to the benchmark runners. No transitive
  GPU/network requirements in the core. Reuse is license-clean with attribution.
