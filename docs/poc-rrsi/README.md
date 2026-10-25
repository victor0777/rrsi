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
| [11-R0-EXECUTION-REPORT.md](11-R0-EXECUTION-REPORT.md) | **R0 execution report**: R0-a PASS (23 tests: core unmodified, 11 call paths, U1 scope isolation, state-machine reject paths, holdout denylist, ledger fail-closed — 1 real defect found and fixed); R0-b NOT EXECUTED (13/13 gold sources missing, pre-start token check conflicts with the 3M cap); pre-registered statistical design (paper-level cluster bootstrap, paired/Welch conditions, D-arm false-accept criteria); recommendation **HOLD** with three unblock conditions |
| [12-BUDGET-POLICY-CHANGE.md](12-BUDGET-POLICY-CHANGE.md) | **Budget policy change (R0-b calibration)**: token hard ceiling abolished — tokens become a metering/optimization metric, ledger retained with only token blocking disabled, fail-closed kept on wall-clock/calls/GPU-hours (GPU-h summed across GPUs, separate from wall-clock), 0 auto-retries, concurrency 1, paid-API cost cap mandatory; R0-b still NOT EXECUTED (13/13 gold sources missing — data blocker, not a budget one); conditional budget formulas pre-registered for R1 |
| [13-R0-B1-CALIBRATION-REPORT.md](13-R0-B1-CALIBRATION-REPORT.md) | **R0-b1 calibration report (executed)**: ai_papers original project located with GT 15/15 present (sources were reset → re-acquired 1 Evolve paper ImagiDrive 2508.11428v2 via governed capture + canonical extraction); deterministic dataset manifest (`57d1a501…`); Reader Baseline 1-trial run: 29/50 model calls, 21m51s wall-clock, GPU-h ≤ 0.364 (upper-bound attribution registered), Reader Note quality coverage 1.0 / high-risk 0; token metering gap + Evolve/denylist split defect found and registered; verdict **GO** with 2 preconditions (telemetry binding, GPU-h policy re-budget) |
| [14-R0-B2-REPEAT-CALIBRATION-REPORT.md](14-R0-B2-REPEAT-CALIBRATION-REPORT.md) | **R0-b2 repeat calibration report (executed)**: token telemetry fixed (per-call usage collected, ledger↔telemetry fail-closed audit PASS, 404 root cause moved to pre-network preflight); split conflict resolved and frozen (`849d1431…`: Evolve = 2 denylist-safe e2e papers, Validation/Holdout empty, 13 blocked); GPU-h measured/upper-bound fields separated; baseline ×3 executed (25 calls each, ~101k tokens/trial ≈ 1/8 of R1.1 estimate); quality ceiling effect confirmed, fine-grained **δ ≈ 0.19 (z=2, n=4, provisional)**; verdict **GO** for RRSI Evolution PoC with δ-uncertainty reduction first |
| [15-RESEARCH-BENCHMARKS-INTEGRATION-DESIGN.md](15-RESEARCH-BENCHMARKS-INTEGRATION-DESIGN.md) | **RRSI × research_benchmarks integration design (static review only)**: reuse-verified existing lane (external QA intake → consumer → official QASPER F1 + separate evidence F1 — no duplication); evaluation structure with per-metric ownership (Reader Gold/QASPER/Evidence/Cost/Pipeline Regression); BenchmarkScore→Reward minimal interface; contamination 0 (dev+final); 5-item minimal code change list; separate Workstream ordering after R0-b2; verdict **GO** |
| [16-R0B2-AUDIT-QASPER-CALIBRATION-REPORT.md](16-R0B2-AUDIT-QASPER-CALIBRATION-REPORT.md) | **R0-b2 audit + QASPER calibration report (A–E, executed)**: 75-vs-84 call difference fully explained (9 = aborted invocations), GPU-h upper-bound re-scoped 0.363→0.425 with registered scope rule; QASPER lane wired with minimal record-extraction glue (contracts unchanged); baseline calibration on 2 papers/10 cases: **Answer F1 0.50, Evidence F1 0.0** (abstention-bias dominated); evaluation-stage variability 0 (byte-identical re-scoring) vs generation-stage variance from R0-b2; QASPER usable as secondary reward axis only; Evolution verdict **HOLD** (δ uncertainty, evidence-integrity, unfrozen split — no fundamental design defect, not STOP) |
| [17-QASPER-FAILURE-ATTRIBUTION-REPORT.md](17-QASPER-FAILURE-ATTRIBUTION-REPORT.md) | **QASPER failure attribution (analysis-only, 0 model calls)**: per-question trace table over the 10 packets — all 4 false-unanswerable cases have grounding text absent from the abstract (**protocol mismatch, not model/implementation defect**); abstention causes: input-condition grounding absence 6 + true-unanswerable 2; **Evidence F1 = 0 is structural** (gold evidence grounded in fulltext/figures vs abstract-only input — impossible under this protocol); empty-annotation→Unanswerable mapping distortion recorded as SCORER_MISMATCH; external-QA lane bypasses Reader Note by design (Gold↔QASPER correlation requires a separate protocol); Evolution verdict **HOLD maintained** |

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
