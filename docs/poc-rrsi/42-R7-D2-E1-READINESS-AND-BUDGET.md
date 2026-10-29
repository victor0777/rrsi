---
doc_id: poc-rrsi-42-r7-d2-e1-readiness-budget
title: R7-D2 E1 Readiness & Budget
status: report
updated: 2026-10-29
---

# R7-D2 — E1 Readiness & Budget (문서 42)

## 1. 토큰 예산 (C1) — 실측과 추정의 구분

| 구성 요소 | 값 | 구분 |
|---|---|---|
| System Prompt (R6I v2 승계 기준안) | **98 tokens** | **실측** (served `/tokenize`) |
| Output Template (v2 확장안) | **166 tokens** | **실측** |
| Claim Anchor 관련 입력 | 미정의 — Anchor 구조 호출당 ~100–300 tokens 추정 | 추정 |
| Source Evidence (논문 발췌) | 논문당 ~150–400 tokens | 추정 (R6I 실측 경험치) |
| A/B Note 발췌 | Unseen 논문 chars/4 하한: 8후보 4.5–8.8k chars → Note 미생성 | **측정 불가 — 실측 대신 추정** |
| User Prompt (합산) | Note 2건 + Source + Template ≈ **1,000–1,800 tokens/호출** | 추정 |
| Output Reservation | **500/호출** (고정) | 상수 |
| 호출당 Worst-case | ~2,300 tokens | 추정 |
| 12회 Worst-case | **~27,600 tokens** | 추정 |

- **Reader Note가 없으므로 실측 입력 토큰을 보고하지 않는다** — 위
  수치는 전부 추정. Note 생성 승인 후 실측 재산정이 Admission ⑥의
  조건.
- **20,000 tokens는 잠정 승인 상한 제안** — 최악 추정(27,600)을
  반영하면 E1 승인 요청 시 상한 재조정(예: 30,000)을 Owner에 제안해야
  함. 본 작업에서 실행 예산으로 승인된 것 없음.

## 2. Admission Gap Matrix (C2 — 8항목)

| # | 조건 | 상태 | 사유 |
|---|---|---|---|
| 1 | Unseen 논문 단위 분리 증명 | **PARTIAL** | 후보 8편 확보 + 분리 증명 생성; 노출 이력 caveat — Owner 검토 필요 |
| 2 | Gold Validity Gate 통과 | **BLOCKED** | Gate 미수행 (Reader Note 부재) — 통과로 기록 안 함 |
| 3 | 지표·집계 규칙 동결 | **SATISFIED** | 문서 39 §1 (D1 동결) |
| 4 | Judge Prompt·스키마 동결 | **PARTIAL** | Anchor 스키마는 문서 40으로 완성; 프롬프트 본문은 Unseen 노트 형식 확정 후 동결 |
| 5 | 실행 대상·호출 수 확정 | **PARTIAL** | 후보 8편 중 E1 12사례 대상 최종 선정 대기 |
| 6 | Token·GPU·Wall 예산 신뢰성 | **PARTIAL** | 실측(system 98, template 166) + 추정 혼합; Note 실측 후 확정 |
| 7 | Owner Approval / Permit 계약 | **SATISFIED** | R6I 계약 재사용 (`poc/execution_permit.py` 무변경) |
| 8 | 실패·Abstain·Evidence 불충분 처리 규칙 | **SATISFIED** | 문서 40 §2–3, 문서 39 §3 |

## 3. 특별 보고 (C2 지정 항목)

| 항목 | 상태 |
|---|---|
| Unseen 후보 확보 | ✓ 8편 `UNSEEN_CANDIDATE` (2편 EXPOSED 제외) |
| Reader Note 생성 필요 | ✓ 필요 — E1 전 별도 Owner 승인 (본 작업에서 금지) |
| 독립 Gold 검토자 2명 | ✗ 미확보 — Owner 지정 필요 |
| Gold Quality Gate 완료 | ✗ 미수행 — 미수행 상태 통과 기록 금지 준수 |
| Prompt·스키마 동결 가능 | ○ Anchor 스키마 확정됨, 프롬프트 본문 1차안 존재 |
| 예산 신뢰성 | ○ 실측 요소 존재하나 Note 실측 대기 |
| Approval/Permit 준비 | ✓ 계약·기계 장치 확보 (R6I 경로 재사용) |

## 4. 남은 차단 요인 → Owner 결정 필요 사항

1. **Reader Note 생성 승인** (후보 중 2–3편) — 차단 ②⑤⑥ 해소의 전제.
2. **독립 검토자 2인 지정** — 차단 ②.
3. **E1 토큰 상한 결정** (20k 제안 vs 최악 추정 30k).
4. 노출 이력 caveat에 대한 Owner 확인 (분리 증명 승격).

## 5. 다음 단계 제안

1. Owner가 위 4항목 결정 → 2. 후보 2–3편 확정, Note 생성(별도 승인) →
3. 실측 토큰 재산정·예산 동결 → 4. Gold Gate 수행·기록 → 5. Admission
체크리스트 재판정 → 6. **R7-E1 승인 요청** (별도).
