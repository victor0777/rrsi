---
doc_id: poc-rrsi-06-limitations
title: Limitations and Follow-up Plan
status: final
updated: 2026-10-20
---

# Limitations and Follow-up Plan

## Limitations of this PoC

1. **Model-free by design.** The proposer is a scripted catalog, the critic runs
   only its deterministic layer, and the analyst is bypassed. The PoC verifies
   the loop's CONTRACTS, not the LLM behaviors that the paper's results depend on.
2. **Scoring model is a fixture.** Latent per-task probabilities and uniform
   mechanism bonuses; the holdout gain is true by construction. No claim about
   real-suite overfitting.
3. **Pinned randomness.** Candidate decisions on realizations of trial salts;
   r2's outcomes sit close to the band edge (documented in `04-POC-RESULTS §4`).
4. **No infra-failure paths.** `rrsi.evaluate` retry and `Run.reevaluate` were
   not exercised (no missing trials).
5. **Scope limits.** No Harness² change, no research_agent integration, no GLM
   run — all deliberately deferred.

## Follow-up plan (bounded, in order)

| Step | Deliverable | Cost |
|---|---|---|
| F1. GLM-backed dry round | one candidate round on a real harness slice (ai_papers reader pipeline or research_agent review triage), evolve/holdout split frozen, all calls via llm-proxy-runtime | one model session, ~10–50 evaluations |
| F2. δ calibration on the real suite | repeat base evaluation ×4 on the frozen baseline; record sd(null ΔS) | ~4 baseline evaluations |
| F3. Critic A/B | run the LLM critic layer over the same diffs; compare with the deterministic screen's verdicts | one model session |
| F4. Integration decision | adopt or defer `poc/03-INTEGRATION-DESIGN`; if adopt: vendor rrsi as package + one Domain adapter | engineering |
| F5. Harness² unification sketch | shared candidate/history schema between harness2 and rrsi core | paper exercise |

## Restorable state

Everything in this session is reproducible from the committed tree:
`poc/` + `docs/poc-rrsi/` only. The fixture loop re-creates its mini repo per
run (`init_repo` wipes `--output/repo`); rrsi core files are untouched
(`git status` on `rrsi/`, `domains/`, `tests/` clean; upstream tests pass).
