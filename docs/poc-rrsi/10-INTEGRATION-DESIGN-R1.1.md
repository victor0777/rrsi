---
doc_id: poc-rrsi-10-design-r1-1
title: RRSI Integration Design R1.1 (design and static review only — no runs)
status: proposal
updated: 2026-10-20
supersedes: poc-rrsi-09-design-r1 (structure retained, R1 full experiment NOT approved)
---

# RRSI Integration Design R1.1

**Scope statement.** Design and static review only. No model calls, no pipeline
execution, no operational change, no automatic promotion. Full R1 experiment
remains unapproved; this document prepares the R0-a / limited R0-b approval
decision. All cost figures are estimates whose derivation is now explicit (§5);
the previous R1 figure (6–17M tokens) is CORRECTED in §5.1 — it undercounted
paper-trials.

---

## 1. 평가 데이터 규모 — PoC 한정과 확장 계획

**한정 선언.** 15 gold papers(10 agent-memory + 5 e2e, 항목 약 90개)는
**Engineering PoC 스케일**이다. 이 규모로 주장할 수 있는 것: 계약·기계 검증,
δ 보정, 파이프라인 결합. 주장할 수 없는 것: 일반화 성능, 코호트 외 전이.

**확장 계획 (승격 단계별, 사전 등록형):**

| 단계 | 데이터 | 목적 | 검증 문제 |
|---|---|---|---|
| E0 (R0–R1) | 15 gold (8/4/3 분할) | 계약 검증 | 루프가 옳게 측정하는가 |
| E1 (R2) | + 신규 코호트 10편 (독립 주제, GT 저자 교차) | 코호트 외 전이 1차 | 개선이 주제에 전이되는가 |
| E2 (R3) | + 외부 QA 확장: QASPER dev 분할 (벤치마크 규모) | gold-외 일반화 | gold 이외의 독해에서도 이득인가 |
| E3 (R4) | + gold 항목 독립 재주석 샘플 5편 × 이중 주석자 | GT 신뢰도 | GT 자체의 측정 오차 |

**검력 산정 (정적).** 이분형 항목 기준, 8편 × 6항목 × k=2 = 96 항목-판정/평가.
p(항목 통과) ≈ 0.6에서 표준오차 ≈ √(0.24/96) ≈ 0.05 → δ~0.10–0.15 수준 효과만
검출 가능. E1에서 10편 추가 시 세부 오차 √(0.24/176) ≈ 0.037로 감소.
**결론**: E0은 효과 검출이 아니라 기계 검증용; 일반화 주장은 E1–E2 확정 후.

**확장 데이터의 누출 규약**: E1 신규 코호트는 R1 종료 후 취득; R1 하네스스 개선
과정에서 어떤 정보도 접촉 금지(취득 시점 타임스탬프 기록). E2 QASPER dev는
`external_qa_producer.py`의 승인 요청 경로만 사용.

## 2. δ 추정 — Baseline ×4의 한계와 보강

**한계 분석 (정적).**

1. **분산 추정의 분산**: R=4 표본의 표준편차 추정 자체가 상대 표준오차
   1/√(2(R−1)) ≈ 41% — δ 과소추정 확률이 높고, 과소추정 시 false-accept 상승.
2. **동일 점수 붕괴**: 이분형 trial에서 두 평가 점수가 같을 확률이 무시 불가
   (8×2 trials의 S가 동점) — calibrate의 `sd_null > 0` 조건이 붕괴 시 bootstrap
   fallback을 쓰지만, 이는 null의 실제 분포를 과소표현할 수 있음.
3. **temporal drift 미제거**: ×4를 순차 실행하면 모델 버전·서비스 상태 변화가
   null 분산에 혼입.

**보강 설계.**

- **Paired evaluation**: 후보 평가와 incumbent 재평가를 **인터리브·동일 조건**으로
  실행(동일 시간창, 동일 모델 버전 고정) — drift를 차단. Per-task paired diff
  (논문 8개의 ΔS_i)의 sd로 null을 추정하는 쌍통계량을 calibrate에 **소비자측**
  추가(코어 변경 없음 — `bootstrap_se`의 입력을 per-task diff로 주는 wrapper).
- **반복 측정 축적**: 각 라운드의 incumbent 재평가가 null 관측치를 1개씩 추가.
  R 관측 축적 시 Welch식 갱신 + 보수 규칙 `δ = z·max(sd_direct, sd_bootstrap)`.
- **확정 조건**: δ는 **R0-b 실측 이후** freeze 문서에 확정 등록. z=2.0 기본,
  z=1.0은 E0처럼 작은 세트에서만 사유와 함께 허용(PoC 선례: `poc/04 §2`).
- **δ 급 변경 시**: 저장 측정값으로 re-adjudicate(새 평가 0) — paper-direct.

## 3. Gold 검증 — 상관 단독 승격 금지

R1의 "다목적 점수 ↔ QASPER 상관"은 **필요조건**이며 타당성 확정 근거가 아니다.
R1.1 검증 패키지는 4요소:

| 요소 | 설계 | 합격 기준 |
|---|---|---|
| 평가자 일관성 | (a) 자동 채점 self-consistency: 동일 산출물 ×3 채점 → 항목 판정 일치율 (b) 인간 재주석(E3): 2 주석자 × 5편 → IAA | self-agreement ≥ 0.9; IAA Cohen's κ ≥ 0.6 (확정은 E3 실측) |
| 근거 정확도 | GT와 무관한 직접 측정: 생성된 `source_sentence_ids` 인용이 실제 소스 문장과 대응하는지 소스 원문 대조 — citation precision/recall | precision 하락 = Gate 위반(기존 §5.5 강화: 정밀도 임계 수치화) |
| Downstream 회귀 원인 분석 | L2/L3 하락 발생 시 승격 판정 보류 + 필수 원인 보고: 어떤 GT 기준이 이득을 만들었는지, 하류에서 어떤 성분(후보 정밀도·KCP gate·리뷰 합치)이 하락했는지, 그 연결이 GT-고유 기제인지 기계적 인과인지 | "GT-고유 기제로 설명되는 회귀" = 승격 차단(§3.4의 일반형) |
| 사전 등록 가설 | freeze 문서에 "이 후보가 어떤 기준을 어떻게 움직이게 예상되는가" 등록 | 예상 밖 기준 상승은 보조 검토 사유 |

QASPER 상관은 이 4요소와 함께 승격 판단에 들어가는 **1/5** 증거로 격하된다.

## 4. Holdout — 소진식 대 일괄식 비교

**한계 검토 (승격당 1 draw).** 승격당 4편 × k=2 = 8 trial로 holdout ΔS의 표준오차
≈ √(2·0.24/8) ≈ 0.24 — **δ 이상의 이득도 단일 draw로는 검출 불가**. 연속 소진은
pool을 빠르게 고갈(쿼터 상한 3회)하면서 통계적 정보는 거의 얻지 못한다. sequential
draw의 유일한 가치: 승격 직후 빠른 이상 신호(대폭 하락 감지).

**비교.**

| 방식 | 검력 | 데이터 효율 | 승격 주기와의 정합 |
|---|---|---|---|
| 소진식(승격당 draw) | 낮 (sd≈0.24) | 나쁨 | 라운드마다 가능 |
| **일괄식(최종 후보 동결 후 독립 Holdout 일괄 평가)** | 높 (pool 4편 + E1 확장 시 sd≈0.11 이하) | 좋음 | 실험 종료 시 1회 |

**R1.1 결정**: 실험 단위 일괄식 채택. 승격의 상태는 `PROMOTED`(측정 기반 권고)까지만
R1 실험 내에서 진행; holdout은 **최종 후보 동결(freeze) 후 일괄 1회** — 실험 전체
holdout pool(4편 + quarantine) × k=2, H0 대조 포함. 승격 주기별 holdout은
E1 이후 고위험 승격에만 예외 허용(승인 사유 문서화). 소진식의 이상 신호 역할은
Validation(라운드 중 접근 허용 축)이 대체. holdout 접촉은 접촉 로그(시각·실행자·
job id)에 기록하고, 로그 없는 holdout 결과는 증거 불인정.

## 5. 비용 — 산출 근거 명시와 예산 상한

### 5.1 산출 근거 (R1의 6–17M 추정을 정정)

**trial 산출 (E0 기준).**
- Baseline ×4: 4 evals × 8 papers × k=2 = **64 paper-trials**
- R1 라운드 3회: 회당 (incumbent 재평가 16 + 후보 2 × 16) = 48 → **144 paper-trials**
- 일괄 Holdout: (H_final + H0) × 4 papers × 2 = **16 paper-trials**
- Validation·스코어러 검증: **≈ 24 paper-trials**
- **합계 ≈ 248 paper-trials** (R1 문서의 "20–28 runs"는 evals를 잘못 세었음 — 정정)

**단위 비용 (추정, R0-b 실측으로 대체).** paper-trial 1개 = reader workflow 1회
≈ 12–20 model calls, 300–600k tokens(입력 우세), local GLM 기준 2–5 GPU-min,
종단 10–30 min.

**총계 추정.** **75–150M tokens, 3.0–5.0k model calls, 8–21 GPU-h,
종단 병렬화 필요**(직렬 시 40–120 h).

### 5.2 예산 상한 (R0-b 실측 기반 확정, 상한은 비율로 선행 선언)

| 항목 | 상한 | 초과 조치 |
|---|---|---|
| paper-trial | 260 | 즉시 중단 |
| tokens | 100M (≈상한 trial × 상한 단위의 80%) | 즉시 중단, ledger 원인 보고 |
| model calls | 4,400 | 즉시 중단 |
| GPU time | 18 GPU-h | 즉시 중단 |
| 지연시간(라운드 종단) | 8 h | 병렬도 상향 또는 k=1 강등 기록 |
| 라운드당 trial | 60 | 후보 m 축소 |

중단은 안전 정지이며 진행 무효(§7의 중단 기준과 동일). `call_budget` ledger가
fail-closed로 예산을 강제하므로 추가 게이트웨이 코드 없음.

## 6. 비교군 실험 설계

동일 평가 예산(동일 trial 상한·동일 데이터)의 4-arm 비교:

| Arm | 후보 생성 | 정규화 | 검증 문제 |
|---|---|---|---|
| A. RRSI 전체 | proposer(history 조건화) + critic | δ+cost+prune | 전체의 효과 |
| B. 선별 규약 + 인간 프롬프트 개선안 | 인간 작성 개선안(사전 수집) | 동일 selection | 이득이 루프인가 제안 품질인가 |
| C. 고정 소규모 탐색 | 프롬프트 변형 grid (기록·critic 없음) | δ floor만 | 정규화된 탐색이 무작위 탐색보다 나은가 |
| D. 무처치 | 없음 (baseline 재평가만) | 없음 | δ 타당성·false-accept률 실측 |

주지표: 실험 종료 시 evolve·holdout S vs H0. 보조지표: 비용, critic 차단 건수,
D-arm의 false-accept 건수. **R1.1 승인 범위는 D(필수)와 B 준비(개선안 수집 규약)까지**;
A/C는 R1 승인 시 실행.

## 7. 승격 상태 — 의미·전이 조건·순서 검증

| 상태 | 의미 | 전이 조건 | 되돌리기 |
|---|---|---|---|
| `EVALUATED` | 측정 완료 | eval.json 유효(missing ≤ 한계) | 재측정 가능 |
| `ADMISSIBLE` | floor·cost·guard 통과 | `selection.judge` + Gate | 판정 재계산(re-adjudicate) |
| `PROMOTED` | **측정-수준 채택 권고**: branch ff 완료. holdout 미사용·감사 전 상태 | argmax 결과 + L2 무하락 확인 | `update-ref` rollback |
| `FROZEN` | 실험 종료 후보 동결 | 추가 라운드 금지 선언 + 트리 해시 등록 | 해제 불가(신규 실험) |
| `HOLDOUT_DRAWN` | 일괄 holdout 평가 실행 완료(소진 기록) | FROZEN 상태 + 접촉 로그 등록 | 불가(데이터 소진은 불가역) |
| `HUMAN_APPROVED` | Collabo milestone accept | **HOLDOUT_DRAWN 이후** + 보고서가 holdout 결과 포함 + Gate 재확인 | accept 취소 = 사후 리뷰 이력 |
| `CANONICAL` | 기록상 하네스스로 확정 | HUMAN_APPROVED + rollback 계획 등록 | CANONICAL rollback = §5.8 (b) |

**순서 검증 (지시 7의 "holdout이 승인에 반영되는 순서").** State Machine이
`HUMAN_APPROVED` 전이에 `HOLDOUT_DRAWN` 이전 기록을 요구하도록 강제 —
holdout 미포함 승인은 유효 전이가 아님(거부·사유 기록). 타임스탬프 단조성
검사(권고 ts < holdout ts < approval ts < canonical ts). R1과의 차이: R1은
승격당 holdout draw를 승격 흐름에 넣었으나, R1.1은 holdout이 **승인 패킷의
필수 선행 요소**로 위치가 명확해졌다.

## 8. 원 논문 적합성 — paper-direct 11개의 근거 연결

**8.1 vendored 코드 ↔ 호출 경로 (11개 전부).**

| # | paper-direct 기능 | vendored 근거 (파일:함수) | 설계 호출 경로 |
|---|---|---|---|
| 1 | weighted estimator (missing=0, full denominator) | `rrsi/evaluate.py::aggregate` | `domain_reader.score()` 결과를 `aggregate`로 접음 — wrapper 없이 직접 |
| 2 | δ 보정 (bootstrap / 반복 evals) | `rrsi/calibrate.py::calibrate, bootstrap_se, pooled` | `evo_cli baseline` → `calibrate([ev...], z)`; paired wrapper는 출력만 다른 입력으로 재사용 |
| 3 | L1 cost rule | `rrsi/selection.py::cost_rule` branch 1 | 라운드마다 `select_round()` 내부에서 호출 |
| 4 | shaped rule (in-band) | `selection.py::cost_rule` branch 2 | 동일 |
| 5 | noise floor · argmax · S* | `selection.py::judge, select_round` | 동일 |
| 6 | critic 정적 denylist | `rrsi/critic.py::precheck, GENERIC_PATTERNS` | 후보 draft 직후 `precheck(diff, FIXTURE+ai_papers 패턴)` |
| 7 | edit history L_t | `rrsi/history.py::History.append_candidate, render, tried, yield_g` | 라운드 종료·프롬프트 조립 시 |
| 8 | prune set B_t | `history.py::prune_set` | 라운드 시작 시 directives 생성 |
| 9 | annealed budget b_t | `rrsi/schedule.py::edit_budget` | `b_min=b_max=1`로 호출(R1 제약은 **매개변수 선택**, 코어 불변) |
| 10 | worktree 격리·ff 승격·복원 | `rrsi/gitops.py::worktree_add/remove, fast_forward, update-ref` | `evo_cli` 전 경로 |
| 11 | heldout slot | `rrsi/domain.py::Domain.heldout_ids` + `Run.heldout` 소비 패턴 | `domain_reader.heldout_ids()`가 일괄 holdout 논문 반환 |

**8.2 두 사실의 구분.**

- **"코어를 수정하지 않는다"** — 검증 방법: vendored 사본과 upstream 원본의
  diff 공백 + upstream 테스트 무수정 통과(PoC 세션에서 확인: upstream 8 +
  PoC 7 = 15 passed). 이 사실은 **필요조건**이며 올바른 사용을 보증하지 않는다.
- **"알고리즘을 올바르게 적용한다"** — 검증 방법(§8.1의 호출 경로 감사 + 정적
  정합 테스트): (i) selection 로그를 손계산 기대치와 대조하는 정합 테스트(PoC
  `test_selection_blocks_cost_without_gain` 선례), (ii) 정규화 가중·guard 정의가
  선언된 입력만 변경함을 보이는 테스트, (iii) R0 종료 시 decision json의 각 REJECTED에
  논문 규칙 절에 대응하는 사유 존재 감사. **이 검증은 R0-b 실행 + R0 감사에서 완성된다**
  — R1.1 시점에는 검증 계획만 확정되고 이행은 아니다. §3.4·§8의 정적 감사 항목이
  R0-b 승인의 전제 조건이다.

**R1.1의 판정 요청 사항**: (i) §5.2 예산 상한 비율 승인, (ii) §6 D-arm(R0-b에 포함) 승인,
(iii) R0-a(GT 재배치·freeze 문서) 및 제한된 R0-b(baseline ×4 + δ 산출) 실행 승인 여부.
