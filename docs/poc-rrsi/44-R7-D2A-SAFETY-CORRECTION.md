---
doc_id: poc-rrsi-44-r7-d2a-safety-correction
title: R7-D2A Verification Safety Correction
status: contract
updated: 2026-10-29
---

# R7-D2A — Verification Safety Correction (문서 44)

구현: `poc/r7_contract.py` · 테스트: `poc/tests/test_r7_contract.py`
(131/131 전체 스위트 통과 — 신규 9건, 2건 수정). R6I 운영 코드
무변경. 모델 호출 0회. 최종 상태: **R7_D2A_SAFETY_VERIFIED**.

## 1. Human Review 계약 (§A — `validate_human_review`)

- `human_review: bool` **제거** → 구조화된 Human Review Record.
- 필수 필드: `reviewer_id`, `claim_id`, `document_digests`,
  `global_absence_verdict`, `source_importance_verdict`, `rationale`,
  `review_scope` — 전부 무결성 검증 대상.
- 기록 존재만으로 VERIFIED 금지. 판정 불명확/미기록 →
  `PENDING_HUMAN_REVIEW`; 부정적 판정(absence REFUTED, importance
  NOT_IMPORTANT) → `FAILED`.
- 기록의 문서 Digest는 등록 문서 sha256과 대조 — 불일치 시 무결성
  실패로 VERIFIED 불가.

## 2. Document Binding (§B)

`verify_info_loss` 내 정적 바인딩: Original Note / Perturbed Note /
Source Paper의 **전달된 텍스트**가 `documents` 등록본과 byte 일치해야
함. 버전 혼합 → `DOCUMENT_VERSION_CONFLICT` → `FAILED` (fail-closed).
동일 규칙이 Review Record digest에도 적용.

## 3. Judge Schema Strict Validation (§C — `validate_judge_output`)

| 검증 | 위반 코드 |
|---|---|
| 허용 필드 목록 외 필드 (최상위·claim) | `EXTRA_FIELD_FORBIDDEN` |
| 정확한 자료형 (bool exact, list[str], dict) | `*_NOT_*` |
| Claim ID 중복 | `DUPLICATE_CLAIM_ID` |
| Evidence Reference 무결성 (refs ⊆ evidence_refs) | `UNKNOWN_EVIDENCE_REF` |
| Abstention↔UNDECIDABLE↔ABSTAINED 양방향 일관성 | `ABSTENTION_*` / `UNDECIDABLE_REQUIRES_ABSTENTION` |
| 길이 제한 (claim_text ≤200, claim_id ≤32) | `*_TOO_LONG` |

## 4. 입력 권한 경계 검증 (§D — `check_component_inputs`)

구성요소 입력 조립 단계에서 금지 자료 전달 여부를 확인하는 정적
경계: denied 입력에 내용 존재 → `FORBIDDEN_INPUT`; Resolver의
source는 `{locator, digest}` 메타데이터만 허용(전문/추가 키 →
`FORBIDDEN_FULL_TEXT`). `PIPELINE_ROLES` 선언은 유지하되 경계 함수가
이를 집행.

## 5. 수정 전후 판정 차이

| 사례 | 수정 전 | 수정 후 |
|---|---|---|
| 검토 기록 존재 + CONFIRMED/IMPORTANT + 어휘 부재 0 | VERIFIED (bool) | **VERIFIED** (구조화 기록 + 무결성 통과 시에만) |
| 검토 기록 존재, 판정 미기록 | VERIFIED (bool=True) | **PENDING_HUMAN_REVIEW** |
| Global Absence 부정 (REFUTED) | VERIFIED | **FAILED** |
| Source Importance 불확실 | VERIFIED | **PENDING_HUMAN_REVIEW** |
| Source Importance 부정 | VERIFIED | **FAILED** |
| 기록 digest 불일치 | VERIFIED | **PENDING_HUMAN_REVIEW** (VERIFIED 불가) |
| 등록 문서와 전달 텍스트 불일치 | 무검증 (probe만 수행) | **FAILED** (VERSION_CONFLICT) |
| Judge 미허용 필드 | 일부 필드만 차단 (JUDGE_FORBIDDEN_FIELD 2종) | **전면 차단** (allow-list) |
| claim refs ⊄ evidence_refs | 무검증 | **스키마 탈락** |
| Judge 입력에 Gold | 무검증 선언 | **경계 위반** (boundary_ok=False) |

## 6. 회귀 테스트 (신규 9건)

| 부정 사례 | 결과 |
|---|---|
| 1. 기록만 존재, 판정 없음 | PASS → PENDING |
| 2. Global Absence 부정 | PASS → FAILED |
| 3. Source Importance 불확실 | PASS → PENDING |
| 4. 기록 문서 Digest 불일치 | PASS → PENDING (VERIFIED 불가) |
| 5. 등록 문서와 전달 텍스트 불일치 | PASS → FAILED (VERSION_CONFLICT) |
| 6. Judge 미허용 최상위 필드 | PASS → EXTRA_FIELD_FORBIDDEN |
| 7. Evidence Reference 누락/미등록 | PASS → 스키마 탈락 |
| 8. Judge 입력에 Gold | PASS → FORBIDDEN_INPUT:gold |
| strict 검증 (중복 ID·자료형·길이·abstained 일관성) | PASS → 스키마 탈락 |

기존 `test_info_loss_verified_with_recorded_human_review` 등 2건은
잘못된 bool VERIFIED를 기대하므로 구조화 기록 기반으로 함께 수정함
(§E 지시 준수).
