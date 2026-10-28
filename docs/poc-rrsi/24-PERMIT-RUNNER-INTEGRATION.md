---
doc_id: poc-rrsi-24-permit-runner-integration
title: Execution Permit Runner 통합 및 재개 가능성 검증
status: report
updated: 2026-10-28
---

# Execution Permit — Runner Integration Report

**Summary.** Permit 계약을 실제 실행 경로에 통합: rrsi 내 직접 모델 호출 경로
2곳(reader-context runner + fulltext runner) 전부 permit-gated. Runner CLI에
비실행형 `preflight` step 추가 — 필수 순서(permit → identity → split/holdout →
model/endpoint → budget → ledger reservation) 검증, 실증: permit 없음 →
`BLOCK(PERMIT_REQUIRED)` 0 calls 0 reservations; 발급된 유효 permit → `READY`
(호출 여전히 0). 신규 통제: **발급-소비 권한 분리** — append-only 발급
ledger(`register_permit`는 발급자 전용, runner는 대조만)로 runner 자체 발급·
변조·서명 없는 permit을 `PERMIT_NOT_ISSUED`로 차단. 회귀시험 **49/49 PASS**.
Same-paper QA 준비: digest·identity 대조 **ALL READY** — QA 실행은 미수행.
판정: **GO (조건부)** — Same-paper QA는 permit 발급 승인과 함께 실행 가능
(예산 12 calls / 15분).

---

## A. Permit Runner 통합 위치 (Workstream A)

| 실행 순서 | 구현 위치 |
|---|---|
| 1. Execution Permit 검증 | `poc.qasper_readercontext_calibration.preflight()` → `poc.execution_permit.assert_authorized` (workstream/call-type/model/endpoint/budget/ledger 7조건) |
| 2. Paper Identity 검증 | `preflight()` → `poc.paper_identity_binding.resolve_binding` (case별, 구조적 provenance 전용) |
| 3. Dataset Split/Holdout 검증 | `resolve_binding` 내 `SPLIT_NOT_ALLOWED`/`FINAL_HOLDOUT_REFUSED` |
| 4. Model Profile/Endpoint 검증 | permit `PERMIT_MODEL_ENDPOINT` (runner 상수와 대조) |
| 5. Budget 검증 | permit `PERMIT_BUDGET` + `BUDGET_CEILING_INSUFFICIENT` (ceiling ≥ case 수) |
| 6. Ledger Reservation | permit `PERMIT_LEDGER` (경로 귀속 + write probe → `PERMIT_LEDGER_UNWRITABLE`) |
| 7. Model Invocation | `run()` 내 `call_model` — **preflight READY 이후에만 도달** |
| 8. Telemetry Terminal | env 바인딩 (`AI_PAPERS_PROCESS_TELEMETRY_EVENTS` — 미바인딩 시 `CALL_BUDGET_ENV_ABSENT` 선차단) |
| 9. Ledger Reconciliation | `poc/r0b2_audit.py` (실행 후 감사; 실행 전 감사는 사전 reconciliation 등록 사용) |

- `run()` 상단에서 `preflight()`를 강제 호출 — BLOCK이면 호출 전 `FAIL_CLOSED`
  (실증 exit 1, 0 calls). fulltext runner에도 동일 게이트 적용 (§C).
- CLI: `python3 -m poc.qasper_readercontext_calibration preflight` — 실행 없이
  진입 가능성만 보고.

## B. Permit 권한 경계 (Workstream B)

| 조건 | 확인 |
|---|---|
| Runner가 Permit을 임의 발급하지 못함 | **검증** — permit 바이트의 sha256이 발급 ledger에 없으면 `PERMIT_NOT_ISSUED` (runner 코드는 register를 호출하지 않음; test_permit_not_issued_block으로 강제) |
| Invocation ID 일치 | permit-bound (`PERMIT_INVOCATION_MISMATCH`) |
| Workstream / Call Type 일치 | `PERMIT_WORKSTREAM_MISMATCH` / `PERMIT_CALL_TYPE_MISMATCH` |
| Dataset / Paper Scope 일치 | `PERMIT_DATASET_MISMATCH` / `PERMIT_PAPERS_MISMATCH` |
| Model / Endpoint 일치 | `PERMIT_MODEL_MISMATCH` / `PERMIT_ENDPOINT_MISMATCH` |
| Budget 상한 미초과 | `PERMIT_BUDGET_EXCEEDED` (permit > ledger ceiling) |
| Permit 파일 존재만으로 승인 아님 | `_assert_issued` — 존재+발급 둘 다 필요 |

**발급자↔실행자 권한 분리 (PoC 최소 통제)**:
1. 발급 행위는 `register_permit(permit_path, issued_by=…)` **한 곳** — owner/
   승인자가 실행하는 발급자 전용 함수. Runner 코드 경로에서 호출 없음(테스트로
   부정).
2. permit은 발급 시점 바이트 digest로 귀속 — 실행자가 내용을 수정하면 digest
   불일치로 차단(tamper test). Scope 변경은 반드시 발급자가 재발급.
3. 발급 ledger는 append-only(jsonl, 삭제·수정 규약 위반 검출 가능) — 발급 이력
   감사 가능.
4. 한계 등록: PoC에서는 발급자 프로세스와 runner 프로세스의 **OS 사용자 분리를
   강제하지 않는다**(동일 사용자 환경에서는 발급 함수를 누구나 호출할 수 있음).
   실제 분리는 (i) 발급 ledger 디렉토리를 runner 사용자에게 읽기 전용으로
   마운트, (ii) 발급 CLI를 승인자 키로 서명 — 다음 승인 시 적용 권고.

## C. 우회 경로 검증 (Workstream C)

rrsi 내 모델 호출 가능 경로 조사:

| 경로 | 현황 | 통제 |
|---|---|---|
| QA Runner 정상 경로 (`call_model` via run loop) | reader-context runner 1곳 | **permit-gated** (preflight READY 전 도달 불가, 실증) |
| QA Runner Preflight 경로 | 비실행형 — 모델 client import 없음 | BLOCK/READY 보고 전용 (preflight QA 시도 → BLOCK test) |
| Model Client 직접 호출 경로 | fulltext runner `call_model` 1곳 | **permit-gated** (env guard + permit, 실증 exit 1) |
| 테스트·진단 스크립트 경로 | rrsi 테스트는 call_model 미사용(네트워크 0) | permit 게이트 대상 아님 — 모의 객체만 사용 |
| Reader Chain ↔ QA Inference 호출 경계 | reader chain은 ai_papers CLI 프로세스(별도 invocation, ledger ceiling 28) — QA inference와 경계 분리됨 | 경계 침범 경로 없음 확인 (runner는 chain을 호출하지 않음) |

- 승인되지 않은 QA 호출 가능 경로: rrsi 내에서는 위 2곳이 유일하며 둘 다
  fail-closed 차단. **잔여 리스크**: ai_papers 측 `call_model`은 어디서든
  import 가능(rrsi 소관 밖 — 23번 보고 §F-7 유지). PoC에서 rrsi 경로만 통제.

## D. 회귀시험 (Workstream D) — 49/49 PASS

Negative 전건: 모델 호출 0회, reservation 0건 (네트워크 접촉 0):

| 조건 | 결과 |
|---|---|
| 유효 Permit + 정상 Ledger | **READY** (진입 가능, 호출 0 — positive integration check 실증: 5 checks + permit 6 checks) |
| Permit 없음 | **BLOCK** (`PERMIT_REQUIRED`) |
| Permit 변조 (발급 후 바이트 수정) | **BLOCK** (`PERMIT_NOT_ISSUED`) |
| Invocation ID 불일치 | **BLOCK** (`PERMIT_INVOCATION_MISMATCH`) |
| Call Type 불일치 | **BLOCK** (`PERMIT_CALL_TYPE_MISMATCH`) |
| Dataset / Paper 불일치 | **BLOCK** (`PERMIT_DATASET_MISMATCH` / `PERMIT_PAPERS_MISMATCH`) |
| Model / Endpoint 불일치 | **BLOCK** (`PERMIT_MODEL_MISMATCH` / `PERMIT_ENDPOINT_MISMATCH`) |
| Budget 초과 | **BLOCK** (`PERMIT_BUDGET_EXCEEDED`) |
| Ledger Reservation 실패 (read-only parent) | **BLOCK** (`PERMIT_LEDGER_UNWRITABLE` — 예약 시도=probe 1회, **성공 예약 0건**, 모델 호출 0건, probe 잔재 0) |
| Final Holdout 입력 | **BLOCK** (`PERMIT_PAPERS_MISMATCH`) |
| Preflight에서 QA 실행 시도 | **BLOCK** (preflight는 실행 불가 + runner-level preflight test) |

추가: runner 자체 발급 시도 → `PERMIT_NOT_ISSUED` (test_permit_not_issued_block).

## E. Same-paper QA 실행 준비 (Workstream E) — QA 실행 0회

| 논문 | Note Digest vs Manifest | Binding | Source Identity |
|---|---|---|---|
| `1802.07862` | **일치** (`99efc53f…`) | **PASS** (note=question=`1802.07862`, v1) | registry sha256 == source-identity ✓ |
| `1901.10133` | **일치** (`97f5dd09…`) | **PASS** (note=question=`1901.10133`, v1) | registry sha256 == source-identity ✓ |

- **ALL READY** — per-paper note digest 고정·identity binding·append-only
  registry 모두 22·24번 등록 상태와 byte-일치 대조 통과.
- **Permit 발급·예산 준비 상태**: 발급 대기. 권고 permit 스펙 — workstream
  `reader_context_qa`, call_type `qa_inference`, dataset
  `2ae7ee62…`(frozen v0.3), papers {1802.07862, 1901.10133}, model
  `qwen3.8-flash-next-fp8` @ `http://192.168.0.199/v1`, budget max_calls 12 /
  max_wall_seconds 900 (retry 0, concurrency 1, 유료 0). Artifact 상태: §E
  표 — 승인 시 permit 발급 → env 바인딩 → 10 calls 실행 가능.

## F. 완료 보고 (Workstream F)

1. **통합 위치**: §A (preflight 1–6 순서 게이트 + run 강제 진입).
2. **호출 경로·우회 경로**: §C (rrsi 직접 경로 2곳 전부 gated, 잔여
   ai_papers 측 import 가능성 등록).
3. **Negative Regression**: §D — 49/49 PASS.
4. **권한 경계**: §B — 발급-소비 분리 + 4항목 최소 통제 + 강제 한계 등록.
5. **Ledger Reservation 연동**: 경로 귀속 + write probe; 실패 시 0 예약·0
   호출 확인.
6. **Same-paper QA 준비**: §E — ALL READY, permit 발급 대기.
7. **잔여 위험**: ① OS 사용자 분리 미강제(동일 사용자 환경의 발급 함수 호출),
   ② ai_papers 측 직접 호출 가능성(rrsi 소관 밖), ③ scorer 매핑 왜곡(등록
   유지), ④ GT 미검증 note(CONDITIONAL 유지).
8. **판정: GO (조건부)** — 실행 통제는 실제 경로에 통합·검증 완료; Same-paper
   QA는 **permit 발급 승인과 동시에** 실행 가능(예산 12 calls / 15분). STOP
   요인 없음.

## 제한사항 준수

신규 모델 호출 **0**, Reader Pipeline 실행 **0**, Same-paper QA 실행 **0**,
RRSI Evolution 0, Final Holdout 소비 0, Scorer 수정 0, Artifact 삭제 0,
ai_papers 운영 상태 변경 0, 신규 worktree 0.
