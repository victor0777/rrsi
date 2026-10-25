---
doc_id: poc-rrsi-17-qasper-failure-attribution-report
title: QASPER Failure Attribution & Evidence F1 Root-Cause Report (analysis-only)
status: report
updated: 2026-10-25
---

# QASPER Failure Attribution Report

**Summary.** 기존 10 packet을 이용한 trace 분석(신규 모델 호출 0). 근거가
있는 것만 분류했고, 분류 근거를 전건 기록했다. 핵심 발견: **false unanswerable
4건 전부 "정답 근거가 abstract에 없음" — protocol mismatch이며 모델·구현
결함 아님**; **Evidence F1 = 0은 구조적 원인(gold evidence가 fulltext·figure에
기반, 입력 조건은 abstract_only)으로 protocol 하에서 원천적으로 불가능**.
판정: **HOLD 유지**(보완 항목 갱신, STOP 근거 없음).

---

## Workstream A — 질문별 Failure Attribution Table (지시 1)

추적 정보: gold answer/answerability(fixture gold) → 원문 근거 존재(dataset
fulltext annotation) → extraction 보존(abstract_only 조건, source digest) →
Reader Note 보존(**해당 없음** — external QA lane은 Reader Note를 경유하지 않고
abstract를 직접 context로 사용; 축 설계상 N/A) → retrieval/context 전달(조건
고정: abstract 전체 전달, retrieval disabled) → 모델 answerability 판단 →
answer/abstention → scorer 판정.

| # | case_id(단축) | 질문 | Gold answerability | 근거가 abstract에 존재? | 모델 행동 | F1 | 분류 |
|---|---|---|---|---|---|---|---|
| 1 | adbf33c6 | NER이 text+image 모두에서 학습? | 답변 가능 (yes) | **예** (구성 요소 기술) | 답변 yes_no | 1.0 | 성공 |
| 2 | 43f56301 | 어떤 모델 사용? | **gold: 불가능** | 부분 (abstract 문장 literal) | 답변 extractive | 0.0 | GENERATION_FAILURE — gold가 credit 부여 안함(주석 불일치 성격 포함, 분류 근거 기록) |
| 3 | 559920eb | unordered text document란? | 답변 가능 | **아니오** (정의는 fulltext) | abstention | 0.0 | SOURCE_MISSING — 입력 조건(abstract_only)이 근거 텍스트 배제 |
| 4 | 0a01341d | code 공개? | 답변 가능 ('No') | **아니오** | abstention | 0.0 | SOURCE_MISSING (동일) |
| 5 | 68cd8433 | dataset 공개? | 답변 가능 ('No') | **아니오** | abstention | 0.0 | SOURCE_MISSING (동일) |
| 6 | 7cd22ca9 | image-parts 연관 검증? | 답변 가능 ('Yes') | **아니오** (fulltext 실험 결과) | abstention | 0.0 | SOURCE_MISSING (동일) |
| 7 | a0543b4a | NE 비연속 가능? | 혼합 (['No', 'Unans']) | 부분 | abstention | 1.0 | 성공(주석 혼합 — abstention-credit, gold 모호성 기록) |
| 8 | f7a89b9c | 인식하는 NE 유형? | 답변 가능하나 **주석 내용 공란** | 아니오 | abstention | 1.0 | SCORER_MISMATCH — 공란 주석이 'Unanswerable' 참조로 매핑되어 credit 부여 |
| 9 | 1591068b | SnapCaptions 크기? | 답변 가능하나 **주석 내용 공란** | 아니오 (10K는 fulltext) | abstention | 1.0 | SCORER_MISMATCH (동일) |
| 10 | a8c862d8 | 평가 언어? | 불가능 | 아니오 | abstention | 1.0 | 성공(올바른 중단) |

**2. False Unanswerable 4건의 원인**: 전부 #3–#6 — **정답 근거가 fulltext에만
존재하고 abstract에 없음**(재검증: 각 gold answer text vs abstract 내용 대조).
모델 abstention은 입력 조건 하에서 합리적이나 gold가 credit 부여 안함 →
**protocol mismatch**(gold answerability 집합 ≠ abstract 도출 가능 집합).
구현 결함·매핑 결함 아님.

**3. Abstention 8건의 원인 분포**: 근거 부재(입력 조건상) 6(#3–#6, #8, #9) +
gold true-unanswerable 2(#7은 혼합, #10은 순수) = 8. 즉 abstention의 원인은
전부 "입력 조건이 근거를 제공하지 않음" 또는 "gold가 불가능 판정"이며, 생성
실패·맥락 손실은 0건.

**5. Reader Gold와 QASPER의 평가 불일치**: (i) 축 불일치 — Reader Gold는
개념 설명 충족(포화 1.0), QASPER는 답변 정확도(abstention 편향 지배).
(ii) **lane 구조 불일치** — external QA lane은 Reader Note를 소비하지 않으므로
"Reader Note 품질이 QASPER 점수에 미치는 영향"은 본 lane 설계상 존재하지 않음.
Reader Gold와 QASPER의 상관을 보려면 reader workflow 산출물을 context로 쓰는
별도 프로토콜(input_mode full_text/selected_sections — external QA intake의
지원 모드)이 필요. 신규 확정 금지(지시).

## Workstream B — Evidence F1 = 0 원인 (지시 4)

측정 대상 8건(gold evidence 존재) 조사 결과:

| 항목 | 결과 |
|---|---|
| Evidence 생성 | 2/8만 생성. 나머지 6건은 abstention → producer 설계상 evidence 없음(abstention 시 answer/evidence 공백) |
| Evidence 출력 스키마 | producer의 literal 검증 규약 준수 — surface는 abstract의 검증된 부분문자열. glue는 변형 없이 전달(입력 계약 충족) |
| Gold와의 식별자 정합성 | **불일치** — gold evidence는 fulltext 문장(#1 "Bi-LSTM/CRF…") 또는 figure 주석(#8 "FLOAT SELECTED: Fig. 1")에 기반. pred surface는 abstract 문장. containment 매칭(`_spans_match`)이 구조적으로 실패 |
| Span 매핑 | 구현 결함 아님 — 본 검토에서 pred→consumer 투영 변형 없음을 재확인 |
| Abstention에 의한 누락 | 6/8 — producer의 근거 추출률(evidence literal 산출 2/10)은 별도의 실제 품질 문제로 분류 |
| Scorer 입력 계약 | 충족 — F1=0은 'scored 0.0'(매칭 실패)과 'gold_evidence_missing'이 구분 기록됨 |

**구분 판정**: Evidence F1 = 0의 원인은 **매핑/protocol 결함**(gold evidence
기반 표면 = fulltext·figure, 입력 표면 = abstract — protocol 하에서 원천적
불가능)이 주이고, **실제 근거 품질 문제**(producer의 evidence literal 산출률
저조)가 차순위. 구현 결함 없음.

## Workstream C — Reward 적합성 (지시 1–6, 가중치 미확정)

1. **Reader Gold ceiling**: 유지 판정 — coarse 축은 상한 효과로 변별 불가.
2. **QASPER Answer F1 변별력**: abstention 행동이 지배 — 변별력은 answered
   lane에 한정되며 본 실행에서 2 case(장기 실측 mean 0.145). Abstention-credit
   공란 매핑이 점수를 상향 왜곡.
3. **Evidence F1 가용성**: 본 protocol(abstract_only)에서 **구조적으로 불가**
   — reward 축 부적합. 가능한 경로: input_mode 전환(full_text) 또는 evidence
   계약 변경 — 프로토콜 변경이므로 별도 승인 필요(임의 확정 금지).
4. **False Unanswerable 별도 측정**: 필수 — `unanswerable_confusion`은 이미
   독립 축으로 기록됨. Answer F1과 혼합 금지 규약 유지.
5. **Evidence Integrity hard guard**: 유지 — 단 "측정 가능 8 / gold_evidence
   missing 0"의 구분 기록을 guard 판정에 요구(기존 계약에 이미 존재).
6. **Cost 지표**: 계측 전용 유지 — reward 계산은 규약상 비용 rule(L1)만.

## Workstream D — Dataset Split 및 평가 독립성 (지시)

- Evolve 2 + BLOCKED_CONFLICTED 13 상태 유지(freeze `849d1431…` 무변경).
- QASPER는 독립 분할 축(dev 70 / final 159) — rrsi split manifest에 미편입.
- **평가 독립성 등록**: candidate 생성 과정에 QASPER final split 상세 결과
  노출 금지 — consumer는 fail-closed로 final 거부(실동작 확인), gold는 scorer만
  접촉, RRSI가 소비하는 것은 요약 metric 뿐(본 보고 포함 금지 확인: 본 보고는
  dev 결과만 기술).
- **Calibration 2편(1802.07862, 1901.10133) 재사용 등록**: 향후 독립 Final
  Holdout으로 재사용 금지 — 본 보고가 소비 기록(등록 축 완료). QASPER final
  cohort는 무접촉 유지.

## Workstream E — 보고 및 판단 (지시 1–8)

1. 질문별 Table: §A. 2. False unanswerable 4건: §A-2. 3. Abstention 8건
   분포: §A-3. 4. Evidence F1=0: §B. 5. Gold↔QASPER 불일치: §A-5.
6. **Reward 보완 필요사항**: (a) abstention 편향 보정 계측(false unanswerable를
   지속 별도 추적), (b) evidence lane의 프로토콜 정합(입력 모드 전환 승인 시),
   (c) 공란 주석 매핑의 영향 정량화 — 가중치 확정은 금지됨(지시 준수, 미실시).
7. **추가 데이터/모델 실행 필요 여부**: 분석 자체는 신규 호출 불요(완료).
   다만 (i) evidence lane 검증을 위한 `evidence_required` 조건 실행, (ii) reader
   workflow context 프로토콜 검증은 **승인 시** 모델 실행 필요 — 본 작업에서
   미실시(0 calls).
8. **Evolution GO/HOLD/STOP: HOLD 유지** — 갱신 사유: (i) evidence 축은 본
   protocol에서 구조적으로 사용 불가(16번 보고의 "보완 필요"를 "protocol 하
   불가능"으로 강화), (ii) QASPER의 reward 가용성은 보조 축으로 한정 확정.
   STOP 아님: 근본 설계 결함 없음 — 계약·구현은 fail-closed로 정확 동작하며,
   HOLD 사유는 프로토콜/승인 보완 문제.

## 범위 준수

신규 모델 호출 0(전건 기존 packet 분석), RRSI Evolution 0, Prompt 변경 0,
Final Holdout 소비 0, 운영 승격 0. RRSI 코어·ai_papers canonical artifact·
research_benchmarks scorer 계약 무수정.

**Committed artifacts**: 본 보고. 분석 근거는 기존 `poc/runs/qasper-calibration/`
artifact(raw packets, predictions.json, score-report.json)와 fixture gold.
