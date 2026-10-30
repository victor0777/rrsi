---
doc_id: poc-rrsi-54-rrsi-integration-boundary-r2
title: RRSI-INTEGRATION-BOUNDARY-R2 — Identity, Revision & Contract Boundary Closure
status: report
updated: 2026-10-30
---

# RRSI-INTEGRATION-BOUNDARY-R2 — Identity, Revision & Contract Boundary Closure (문서 54)

기준: RRSI `e952cc5` (baseline main HEAD) · Workbench
`research_benchmarks@f9918e1` (변경 0) · Researcher
`research_agent@2fe7fa52` (변경 0). 모델 호출 0, Task 실행 0.
작업 착수 시점 미커밋 변경: `poc/rest_preflight_r1.py`,
`poc/tests/test_rest_preflight_r1.py` (이번 작업 일부로 흡수).

구현: `poc/integration_boundary_r2.py` (신규) +
`poc/rest_preflight_r1.py` (레지스트리·결과매핑 수정) +
테스트 `poc/tests/test_integration_boundary_r2.py` (28) /
`poc/tests/test_rest_preflight_r1.py` (27).

## 1. WS-A — Identity / Revision 분리

### A1. Identity Triple — 구현

Candidate는 (candidate_id, candidate_revision,
candidate_content_digest) 삼중으로 식별 (`candidate_identity()`).
내용 변경 ⇒ **새 Revision** (`derive_revision()` — r1→r2→r3 단조).
기존 Revision의 digest는 결코 덮어쓰지 않으며, 이전 Revision은
자신의 원본 내용에 대해 계속 검증 가능
(`test_ws_a1_identity_triple_and_content_change_new_revision`).
동일 Revision + 다른 digest ⇒ `REVISION_DIGEST_MISMATCH`
무결성 오류 (새 버전으로 해석 안 함,
`test_ws_a1_same_revision_different_digest_integrity_error`).

### A2. Evaluation Snapshot Binding — 구현

8필드 (evaluation_id, candidate_id, candidate_revision,
candidate_content_digest, baseline_revision,
baseline_content_digest, evaluation_contract_version,
evaluation_policy_version) 스냅샷 — 생성 시 고정, 불변
(`EvaluationSnapshotBinding.seal/verify`). 새 Revision은 기존
Evaluation의 스냅샷을 결코 재작성하지 않음
(`test_ws_a2_snapshot_binding_fixed_and_immutable`). 불완전
생성 ⇒ `SNAPSHOT_INCOMPLETE` (`test_ws_a2_snapshot_incomplete_rejected`).

### A3. Resume 정책 — Snapshot 기반 (R2.3.1 미약화)

`resume_against_snapshot()`은 **실행 시점 스냅샷**에만 비교:
evaluation id / candidate id / revision / digest /
baseline digest / policy version / task binding id —
최신 Candidate는 결코 조회하지 않음. 최신 Candidate가
변경되어도 기존 Evaluation의 Resume은 허용되고
(`test_ws_a3_latest_candidate_change_never_blocks_old_resume`),
스냅샷 digest 불일치는 거부됨
(`test_ws_a3_snapshot_digest_mismatch_rejected`).
R2.3.1 Full Identity Binding은 약화되지 않음 — 6필드 전부
스냅샷 자체 값과 대조 (EVALUATION_ID/CANDIDATE_ID/
CANDIDATE_REVISION/CANDIDATE_DIGEST/BASELINE_DIGEST/
POLICY_VERSION 불일치 + TASK_BINDING_IDENTITY_MISSING,
`test_ws_a3_baseline_and_policy_and_task_binding_required`).
Controller 수준 회귀: 스냅샷 봉인 후 최신 candidate 변경 →
resume 성공 + 스냅샷 값 보존; 스냅샷 변조 → 거부
(`test_controller_resume_after_latest_candidate_changed`).

## 2. WS-B — SHA 결합 범위 교정

- **B1 무결성 전용**: SHA-256은 Revision · Snapshot · Binding
  Record · Result/Evidence · 실행 Provenance의 무결성에만
  사용. Repository HEAD 핀, API 호환성 판단, 최신/구 Candidate
  식별로 사용하지 않음 (모듈 docstring에 정책 고정).
- **B2 Contract 호환성**: `contract_compatible()` —
  (contract_name, contract_version, required_capabilities,
  schema_validation)로 판단. 호환 계약은 상이한 커밋 SHA에서도
  연결되고 (`test_ws_b_compatible_contract_connects_across_differing_shas`),
  동일 SHA라도 계약 미충족 시 거부되며
  (`test_ws_b_identical_sha_still_refused_when_contract_unmet`),
  필수 Capability 누락은 `CONTRACT_CAPABILITY_MISSING:<cap>` 명시
  (`test_ws_b_missing_required_capability_refused`). Git SHA는
  결코 조회하지 않음.
- **B3 정규화 규칙 보존**: 기존 canonical JSON digest 규칙
  (UTF-8 · ensure_ascii=False · sort_keys · compact) 변경 없음.
  digest 의미론을 조용히 바꾸지 않음 — 계약 충돌 시 신규
  Contract Version 제안 절차를 요청으로 기록 (§7).

## 3. WS-C — Binding Registry 결함 수정

### C1. 권위 분리 — 확정

Workbench = 영속 evaluation↔task binding 권위 / RRSI = 검증 +
읽기 전용 프로젝션 / Researcher = task identity·실행 결과 권위.
RRSI 내부 `BindingRegistry`는 **TEST/PROTOTYPE 전용**임을
docstring·테스트로 고정 — 영속 권위 선언 금지.

### C2. 멱등/충돌 테이블 — 6행 구현

| 조건 | 결과 |
|---|---|
| 동일 key + 동일 request digest + 동일 binding | 기존 binding 반환 (멱등) |
| 동일 key + 다른 request digest | `IDEMPOTENCY_CONFLICT` |
| 동일 evaluation + 다른 task id | `EVALUATION_BINDING_CONFLICT` |
| 동일 task id + 다른 evaluation | `TASK_BINDING_CONFLICT` |
| 동일 candidate + 다른 revision | 별도 binding (분리) |
| 동일 revision + 다른 content digest | 무결성 오류 (`REVISION_DIGEST_MISMATCH`) |

E2 부정 테스트: 동일 task id + 다른 evaluation 거부
(`test_e2_same_task_id_different_evaluation_rejected`),
동일 key + 다른 request 거부
(`test_e2_same_key_different_request_rejected`).

### C3. 공식 Binding Record 검증 — 구현

`verify_official_binding_record()` — 스키마
`research-bench-evaluation-task-binding/v0.1` 고정, 필드
부재 시 **가정·생성 금지**: 권위 필드 (contract_version,
evaluation_id, task_id, candidate_id, candidate_content_digest,
baseline_content_digest, policy_version, binding_record_digest)
누락 ⇒ `BINDING_AUTHORITY_UNAVAILABLE:<field>`;
capability 필드 (candidate_revision, baseline_revision,
configuration_identity) 누락 ⇒
`CONTRACT_CAPABILITY_MISSING:<field>`. 자기제외
binding_record_digest 재계산 불일치 ⇒ `BINDING_RECORD_TAMPERED`
(`test_ws_c3_*` 4건).

### C4. 재시작 복구 경계 — 구현

`restart_recovery()` — RRSI 내부 인메모리 상태만으로 복구
선언 금지. 공식 binding 조회 불가 ⇒ `RESTART_RECOVERY_BLOCKED`
+ task 재생성 0; identity 불일치 ⇒ BLOCKED; 공식 조회로만
CONFIRMED (`test_ws_c4_*` 3건). 모든 경로 task_recreated=False.

## 4. WS-D — 결과 매핑 경계 강화

`map_task_result_to_evaluation_result()` — 고정 10단계 검증 순서:
1 binding record integrity → 2 evaluation/task identity →
3 candidate id/revision/digest → 4 baseline revision/digest
(**누락은 결코 조건부 스킵되지 않고 `BASELINE_IDENTITY_MISSING`
거부** — 기존 `if identity.get("baseline_digest") and ...` 조건 제거) →
5 policy version → 6 result schema → 7 result digest/provenance →
8 usage schema → 9 evidence/answer → 10 task status → evaluation result.

- **D2 비종료 상태 보존**: CREATED/QUEUED/RUNNING → `PENDING`,
  BLOCKED → `BLOCKED` (resumable 보존) — 결코 CANCELLED로
  축소하지 않고 결코 완료된 평가로 변환하지 않음
  (`test_wsd_blocked_status_preserved`).
- Usage 누락/null/bool/음수 → `BUDGET_ACCOUNTING_UNKNOWN`
  (결코 0 해석 안 함, `test_wsd_usage_missing_rejected`).
- Task id 변경 / result digest 변조 / policy 불일치 → 거부
  (`test_wsd_task_id_change_blocked`, `test_wsd_result_digest_tamper_blocked`,
  `test_wsd_policy_version_mismatch_blocked`).
- 검증 통과 usage만 Controller Ledger에 누적 (R2.3 규칙 유지).

## 5. WS-E — 가짜 PASS 제거

- **E1 T07 수정**: 기존 `assert not identity_chain_ok(tampered)
  is None or True` (항상 참) 제거. 신규 T07은 실제 레지스트리
  경로에서 동일 evaluation의 task-id 변경 시도를 거부하고,
  변조 binding의 자체 무결성(`identity_chain_ok(tampered)`)과
  원본 보존을 각각 실제 코드로 검증.
- **E2 필수 부정 테스트 13종 전부 구현**: candidate id 동일 +
  revision 변경(분리) · 동일 revision + digest 불일치(거부) ·
  기존 Evaluation Resume 중 최신 candidate 변경(허용) ·
  baseline digest 누락(거부) · binding record digest 변조(거부) ·
  동일 key + 다른 request(거부) · 동일 task id + 다른 evaluation(거부) ·
  policy version 불일치(거부) · 필수 capability 누락(거부) ·
  researcher usage 누락(거부) · BLOCKED 상태 보존 ·
  result digest 변조(거부) · workbench binding 조회 불가(BLOCKED).
- **E3 전체 회귀**: RRSI 332/332 PASS (기존 304 + 신규 28, 회귀 0).

## 6. WS-F — 타 Repository Contract Request (구현 대기)

RRSI 측 검증 로직과 테스트는 먼저 완성됨 (§1–§5). 아래 외부
계약은 미구현이며 **BLOCKED/PENDING으로 표시** — 구현 완료로
표시하지 않음.

### WB (Workbench 소유자) — 요청 8건

| # | 요청 | RRSI 측 필요 정보 |
|---|---|---|
| WB-1 | 공식 evaluation↔task binding 조회 API | evaluation_id → (task_id, candidate_id/revision/digest, baseline_digest, policy_version, configuration_identity) 반환; 권위 소재·보존 기간 |
| WB-2 | Candidate revision/digest 공식 표면 | revision 표기(rN) · content digest 전달 위치 · revision 간 구분 규칙 |
| WB-3 | Baseline revision/digest 공식 표면 | baseline revision(rN) · digest 전달 위치 (input payload vs 전용 필드) |
| WB-4 | Task id 바인딩 | canonical record의 task_id 필드 또는 별도 레지스트리 소유 결정 |
| WB-5 | Binding record 무결성 | record digest 알고리즘(자기제외 canonical JSON) · 검증 실패 시 반환 계약 |
| WB-6 | 재시작 후 조회 보장 | 재시작 창에서 binding 조회 가능 보장/SLA, 불가 시 상태 코드 |
| WB-7 | 멱등/충돌 의미론 | 동일 key/eval/task 충돌 시 공식 오류 코드 (RRSI C2 테이블과 정렬) |
| WB-8 | digest 의미론 충돌 시 | 신규 Contract Version 제안 절차 (기존 digest 규칙 조용히 변경 금지) |

### RA (Researcher 소유자) — 요청 6건

| # | 요청 | RRSI 측 필요 정보 |
|---|---|---|
| RA-1 | COMPLETED result usage 필드 | result_ref에 model_calls/tool_calls/tokens_used 추가 (문서 53 §7.1 결함 제안과 동일) |
| RA-2 | Usage 측정 원천 | 누가 어떤 계측으로 usage를 산출하는지 (권위 경계) |
| RA-3 | Task/Request ID 전달 | request_id(evaluation id) ↔ task_id 대응 공식 규칙 |
| RA-4 | Result digest | terminal 결과 sha256 재계산 알고리즘·커버 필드 |
| RA-5 | 상태 의미론 | CREATED/QUEUED/RUNNING/BLOCKED 비종료 보존, BLOCKED resumable 규칙 |
| RA-6 | Result identity 전송 | identity(candidate/baseline/policy) 전달 위치와 API contract version/capabilities 표기 |

각 요청의 구현 완료 전까지 대응 RRSI 검증은 fail-closed(BLOCKED)
동작을 유지하며, 외부 계약을 구현된 것으로 표시하지 않는다.

## 7. 수용 기준 판정 (15항목)

1 RRSI만 변경 — **PASS** (Workbench `f9918e1` · Researcher `2fe7fa52` 유지)
2 Identity/Revision 분리 — **PASS** (§1.1)
3 Snapshot 불변 — **PASS** (§1.2)
4 최신 candidate 변경 후 resume — **PASS** (§1.3, 단위 + controller)
5 Binding 충돌 수정 — **PASS** (§3.2, 6행)
6 Baseline 누락 거부 — **PASS** (§4)
7 T07 수정 — **PASS** (§5 E1)
8 비종료 상태 보존 — **PASS** (§4 D2)
9 회귀 통과 — **PASS** (332/332)
10 Workbench/Researcher 변경 0 — **PASS**
11 모델 호출 0 — **PASS**
12 미구현 항목 BLOCKED/PENDING 표시 — **PASS** (§6)
13 Canonical digest 규칙 보존 — **PASS** (§2 B3)
14 공식 binding record 검증 — **PASS** (§3.3)
15 재시작 task 재생성 금지 — **PASS** (§3.4)

## 8. 최종 상태

**`RRSI_INTEGRATION_BOUNDARY_READY`**

단, 이는 RRSI 측 계약 준비 완료일 뿐이다. 타 Repository 연동
완료(문서 54 §6 요청 처리)도 아니고, 실제 평가 실행 허가도
아니다. 실제 Researcher 모델 평가 및 RRSI Improvement Iteration은
Owner의 별도 명시적 승인 전까지 HOLD한다
(`REAL_EVALUATION_ADMITTED = False` 유지).
