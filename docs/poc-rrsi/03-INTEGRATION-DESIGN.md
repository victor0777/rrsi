---
doc_id: poc-rrsi-03-integration
title: Research Agent Integration Design (RRSI -> existing runtimes)
status: final
updated: 2026-10-20
---

# Research Agent Integration Design

Scope: how RRSI's mechanisms map onto the existing stack — `research_agent`
(research execution / self-improvement target), `ai_papers` (paper-analysis
harness), `agents` / `agent-worker-runtime` (execution & isolation),
`llm-proxy-runtime` (GLM + frontier gateway), Collabo (`collaboration`: task
management, run & review history). **No runtime is modified by the PoC**; this
document is the design, and actual integration remains a separate decision.

## 1. Duplication audit — what NOT to build

| Existing capability | Owner | RRSI equivalent | Verdict |
|---|---|---|---|
| Model gateway, budget bindings, qualification contracts | `llm-proxy-runtime` (controller-task-budget-bindings, qualification-inheritance) | `rrsi.llm` (Vertex round-robin), `evaluate` cost | Reuse gateway; RRSI's cost ESTIMATE (ΔC in selection) plugs on top of token accounting, no new proxy code |
| Worktree / capsule isolation | `agents`, `agent-worker-runtime`; research_agent's `execution-capsule` qualification files | `rrsi.gitops` | Same primitive (branch+worktree per candidate). Adopt `gitops` (126 LOC) as-is into the runtime instead of writing a parallel one; do NOT fork both |
| Run & review history | Collabo (`collaboration/collab`, issues, requests) | `rrsi.history` JSONL | Different granularity: Collabo = tasks/reviews; History = per-EDIT evidence. Keep both: History is the evolution log, Collabo is the audit UI |
| Bounded retry / give-up guards | research_agent (`bounded_reasoning`, execution harness qualification) | `critic` rubric criterion 6 (unbounded work) | Overlapping concern; keep the critic SCREEN, do not add a second retry engine |
| Review gates (blind review, promotion acceptance) | research_agent (`cross_paper_review_*`, `promotion_acceptance`) | `selection.judge` | Complementary: research gates review content decisions; RRSI judges harness candidates. Do not merge |
| Experience reuse | research_agent memory engine / `research_state_memory_*` | L_t history conditioning | RRSI's L_t IS an experience mechanism, but only for harness edits; reuse where already present |

## 2. Integration design (minimal runtime)

The PoC showed the method core is importable as-is. The target shape:

```
research_agent/
  harness_evolution/            NEW, ~600 LOC total
    domain_adapter.py           maps research_agent/ai_papers harness -> rrsi.Domain
    candidate_isolation.py      thin wrapper: delegate to rrsi.gitops
    evo_cli.py                  driver commands (baseline / round / heldout / readjudicate)
```

- **Improvement target.** Start with ONE harness with measurable tasks:
  `ai_papers`' analysis/KG reading pipeline (per-paper criteria = rewards) or
  research_agent's review triage (admission decisions = rewards). Do not evolve
  both simultaneously (attribution noise, b_t annealing).
- **Task split.** evolve set vs holdout ids — research_agent already has
  dataset-freeze conventions (frozen cohorts, exposure manifests); reuse that
  discipline. RRSI's own `Domain.heldout_ids` slot exists for it.
- **Roles.** Proposer/critic/analyst = GLM via llm-proxy-runtime (replace rrsi's
  Vertex client with a ~40-line LiteLLM-compatible client). Keep rrsi's strict-JSON
  action protocol — the PoC confirmed it is the proposer's hard-contract anchor.
- **Candidate isolation.** Candidate branches off `evolve/<domain>`; runtime jobs
  keep their own capsule format; the PoC verified acceptance is fast-forward-only,
  so Collabo's run history always points at the adopted commit.
- **Budget/permission guards.** Map `Domain.guards` onto Collabo review gates:
  criteria that must not regress (e.g., evidence-authority violations, hallucination
  rate) go here, NOT into the shaped rule.

## 3. Reuse checklist if adopted

1. Vendor `rrsi/` as a package (Apache-2.0 + attribution) — no fork of files
   like `gitops.py` into multiple projects.
2. One `Domain` adapter per improvement target; evolve/holdout split declared
   upfront in the freeze document.
3. GLM client behind rrsi's `generate` signature (model string via LiteLLM).
4. Collabo milestone records decisions; rrsi History records measurements; the
   two are linked by (round, variant) ids.
5. Cost: llm-proxy-runtime token accounting feeds ΔC; β0/β1 set so a typical
   +1pp gain must pay for itself.

## 4. Explicit non-goals

- No second self-improvement runtime; research_agent remains the improvement
  executor, rrsi core becomes a library it calls.
- No modification of `harness2`/Harness² (separate comparison doc).
- No auto-adoption: the selection's ACCEPT is a recommendation; human/Collabo
  review remains the promotion gate for anything touching production prompts.
