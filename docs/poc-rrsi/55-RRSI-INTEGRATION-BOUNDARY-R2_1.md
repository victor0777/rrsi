---
doc_id: poc-rrsi-55-rrsi-integration-boundary-r2-1
title: RRSI-INTEGRATION-BOUNDARY-R2.1 — Revision Enforcement, Task Binding Verification & Controller Integration
status: report
updated: 2026-10-30
---

# RRSI-INTEGRATION-BOUNDARY-R2.1 — Revision Enforcement, Task Binding Verification & Controller Integration (문서 55)

기준: RRSI `5f36afb` (victor0777/rrsi main) · Workbench
`research_benchmarks@f9918e1` (변경 0) · Researcher
`research_agent@2fe7fa52` (변경 0). 모델 호출 0, Task 실행 0.

구현: `poc/integration_boundary_r2.py` (CandidateRevisionRegistry +
resume 재작성) · `poc/rest_preflight_r1.py` (binding 계약 revision 필수화 +
결과매핑 재배열) · `poc/recursive_loop_r2.py` (Controller 통합) ·
테스트 `poc/tests/test_integration_boundary_r2_1.py` (F01–F18 + 실제 경로
체인, 신규 20건) 및 기존 테스트 갱신. **전체 회귀 352/352 PASS**.

## 1. WS-A — Candidate Revision의 실제 경로 적용

### A1. 데이터 흐름 조사 — 기록

| 단계 | candidate_id | candidate_revision | candidate_content_digest | baseline_revision | baseline_content_digest |
|---|---|---|---|---|---|
| generate_candidate | 후보 필드에서 생성 | **컨트롤러가 발급** (자체 Registry) | candidate_digest와 동일 값 | — | — |
| validate_candidate_step | 불변 | 불변 | drift 재계산으로 검증 | — | — |
| request_evaluation | 불변 | 불변 (evaluation_history에 기록) | 불변 | bind_baseline에서 발급 "r1" | baseline_wire |
| Workbench Request | 전달 | **전달 안 함** (R1 고정 매핑 — 아래) | 전달 (candidate_digest) | 전달 안 함 (WB-2 pending) | 전달 (baseline_digest) |
| Result Verification | 대조 | 대조 (adapter projection) | 대조 | 대조 | 대조 |
| Decision Record | — | — | candidate_digest 결합 | — | — |
| snapshot/resume | 스냅샷 | **스냅샷 최상위 필드** | 스냅샷 | 스냅샷 | 스냅샷 |

**두 Digest의 의미 비교 (지시문 A1 — Alias 판정)**: 기존 R1
`candidate["candidate_digest"]` = sha256_obj({description, profile,
envelope}) — UTF-8 · ensure_ascii=False · sort_keys · compact canonical
JSON의 `sha256:<hex>`. 신규 `candidate_identity(content)`의
`candidate_content_digest` = 동일 canonicalization 규칙의
`sha256:<hex>`. **revision content를 정확히 {description, profile,
envelope} 3키 dict로 정의**하면 두 digest는 같은 내용을 같은 규칙으로
해시 — **같은 의미임의 근거가 확보**되어 Alias 처리 근거를 문서로 기록
(값이 동일하며 `test_real_path_controller_to_decision_chain`이 동일성을
실행). Contract Version 전환 불필요 (충돌 없음).

**R1 고정 매핑 경계**: `to_workbench_request`(R1)는 unknown candidate
키를 `UNMAPPABLE_FIELDS`로 거부 — R1 공개 계약은 변경하지 않기 위해
revision은 candidate dict에 주입하지 않고 **컨트롤러 속성 +
스냅샷 최상위 필드**로 운반. wire candidate에 revision 필드를 추가하는
것은 Contract Version 전환 사항 (WB-2 요청, §5).

### A2. Revision 생성 규칙 — `CandidateRevisionRegistry`

- 동일 ID + 동일 내용 → 기존 Revision 반환 (`issue` — 신규 발급 없음)
- 동일 ID + 변경 내용 → 새 Revision (rN 단조)
- 동일 Revision + 다른 digest → `REVISION_DIGEST_MISMATCH`
  (`restore`/`verify` — 기록된 Revision은 결코 재작성되지 않음)
- 과거 Revision 불변, 자신의 원본 내용으로 계속 검증 가능
- 과거 Evaluation은 기존 Revision 참조 유지 (스냅샷 최상위 필드)

**제한의 명시 (지시문 요구)**: `rN+1` 규칙만으로 전역 단조성을 주장하지
않는다 — Registry docstring에 고정: 단조성은 **단일 RRSI 실행 내**에서만
보장; 동시 발급자·재시작·영속 레지스트리 미커버; 전역 Revision 발급은
별도 계약 (PENDING). 재시작 시 과거 Revision은 `restore()`로 재등록되며
(단조 위반·digest 충돌 거부) 이는 실행 간 병합 규칙일 뿐 전역 Authority
선언이 아님.

### A3. Controller Integration — 실제 연결 지점

`RecursiveLoopControllerR2`:
1. `generate_candidate` 오버라이드 — R1 생성 후 자체 Registry로
   Revision 발급 → `self.candidate_revision` / `self.candidate_content_digest`
   (candidate dict 미변경 — A1 경계).
2. `bind_baseline` — `self.baseline_revision = "r1"` (단일 실행 발급,
   실행 내 불변).
3. `request_evaluation` — evaluation_history 항목에 candidate_revision 기록.
4. `snapshot()` — `rrsi-loop-snapshot/v0.3`로 승격, 최상위
   `candidate_revision` / `baseline_revision` 포함.
5. `resume()` — v0.3 스냅샷에 revision 필드 **필수** (누락 시
   `CANDIDATE_REVISION_MISSING_IN_SNAPSHOT` — 조용한 r1 가정 없음);
   candidate content digest 재계산 대조 (`REVISION_DIGEST_MISMATCH`);
   registry restore는 **커밋 블록 안에서만** (실패 resume 무변경 — F15).
6. RUNNING 재연결 — 공식 Binding Record 검증 (§3.2).

호환성: R1 컨트롤러/테스트 무변경. R2 인터페이스에
`get_official_binding_record` 추가 (기본값 fail-closed
`BINDING_AUTHORITY_UNAVAILABLE`) + `OFFICIAL_BINDING_CAPABLE` 플래그 —
기존 호출자는 영향 0.

## 2. WS-B — Result Mapping의 Revision 검증 강제

### B1. 기본값 제거

`EvaluationTaskBinding.__init__`의 `candidate_revision: str = "r1"`
기본값 **삭제** — revision 미제공 시 `BINDING_REVISION_REQUIRED`
거부 (조용한 r1 없음). Legacy Fixture는 `build_legacy_binding()`
명시적 어댑터로 격리: `legacy: True` / `revision_provided: False`로
표시되며 Legacy 값이 검증된 Revision으로 오인되지 않음.

### B2. Binding 필드 — 10정보

Evaluation ID · Task ID · Candidate ID · Candidate Revision ·
Baseline Revision · Baseline Digest · Policy Version · Configuration
Identity · Configuration Digest · Binding Record Digest — 전부
EvaluationTaskBinding에 결합 (자기제외 record_digest). Workbench 공식
Binding 계약 미구현 → 합성 Fixture로 검증, **실제 API 준비 완료로
표시하지 않음** (`projection: synthetic-mock-adapter` 마크).

### B3. Result Identity — 고정 10단계 (모든 상태 공통)

1 Binding Record Digest → 2 Evaluation/Task ID → 3 Candidate ID →
4 Candidate Revision (결과에 누락 =
`CONTRACT_CAPABILITY_MISSING:candidate_revision_in_result`,
불일치 = `CANDIDATE_REVISION_MISMATCH`) → 5 Candidate Content Digest →
6 Baseline Revision (동일 규칙) → 7 Baseline Content Digest (누락 =
`BASELINE_IDENTITY_MISSING`) → 8 Policy Version → 9 Result Schema →
10 상태별 검증.

**Researcher Revision 전달 공백 (RA 요청)**: 현재 Researcher 결과
계약은 Revision을 제공하지 않음 (RA-1..6 pending, §5) — 공식 Binding +
신뢰 가능한 실행 증거로 Revision을 입증할 수 있는 표면이 없어
**`CONTRACT_CAPABILITY_MISSING`으로 차단** (실제 결과 매핑은 현재
fail-closed). Result Payload에 임의의 Revision을 삽입해 테스트를
통과시키지 않음 — 합성 Fixture의 revision 필드는 "계약이 제공해야
할" 합성 프로젝션일 뿐이며 누락 부정 테스트(F03/F05)가 함께 고정.

## 3. WS-C — Resume Task Binding Identity Closure

### C1/C2. `resume_against_snapshot` 재작성 — 고정 순서

1 Evaluation Snapshot 무결성 → 2 공식 Binding Record 가용성
(없음 = `BINDING_AUTHORITY_UNAVAILABLE` — 가정·생성 금지) →
3 Binding Record 무결성 (tamper = `BINDING_RECORD_TAMPERED`) →
4 Record의 Evaluation ID (= 스냅샷) → 5 Record의 Task ID vs
identity surface의 task binding (상이 = `TASK_BINDING_IDENTITY_MISMATCH`
— 기존 실행과 동일한 Task Binding인지의 검증; Task ID는 Evaluation
생성 전에 존재한다고 가정하지 않음 — Record는 Task 할당 시 생성) →
6 Candidate ID/Revision/Digest → 7 Baseline Digest → 8 Policy Version
→ 9 Researcher Task 가용성 (불가 =
`RESEARCHER_TASK_LOOKUP_UNAVAILABLE` — 새 Task 자동 생성 없음).

### C3. 권위 관계 유지

```text
Evaluation Snapshot ──evaluation_id──▶ Official Workbench Binding Record
                                            │ task_id
                                            ▼
                                     Researcher Task
```

Evaluation↔Task 관계는 Workbench 소유; RRSI는 조회·검증만. 내부
In-memory Registry는 영속 Authority로 승격하지 않음 (TEST/PROTOTYPE
고정 유지).

### C4. Resume 안전성

Controller `resume()` RUNNING 재연결에 공식 Binding 검증 추가 —
`OFFICIAL_BINDING_CAPABLE=True` 클라이언트(mock projection)는 Record
필수 (조회 실패 = `BINDING_AUTHORITY_UNAVAILABLE`, evaluation 불일치 =
`BINDING_EVALUATION_ID_MISMATCH`, task 불일치 =
`TASK_BINDING_IDENTITY_MISMATCH`); 미capability 클라이언트(loopback —
실제 API pending)는 `official_binding_lookup: PENDING_EXTERNAL_CONTRACT`
으로 표시되고 기존 R2.3.1 4필드 identity binding이 가용한 전체 검증
(약화 아님 — 명시적 표시). 모든 검증은 커밋 전 완료 — 실패 resume은
컨트롤러 상태 무변경 (F15 실행 검증).

## 4. WS-D — 상태별 Result 검증 순서 정정

- **D1 공통 (모든 상태)**: binding digest → eval/task id → candidate/
  baseline/policy identity → schema → 상태 유효성 — 코드에 고정 순서로
  구현, docstring이 실행 순서와 동일하게 갱신 (D4).
- **D2 비종료 (CREATED/QUEUED/RUNNING/BLOCKED)**: terminal Result Digest
  요구하지 않음 (`verified_usage: False`로 반환 — 검증 불가 값은 검증된
  사용량으로 정산하지 않음). BLOCKED는 비종료 유지. 상태별 Usage·Event
  무결성 공식 계약 존재 여부 조사 → Researcher 계약에 없어 RA 요청으로
  기록 (§5).
- **D3 종료**:
  - COMPLETED: Result Digest (`RESULT_DIGEST_MISSING` 우선) → Provenance
    (digest 재계산) → Usage → Evidence/Answer → Budget Cap —
    `verified_usage: True`.
  - FAILED/CANCELLED: Terminal Status → **Failure/Cancellation Reason
    필수** (`TERMINAL_REASON_MISSING`) → 실제 소비 Usage (누락 결코 0) →
    Terminal Record Integrity.
- **D4 문서 일치**: 검증 단계 순서가 안전성에 영향(비종료 상태에 terminal
  digest 강요 금지, digest 전 identity 차단) — 테스트가 실제 거부 코드로
  실행 순서를 고정 (F11/F12/F13, T03/T08).

## 5. WS-E — Configuration Binding

- `map_evaluation_to_task_request()` — 합성 고정값(task_type="qa",
  model_profile, tool_policy) 제거, **configuration 명시 인자 필수**
  (누락 = `CONFIGURATION_BINDING_REQUIRED`). 합성 값은
  `SYNTHETIC_EVALUATION_CONFIGURATION` 상수로 fixture 전용 표기 —
  실제 Integration Adapter의 자동 사용 금지.
- Revision-aware Evaluation은 실행 시점 Configuration을 바인딩:
  Task Type · Model Profile · Tool Policy · Configuration Identity ·
  Configuration Digest — binding 생성 시 고정, 이후 Configuration
  변경이 기존 Evaluation의 실행 Configuration을 덮어쓰지 않음
  (불변 record_digest).
- **F14**: 동일 key + 다른 Configuration →
  `IDEMPOTENCY_CONFLICT:configuration` (레지스트리 명시 검사).
- Workbench/Researcher Configuration 전달 계약 미구현 → 필요 필드를
  Contract Request로 기록 (§5 요청 WB-4/RA-5).

## 6. WS-F — F01–F18 테스트 결과 (20건 신규, 전부 PASS)

| ID | 검증 | 결과 |
|---|---|---|
| F01 | 동일 Candidate ID + 새 Revision, 기존 Evaluation/Revision 유지 | **PASS** |
| F02 | 동일 Revision + 다른 Digest (registry restore + controller resume) | **거부 PASS** |
| F03 | Result Candidate Revision 누락 | **거부 PASS** (CONTRACT_CAPABILITY_MISSING) |
| F04 | Result Candidate Revision 불일치 | **거부 PASS** |
| F05 | Baseline Revision 누락 | **거부 PASS** |
| F06 | Baseline Revision 불일치 | **거부 PASS** |
| F07 | Binding Record Digest 변조 | **거부 PASS** |
| F08 | Resume Task ID 변경 | **거부 PASS** |
| F09 | Workbench Binding 조회 불가 | **BLOCKED PASS** |
| F10 | 최신 Candidate 변경 후 과거 Resume | **허용 PASS** |
| F11 | 비종료 상태 Result Digest 없음 | **상태별 계약 PASS** (verified_usage=False) |
| F12 | COMPLETED Result Digest 누락 | **거부 PASS** (RESULT_DIGEST_MISSING) |
| F13 | COMPLETED Usage 누락 | **거부 PASS** (결코 0) |
| F14 | 동일 Key + 다른 Configuration | **거부 PASS** |
| F15 | 실패한 Resume의 Controller 상태 | **불변 PASS** (속성 + registry 전부) |
| F16 | Git SHA 변경 + API 계약 동일 | **호환 PASS** |
| F17 | Git SHA 동일 + Capability 누락 | **거부 PASS** |
| F18 | Legacy Revision 미제공 | **명시적 처리 PASS** (차단 + Legacy 격리) |

**F2 실제 경로 테스트**: Controller Candidate → Evaluation Snapshot →
Binding Projection(합성 마크) → Synthetic Researcher Result → Result
Verification(`revision_enforced=True`) → Controller Decision(ADVANCE) →
재시작 resume(atomic, revision 보존) — 실제 컨트롤러·어댑터 코드 경로
실행, helper-only PASS 아님. Workbench 공식 Binding API 미구현 구간은
합성 Projection임을 실행 중 단정 (`projection: synthetic-mock-adapter`)
— 실제 REST 통합 검증과 구분.

**F3 회귀**: RRSI 전체 **352/352 PASS** (기존 304 + 경계 R2 28 +
R2.1 신규 20) — R2.3.1 Full Identity Binding · Settlement
Reconciliation · Cumulative Budget · Decision Record Integrity ·
Snapshot/Resume Atomicity 전부 포함. F15는 실제 결함을 발견·수정:
실패 resume이 검증 전에 revision registry를 변경하던 것 — restore를
커밋 블록으로 이동.

## 7. WS-G — Git Remote 조사 (읽기 전용, 변경 없음)

| 항목 | 결과 |
|---|---|
| 1 `origin`의 실제 URL | `https://github.com/google-research/rrsi.git` (Google 원본 upstream) |
| 2 `victor0777/rrsi.git` Remote 이름 | `fork` (fetch/push 모두) |
| 3 현재 main의 Tracking Remote | `origin/main` (`ahead 56` — tracking이 푸시 불가한 upstream을 가리킴) |
| 4 Google 원본이 Remote로 등록된 근거 | reflog `HEAD@{56}: clone: from https://github.com/google-research/rrsi.git` — **저장소를 Google 원본에서 clone**하여 기본값으로 origin에 등록됨; fork는 이후 별도 remote로 추가 |
| 5 Fork Push의 실제 대상 | `victor0777/rrsi.git` main (지금까지의 커밋 푸시 실제 경로) |

**원인 판정**: 403은 권한 부재(victor0777 계정에 google-research 쓰기
권한 없음)로, origin이 upstream인 상태에서 `git push origin main`을
실행하기 때문. Tracking remote가 origin/main인 것도 같은 원인
(clone 기본값).

**변경 전후 계획 (제안만 — 자동 변경 없음)**:
1. `git fetch fork && git branch -u fork/main main` — tracking을
   fork/main으로 전환 (push/pull 실수 방지).
2. 선택: origin의 push URL을 fork로 겹치기(`git remote set-url --push
   origin …`) — 다만 remote 이름 의미가 왜곡되므로 1안 권장.

## 8. WS-H — Cross-Repository Contract Requests (전부 PENDING)

### WB (Workbench) — PENDING
- WB-1 공식 Binding 조회 API (evaluation_id → task_id, candidate
  id/revision/digest, baseline revision/digest, policy, configuration
  identity, record digest; resume 동일-task 보장)
- WB-2 Candidate Revision 전달 (wire candidate에 revision 필드 —
  Contract Version 전환 필요)
- WB-3 Baseline Revision 전달
- WB-4 Configuration Identity 전달 (task type / model profile / tool
  policy / envelope / input artifact identity / configuration digest)
- WB-5 재시작 후 Binding 조회 보장 (조회 불가 시 상태 코드)

### RA (Researcher) — PENDING
- RA-1 Result Revision Identity (candidate_revision / baseline_revision
  필드) — 현재 부재로 실제 결과 매핑 fail-closed
- RA-2 COMPLETED Usage (model_calls / tool_calls / tokens_used)
- RA-3 Usage 측정 권위 원천
- RA-4 Result Digest 알고리즘·커버 필드
- RA-5 Model Profile / Configuration 전달 계약
- RA-6 API Contract Version / Capability 표면

## 9. Acceptance Gate 판정

| Gate | 판정 |
|---|---|
| `REVISION_CONTROLLER_INTEGRATED` | **PASS** (§1.3 — 6 연결 지점, R1 무변경) |
| `REVISION_RESULT_ENFORCED` | **PASS** (§2.3 — 합성 경로; 실제 결과는 RA-1 pending으로 fail-closed) |
| `BASELINE_REVISION_ENFORCED` | **PASS** (binding 발급 + 결과 대조 F05/F06) |
| `TASK_BINDING_IDENTITY_VERIFIED` | **PENDING_EXTERNAL_CONTRACT** (합성 projection 검증 PASS; 실제 Workbench API 미구현 — WB-1) |
| `RESUME_ATOMICITY_PRESERVED` | **PASS** (F15 실행 증명) |
| `CONFIGURATION_BINDING_DEFINED` | **PASS** (명시 바인딩 + F14) |
| `STATUS_SPECIFIC_VALIDATION_READY` | **PASS** (§4) |
| `REGRESSION_PASS` | **PASS** (352/352) |
| `EXTERNAL_CONTRACT_PENDING_RECORDED` | **PASS** (§8) |
| `NO_MODEL_EXECUTION_CONFIRMED` | **PASS** (모델 호출 0, Task 실행 0) |

## 10. 최종 상태

**`RRSI_INTEGRATION_BOUNDARY_R2_1_READY`**

단, `TASK_BINDING_IDENTITY_VERIFIED`는 외부 계약(WB-1) 대기로
`PENDING_EXTERNAL_CONTRACT` 병기 — 합성 테스트 성공만으로 외부 API
준비 완료로 처리하지 않음. 이 판정은 RRSI 측 계약 준비 완료일 뿐이며
실제 Researcher Evaluation 및 RRSI Improvement Iteration은 Owner의
별도 명시적 승인 전까지 HOLD한다 (`REAL_EVALUATION_ADMITTED = False`).
