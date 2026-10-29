---
doc_id: poc-rrsi-39-r7-metrics-admission
title: R7 Evaluation Metrics and Admission
status: design
updated: 2026-10-29
---

# R7 — Evaluation Metrics & Admission (R7-D0 문서 3)

## 1. 지표 정의 — 분모·집계 단위·Abstain 정책

집계 단위: **사례(case) = (논문, note 변형, 차원)** — 논문이 아님.
주 집계 분모는 **Gold Quality Gate VALID 사례만**. CONFLICTED/
INSUFFICIENT_EVIDENCE/EXCLUDED는 별도 부록 보고.

| 지표 | 정의 | 분모 | Abstain 처리 |
|---|---|---|---|
| Gold Agreement | 판정 방향 일치율 | VALID 사례 전부 | ABSTAINED는 분모 포함·Agreement 아님 (별도 비율 병기) |
| Claim Precision | 실제 오류인 Judge 주장 / 전체 Judge 주장 | 주장 단위 (VALID) | Abstain 사례의 미제기 주장 제외 |
| Claim Recall | 발견된 실제 오류 / 전체 심어진 실제 오류 | 심어진 오류 단위 (VALID) | Abstain 사례 오류는 미발견으로 집계 + 병기 |
| Evidence Grounding | 인용이 실제 해당 텍스트에 존재 비율 | 인용 단위 | 인용 없는 주장 = 미그라운딩으로 집계 |
| False Positive Rate | 정상(반사례) 사례를 오류로 비판 비율 | 반사례 사례 (VALID) | Abstain은 FP 아님 |
| Abstention Quality | 유보 적절율 | 유보 대상 사례 + 비유보 대상 사례 | — |
| Cost per Valid Judgment | (입력+출력 tokens·latency) / 유효 판정 | 유효 판정 (PARSE/SCHEMA 실패 제외) | — |

- **PARSE_FAILURE / INVALID_SCHEMA**: Agreement 집계 금지, INCONCLUSIVE
  기록 (R6I 계약 승계).
- **소표본**: n<30이면 Wilson 95% 신뢰구간 병기, 점추정 단독 해석 금지.
- Challenge 집계는 별도 표 (주 지표와 혼합 금지).
- 동결: 이 표는 R7-E1 승인 요청 전 수정 금지 (수정 시 재-Admission).

## 2. Judge 출력 스키마 (설계 방향 — E1 전 동결)

R6I v2 계약에서 확장하되 고정 레지스트리 제거:

```
{"relative": "A"|"B"|"equal"|"abstain",
 "reason": "<=200 chars, abstain only",
 "a_verdict"/"b_verdict": "high"|"medium"|"low",
 "ev_a"/"ev_b": ["<=120-char quoted phrase, max 2"],
 "claims": [{"kind": "numeric_error"|"info_loss"|"missing_evidence"
                    |"contradiction",
             "target_side": "A"|"B",
             "claim": "<=120 chars",
             "source_anchor": "<=120 chars quote"}],
 "abstention_note": "optional"}
```

**Claim Verification 3층 구조** (판정자는 실행 시스템, 설계만):

1. *원문 근거 위치*: `source_anchor`가 해당 Note에 존재하는가 (문자·
   정규화 수준).
2. *주장 내용*: claim이 원문 근거 위치에서 성립하는 내용인가 (차원별
   판정 규칙).
3. *의미적 일치*: claim의 종류가 심어진 오류 유형과 실질 동일한가 —
   R7-E1에서는 **정적 규칙 + 수동 검토**로 판정; 모델 기반 검증기는
   이 단계에서 구축·실행하지 않음 (E2 후보로만 기록).

상태: `VERIFIED` / `OVER_CLAIM_REJECTED` / `PENDING_HUMAN_REVIEW` /
`PARSE_FAILURE` / `INVALID_SCHEMA` / `ABSTAINED`.

## 3. R7-E1 → R7-E2 확장·중단 기준 (E1 전 동결 예정, E1 승인 시 최종 확정)

**확장(E2) 후보 조건** (E1, n≈12, VALID 기준):
- Claim Precision ≥ 0.8 (Wilson 하한 ≥ 0.6)
- Claim Recall ≥ 0.7 (하한 ≥ 0.5)
- Evidence Grounding ≥ 0.9
- FPR ≤ 0.2
- Abstention: 유보 대상에서 유보율 ≥ 0.5, 비유보 대상에서 과다 유보
  (≥ 0.4) 아님
- Cost per Valid Judgment ≤ 2,000 tokens

**중단 기준**: PARSE/SCHEMA 실패율 > 0.3, 예산 초과, Permit/Ledger
계약 위반, Gold Gate 사후 붕괴(CONFLICTED 전이), 증거 영속화 실패 —
즉시 중단, 재시도 없음.

## 4. Admission Checklist (R7-E1 승인 요건 — 문서 1 §8)

| # | 요건 | 증거 위치 |
|---|---|---|
| 1 | Unseen 논문 단위 분리 증명 (교집합 ∅) | `poc/runs/r7-evaluation/separation-proof.json` (E1 전 생성) |
| 2 | Gold Validity Gate 통과 | `poc/runs/r7-evaluation/gold-gate.json` |
| 3 | 지표·집계 규칙 동결 | 본 문서 §1 |
| 4 | Judge Prompt·출력 스키마 동결 | 본 문서 §2 + 동결 스냅샷 |
| 5 | 실행 대상·호출 수 확정 | `poc/runs/r7-evaluation/e1-plan.json` |
| 6 | Token·GPU·Wall-clock 예산 산정 | e1-plan.json (예상 ~16k tokens) |
| 7 | Owner Approval / Permit 계약 | R6I 계약 재사용 (`poc/execution_permit.py` 무변경) |
| 8 | 실패·Abstain·Evidence 불충분 처리 규칙 | 본 문서 §1·§3 |

Admission 통과해도 **자동 실행 금지** — 별도 Owner 승인 후
`owner_issue_permit.py` → runner 순서.

## 5. E1 실행 예상 비용

- 호출 12회 × (입력 ~1,000 + 출력 ~250) ≈ **15,000 tokens**
  (±30% — Challenge 길이 편차)
- Wall: 12 × ~3.5s ≈ 45s + 수동 검토 시간 별도
- GPU: 공유 vLLM 서버 — upper-bound 기록(R0-b2 구분 유지), measured 없음
