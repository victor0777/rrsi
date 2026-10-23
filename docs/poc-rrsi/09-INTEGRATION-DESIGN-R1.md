---
doc_id: poc-rrsi-09-design-r1
title: RRSI Integration Design R1 (design review only — no runs)
status: proposal
updated: 2026-10-20
supersedes: poc-rrsi-07-proposals (C -> A -> B direction retained)
---

# RRSI Integration Design R1

**Scope statement.** This document is a design review only. No model calls, no
pipeline execution, no operational configuration change, no automatic promotion.
Every statement about existing code/assets below was verified by reading the
referenced files; every cost figure is an ESTIMATE to be replaced by ledger
data at R0.

---

## 1. RRSI 적용 목적 재정의

**재정의.** RRSI는 프롬프트 자동 개선기가 아니라, frozen pipeline(fixed model
weights, fixed extraction/extraction-bundle layer, fixed graders)을 둘러싼
**실험적 최적화 계층**이다. 하네스스 후보를 과학 실험의 대상으로 취급한다:
사전 등록된(frozen) 데이터 분할 위에서, 측정된 효과(ΔS)가 측정된 노이즈(δ)와
측정된 비용(ΔC)을 넘을 때만 승격을 권고한다. 계층은 권고만 하며, 승격은
State Machine + Regression Gate + Human Approval을 통과해야 한다.

**원 논문 알고리즘 ↔ 본 설계 대응표.**

| 원 논문 (arXiv:2609.24972) | 본 설계 대응 | 지원 주체 |
|---|---|---|
| Evaluate(H', D, k) — S_hat, C_hat, missing trial = 0 under full denominator | Reader Note trial = 1 paper run; C_hat = tokens/paper | **paper-direct** (`poc/04` 검증, `rrsi/evaluate.py`) |
| δ = z·sd(null ΔS) from repeated base evaluations | Baseline ×4 반복 → δ 산출 (R0 산출물) | **paper-direct** (`rrsi/calibrate.py`) |
| L1 cost rule ΔC ≤ β0 + β1·ΔS (gains) / shaped rule w_sΔS − w_cΔC + w_nν > 0 (in-band) | 그대로 적용. 다만 ΔC의 정의 확장(§5 비용) | **paper-direct** (`rrsi/selection.py`) |
| Critic(H_t, H') 사전 차단 + bounded repair | Denylist(논문 id, GT 항목 id, grader 경로) + LLM rubric | **paper-direct** (`rrsi/critic.py`) |
| Edit history L_t — falsified hypothesis 미재도화 | Reader 하네스스 변경 1건 = 1 edit record(JSONL) | **paper-direct** (`rrsi/history.py`) |
| Annealed budget b_t (cosine) | R1에서는 b_t = 1 고정(단일 변경 단위, §2). 어닝은 R2 도입 | **paper-direct, hyperparameter 축소** |
| Prune set B_t | Reader 하네스스의 기계(추가 모듈·반복 정책) 제거 권고 | **paper-direct** |
| git worktree 후보 격리, fast-forward 승격, 복원 | 후보 branch off `evolve/reader`; 승격 = ff; rollback = `update-ref` | **paper-direct** (`rrsi/gitops.py`) |
| Re-adjudication without re-evaluation | δ 개정 시 저장 측정값으로 재판정 (PoC 검증) | **paper-direct** |
| Heldout slot `Domain.heldout_ids` | Final Holdout (§3) | **paper-direct** (업stream 미사용 slot) |
| **(paper 미지원 — 프로젝트 독자 추가)** | | |
| 단일 목적 보상 | 다목적 보상 합성: Coverage·Faithfulness·Understanding·Evidence Integrity·Cost (§3) | **project-added** |
| C = policy tokens 만 | 비용 = tokens + GPU time + latency 3축 (§5) | **project-added** |
| suite-level 승격만 | 3-수준 End-to-End 승격 조건 (§4) | **project-added** |
| gold 충족 = 개선 가정 | gold 충족 ↔ 실제 이해도 별도 검증 (§3.4) | **project-added** |
| (human gate 미정의) | State Machine + Human Approval + Holdout 소진 정책 (§5) | **project-added** |
| (보상 미정의) | research_agent 복합 보상 정의 (§6) | **project-added** |

**판단 기준.** paper-direct 부분은 원 코드를 vendoring하여 수정 없이 사용한다.
project-added 부분은 `rrsi.Domain`/`selection` 인터페이스 안에서 정의하며
코어를 변경하지 않는다.

## 2. 최적화 대상 분리

5개 독립 최적화 단위. 각 단위는 자체 evolve branch(`evolve/<unit>`)·자체 δ·
자체 보상 정의를 갖는다. 단위 간 동시 변경은 attribution을 깨뜨리므로 금지.

| 단위 | 하네스스 상태 (편집 표면) | 고정(frozen) | 측정 task | 보상 |
|---|---|---|---|---|
| U1 Reader Prompt | `paper/study/reader_note/prompts.py`, section_plan 프롬프트 | context_planning, multi_pass, KG policy, extraction layer | evolve 논문 × k=2 | §3.3 다목적 |
| U2 Context Planning | `context_planning/` 설정·정책 | reader prompts 고정 | 동일 | 동일 |
| U3 Multi-pass Policy | `multi_pass/` pass 구성·반복 한도 | reader prompts, context planning | 동일 + loop-stability | 동일 |
| U4 Analysis/KG Policy | `analysis_kg/` candidate policy v2b 설정·임계값 | U1–U3 | analysis-kg-quality gold | KG 후보 기준 (별도 정의) |
| U5 RA Review/Triage Policy | `research_agent/` 트리아지 프롬프트, admission 임계값, memory 정책 | ai_papers 전체 | frozen 리뷰 코호트 | §6 복합 보상 |

**R1 제약.** 첫 PoC는 U1만 편집. U2–U5는 파일 단위 frozen 선언(freeze 문서에
glob 목록 명시) + 두 정책으로 강제: (a) candidate diff가 frozen glob를 건드리면
critic 차단, (b) component tag가 `prompt` 아닌 edit은 over-scope 기각.
승격 후에도 U2–U5 하네스스 트리 해시가 baseline과 동일함을 검증(frontier가
기록하는 subtree hash로 자동 검증 — `loop.py:235` 패턴).

## 3. 평가 체계 보완

### 3.1 데이터 분할 (15 gold papers, 10 agent-memory + 5 e2e 기준)

| 분할 | 논문 수 | 용도 | 접근 규칙 |
|---|---|---|---|
| Evolve | 8 (agent-memory 6, e2e 2) | 매 라운드 전체 평가·측정 | proposer/analyst가 본다 (eval 출력만) |
| Validation | 4 (agent-memory 3, e2e 1) | selection 가중치·GT 타당성 상관 검증 (§3.4) | 라운드 중 측정 허용, argmax 조건 미사용 |
| Final Holdout | 3 (agent-memory 2, e2e 1) + quarantine 1 | 승격 직후 1회 소진 측정 | **승격 전 임의 접근 금지** |

분할 축 설계: R1은 agent-memory 중심 evolve → e2e 축이 자연 holdout.
R2에서 축을 뒤집어(cross-over) 일반화 재확인. 코호트 축 = suite-level OOD proxy.

### 3.2 누출 방지 정책

1. **물리 분리**: GT 파일을 3 디렉터리로 분리(`evolve/` `validation/` `holdout/`); quarantine은 holdout 디렉터에 이동·현황 기록.
2. **ID denylist**: holdout 논문 제목·arxiv id·workflow_id를 critic denylist에 등록 — diff에 등장 시 사전 차단.
3. **proposer 격리**: proposer는 evolve eval 출력(실패 모드·per-task digest)만 본다. GT 파일·holdout eval·validation eval 출력은 프롬프트에 주입 금지.
4. **유래 제한**: holdout eval로부터 파생된 candidate(사후 조정)는 승격 무효 — history에 holdout 소식 이전 타임스탬프 검증.
5. **재분할 금지**: 분할은 freeze 문서에 해시 등록; 승격 주기 내 재분할 시 전체 진행 무효.

### 3.3 Reader Note 품질 다목적 보상

GT 항목은 항목당 6개(논문당)이며 category는 key_concept/mechanism/artifact/claim_evidence 등.

| 축 | 정의 | 측정 근거(기존 자산) |
|---|---|---|
| Coverage | section/full-source coverage 만족 | `reader-note-coverage.schema.json`, `full_source_coverage.py` |
| Faithfulness | citation 무결성: `source_sentence_ids` 유효성·인용 문장 존재 | GT `source_sentence_ids`, `reader-note-provenance-quality-report.schema.json` |
| Understanding | `must_explain`/`expected_reader_understanding` 충족률 | gold GT 항목 |
| Evidence Integrity | 증거-주장 대응 무결성(무결 증거, hallucinated evidence 없음) | `analysis-kg-evidence.schema.json`, provenance report |
| Cost | tokens + GPU time + latency (하락이 보상) | `call_budget.py` ledger + runner 측정 |

합성: `S = w_cov·Coverage + w_faith·Faithfulness + w_und·Understanding + w_int·Evidence Integrity − w_cost·Cost_norm`,
시작 가중치 균등(각 0.25, Cost 0.25). **비보상성 원칙**: Faithfulness·Evidence Integrity는
가중 합으로 상쇄 불가 — 이 두 축은 Regression Gate(§5)로도 별도 게이트.
가중치 조정은 Validation에서 1회 허용(라운드 중 조정 금지).

### 3.4 gold 충족 ↔ 실제 이해도 별도 검증

gold가 GT 저자의 기대 독해를 코드화한 것이라는 가정은 검증 대상이다.
**검증 설계**: Validation 논문 4편에 (a) 다목적 점수, (b) 외부 QA 점수
(QASPER 기반 paper-level 질의응답 정확도, §4 자산 재사용)를 동시 측정.
승격 조건: (a)–(b) 스피어만 상관이 양(≥0)이고, 후보가 gold 점수를 올리면서
(b)를 유지·상승시켜야 함. gold 상승 + QA 하락 조합은 "GT 과적합"으로 승격
차단 — 이 조합은 Regression Gate 위반이다.

## 4. End-to-End 평가 (3-수준 승격 조건)

| 수준 | 평가 | 측정 | 승격 조건 |
|---|---|---|---|
| L1 Component | Reader Note 품질 (§3.3) | evolve ×k, validation ×1, holdout ×1(승격 시) | L1 다목적 ΔS > δ **그리고** §3.4 통과 |
| L2 Pipeline | Analysis/KG/KCP 하류 영향 | analysis-kg-quality gold(고정 논문) 재측정: 후보 정밀도, KCP draft-gate 수용률, `candidate_quality.py` 지표 | **무하락**(non-compensatory) — 하락 시 승격 차단 |
| L3 Downstream | Research Agent 하류 소비 | (i) external QA: QASPER 기반 논문 QA 정확도 (ii) research_agent 리뷰/답변 소비 산출의 frozen 기준 합치 | L3는 신뢰구간 하락 미감지 수준; 승격 권고의 3차 조건 |

**재사용 검토 — 실제 자산 기준:**
- **QASPER**: `paper/study/reader_note/external_qa_producer.py`가 benchmark-native
  QASPER case → 승인된 model request 변환기(`run_id="qasper-dev-real-inference-r0"`)
  및 `external_qa_evidence.py` 존재. L3 QA 평가는 이 경로를 재사용(신규 파이프라인 아님).
- **Unified Evidence Schema**: `schemas/analysis-kg/analysis-kg-evidence.schema.json`
  및 operational evidence 스키마 존재 → Evidence Integrity 축·L2 측정의 공통 형식으로 사용.
- **교차 프로젝트 데이터셋**: `schemas/jev-shared-dataset/r0.1-candidate.schema.json`
  (shared-dataset 후보) — L3에서 ai_papers 산출을 research_agent가 소비할 때의
  패킷 형식 후보로 검토. 미확정 요소로 R1 승격 조건에는 넣지 않는다.

## 5. RRSI 실행 및 안전 규약

**5.1 Baseline 반복·분산 측정.** R0: frozen U1 baseline을 동일 데이터로 ×4 반복
(job salt만 다름). δ = z·sd(null ΔS), z=2.0 시작(§4의 L1 분산은 실측으로 대체).
δ는 freeze 문서에 등록; δ 개정 시 저장 측정값으로 re-adjudicate(새 평가 0).

**5.2 단일 변경 단위·이력.** 1 candidate = 1–b_t개 독립 edit(각 edit =
component·hypothesis·diff·trigger_condition·predicted_affected·retroactive_check).
기록: `history.jsonl` per-edit + `decisions.json` per-round + diff.patch.
b_t=1 (R1). 1 edit = 1 commit (worktree, 단일 파일 스코프 검증 포함).

**5.3 Candidate State Machine.**

```
DRAFTED -> CRITIC_SCREEN -(pass)-> SMOKE -(pass)-> EVALUATED
        -(floor+cost+guard pass)-> ADMISSIBLE -> argmax -> PROMOTED
        -> HOLDOUT_DRAWN -> REPORTED -> (Human Approval) -> CANONICAL
                  |                                   \
                  +-(fail)-> REJECTED / OVER_BUDGET / UNSAFE   +-> WITHDRAWN
EVALUATED -> REVERTED (update-ref rollback, 언제든)
```

전이는 사유 필수(reason); REJECTED/REVERTED도 history에 측정값·사유와 함께 영구 기록.
RESUMED 상태: eval.json 존재 시 재평가 없이 동일 상태 복귀 (PoC 검증).

**5.4 Critic denylist·누출 방지.** 정적: holdout/evolve 논문 id·제목, GT 항목 id,
grader 경로, credential 패턴. 동적(LLM rubric): rrsi 6-criterion + "GT 항목 문구
복사" 검사. 차단 시 사유를 proposer에게 반환, repair ≤5회.

**5.5 근거 무결성·Regression Gate.** Gate는 비보상성 축: Faithfulness, Evidence
Integrity, L2 파이프라인 무하락, valid-output rate. 하나라도 위반 → 승격 불가
(가중 합이 좋아도). Gate 측정은 승격 후보 argmax 직전 1회, holdout 소진 직후 재확인 1회.

**5.6 비용 측정.** tokens: `call_budget` ledger(기존 fail-closed 예약 시스템).
GPU time: runner가 기록하는 model-call 총 소요(호스트측 wall time과, local GLM
bounded run 시 provider측 GPU-sec). latency: trial 종단 p50/p95. 세 축 모두
per-trial 기록; ΔC는 tokens 축 우선, GPU·latency는 Gate 참고치(R1).

**5.7 Holdout 재사용·소진.** 승격 1건당 holdout draw 1회(논문 4편 × k=2).
소진 후 draw의 논문 4편은 향후 1개월 쿼터 동안 holdout 자격 상실(pool 재분할),
쿼터당 소진 상한 3회. 상한 초과 시 승격은 Validation-only 권고로 강등 기록.

**5.8 Human Approval·Rollback.** 승격 권고(PROMOTED→REPORTED)는 Collabo milestone
review 필수. Approval 전에도 branch는 승격 커밋에 있지만 CANONICAL 승격은
milestone accept 이후. Rollback: (a) Approval 전 — `update-ref` 되돌림 + smoke
1회; (b) Approval 후(제품 영향) — 동일 절차 + 사후 리뷰 이력 남김. Rollback 자체는
자동 무효화가 아니며, 재진행 시 신규 라운드로 간주.

## 6. Research Agent 보상 설계 (U5, 별도 정의)

인간 합치율 단독 보상은 불완전 — 리뷰어 선호 과적합·회귀 감지 불가. 복합 보상:

| 축 | 정의 | 측정 |
|---|---|---|
| Evidence Quality | 결정 근거의 인용 유효성·KG 증거 대응 | `analysis-kg-evidence` 스키마 대응률 |
| Abstention | 정확한 거절(증거 부족 시), 과잉 거절 감점 | frozen 코호트 라벨, `abstention` 계약 |
| Contradiction Handling | 논문 간/증거 간 모순 탐지·처리 정확도 | frozen 코호트 모순 라벨 |
| Research Decision Quality | 최종 결정 vs 수용된 결과(acceptance records) | `coordination/milestones` acceptances |

`S = w_e·EQ + w_a·Abstention + w_c·Contradiction + w_d·Decision Quality` — 균등 시작.
**Novelty·Hypothesis Generation은 보상에서 제외하고 독립 평가 트랙으로 분리**:
제안된 가설은 별도 평가 기준(정합성, 검증 가능성)으로 측정되며, 검증되지 않은
창의적 주장은 보상 0 상한 — 가중 합 기여도 0, 과잉 주장 발생률 상승은 Guard 위반.

## 7. 구현 범위·산출물

**7.1 재사용 가능성 분석 (실측 근거).**

| 필요 기능 | 기존 소유자 (확인 경로) | 신규 필요량 |
|---|---|---|
| Model 호출·리실리언스 | `llm/llm.py` + `raw_client.resilient_chat_completion` + `resilience.py` | 0 (rrsi `generate`는 이 시그니처 뒤 40줄 어댑터) |
| Call budget | `call_budget.py` (fail-closed ledger 예약) | 0 — ledger 읽기 소비자만 |
| Evaluation harness | `docs/eval/*` gold GT·quarantine·`reader_note/quality.py` | split 재배치 + 합성 스코어러 (~150줄) |
| External QA | `external_qa_producer.py` (QASPER-native) | 0 — L3 재사용 |
| Evidence schema | `analysis-kg-evidence.schema.json` | 0 |
| 격리·복원 | `rrsi/gitops.py` (126줄, vendored) | 0 |
| Run history | rrsi `history.py` JSONL + Collabo milestones | 링크 레코드 (~50줄) |
| Retry 엔진 | 기존 `resilience.py` | 0 — rrsi critic repair만 유지 |

**7.2 통합 아키텍처.**

```
ai_papers/
  harness_evolution/                    NEW ~600 LOC
    domain_reader.py        rrsi.Domain 구현: run=reader workflow 1 paper, score=GT 채점
    rewards.py              다목적 스코어러 + 비보상성 Gate
    state_machine.py        §5.3 전이 테이블
    evo_cli.py              baseline / calibrate / round / heldout / readjudicate / rollback
    (rrsi/ = vendored package, paper-direct, 수정 없음)
evolve/reader  <- 후보 branch, 승격 = ff, Collabo = approval gate
```

**7.3 Reward·Guard 정의.** §3.3·§5.5 참조. Guard 목록(비보상성): Faithfulness
무결, Evidence Integrity, L2 무하락, valid-output rate, 과잉 주장 발생률 상한(U5).

**7.4 Dataset Split 계획.** §3.1. freeze 문서에 (논문 id 목록, 디렉터 이동, 해시, δ) 등록.

**7.5 R0 Baseline → R1 Reader PoC 실행 계획.**

| 단계 | 산출 | 소요 |
|---|---|---|
| R0-a | GT 3분할 재배치 + freeze 문서 | 0.5일 |
| R0-b | Baseline ×4 실행, δ 산출 | 0.5일 |
| R0-c | 다목적 스코어러 GT 대조 검증(기존 quality.py와 상관) | 0.5일 |
| R1-r1 | U1 후보 2개 + critic + 평가 + 판정 | 1일 |
| R1-r2/r3 | 라운드 반복, b_t=1, prune 대상 기록 | 1–2일 |
| R1-종료 | holdout draw + L2/L3 확인 + 보고 | 1일 |

**7.6 예상 비용 (추정 — ledger 실측으로 대체 예정).**
Reader run 1 paper ≈ 12–20 model calls(section pass × n_sections + understanding
map + quality check), input-heave, 논문당 ~300–600k tokens(입력 우세) 추정.
R0+R1 전체 ≈ (4+2×2×3 rounds) × 논문당 1 run ≈ 20–28 runs →
**총 6–17M tokens, 250–550 model calls**. GPU time은 API 호출 추정 기준;
local GLM bounded run 시 논문당 2–5 GPU-min 수준으로 추정. 정확화는 R0-b의
ledger 실측으로 수행.

**7.7 성공/실패/중단/승격 기준.**

| 기준 | 정의 |
|---|---|
| 성공(R1) | ≥1 후보가 δ 이상 개선 + Gate 전부 통과 + §3.4 상관 양(+) + L2/L3 무하락 |
| 실패 | 라운드 3회 연속 admissible 후보 없음 → 정규화 실패 진단 보고로 종료 (RRSI가 옳게 "변화 없음"을 보고) |
| 중단 | δ의 상대편: baseline 분산이 측정 불가 수준(sd 무한대)·runner 장애 2회 재시도 실패·budget ledger 소진 — 안전 정지, 진행 무효 |
| 승격 | PROMOTED → holdout draw → L2/L3 확인 → REPORTED → Collabo Human Approval → CANONICAL. 자동 승격 없음 |

**7.8 소유권 유지.** llm gateway(`llm/`), retry(`resilience.py`), run-history
(Collabo), evaluation harness(`docs/eval/` + `quality.py`) 소유권 유지.
본 설계의 신규 코드는 `harness_evolution/` 한 디렉터로 한정하며 코어·기존 모듈을
변경하지 않는다.
