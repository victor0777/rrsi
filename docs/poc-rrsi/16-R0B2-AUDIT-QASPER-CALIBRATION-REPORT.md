---
doc_id: poc-rrsi-16-r0b2-audit-qasper-calibration-report
title: R0-b2 Audit, QASPER Calibration Workstream Report (A–E)
status: report
updated: 2026-10-25
---

# R0-b2 Audit 및 QASPER Calibration Report

**Summary.** Workstream A–E 수행. A: audit 정합성 전건 검증(차이 9 calls =
중단 invocation 3+6으로 완전 설명; repeat-4의 reservation 1건 terminal 없음은
fail-closed 유지). B: QASPER lane 연결 검증 + 최소 record extraction 구현
(기존 계약 무변경). C: QASPER Calibration **실행** — 2편 10 cases, Answer F1
**0.50**, Evidence F1 **0.0**(8 case 측정 가능). D: 평가 단계 변동성은
0(재채점 byte-identical), Reader 생성 단계 변동성은 R0-b2 실측. E: **HOLD**
권고 — Evolution 미승인 상태 유지, 보완 항목 3건(§5).

---

## Workstream A — R0-b2 Audit 정합성 (지시 1–5)

**1. 75 vs 84 calls 차이 — 완전 설명.** 84 = r0b2 ledger 전체 예약
(r2 25 + r3 3 + r3b 25 + r4 6 + r4b 25). 75 = 성공 trial 3회 × 25
(r3·r4b·r4b). 차이 9 = 중단 2 invocation(3+6). r0b1의 29 calls는 별도 ledger
(r0b1 budget root)이므로 r0b2 84에 미포함 — "완료된 Trial 75"와 "전체 84"는
범위(성공 trial vs 전체 invocation)의 차이다.

**2. 중단 Invocation 사용량 별도 기록** (기존 결과 무변경, 기록 보강):

| Invocation | 종료 사유 | calls | tokens(입+출) | wall |
|---|---|---|---|---|
| r0b2-repeat-3 | plan 품질 게이트 거부 (fail-fast) | 3 | 11,818 + 5,736 | 1.52분 |
| r0b2-repeat-4 | 실행 환경 종료 (process kill) | 6 (terminal 5) | 17,617 + 8,040 | 2.18분 |

repeat-4의 마지막 1 call은 kill 시점에 in-flight — **reserved-without-terminal
1건**. 본 audit에서 위반으로 유지(임의 보완 금지, fail-closed 규약 정확 동작).

**3. 집계 범위 명시(보고 코드 수정 — 스코프 등록):**
- **Wall-clock 80.5분** = 세션 전체 창(첫 예약→마지막 terminal, 중단·대기·idle
  포함) — *순수 실행 시간 아님*.
- **GPU-hours 상계 0.363** = 성공 trial 3회의 telemetry span 합(21.8분)만 귀속.
- **정정**: 중단 invocation의 wall(3.7분, ub 0.062 GPU-h)까지 포함한 r0b2 총
  상계는 **0.425 GPU-h**. 상한 2.0 대비 여유 유지. 세션 창 전체(80.5분)를
  GPU-h로 환산(1.34)은 **idle 포함 과대계**로 사용 금지 — 상계의 올바른
  스코프는 "call-in-flight 기간"이다.
- Wall-clock 소비(지시 상한 120분 대비): 순수 실행 창 스코프 ≈ 43.8분
  (r0b1 21.9 + r0b2 성공 21.8; 중단 별도), 세션 창 스코프 80.5분 — 두 값 모두
  상한 내. **스코프 등록**: 향후 상한 준수 판정은 "순수 실행 창" 기준으로 통일.

**4. GPU-hours 상계 계산식 검증 — 일치.** `sum(spans)/60 = 0.363` = 보고값
0.363 (재계산 동일). 보강: r0b2 전체 스코프 재산정 0.425 (§A-3).

**5. Trial별·Invocation별 Ledger↔Telemetry 정합 — PASS (1건 설명됨).**
전 5 invocation에 대해 ledger 예약 수 = telemetry terminal 수 (r4의 6≠5는
§A-2 사유). per-invocation 예약/terminal/usage 스코프 검증은 `poc/r0b2_audit.py`
가 수행하며, audit의 invocation 스코핑 결함(ledger 미스코프로 과대 위반
보고)은 본 검토에서 수정 — 기존 결과 임의 변경 없음(재실행 결과 동일).

## Workstream B — QASPER 실행 준비 (지시 1–8)

| 항목 | 결과 |
|---|---|
| 1. Fixture 데이터 상태 | dataset `qasper-dev-v0.3.json` byte-실존, fixture manifest에 digest 등록(CC BY 4.0), dev 20 papers/70 cases. **논문 fulltext·abstract dataset 내 포함** |
| 2. 파이프라인 재사용 | ai_papers `external_qa_collect_r0.py` (승인 envelope: 모델 id·70-call 상한·gold-independent) **무수정 사용**. 승인 gateway 실존 확인(모델 id listing 일치) |
| 3. Stage-01/Extraction | abstract_only 조건이라 fulltext bundle 불요 — Stage-01 승인 없이 calibration 가능(15번 문서 차단 요인 1건 해소) |
| 4. Intake↔Consumer 연결 | packet의 intake record(schema `ai-papers-external-qa-intake/v0.1`) → consumer 투영 **연결 검증 PASS**(10/10 case 투영·dev-gold 매칭) |
| 5. Record extraction 최소 구현 | `poc/qasper_calibration.py`: collection packet의 `evidence_spans[].surface`(producer 검증 literal)를 consumer prediction으로 복원 — glue ~100 LOC, **ai_papers·adapter·scorer 무변경** |
| 6. 기존 계약 유지 | scorer(`qasper-answer-f1/v0.1`)·consumer(`evidence-match/v0.1` 분리)·adapter 계약 무변경. 신규 scorer 구현 0 |
| 7. Hash/환경 freeze | run manifest에 ai_papers commit(`consumer`가 expected_commit 검증), dataset sha256, endpoint(LAN, 유료 API 아님), contract versions 기록 — **manifest SHA-256 `328fde84…`** |
| 8. Contamination/Split | gold 15편 ↔ QASPER dev/final 교집합 **0건**(재검증); QASPER는 rrsi split manifest와 독립 축; consumer fail-closed(final split 거부) 실동작 |

## Workstream C — QASPER Baseline Calibration (실행함)

- **대상**: QASPER dev fixture 중 2편 — 1802.07862(5 cases), 1901.10133
  (5 cases) = 10 cases. Evolve/Calibration 승인 범위(사전 승인된 fixture 분할
  dev cohort) 내. Reader Prompt baseline 고정, candidate evolution 0, Final
  Holdout 미사용.
- **실행 전 명시·강제한 상한**(기존 실측 참고): model calls ≤ 12(external QA lane
  실측 1 call/case + slack — 기존 collection CLI의 envelope 상한 메커니즘으로
  독립 강제, budget guard offset 기법 등록), wall-clock ≤ 15분(timeout 900 —
  실측 4.1분), token ceiling 없음, retry 0(case당 1 documented attempt), 동시
  실행 1, 유료 API 미사용(LAN gateway).
- **실행 결과**: 10/10 cases 수집, 실패 0, latency mean 0.99s.
- **채점(무변경 consumer+scorer)**: **Answer F1 0.50**, **Evidence F1 0.0**
  (gold evidence 존재 8 case 측정), false unanswerable 4/10, missed 1/10,
  answered claim 2·abstention claim 8, evidence literal 산출 case 2/10
  (literal 2+1개).

## Workstream D — 평가 변별력 분석 (지시 1–6)

1. **Reader Gold vs QASPER Answer F1**: Reader Gold는 개념 충족 축(coarse
   포화 1.0, 변별력 없음), QASPER F1 0.50은 답변 정확도 축. 2편·10 case로
   **상관 확정 금지**(지시 준수) — 질적으로는 측정 대상이 다른 별개 축.
2. **Reader Gold vs Evidence F1**: Evidence F1 0.0 — gold note 충족도가 높아도
   근거 추출 능력과는 무상관 소견(축 분리 실증). evidence literal 산출 case가
   2/10에 불과해 evidence lane 자체가 실험적으로 저정보.
3. **평가 재현성**: 재채점 **byte-identical**(deterministic) — 평가 단계 변동성
   0. 변동성의 전부는 Reader 생성 단계 소속(R0-b2 실측: coarse 불변, term-hit
   sd 0.097).
4. **정보 누락 영향**: abstention 8/10 중 false claim 4 — 모델이 답변 대신
   중단하는 비율이 Answer F1을 지배(abstention-credit 구조). Reader Note의
   정보 누락보다 **중단 행동 편향**이 QASPER 점수의 주 변인으로 관측.
5. **기존 Gold ceiling effect**: 재확인(R0-b2 §5-3). Gold의 상한 효과 하에서
   QASPER가 갖는 추가 변별력은 answered-lane F1(본 실행 2 case, R0-b2 pilot
   실측 mean 0.145)에 한정 — 낮음.
6. **QASPER의 RRSI Reward 가용성**: **보조 축으로 가능** — (a) 결정론적 재현,
   (b) 외부 dataset의 저비용 측정(1 call/case), (c) gold 격리 유지. 단 (i)
   Evidence F1은 현 상태에서 reward 불가(무정보), (ii) 중단 행동 편향 보정 없이는
   answered-lane 신호 과소, (iii) 가중치·δ 재산정 필요(15번 문서 §4). 주
   reward는 Reader Gold 유지 권고.

## Workstream E — Evolution 진입 판단 — **HOLD** (권고)

| 진입 조건 | 상태 |
|---|---|
| Token Telemetry 완전성 | PASS (r0b2 3 trial 25/25/25 reported; r4 kill 1건은 규약 준수 기록) |
| Ledger 정합성 | PASS (84 calls 전건 대조; audit 스코핑 결함 수정) |
| Dataset Split 유효성 | PASS (freeze `849d1431…`, Validation/Holdout frozen empty — 후보 평가 표본 부족은 HOLD 요인) |
| QASPER Adapter 실행 성공 | PASS (본 실행, 계약 무변경) |
| Evidence Integrity 검증 | **미충족** — Evidence F1 무정보(0.0), reward 축 부적합 |
| 평가 지표 변별력 | **부분** — coarse gold 포화, QASPER answered-lane 저신호, δ 불확실(n=4) |
| 후보 평가 비용 | 양호 (~101k tokens/trial, reader 1회 ≈ 8분; 후보 1개 × evolve 2편 ≈ 200k tokens) |

**HOLD 사유(보완 항목, 우선순위 순):**
1. δ 불확실성: baseline repeat n≥6으로 sd/δ 구간 축소(14번 문서 권고 이행).
2. Evidence Integrity: producer의 evidence literal 산출률 저조(evidence_required
   조건 실험 또는 span locator 개선) — Evidence 축을 reward로 쓰려면 필수.
3. 무충돌 분할 승인: Validation/Holdout 공측 해소 전 승격 주기 진입 불가(R1 §3.2 #5).

STOP 아닌 근거: 실험 설계의 근본 결함 없음 — 모든 실존 계약이 fail-closed로
동작하고, 변별력 결핍은 측정 보강 문제(반복·조건 조정)로 분류됨.

## 본 작업 범위 준수

RRSI Evolution 0, Prompt 자동 변경 0, B/C 비교군 0, Final Holdout 평가 0,
운영 승격 0, 신규 scorer 구현 0. RRSI 코어·ai_papers canonical artifact·
research_benchmarks 계약 무수정(변경은 rrsi `poc/` glue와 보고 스코프 등록뿐).

**Committed artifacts**: `poc/qasper_calibration.py`, 본 보고. Run 산출물은
`poc/runs/qasper-calibration/` 로컬 미추적.
