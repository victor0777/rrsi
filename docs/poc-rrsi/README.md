---
doc_id: poc-rrsi-index
title: RRSI Analysis & Research Agent Integration PoC (R0)
status: final
updated: 2026-10-20
---

# RRSI Analysis & Research Agent Integration PoC — R0

Goal: analyze Google RRSI (arXiv:2609.24972), verify its mechanisms, and assess
what its self-improvement algorithm contributes to the existing Research Agent /
ai_papers harness stack — without modifying any existing runtime.

## Documents

| Doc | Contents |
|---|---|
| [01-ARCHITECTURE.md](01-ARCHITECTURE.md) | Architecture, modules, round flow, worktree isolation, regularizers, paper-vs-code separation, license/dependencies |
| [02-CODE-TO-MECHANISM.md](02-CODE-TO-MECHANISM.md) | Paper symbol -> code line mapping with evidence status (upstream tests / PoC tests) |
| [03-INTEGRATION-DESIGN.md](03-INTEGRATION-DESIGN.md) | Duplication audit vs research_agent / ai_papers / agents / llm-proxy-runtime / Collabo; minimal integration design; non-goals |
| [04-POC-RESULTS.md](04-POC-RESULTS.md) | Model-free fixture PoC: implementation, per-round outcomes, completion-criteria checklist, honest notes |
| [05-HARNESS2-COMPARISON.md](05-HARNESS2-COMPARISON.md) | Mechanism comparison with Harness²; no duplication; reusable common interface |
| [06-LIMITATIONS.md](06-LIMITATIONS.md) | Limitations and bounded follow-up plan |
| [07-RESEARCH-AGENT-AI-PAPERS-PROPOSALS.md](07-RESEARCH-AGENT-AI-PAPERS-PROPOSALS.md) | Review of research_agent / ai_papers harness surfaces and assets; three integration proposals (audit-first → reader harness → review triage) |
| [08-INTEGRATION-PROPOSALS.md](08-INTEGRATION-PROPOSALS.md) | KB edition: review detail, sequencing rationale, cost estimates, decision points |
| [09-INTEGRATION-DESIGN-R1.md](09-INTEGRATION-DESIGN-R1.md) | **R1 design**: purpose redefinition with paper-direct vs project-added mapping, five optimization units (R1 = U1 Reader Prompt only), Evolve/Validation/Holdout split with leakage policy, multi-objective reader rewards + gold-validity check, 3-level E2E promotion, execution & safety contracts (state machine, gates, cost, holdout exhaustion, approval/rollback), RA composite reward |
| [10-INTEGRATION-DESIGN-R1.1.md](10-INTEGRATION-DESIGN-R1.1.md) | **R1.1 design (R1 full run NOT approved)**: expansion plan beyond the 15-paper PoC scale, paired + accumulating δ estimation with limits analysis, 4-element gold validation (rater consistency, evidence accuracy, regression root-cause, pre-registered hypothesis), batch-frozen holdout replacing per-promotion draws, explicit trial arithmetic with corrected cost estimate (75–150M) and ledger-enforced budget caps, 4-arm comparison design (A/B/C/D), sharpened promotion state semantics with enforced holdout-before-approval ordering, and vendored-code evidence linking for all 11 paper-direct features with the "core unmodified" vs "algorithm correctly applied" distinction |

## PoC quickstart

```bash
python3 -m poc.run_poc --output poc/runs/r0     # baseline -> calibrate -> 4 rounds -> holdout -> restore (~10 s)
python3 -m pytest -q poc/tests/                 # 7 tests, no network
```

## Headline result

The method core (2,964 LOC, Apache-2.0) is self-contained and reusable as-is;
the PoC exercises its full round structure unmodified against a model-free
fixture: 3 candidates adopted, 2 measured-rejected, 4 critic-rejected
pre-evaluation, 1 over-budget bounce, 2 proposer declines on prune logic, holdout
measurement and restore verified. The paper's empirical claims belong to its
benchmark adapters and stay separate. Actual Research Agent integration remains a
separate decision (see 03 §4 and 06).
