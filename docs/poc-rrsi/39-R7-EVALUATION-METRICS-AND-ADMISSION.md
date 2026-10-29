---
doc_id: poc-rrsi-39-r7-metrics-admission
title: R7 Evaluation Metrics and Admission
status: design
updated: 2026-10-29
---

# R7 — Evaluation Metrics & Admission (R7-D0 문서 3)

## 1. 지표 정의 — 분모·집계 단위·Abstain 정책 (D1 수정)

집계 단위: **사례(case) = (논문, note 변형, 차원)** — 논문이 아님.
주 집계 분모는 **Gold Quality Gate VALID 사례 전부** (CONFLICTED/
INSUFFICIENT_EVIDENCE/EXCLUDED는 부록).

**P1-2 수정 — 파싱 실패를 분모에서 빼지 않는다.** Agreement는 이중
보고하며 주 판단에는 End-to-end를 사용:

| 지표 | 정의 | 역할 |
|---|---|---|
| **End-to-end Agreement** | 정답 판정 수 / **전체 VALID 사례** | **주 성능 지표** — 파싱 실패·스키마 무효는 자동으로 비판정(실패)으로 반영 |
| Conditional Agreement | 정답 판정 수 / 유효하게 파싱된 판정 | **진단용** — 파싱 성공 시 판정 품질만 |
| Schema Success Rate | 유효 출력 수 / 전체 호출 | 실행 신뢰성 |
| Abstention Rate | 유보 수 / 전체 VALID 사례 | 과다/과소 유보 진단 |

| 지표 | 정의 | 분모 | Abstain 처리 |
|---|---|---|---|
| Claim Precision | 실제 오류인 Judge 주장 / 전체 Judge 주장 | 주장 단위 (VALID) | Abstain 사례의 미제기 주장 제외 |
| Claim Recall | 발견된 실제 오류 / 심어진 실제 오류 | 심어진 오류 단위 (VALID) | Abstain 사례 오류는 미발견으로 집계 + 병기 |
| Evidence Grounding | 인용이 실제 해당 텍스트에 존재 비율 | 인용 단위 | 인용 없는 주장 = 미그라운딩 집계 |
| False Positive Rate | 정상(반사례) 사례를 오류로 비판 비율 | 반사례 사례 (VALID) | Abstain은 FP 아님 |
| Abstention Quality | 유보 적절율 | 유보 대상 + 비유보 대상 사례 | — |
| Cost per Valid Judgment | (입력+출력 tokens·latency) / 유효 판정 | 유효 판정 | — |

- **PARSE_FAILURE / INVALID_SCHEMA**: End-to-end 분모에는 포함(비판정),
  Conditional 분모에서는 제외, INCONCLUSIVE 개별 기록 (R6I 계약 승계).
- **표본 독립성 주의 (P1-3)**: 동일 논문에서 파생된 사례는 독립이 아니므로
  case-level Wilson 신뢰구간은 **논문 내 재현의 불확실성**일 뿐,
  새 논문 일반화 신뢰구간이 아님 — 보고 시 논문급(cluster) 결과를 병기.
- **소표본**: n<30이면 신뢰구간 병기, 점추정 단독 해석 금지.
- Challenge 레이어 집계는 별도 표 (주 지표 혼합 금지).
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
             "anchors": {... — 아래 계약}}],
 "abstention_note": "optional"}
```

**P2-1 수정 — Claim Anchors 계약 (kind별 필수 근거 분리):**

| 주장 종류 | 필수 anchors |
|---|---|
| `numeric_error` | `quoted_text` (대상 Note 내 존재 구절) + `expected_from_source` (원문 근거) |
| `info_loss` | **3-anchor 필수**: ① `original_note_anchor` — 원본 Note에 해당 정보가 존재했던 위치 인용, ② `absence_evidence` — 대상 Note에서 제거됐다는 근거(인접 문맥 인용 — 원문 문장은 존재하지 않으므로 "제거"는 인접 구절 대조로 증명), ③ `importance_evidence` — 원문 논문에서 그 정보가 실제로 중요하다는 근거 |
| `missing_evidence` | `quoted_text` (근거 없는 주장 인용) + `absence_evidence` (원문에 대응 근거 없음) |
| `contradiction` | `quoted_text_a` + `quoted_text_b` (상호 모순 구절 2건) |

**Claim Verification 3층 구조** (판정자는 실행 시스템, 설계만):

1. *원문 근거 위치*: 위 계약의 각 anchor가 실제로 존재하는가 (문자·
   정규화 수준).
2. *주장 내용*: claim이 anchors에서 성립하는 내용인가 (차원별 판정
   규칙) — info_loss는 3-anchor가 모두 성립해야 함. 이 구분이 R6H의
   부분 소실 vs 방법론 전체 소실 혼동 재발을 막는다.
3. *의미적 일치*: claim의 종류가 심어진 오류 유형과 실질 동일한가 —
   R7-E1에서는 **정적 규칙 + 수동 검토**로 판정; 모델 기반 검증기는
   이 단계에서 구축·실행하지 않음 (E2 후보로만 기록).

상태: `VERIFIED` / `OVER_CLAIM_REJECTED` / `PENDING_HUMAN_REVIEW` /
`PARSE_FAILURE` / `INVALID_SCHEMA` / `ABSTAINED`.

## 3. R7-E1 → R7-E2 전환·중단 기준 (D1 재정의 — E1 전 동결, E1 승인 시 최종 확정)

**P1-3 — R7-E1의 목적 재정의**: E1은 성능 입증 단계가 아니라 **평가
계약·실패 모드·실행 가능성 검증** 단계. case-level 수치를 일반화 성능
증거로 보고하지 않는다. E2는 일반화 성능 확인을 위한 더 넓은 평가
(논문 수 확대) 단계로 설계.

**E2 승격 후보 조건** (성능 임계 + 신뢰성·실행 가능성·오판 포함):
- Schema Success Rate ≥ 0.7 (파싱 계약이 실제로 작동하는가)
- PARSE/SCHEMA 실패 모드가 재현·기록·해석 가능 (원인별 분류 완료)
- Gold 사후 무결성: Gate 통과 사례 중 CONFLICTED 전이 0건
- 중대한 오판 없음: 반사례(정상 Note)를 "오류"로 주장한 성격이
  문서화되고, 유보 대상 사례에서 Judge가 정상 판정을 내린 건 없음
- End-to-end Agreement의 논문급(cluster) 결과가 성능 지표로 **보고
  가능 수준** (점수 자체의 문턱은 E2 설계에서 확정 — E1 표본으로
  임계 확정 금지)
- Cost per Valid Judgment ≤ 2,000 tokens

**중단 기준**: PARSE/SCHEMA 실패율 > 0.3, 예산 초과, Permit/Ledger
계약 위반, Gold Gate 사후 붕괴(CONFLICTED 전이), 증거 영속화 실패,
승인 범위 밖 사례 실행 — 즉시 중단, 재시도 없음.

## 4. Admission Checklist (R7-E1 승인 요건 — 문서 1 §8)

| # | 요건 | 증거 위치 |
|---|---|---|
| 1 | Unseen 논문 단위 분리 증명 (ID·버전 교집합 ∅ **+ 노출 이력 조사 기록**) | `poc/runs/r7-evaluation/separation-proof.json` (E1 전 생성) |
| 2 | Gold Validity Gate 통과 | `poc/runs/r7-evaluation/gold-gate.json` |
| 3 | 지표·집계 규칙 동결 | 본 문서 §1 |
| 4 | Judge Prompt·출력 스키마 동결 | 본 문서 §2 + 동결 스냅샷 |
| 5 | 실행 대상·호출 수 확정 | `poc/runs/r7-evaluation/e1-plan.json` |
| 6 | Token·GPU·Wall-clock 예산 산정 | e1-plan.json (예상 ~16k tokens) |
| 7 | Owner Approval / Permit 계약 | R6I 계약 재사용 (`poc/execution_permit.py` 무변경) |
| 8 | 실패·Abstain·Evidence 불충분 처리 규칙 | 본 문서 §1·§3 |

Admission 통과해도 **자동 실행 금지** — 별도 Owner 승인 후
`owner_issue_permit.py` → runner 순서.

## 5. E1 실행 예상 비용 (P2-2 단일 예산표)

| 항목 | 추정 |
|---|---|
| 모델 호출 | 12회 (g4·g7 유형 프롬프트 기준) |
| 입력 | 12 × ~1,000 tokens = ~12,000 |
| 출력 (한도 500/호출) | 12 × ~250 tokens = ~3,000 |
| **총 토큰 예산** | **~15,000 (상한 20,000로 승인 요청 권장)** |
| Wall | 12 × ~3.5s ≈ 45s |
| GPU | 공유 vLLM 서버 — upper-bound 기록만 (R0-b2 구분 유지) |
| 수동 검토 | **검토자 1인당 9–12시간, 2인 기준 18–24인시** + 불일치 조정 별도 |

E1 실행 승인 시 실제 입력 길이·출력 한도 기준으로 본 표를 갱신 후
동결한다. (문서 37 §8의 "≈16k"는 본 표로 통일 — 15k.)
