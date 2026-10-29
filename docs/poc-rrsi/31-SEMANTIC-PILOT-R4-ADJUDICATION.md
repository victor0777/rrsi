---
doc_id: poc-rrsi-31-semantic-pilot-r4-adjudication
title: Semantic Pilot Plan & R4 Adjudication Report (0 model calls)
status: report
updated: 2026-10-29
---

# Semantic Pilot Preparation & R4 Adjudication Report

**Summary.** R4 독립 재검정 판정 8건을 append-only Review Record(r5)에 등록 —
**Gold 후보 3건(g3·g4·g7) 범위 한정 권고, APPROVED 0**(사용자 최종 승인 전
자동 승격 없음 — 계약에 `Recommend Approval`을 추가해 권고와 승인을 구조적
분리, 상태는 `RECOMMENDED`로 유지). **g1 최소 변형 생성**(`p1min` — 우위
주장 1문장만 제거, 타 주요 정보 보존 확인; 원 P1·P4는 보존). **g8 원본
오류 확정**: 원문 Eq.1 `S(x,y)=t·S₁+(1−t)·S₂` 대조에서 원본 note의 가중치
해석이 **반대**(t=0.25 → S₁ 0.25 < S₂ 0.75) — 오류 보존·Gold 정답 사용
금지, Value/Interpretation 축 분리. g2·g6·g9 UNAVAILABLE 확정 인정, 사례
미계산. 최소 Semantic Pilot 계획 수립 — **실행 가능 (별도 승인 대기)**.

---

## A. Gold 후보 확정 (지시 §A) — 기록 + 범위 한정

- R4 판정 8건 → `poc/runs/perturbation-audit/r5-adjudication/review-records.jsonl`
  (append-only 연속: r3 실증 → r4 R1 8건 → r5 R4 8건, 파일별 무변경).
- `gold-candidate-registry.json` (r5, fixture별 상태 권위 — approval_state는
  bundle digest 단위라 fixture별 구분 불가라는 한계 명시).
- 범위 한정: **g3 = Numeric Fidelity / g4 = Normalized Numeric Fidelity /
  g7 = Partial Required Information Coverage Loss**.
- **APPROVED 0 유지** — 독립자 `Recommend Approval`은 상태 `RECOMMENDED`
  뿐이며, 최종 Owner 승인(`Approve` + 5조건)만 APPROVED 승격. author-path의
  권고조차 `SELF_APPROVAL_REFUSED` (실증).

## B. g1 최소 변형 (지시 §B) — `p1min-1802-claim-only-removed.md`

| 항목 | 값 |
|---|---|
| 제거 | "Experimental results show that the proposed model significantly outperforms state-of-the-art text-only NER baselines." (1문장, 118자) |
| digest | `bda31b8338a2c148c1ab9c1cf9433250b02d0605201ea668a8d0331b13e703af` |
| 보존 확인 | modality attention ✓ / release·10,000 ✓ / 15,733 ✓ / 모호성 해소 ✓ / 한계 서술 ✓ — 타 주요 정보 전부 보존 |
| 기존 변형 | 원 P1(문단 전체 제거)·P4(모순 삽입) **보존** — P4는 별도 평가 사례로 유지 |

## C. g8 원본 오류 검증 (지시 §C) — **오류 확정**

- 원문 Eq.1: `S(x,y) = t·S₁(x,y) + (1−t)·S₂(x,y)`; S₁ = 문장↔keyword 유사도,
  S₂ = 문장↔keyword에 이미 매핑된 문장들의 최대 유사도(클러스터 응집).
- 원본 note 해석: "t=0.25 … the model places greater emphasis on the
  similarity to the keyword (S₁) than on the cluster coherence (S₂)".
- **기계 대조**: t=0.25 → S₁ 가중 0.25, S₂ 가중 0.75 — note 해석은
  **반대**. note가 스스로 계산한 `1−t = 0.75`와도 모순.
- 분리: **Numeric Value Fidelity = 정합**(0.25 = 원문) / **Numeric
  Interpretation Fidelity = 부정**(해석 반대).
- 처리: 오류 기록 보존(r5 registry + 본 문서)·**Gold 정답으로 사용 금지** —
  Gold 사용 시 Numeric Value Fidelity로 한정해야 하며, p2ext(0.25→0.75)의
  기대 판정도 Value 축으로 한정.

## D. UNAVAILABLE 사례 (지시 §D) — 인정

- g2·g6·g9: 잘못된 cross-paper 연결 제거 **인정**. Fixture는 유지, 변형
  부재는 **승인된 Semantic Discrimination 사례로 계산하지 않음**.
- 신규 변형: 현재 승인 후보 3건의 평가에 필요한 변형은 이미 보유(r1/r2) —
  **신규 변형 0건 추가** (필요 시에만, 별도 지시).

## E. Semantic Pilot 계획 (지시 §E) — 최소 Pilot (실행 대기)

| 항목 | 내용 |
|---|---|
| **Approved Gold vs 미승인** | Approved: 없음 — Pilot 실행은 최종 Owner 승인(3건 APPROVED)이 선행 조건. 미승인: g1·g8(개정 대상), g2·g6·g9(UNAVAILABLE), g5(제외) |
| **Original/Perturbed Pair** | g3: note(1802) `99efc53f…` ↔ `p2-1802-vocab` `cac6ae09…` / g4: 〃 ↔ `p2-1802-size` `063d6aca…` / g7: note(1901) `97f5dd09…` ↔ `p5-1901-method-removed` `4832a553…` (+g1 확정 시 `p1min` `bda31b83…`) |
| **평가 차원** | g3 Numeric Fidelity / g4 Normalized Numeric Fidelity / g7 Partial Required Information Coverage Loss |
| **기대 판정** | g3·g4: consistency ↓ (결정론 designated_numeric_consistency 재사용 가능 — 판별 확인용) / g7: coverage ↓ (결정론 길이·문장수 감소는 보조 신호, coverage 판정은 Gold/judge) |
| **Judge 출력 계약** | `rrsi-semantic-evaluation/v0.1` (30번 §E) 유지 — dimension / gold_expected_direction / evaluator_observed_direction / agreement / confidence XOR unverified_reason / evidence_references. judge 호출은 별도 승인 대상 |
| **Gold Agreement 측정** | 사례별 agreement ∈ {Agreement, Disagreement} 빈도 + confidence 분포 보고 — 3건 Pilot에서 Disagreement 1건이라도 발생 시 gold·계약 재검토 트리거 |
| **실행 비용 상한** | 모델 호출 ≤ 3 (사례당 1) / tokens ≤ 6,000 / wall ≤ 5분 / 유료 API 0 / 로컬 vLLM endpoint만 |
| **실패 시 중단 조건** | ① judge 미승인·endpoint 불가 ② reservation↔terminal 불일치 1건 ③ unverified_reason 없는 confidence 누락 ④ 원본/변형 digest 불일치 — 즉시 중단·보고, 재시도 없음 |

- **변경 없음**: 기존 Scorer 무변경, Dataset Split 무변경(freeze `849d1431…`),
  Final Holdout 무접촉, Reader Note 원본 무변경.

## F. 완료 보고 (지시)

1. **수정된 Fixture**: 신규 생성 3건(r5) — `p1min`(B), `review-records.jsonl`
   (A), `gold-candidate-registry.json`(A/C). 기존 fixture 파일·원본 artifact
   무변경. 2. **원본 오류 확인 결과**: g8 원본 note 해석 오류 확정(§C) —
   보존·Gold 미사용. 3. **독립 검토 기록**: R4 8건 등록, APPROVED 0,
   RECOMMENDED 3. 4. **Pilot 실행 가능 여부**: **가능(대기)** — 사용자의
   3건 최종 승인(APPROVED 승격) + judge 승인이 남은 조건.

## 제한사항 준수

신규 모델 호출 **0**, Reader Pipeline 0, QA 재실행 0, δ 반복 확대 0, RRSI
Evolution 0, Final Holdout 소비 0, Scorer 수정 0, Reader Note 원본 변경 0,
기존 fixture/Source 무변경, 자동 Gold 승인 0 (APPROVED 0), 신규 worktree 0
(main 브랜치 작업).
