---
doc_id: poc-rrsi-48-r7-d2b-e1-admission-readiness
title: R7-D2B E1 Admission Readiness R1
status: report
updated: 2026-10-29
---

# R7-D2B — E1 Admission Readiness R1 (문서 48)

모델 호출 0, tokenizer 계측만 허용(모델 추론 금지). 최종 상태:
**R7_D2B_READINESS_REVIEW**.

## 1. Token Budget 재검증 (E1) — 실측/추정 구분

| 항목 | 값 | 구분 |
|---|---|---|
| System Prompt | 98 tokens | **실측** (served `/tokenize`) |
| Output Template | 166 tokens | **실측** |
| User Prompt | ~1,000–1,800/호출 | **추정** (Reader Note 부재 — 실측 불가, 추정치 생성 금지) |
| Claim Evidence | anchor당 ~100–300 | **추정** |
| Output Reservation | 500/호출 | 상수 |
| Worst-case 12회 | ~27,600 | **추정** |
| GPU / Wall-clock | — | **추정** (호출 없음 — 산출 불가, 추정 라벨) |

- 문서 42 확인: 최악 추정 27,600 > 잠정 상한 20,000 — **상한
  재결정(예: 30k)이 Owner 사항**.
- **20,000 tokens는 실행 승인 예산이 아님** (잠정 제안).

## 2. Reader Note 생성 필요량 (B2)

| 항목 | 값 |
|---|---|
| 신규 생성 필요 | 8편 (E1 12사례 대상 재선정 시 2–3편 우선 가능) |
| 재사용 가능 / 재생성 필요 | 0 / 0 |
| 생성 Profile | **미확정** — 비용은 전부 추정 라벨 |
| 예상 모델 호출 | ~1/편 (추정) |
| 생성 후 검증 | source digest 결합, note digest, locator 지원, 노출 이력 재확인 |

## 3. Gold 검토 준비 (B3/B4)

Gold 전원 `ABSENT` — Source Evidence, 검토자 2명, Quality Gate,
Freeze 전부 미충족. 독립 검토 절차는 문서 47 §7에 정의 완료.

## 4. Admission Gap Matrix (E2 — 원문 기준 8조건)

| # | 조건 | 상태 | 근거 |
|---|---|---|---|
| 1 | Unseen 독립성 | **PARTIAL** | 보완 스윕+git -S 무적중; caveat 유지 |
| 2 | Gold Validity Gate | **BLOCKED** | Gate 미수행, Note 부재 |
| 3 | 지표·집계 동결 | SATISFIED | 문서 39 §1 |
| 4 | Judge Prompt·Schema 동결 | PARTIAL | Anchor 스키마·안전 계약 동결(40/43/44/45), 프롬프트 본문 대기 |
| 5 | 대상·호출 수 확정 | PARTIAL | 8후보, 12사례 선정 대기 |
| 6 | Token/GPU/Wall 신뢰성 | PARTIAL | 실측 98/166 + 추정; Note 실측 대기 |
| 7 | Owner Approval / Permit | SATISFIED | R6I 계약 재사용 |
| 8 | 실패·Abstain·Evidence 규칙 | SATISFIED | 문서 40 §2–3, 39 §3 |

## 5. Readiness States (E3)

| 상태 | 판정 |
|---|---|
| `CONTRACT_READY` | **True** — 평가 계약·정적 검증 완료 (D2A.1/D2B) |
| `CANDIDATE_DISCOVERY_COMPLETE` | **True** — 8+2편 조사 완료 |
| `DATASET_READY` | **False** — Reader Note 0/8, Gold 미생성 |
| `E1_ADMITTED` | **False** — Owner 승인·Permit 없음, 조건 ②④⑤⑥ 미충족 |

각 상태 독립 판정 — CONTRACT_READY는 DATASET_READY를 의미하지 않음.

## 6. 차단 요인 → Owner 결정 필요 사항

1. Reader Note 생성 승인 (2–3편 우선 제안).
2. 독립 Gold 검토자 2인 지정.
3. E1 토큰 상한 재결정 (20k 제안 vs 27.6k 최악 추정).
4. 노출 이력 caveat 확인 → 후보 승격.
5. (Gold Gate 후) Gold Freeze 승인.

**R7-D2B 완료는 R7-E1 실행 승인이 아님.**
