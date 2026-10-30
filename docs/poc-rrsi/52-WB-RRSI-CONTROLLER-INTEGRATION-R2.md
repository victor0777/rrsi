---
doc_id: poc-rrsi-52-wb-rrsi-controller-integration-r2
title: WB-RRSI-CONTROLLER-INTEGRATION-R2 — Real Controller ↔ Real EvaluationService Integration
status: report
updated: 2026-10-30
---

# WB-RRSI-CONTROLLER-INTEGRATION-R2 — Real Controller ↔ Real EvaluationService Integration (문서 52)

기준: Workbench `research_benchmarks@dfabe70` · RRSI `rrsi@<본 커밋>` ·
Architecture Boundary R2 `e395ac7`. 모델 호출 0, 벤치마크 실행 0,
운영 REST 배포 없음. R1 파일(`poc/recursive_loop_r1.py`)은 변경하지
않고 상속·재사용으로 통합(R2 모듈 `poc/recursive_loop_r2.py`).

## 1. Workstream A — 공식 Client Interface (Gate A)

- `WorkbenchClientInterface` — 6개 공식 오퍼레이션:
  `submit_evaluation` / `get_evaluation_status` /
  `get_evaluation_result` / `get_evaluation_events` /
  `cancel_evaluation` / `get_evaluation_usage`.
- 구현 2종: `MockClientAdapter`(R1 Mock 랩핑, 어댑터가 mock 결과를
  Canonical Result 봉인) · `LoopbackClientAdapter`(실제
  `EvaluationService` + Loopback HTTP-shaped 전송).
- **Controller의 Workbench 내부 자료구조 접근 0건** — 정적 소스 스캔
  (`client.jobs` / `.records` / `.by_key` / `.idempotency` /
  `client.budget*` 정규식 스캔 PASS). R1 대비 제거 항목:
  `propose_promotion()`의 `self.client.jobs` 2곳, `snapshot()`의
  `client.jobs` 반복 1곳, `resume()`의 `client.jobs` 검증 1곳.
- 중복 submit은 동일 evaluation id 반환, 평가 카운트·예산 이중 청구
  없음 (`duplicate=True`).

## 2. Workstream B — Canonical Result 소비 (Gate B)

`complete_evaluation()` 고정 12단계: 1 수신(Interface) → 2 스키마 →
3 evaluation id → 4 candidate identity → 5 baseline identity →
6 profile/policy → 7 provenance → 8 status → 9 필수 지표 → 10 예산
사용량 → 11 reward/cost/risk 매핑 → 12 상태 전이.

- **Negative 8종 전부 fail-closed (TERMINATED)**: 타 candidate 결과
  (CANDIDATE_IDENTITY_MISMATCH), 타 baseline 결과
  (BASELINE_IDENTITY_MISMATCH), policy version 변경
  (POLICY_VERSION_MISMATCH), score 변조
  (PROVENANCE_VERIFICATION_FAILED), 필수 지표 누락
  (REQUIRED_METRICS_MISSING), 무효 평가 (EVALUATION_INVALID /
  INSUFFICIENT_EVIDENCE / BUDGET_EXHAUSTED / CANCELLED 명시 매핑),
  예산 초과 (BUDGET_CAP_EXCEEDED), 중복 수신(멱등 — 동일 봉인
  기록 반환, budget 재청구 0).
- 고정 단계 순서 검증: evaluation id 재작성 없이 타 결과 투입 시
  3단계(EVALUATION_IDENTITY_MISMATCH)에서 먼저 차단.
- `COMPLETED_VALID`만이 usable basis — 단독으로는 절대 ADVANCE를
  결정하지 않고 reward/cost/risk 평가로만 상태가 결정됨.

## 3. Workstream C — Promotion Guard 독립 (Gate C)

- `propose_promotion()`은 **검증된 controller 소유 상태만** 사용:
  `validated_result`(10조건 통과 + provenance_verified) · Decision
  Record · baseline 결합 — client 접근 0.
- 사전조건 8종 그대로 유지 + `approved_profile` 하드코딩 `True`
  제거 → `APPROVED_EVALUATION_PROFILES` 명시 허용 목록 대조.
- **불변 Decision Record**: `evaluation_id` + `candidate_digest` 결합,
  `decision_record_digest`(자기 제외 canonical digest) — 변조 시 digest
  불일치로 검증 가능, append-only.
- REJECT / HOLD / UNDECIDABLE / TERMINATED 상태는 제안 생성 불가
  (테스트 3+1 상태 전부 PASS). 통과 시에도
  `PENDING_OWNER_APPROVAL` — 운영 승격은 Researcher Owner.

## 4. Workstream D — Durable Resume (Gate D)

`resume()` 10단계: 1 스키마 버전 → 2 digest → 3 baseline → 4
candidate → 5 evaluation id → 6 Workbench 상태 재조회 → 7 Workbench
결과 identity 재검증 → 8 사용량 조회 → 9 budget ledger 대조 → 10
안전 복원.

- 변조 / 구버전 / 불완전 Snapshot 거부 (SNAPSHOT_TAMPERED /
  SNAPSHOT_VERSION_MISMATCH / SNAPSHOT_INCOMPLETE).
- Workbench 상태 불일치(CANCELLED 등) / 결과 identity 불일치
  ⇒ 정상 resume 불가 (WORKBENCH_EVALUATION_STATE_MISMATCH /
  WORKBENCH_RESULT_IDENTITY_MISMATCH).
- **Snapshot budget은 Workbench 신뢰된 사용량보다 우선하지 않음**:
  snapshot 사용량 > Workbench 사용량 ⇒ 거부
  (SNAPSHOT_BUDGET_EXCEEDS_WORKBENCH), Workbench 사용량 >
  snapshot ⇒ Workbench 값 채택 (authoritative). 테스트에서
  Workbench 700 vs snapshot 300 → 700 채택 확인.
- 재개 후 `request_evaluation()`은 중복 키로 동일 evaluation 반환 —
  평가·settlement 중복 없음.

## 5. Workstream E — Cross-repo Controller E2E (Gate E)

실제 `RecursiveLoopControllerR2`가 실제 `EvaluationService`(Loopback)
을 구동 — harness는 controller의 history/state/tokens_spent를 직접
수정하지 않음. 정확한 판정/상태 테이블:

| 시나리오 | Decision | State |
|---|---|---|
| 품질 개선·비용 허용 | ADVANCE | NEXT_ITERATION |
| 품질 저하 | REJECT | REJECTED |
| 비용 상한 초과 | HOLD | REVISE_CANDIDATE |
| 표본 불충분 | UNDECIDABLE | REVISE_CANDIDATE |
| Provenance 실패 | BLOCKED | TERMINATED |
| Budget 소진 | BLOCKED | TERMINATED |

6행 전부 정확 일치 (느슨한 어설션 없음). Workbench 측 변조는
service 기록에 대한 negative test로만 수행.

## 6. Workstream F — Shared Fixture 실행 의미론 (Gate F)

16종 공유 Fixture를 실제 실행 경로로 검증:

- Request형 (01·03·04·05) → 실제 `EvaluationService` 경로: 생성 성공 /
  `schema_validation_failed` / `idempotency_conflict` /
  `candidate_binding_missing`→FAILED.
- Result형 (02·06·07·08·09) → 실제 RRSI 10조건 검증기 + reward policy:
  수신 성공 / provenance_mismatch / quality·evidence regression
  →REJECT / usage 초과→budget 거부.
- 상태형 (10·11·12) fail-closed, 13 held-out(aggregate-only 표면 —
  gold/per_case/detail 부재, 경계 선언만), 14 improvement evidence,
  15 무효 평가 promotion 거부, 16 resume이 workbench와 대조 검증.

## 7. 전체 Regression

- RRSI: **252/252 PASS** (R1 기존 217 + R2 신규 35, 회귀 0)
- Workbench: **114/114 PASS** (변경 0)

## 8. 미해결 결함 / 실행 제한 준수

- 미해결 결함 없음.
- 준수: main 유지, 브랜치·Worktree 없음, 모델 호출 0, 벤치마크 0,
  Gold/Held-out 무접근, 운영 REST 배포 없음, Production Candidate
  변경 없음, 자동 Qualification/Promotion 없음
  (REAL_QUALIFICATION_BASIS.auto_qualification=FORBIDDEN), OS Isolation
  정책 우회 없음, R6I/R7 승인·예산 정책 우회 없음.

## 9. 완료 판정

| Gate | 조건 | 결과 |
|---|---|---|
| A | 공식 Client Interface + 내부 접근 0 | **PASS** |
| B | Canonical 소비 12단계 + negative 8 | **PASS** |
| C | Promotion Guard 독립 + Decision Record | **PASS** |
| D | Durable Resume + Workbench 사용량 우선 | **PASS** |
| E | Cross-repo Controller E2E 판정 테이블 | **PASS** |
| F | Shared Fixture 실행 의미론 | **PASS** |
| G | 실행 제한 준수 | **PASS** |

**최종 상태: `CONTROLLER_CLOSED_LOOP_VERIFIED`**

단, 이는 결정적 mock·loopback 경로에서 Controller↔EvaluationService
닫힌 루프의 계약·무결성이 검증된 것일 뿐, 실제 Researcher 성능 개선이나
운영 승격이 완료됐다는 의미가 아니다.

---

## R2.1 — Controller Integrity & Resume Atomicity (검토 의견 보완)

독립 검토에서 발견된 결함 4종을 수정 (새 기능 추가 없음):

### P0-1 — Loopback 사용량 조회 공식 경계 위반 → 수정

`LoopbackClientAdapter.get_evaluation_usage()`이
`self._service.records[...]` 내부 접근 → 제거. 이제 settle-budget
응답 + **provenance 검증을 통과한 공식 결과 표면**
(`get_evaluation_result`)에서만 사용량 취득. 어댑터 자체 소스에 대한
정적 스캔 테스트 추가 (`self._service.records` / `records[` / budget·jobs
접근 0건) + 행위 검증(공식 표면 기반 usage).

### P0-2 — Resume 비원자적 복원 → 원자적 복원

기존: Snapshot 검증 직후 controller 상태를 먼저 수정하고 그다음
Workbench 재검증 → 검증 실패 시 변경된 상태 잔존.
수정: **모든 검증을 지역 사본에서 수행** — 6 상태 재조회 → 7 결과
identity 재검증 → 8+9 사용량 조회·대조 전부 완료된 뒤, 최종 단일
commit 블록에서 한 번에 복원. 실패한 resume은 controller 상태를
전혀 변경하지 않음 (테스트: identity 실패 후 prior 상태 8필드 전부
불변 확인).

### P1 — 누적 사용량 vs 단일 평가 사용량 혼동 → 수정

기존 `resume()`은 누적 `tokens_spent`와 마지막 평가 1건의 사용량을
직접 비교 → 다중 평가 후 resume에서
`SNAPSHOT_BUDGET_EXCEEDS_WORKBENCH` 오탐. 수정: **evaluation_history
전체에 대한 평가별 신뢰된 사용량 합산**과 대조. 테스트: 3건 완료
(누적 900) 후 resume → 오탐 없음, 누적 보존; workbench 합산 초과 시
채택(2000), 미달 시 거부.

### 검토 사항 정리 (Gate B/C/D)

- **Gate B 단계 순서**: status 검사를 provenance 검증(7) 이후로
  재배치 — 실행 순서가 문서 고정 12단계와 동일해짐 (명시적 순서 검사
  4→5→6→7→8→9).
- **Gate C Decision Record**: `decision_records`는 append-only
  list[dict]로 "불변 객체"가 아니라는 지적 반영 — 문서 표현 수정 +
  promotion 시점에 **digest 재검증** 추가 (변조 탐지가 promotion
  경계에서 작동; `decision_record_integrity` 사전조건 신설).
- **Gate D Snapshot digest**: 무결성 전용이며 변조 방지 증거가
  아니라는 점을 docstring에 명시 — 영속 신뢰는 신뢰된(봉인된)
  snapshot 저장소가 별도 전제. `snapshot()`은 digest 없는 상태로
  반환하고 `seal_snapshot()`으로 봉인하는 계약 명시.

### R2.1 회귀

- RRSI: **256/256 PASS** (R2.1 신규 4: resume 원자성 · 다중 평가
  누적 정산 · 어댑터 공식 표면 스캔+행위 · Decision Record 재검증)
- Workbench: **114/114 PASS** (변경 0)
- 동일 6개 E2E 시나리오 + 다중 평가 resume 시나리오 재실행 PASS.

**R2.1 최종 상태: `CONTROLLER_CLOSED_LOOP_VERIFIED`** (강화 근거)

---

## R2.2 — Settlement Order, Running Reconnect & Candidate Binding (검토 의견 보완)

독립 검토(`R2.1_ACCEPTED_WITH_P0_REMAINING`)의 잔여 결함 3종 수정:

### P0 — 검증 실패 시 예산 선차각 → 정산 순서 수정

기존 `complete_evaluation()`은 `tokens_spent += tokens`가 step-11
전체 검증기보다 먼저 실행 → 예산 초과 결과(`BUDGET_CAP_EXCEEDED`)가
ledger를 선차각하고 실패. 수정:

- **10단계에서 예산 상한 선검증** (상한 초과 → 즉시 fail-closed,
  ledger 변경 0).
- **정산을 step-11 전체 검증 이후로 이동** — 검증된 수치만 ledger에
  반영, 정산은 정확히 1회.
- 어댑터 양쪽(`LoopbackClientAdapter` · `MockClientAdapter`)의
  `get_evaluation_usage()`이 **자체적으로 provenance 검증 강제**
  (검증 실패 → `PROVENANCE_VERIFICATION_FAILED` ClientError) —
  신뢰되지 않은 결과는 결코 정산 기준이 아님. 테스트: 초과 결과 →
  TERMINATED + `tokens_spent == 0`; 변조 service 기록 → ClientError.

### P0 — 진행 중 평가의 Durable Resume → 재연결 도입

기존 `resume()`은 evaluation id가 있으면 Workbench 상태가 반드시
`COMPLETED`여야 함 → 평가 요청 직후 재시작 시 복원 거부. 수정 —
상태별 구분 처리 (원자성 유지, 검증은 지역 사본):

| Workbench 상태 | Resume 처리 |
|---|---|
| RUNNING | **재연결**: evaluation id 보존, `EVALUATION_REQUESTED`로 복원 — 이후 poll·소비 정상 계속 |
| COMPLETED | 결과 identity 재검증 후 복원 (기존 경로) |
| CANCELLED | 종료 처리: `TERMINATED` + `stop_reason=EVALUATION_CANCELLED` 복원 |
| 그 외/오류 | `WORKBENCH_EVALUATION_STATE_MISMATCH` 거부 (fail-closed) |

테스트: RUNNING 재연결 후 `deliver_result → poll → complete` 정상
완료; CANCELLED → TERMINATED 복원; 알 수 없는 상태 → 거부.

### P1 — Promotion Candidate 결합 강화

`reward_cost_risk_pass`가 Decision Record의 `candidate_digest`를
**현재 candidate digest와 직접 비교** (기존은 evaluation id만) —
candidate 교체·상태 오용 상태에서 promotion 차단. 테스트: digest
불일치 → `promotion_blocked`.

### R2.2 회귀

- RRSI: **261/261 PASS** (R2.2 신규 5: 초과 결과 미차각 · 어댑터
  provenance 강제 · RUNNING 재연결 · CANCELLED 종료 · candidate 결합)
- Workbench: **114/114 PASS** (변경 0, `dfabe70` 유지)
- 동일 6개 E2E 시나리오 + 다중 평가 resume 재실행 PASS.

**R2.2 최종 상태: `CONTROLLER_CLOSED_LOOP_VERIFIED`**

다음 단계(검토 권고 반영): Mock 통합 반복 종료 — Researcher Task
REST API와 연결하는 실제 평가 단계로 진행 (Owner 승인 필요).
