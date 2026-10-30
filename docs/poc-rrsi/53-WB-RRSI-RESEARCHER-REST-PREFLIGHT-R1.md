---
doc_id: poc-rrsi-53-wb-rrsi-researcher-rest-preflight-r1
title: WB-RRSI-RESEARCHER-REST-PREFLIGHT-R1 — Settlement Closure & Researcher REST Integration Readiness
status: report
updated: 2026-10-30
---

# WB-RRSI-RESEARCHER-REST-PREFLIGHT-R1 — Settlement Closure & Researcher REST Integration Readiness (문서 53)

기준: RRSI `rrsi@fbcb109` · Workbench `research_benchmarks@f9918e1` ·
Researcher `research_agent@2fe7fa52` (읽기 전용 조사). 모델 호출 0,
Researcher Task 실행 0, 벤치마크 0, Gold/Held-out 무접근, 운영 배포·
Production Candidate 변경 없음.

## 1. WS-A — Settlement Closure (RRSI만 변경)

### A1. 실제 Reconciliation 경로 검증 — PASS

R2.3.1의 `test_r231_settlement_reconciliation_required_on_bad_response()`
는 어댑터 메서드를 예외 발생 이중으로 대체한 스텝 테스트 → 폐기 성격.
**신규 WS-A1 테스트는 실제 Adapter 코드 경로를 전부 실행** —
`LoopbackClientAdapter`에 전송 주입점(`transport=`)을 추가하고,
**settle-budget을 실제로 수행한 뒤 응답만 wire 수준에서 변조** (5종:
Evaluation ID 불일치 · Settlement Basis 불일치 · 음수 사용량 · 잘못된
자료형 · 필수 필드 누락) → 실제 어댑터 코드에서
`SETTLEMENT_RECONCILIATION_REQUIRED` 발생. 스텝 회귀 방지 가드 테스트
포함 (실제 settle 성공 + 실제 사용량 회수를 먼저 입증).

### A2. Settlement 멱등성 — PASS

- **응답 유실 재현**: 정산이 Workbench에서 실행된 뒤 응답이 전송 중
  유실(전송 실패) → 어댑터는 불확실 상태 인지. 재시도(실제 어댑터):
  동일 Evaluation ID · 동일 사용량(10 model calls) · `service.budget`
  및 `record.model_calls_used` 변경 없음 — **이중 정산 0**.
- Controller 중복 정산: 검증 결과 봉인 후 재수신은 멱등 (정산 1회).
- **정산 상태 조회 API 조사**: Workbench 공식 표면(get_evaluation)에
  정산 상태 조회 필드 없음 (`settlement` 키 부재를 테스트로 고정) →
  새 API를 임의로 만들지 않고 **`RECONCILIATION_BLOCKED` 기록** —
  불확실 창의 상태 조회는 불가, 재시도가 정산 경로.
- 정산 응답이 불확실한 동안 Controller는 결과를 성공 확정하지 않음
  (불확실 → ClientError, 결정 기록 없음).

### A3. Ledger Authority — 확정

| Ledger | Authority |
|---|---|
| 실제 Model Calls 사용량 | **Workbench** (`record.model_calls_used`, actual_usage) |
| 실제 Token 사용량 | 검증된 Canonical Result 또는 공식 계측 서비스 (연동 단계 확정) |
| Controller의 검증된 Token 누적값 | **RRSI** (검증 통과 결과만 누적) |
| 실행 예산 승인 | **Owner Permit** |
| Promotion 승인 | **Owner** |

**중요 (테스트 고정)**: 검증 실패로 Controller Ledger가 증가하지
않았어도 실제 모델 사용량은 0이 아니다 — Workbench 소비 기록은 검증
실패 이후에도 보존 (`test_ws_a3_verification_failure_preserves_workbench_usage`).

## 2. WS-B — Researcher Task REST API 실제 구현 (research_agent@2fe7fa52)

구현 위치: `src/research_agent/researcher_api/` — rest_service.py(318행,
in-process dispatch + HTTP 어댑터), task_store.py(파일 영속성),
task_executor.py(claim-and-run). 테스트:
`tests/test_researcher_api_rest.py` 등 다수 — **문서가 아닌 실제 구현**.

### B1. Task Lifecycle — 실제 구현 범위

| 기능 | Method/Path | 상태 | 비고 |
|---|---|---|---|
| Task 생성 | POST `/v1/tasks` | **구현** | `TASK_REQUEST_REQUIRED=(input,)` + Optional 16필드, unknown-field 거부 |
| Task 조회 | GET `/v1/tasks/{id}` | **구현** | task id 패턴 `task-[0-9a-f]{16}` |
| 실행 상태 조회 | GET (동일 조회 필드) | **구현** | `_task_view` status/parent/failure_reason 포함 |
| Result 조회 | GET `/v1/tasks/{id}/result` | **구현** | COMPLETED만 (그 외 404 fail-closed) |
| Events 조회 | GET `/v1/tasks/{id}/events` | **구현** | append-only JSONL 이벤트 로그 |
| Manifest 조회 | GET `/v1/tasks/{id}/manifest` | **구현** | model_profile/tool_policy/digests/trace |
| 취소 | POST `/v1/tasks/{id}/cancel` | **구현** | QUEUED 즉시, RUNNING은 cancel-requested → 협력 중단 |
| 실패 후 Resume | executor.resume_blocked | **구현** | BLOCKED→QUEUED, resumable=False 거부 |
| Idempotent Retry | `idempotent_create` | **구현** | `request_id` → 동일 task 반환, 다른 내용 → `IDEMPOTENCY_KEY_CONFLICT` |
| Sessions | POST `/v1/sessions` | **구현** | 세션 결합 작업은 세션 identity 대조 |

인증: Bearer 토큰(`auth_token` 설정 시) + 세션 결합 읽기 경계.
영속성: `tasks/<id>.json` (terminal 후 불변) + `<id>.events.jsonl`
(상태 진실 원) + `idempotency.json`. 무결성 검증:
`verify_task_integrity` (이벤트 시퀀스 + terminal 결과 digest) —
변조는 fail-closed.

### B2. 상태 모델 — 실제 확인

구현된 상태: `CREATED, QUEUED, RUNNING, BLOCKED` (비종료) +
`COMPLETED, FAILED, CANCELLED` (종료). `QUEUED/RUNNING/COMPLETED/
FAILED/CANCELLED`는 지시문 상태와 직접 대응; `BLOCKED`는 Workbench
상태로 축소하지 않음 (researcher BLOCKED ≠ evaluation CANCELLED —
테스트 고정). `CREATED`는 Workbench PENDING에 대응. 알 수 없는 상태는
성공으로 해석하지 않음 (`TASK_STATUS_UNKNOWN` → fail-closed, T15).

### B3. 결과 계약 — 실제 응답 필드

result_ref (`research-agent-task-result/v0.1`): answer_text /
answer_type / evidence_refs / abstained / provenance /
execution_trace / stop_reason + record의 task_id / request_id /
result_digest(terminal 결과 sha256) / execution_identity.
**결함 발견 (읽기 전용 기록)**: **COMPLETED 경로 result_ref에 usage/
ledger가 없음** — 실패 경로만 `_finish`가 ledger
({model_calls, tool_calls, tokens_used}) 보고. 사용량은 Workbench 또는
RRSI가 아닌 Researcher가 직접 보고해야 하는 권위 자료 —
`WB-RRSI-RESEARCHER-REST-PREFLIGHT-R1`의 C2 규칙상 usage 누락 →
`BUDGET_ACCOUNTING_UNKNOWN` (결코 0 해석 안 함, T09 + 별도 테스트).
**제안 (별도 워크스트림)**: COMPLETED 결과에 usage 보고 필드 추가.

## 3. WS-C — Workbench ↔ Researcher Contract Mapping

프로토타입: `poc/rest_preflight_r1.py` (무모델 fixture 기반, 지시문 WS-F 허용).

### C1. Request Mapping — Evaluation ID ≠ Task ID

```
RRSI Candidate → Workbench Evaluation Request → Researcher Task Request
```

- `map_evaluation_to_task_request()`: evaluation id를 `request_id`
  (researcher 멱등 키)로 전달 → 재시도는 동일 task; candidate digest ·
  baseline digest · policy version은 input payload로 결합 전달
  (researcher는 불투명 identity로 취급, 채점에 사용 안 함).
- `EvaluationTaskBinding` + `BindingRegistry`: **영속 조인**
  evaluation_id ↔ task_id + candidate/baseline/policy/config/input
  digest + idempotency key, 자기제외 record_digest로 변조 탐지.
  동일 evaluation의 task-id 변경은 `EVALUATION_BINDING_CONFLICT`로
  거부 (T05 — 테스트가 실제 결함 잡아 수정), 동일 키 다른 내용은
  `IDEMPOTENCY_CONFLICT` (T06).

### C2. Result Mapping — fail-closed

`map_task_result_to_evaluation_result()`: researcher COMPLETED만으로
성공 선언 안 함 (answer + usage + digest + evidence 추가 요구) · usage
누락/음수/bool → `BUDGET_ACCOUNTING_UNKNOWN` · FAILED/CANCELLED/BLOCKED
task → FAILED 평가 (정상 결과로 변환 금지, T08) · candidate/baseline
identity 불일치 차단 (T02/T03) · result_digest 재계산 검증 (T10) ·
미지 상태 → fail-closed (T15).

### C3. 책임 분리

Researcher(연구 Task 수행·Answer/Evidence/Trace 생성·실제 실행 Usage
보고) / Workbench(실행 관리·Budget·ID 연결·Canonical Result·영속화) /
RRSI(candidate 검증·결과 검증·reward/cost/risk·iteration 결정·
Promotion **요청**). Researcher의 직접 Promotion, RRSI의 Workbench
내부 Ledger 수정 경로 — 이번 단계에서 만들지 않음.

## 4. WS-D — Identity · Budget · Permit Gate

- **D1 Identity Gate**: digest↔request↔configuration↔result↔canonical↔
  decision 전 체인 — 프로토타입의 binding이 조인을 담당; RUNNING
  Resume은 Evaluation ID · Researcher Task ID · Candidate ID ·
  Candidate Digest · Policy Version 5필드 검증 (R2.3.1 구현 +
  프로토타입 조인). **Digest 없이 Candidate ID만으로 성공 처리 금지**.
- **D2 Budget Gate**: Workbench model-calls budget(Workbench 권위) /
  researcher 실제 token usage(researcher 보고 — 현재 결함 기록) /
  RRSI 승인 token budget(RRSI 검증 ledger) / wall-clock·GPU(확정 대기).
  실행 전 예약과 실행 후 실제 정산 구분 — 초과 사용량도 소비 기록
  삭제 없음.
- **D3 Permit Gate**: `CONTRACT_INSPECTION_PERMIT`(사용 — 읽기 전용
  조사) · `NO_MODEL_PREFLIGHT_PERMIT`(사용 — 무모델 테스트) ·
  `RESEARCH_EVALUATION_EXECUTION_PERMIT` **NOT_GRANTED 고정**. 프로젝트
  전체 소스에 실제 Task 생성 호출 표면 0 (T12 구조 검증: requests/
  urlopen/http.client/create_task 부재).

## 5. WS-E — No-Model Contract Test 결과 (27 tests)

| ID | 테스트 | 결과 |
|---|---|---|
| T01 | 정상 Identity Mapping | **PASS** |
| T02 | Candidate Digest 불일치 | **BLOCK** |
| T03 | Baseline Digest 불일치 | **BLOCK** |
| T04 | Policy Version 불일치 | **BLOCK** (record digest 파기) |
| T05 | Task ID 변경 | **BLOCK** (EVALUATION_BINDING_CONFLICT) |
| T06 | 중복 Request | **중복 실행 없음** (멱등 조인) |
| T07 | RUNNING Resume Identity 불일치 | **BLOCK** (R2.3.1 경계 + 조인) |
| T08 | Researcher FAILED/CANCELLED/BLOCKED/RUNNING/QUEUED | **Evaluation 성공 금지** |
| T09 | Usage 누락/null/bool/string | **BLOCK** (BUDGET_ACCOUNTING_UNKNOWN) |
| T10 | Result Digest 불일치 | **BLOCK** |
| T11 | Budget 초과 | **BLOCK** |
| T12 | Execution Permit 없음 | **실제 실행 불가** (구조 검증) |
| T13 | Settlement 응답 변조 | **RECONCILIATION_REQUIRED** (실제 어댑터 경로) |
| T14 | Settlement 응답 유실 후 재시도 | **이중 정산 없음** |
| T15 | 미지 Task 상태 | **Fail-closed** |
| T16 | Result 재수신 | **중복 Decision/정산 없음** |

NOT_EXECUTED: 실제 Researcher Task 생성·실행이 필요한 항목 전부 —
이번 단계에서 실행 금지이므로 Mock 성공을 실제 REST 성공으로 표시하지
않음.

## 6. 전체 Regression

- RRSI: **304/304 PASS** (기존 277 + preflight 27, 회귀 0)
- Workbench: **114/114 PASS** (이번 단계 변경 0, `f9918e1` 유지)
- Researcher: 변경 0 (읽기 전용), `2fe7fa52` 유지

## 7. 실제 REST 연동에 필요한 최소 변경 목록 (별도 워크스트림 제안)

1. **Researcher**: COMPLETED result_ref에 usage 보고 필드 추가
   (model_calls/tool_calls/tokens_used) — C2 사용량 권위 자료.
2. **Workbench**: Evaluation↔Task 조인 영속화 소유 결정 (Workbench
   canonical record에 task_id 바인딩 필드 또는 별도 레지스트리).
3. **Workbench**: 정산 상태 조회가 필요하면 공식 표면 확장 (현재
   RECONCILIATION_BLOCKED — 재시도가 유일한 정산 경로).
4. **RRSI**: `ResearcherTaskClient` 어댑터 — 프로토타입 매핑을 실제
   REST 호출로 승격 (Owner 승인 후).
5. Baseline identity의 researcher-side 전달 형식 확정 (input payload
   vs 전용 필드).

## 8. 미충족 사항 및 Owner 승인 필요 항목

- Researcher COMPLETED 경로 usage 미보고 (결함 — 제안만, 코드 변경
  없음).
- Workbench 정산 상태 조회 불가 (RECONCILIATION_BLOCKED).
- 실제 REST 호출 표면 검증 — `RESEARCH_EVALUATION_EXECUTION_PERMIT`
  승인 필요.
- 실제 모델 평가·RRSI Improvement Iteration — **Owner 승인 전 HOLD**.

## 9. Readiness 판정

| 항목 | 판정 |
|---|---|
| `SETTLEMENT_CLOSED` | **True** (실제 경로 reconciliation + 멱등 재시도) |
| `RESEARCHER_API_CONTRACT_READY` | **True** (B1 10기능 구현 확인; usage 보고만 결함) |
| `IDENTITY_BINDING_READY` | **True** (영속 조인 + 4필드 RUNNING 결합) |
| `BUDGET_ACCOUNTING_READY` | **True** (권위 경계 확정; researcher usage 보고는 결함 기록) |
| `PERMIT_BOUNDARY_READY` | **True** (3-Permit 분리, 실행 Permit NOT_GRANTED) |
| `NO_MODEL_PREFLIGHT_VERIFIED` | **True** (T01–T16 중 실행 가능 16건 전부) |
| `REAL_EVALUATION_ADMITTED` | **False** (이번 단계에서 반드시 False) |

**최종 상태: `REST_PREFLIGHT_READY`**

단, 이는 실제 평가 실행 허가가 아니다. 실제 Researcher 모델 평가 및
RRSI Improvement Iteration은 Owner의 별도 명시적 승인 전까지 HOLD한다.
