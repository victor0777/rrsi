---
doc_id: poc-rrsi-49-r7-d2c-evaluation-boundary-closure
title: R7-D2C Evaluation Boundary Closure & Admission Correction
status: contract
updated: 2026-10-29
---

# R7-D2C — Evaluation Boundary Closure & Admission Correction (문서 49)

구현: `poc/r7_contract.py` · 테스트: `poc/tests/test_r7_contract.py`
(179/179 — 기존 162 보존, 신규 17건). R6I 운영 코드 무변경, Unseen
후보 Manifest 무변경. 모델 호출 0회. 최종 상태:
**R7_D2C_BOUNDARY_REVIEW**.

## 1. 수정 전후 경계 비교

| 영역 | D2B (문서 47) | D2C (본 계약) |
|---|---|---|
| Record Context | 허용 값만 검사 | **요청 Context와 일치 강제** (A1) |
| TEST 기록 재사용 | 가능 (context만 맞으면) | **EVALUATION에서 BLOCKED** |
| Record Digest | 전체 payload 결합 | 동일 + **context 변경 시 무결성 실패 확인** (A3) |
| EVALUATION 승격 | REGISTERED 비합성이면 가능 가능성 | **Governance Gate — 운영 준비 전 전면 차단** (B2) |
| Residual Review | status/verdict 일부 검사 | **6필드 strict schema + reviewer/evidence 결합** (C1–C3) |
| Manifest 결합 | 실패 시 problems만 추가 | **결합 실패 시 manifest 미생성 + 최종 FAILED 반영** (C4) |
| Admission 7 | SATISFIED (계약/실행 혼동) | **Contract Reuse / Execution Permit 분리, BLOCKED** (D1) |

## 2. Context Binding 계약 (Workstream A)

| Review Record | Request | 결과 |
|---|---|---|
| TEST | TEST | 허용 |
| TEST | EVALUATION | BLOCKED |
| EVALUATION | TEST | BLOCKED |
| EVALUATION | EVALUATION | 후속 Governance Gate |
| Missing | EVALUATION | BLOCKED |
| Invalid | Any | BLOCKED |

- 검사는 **최종 상태 결정 전** 수행 — 실패 시 review invalid →
  승격 불가.
- 기록: Request/Record Context, Binding Result, Failure Reason,
  Evaluation Eligibility (`record.context_binding`).
- **A3 재사용 방지**: digest는 verification_context 포함 — TEST로
  서명된 기록을 EVALUATION으로 바꾸면 `REVIEW_RECORD_DIGEST_INVALID`
  (T04). context 필드만 수정해 통과하는 경로 차단.
- 하위 호환: context 누락은 **TEST에서만** 합성 Fixture로 허용,
  EVALUATION에서는 절대 불허.

## 3. Reviewer Governance Fail-closed (Workstream B)

- `_REVIEWER_REGISTRY` = **in_memory_test_scaffold** — 운영 registry
  아님. `governance_state = REVIEWER_GOVERNANCE_NOT_READY` (본 단계
  기본값).
- `reviewer_governance_ready()` — 본 단계에서 **항상 False**; 활성화
  기능 미구현 (계약만).
- Gate (B2): EVALUATION 요청 중 governance 미준비 →
  `PENDING_HUMAN_REVIEW` + `evaluation_eligible=False` +
  `gate_reason=REVIEWER_GOVERNANCE_NOT_READY`. 비합성·REGISTERED·
  approved_by/approved_at 보유·digest 정상·CONFIRMED·IMPORTANT를 모두
  만족해도 차단 (T05/T06).
- **B3 증거 계약** (`GOVERNANCE_READY_EVIDENCE_CONTRACT`): 영속
  Registry / Version+Digest / Owner 승인 기록 / Identity Binding /
  승인·철회 이력 / 기록-Registry Snapshot 결합 / 승인된 Evaluation
  Permit — 단순 boolean으로 활성화 금지.
- **B4 우회 방지**: `register_reviewer()`는 TEST 스캐폴드 전용 —
  등록만으로 EVALUATION 승격 불가. 기록에 registry_type/version/
  digest/governance_state/evaluation_eligible 포함.

## 4. Residual Review Strict Schema (Workstream C)

- **C1 필수 6필드**: reviewer_id, review_status, verdict, rationale,
  review_evidence_refs (+location_id 검증). 허용 값 외
  (`MAYBE`, `SORT_OF_EQUIVALENT` 등) → 절대 VERIFIED 아님 (T07/T08);
  미등록 Location ID → FAILED; 근거 비어있거나 rationale <10자 →
  PENDING.
- **C2 Reviewer Binding**: location review의 reviewer_id가 Human
  Review Record reviewer와 불일치 → **PENDING** (암묵 동일 검토 처리
  금지, T09).
- **C3 Evidence Binding**: ref의 document_id/digest/locator가 실제
  manifest 위치와 일치해야 함 — 다른 문서 버전 참조 → **FAILED**
  (T10).
- **C4 Manifest Binding**: `documents[document_id] != perturbed_note`
  → `ResidualManifestError` (manifest 미생물 없음 — 잘못된 manifest를
  정상 결과로 반환 금지). 오류는 `manifest_error`로 반환되고 **최종
  상태 FAILED에 반영** (T12) — `review["problems"]`만 추가하고
  `valid`를 유지하는 방식 금지.
- **C5 우선순위**: Manifest 결합 실패 FAILED / Schema 오류
  PENDING·FAILED / Reviewer 결합 PENDING / Evidence 결합
  PENDING·FAILED / 미검토 PENDING / 동등 정보 FAILED / 불확실
  PENDING / 전부 검토·비동등 → Residual 단계 VERIFIED 가능 —
  EVALUATION에서는 Governance Gate 추가 통과 필요 (T13 vs T14).

## 5. Manifest Binding 검증 결과

`build_residual_manifest`: registry=13,000 버전 + probe=12,000 텍스트
→ `RESIDUAL_MANIFEST_DOCUMENT_BINDING_FAILED` → `manifest_error` →
최종 `FAILED`. 기존 D2B T10은 "problems-only" 방식에서 raise 방식으로
갱신 (변경 사유: C4 금지 규정 준수).

## 6. Admission 7번 정정 (Workstream D1)

| 항목 | 상태 |
|---|---|
| **Contract Reuse Authorization** | R6I 계약 구성요소(permit 경로, blind mechanics, /tokenize 계측)는 계약으로 재사용 가능 — 원 승인 범위는 R6I g4/g7에 한정, **기존 근거 확인 필요** (Owner 확인 대기) |
| **R7-E1 Execution Permit** | **NOT_GRANTED** — 별도 Owner 승인·데이터 범위·호출 예산·GPU/Wall 예산·실행 기간·중단 조건 전부 미승인 |
| **Admission 7 (합산)** | **BLOCKED** — 계약 재사용 승인만으로 실행 승인 아님 (T15/T16) |

Admission 1–6, 8은 유지; 최종: 3 SATISFIED, 4 PARTIAL, **1 BLOCKED
(7번 — 정정)**.

## 7. Readiness State 재판정 (D2)

| 상태 | 판정 | 의미 |
|---|---|---|
| `STATIC_CONTRACT_READY` | **True** | 정적 계약·테스트 통과 |
| `EVALUATION_BOUNDARY_READY` | **True** | **미준비 운영 조건의 fail-closed 차단이 검증됨 — 실행 가능 의미 아님** |
| `REVIEWER_GOVERNANCE_READY` | **False** | 운영 Registry·Owner 승인 없음 |
| `DATASET_READY` | **False** | Note 0/8, Gold 없음 |
| `E1_ADMITTED` | **False** | Permit 없음 |

## 8. 테스트 — 신규 17건

T01–T16 (표 순서) + **불변식 테스트**: 정상·비정상 입력 5종 ×
EVALUATION 요청 → 전부 `status != VERIFIED` ∧
`evaluation_eligible=False`. 기존 D2B T07/T10 2건은 정책 변경으로
갱신 (변경 사유: Governance Gate + C4). **179/179 PASS.**

## 9. 남은 차단 요인 / Owner 결정 필요 사항

1. 운영 Reviewer Registry 구현·영속 저장소 (Owner 승인 후).
2. 독립 검토자 2인 지정.
3. **R7-E1 Execution Permit 발급 여부** (현재 NOT_GRANTED).
4. Contract Reuse Authorization 원 근거 확인.
5. Reader Note 생성 승인, 토큰 상한, Gold Gate 후 Freeze.

**R7-D2C 완료는 R7-E1 실행 승인이 아니다.**
