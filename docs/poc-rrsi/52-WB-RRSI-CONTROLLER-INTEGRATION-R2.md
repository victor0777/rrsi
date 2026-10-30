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
