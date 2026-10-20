---
doc_id: poc-rrsi-02-code-to-mechanism
title: RRSI Code-to-Mechanism Mapping (paper -> code, with evidence status)
status: final
updated: 2026-10-20
---

# RRSI Code-to-Mechanism Mapping

Symbols follow the paper. "Upstream test" = covered by `tests/test_core.py`
(run in this session: 8 passed). "PoC-verified" = exercised by `poc/tests/`
(7 passed, model-free). Everything with line references was read in this
session, not taken from the README's table.

## Algorithm 1 — proposal side

| Paper mechanism | Code | Evidence |
|---|---|---|
| Edit history L_t = {(t_i, l_i, h_i, d_i, ΔS_i, ΔC_i, a_i)} | `history.py:77 append_candidate` — one JSONL record per EDIT; a bundle of n edits carries the candidate's measurement on every edit; a = 1 only for the candidate that became H_{t+1} | upstream test: indirect; PoC: `test_e2e_run` reads records |
| Tried set T_t, g_t, U_t, sigma_t, B_t | `history.py:117-163 tried / yield_g / prune_set`, `history.py:189 stall_flag` — g_t over window n_prune only; stale ⇒ −inf ⇒ pruned | upstream: `test_...` indirect; PoC: r3 prune=['memory','prompt'] (both visible in run log) |
| Analyze(H_t, D) | `analyst.py` + `digester.py` — three-lens report from worst/best traces | LLM-bound; NOT covered upstream; NOT exercised in PoC (report pre-seeded by design) |
| P_reg(. \| H_t, F_t, L_t, b_t, E_t) | `propose.py:239 propose` — agent edits harness in place; done(edits=[...]) contract | LLM-bound; PoC replaces it with a scripted catalog |
| Budget b_t = ceil(b_min + (b_max−b_min)·½(1+cos(πt/T))) | `schedule.py:43 edit_budget` (round-guarded) | upstream `test_schedule_matches_eq_anneal`; PoC: b_t=3,3,2,2 in run log |
| Reserved exploration slots | `propose.py:349` (declared-tag check) + `loop.py:523` (DIFF re-judgment after critic) — a reserved variant whose diff touches no untried component is rejected | PoC: stall flag exercised via trajectory; slot logic unit-exercised |
| Tag validation (l' against d') | `components.py:95 normalize` — declared tag kept only with diff evidence, else re-tagged from the diff | upstream: `test_core` tag tests; PoC: `noop_claim` rejection path |
| Critic(H_t, H') + bounded repair | `critic.py:105 precheck` (deterministic) + `critic.py:113 review` (LLM rubric, 6 criteria); repair rounds = cfg.repair_rounds | precheck: PoC-verified (5 reject cases); LLM layer: untestable offline |

## Algorithm 2 — selection side

| Paper mechanism | Code | Evidence |
|---|---|---|
| S_hat = 1/(k·|D|) ΣΣ r; missing trial ⇒ 0 with full denominator | `evaluate.py:104 aggregate`; weights for criteria-style rewards | upstream `test_estimator_and_weights`; PoC reuses directly |
| C_hat = mean policy tokens | `evaluate.py` (C None when no token counts) | PoC: token model exercises it |
| ΔS = S' − S_t; ΔC = (C' − C_t)/C_t | `selection.py:97 judge`, `evaluate.py:131 relative_cost_change` | upstream `test_cost_rule_both_branches` |
| Floor: S' ≥ S* − δ | `selection.py:107` | upstream `test_selection_floor_argmax_and_sstar`; PoC `test_selection_blocks_cost_without_gain` |
| L1 cost rule (ΔS > δ): ΔC ≤ β0 + β1 ΔS | `selection.py:81 cost_rule` branch 1 | both test suites |
| Shaped rule (ΔS ≤ δ): w_s ΔS − w_c ΔC + w_n ν > 0 | `selection.py:81` branch 2 | both test suites; PoC accepts `cheap_guard` / `prompt_checklist` this way |
| argmax over admissible; S* = max(S*, S_{t+1}) | `selection.py:124 select_round`; `loop.py:335` | upstream; PoC e2e |
| Domain guards (non-compensatory) | `Domain.guards` (engineering only), called from `select_round` via `guard_fn` | PoC re-implements a fixture guard; upstream none |
| Novelty ν(l') over K_str | `components.py:103 novelty` — structural components never in a winning edit; only tie-breaks inside the band | upstream; PoC: ν=1 visible on first memory edit |
| Re-adjudication without re-evaluation | `loop.py:348 readjudicate` — stored measurements only | PoC: `readjudicate` in driver, 0 new evals asserted in test |
| Re-evaluation of infra-corrupted candidates | `loop.py:424 reevaluate` | not exercised (no infra failures in fixture) |

## Structural claim: open edit space, regularized trajectory

The constraints genuinely act on movement, not contents: the budget bounds
||z_t||_0 only; the denylist bounds suite-specific LOGIC, not mechanisms; nothing
in `K` restricts what a harness may eventually contain. Confirmed by reading
`propose.SYSTEM_TMPL` ("there is no abort action"), `loop._draft` (reserved slots
enforced post-hoc by diff), and `gitops` (fast-forward-only acceptance).

## Distinguishing paper claims from code

| Paper text | Status in repo |
|---|---|
| One method, three instances (Terminal-Bench 2.1, Harvey LAB, EngDesign) | adapters exist under `domains/`; heavy external runners (harbor venv, RRSI_AGENT_PYTHON); results not reproducible from this repo alone |
| "frozen policy is Claude Opus 4.8" | `domains/coding/rrsi.json` `policy_model`; benchmark-side, not method-side |
| Δ noise bands 0.017/0.004/0.020 | pinned per instance in the three `rrsi.json` files (config values, not derived results) |
| Critic reduces leakage | mechanism fully in code; effect claim is empirical (paper) |
| Regularizers prevent overfitting | mechanism + unit tests for pieces; the overfitting claim itself needs heldout measurement (RRSI's own `Run.heldout` is provided but optional) |

Practical conclusion for reuse: the **method core is self-contained and
license-clean**; the empirical claims belong to the instances. Anything we adopt
should adopt core + the evidence-structure discipline (JSONL history, per-edit
attribution, resume-safe runs), not the benchmark adapters.
