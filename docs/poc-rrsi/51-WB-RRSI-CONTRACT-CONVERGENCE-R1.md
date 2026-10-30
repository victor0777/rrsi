---
doc_id: poc-rrsi-51-wb-rrsi-contract-convergence-r1
title: WB-RRSI-CONTRACT-CONVERGENCE-R1 — Cross-repository Contract Convergence
status: report
updated: 2026-10-30
---

# WB-RRSI-CONTRACT-CONVERGENCE-R1 — Cross-repository Contract Convergence (문서 51)

기준: Workbench `research_benchmarks@dfabe70` · RRSI `rrsi@<본 커밋>` ·
Architecture Boundary R2 `e395ac7`. 모델 호출 0, 벤치마크 실행 0,
운영 REST 배포 없음.

## 1. Canonical Schema (Gate A)

- Workbench `contracts/` 산하 스키마를 공식 기준으로 확정.
- Wire Format: **64-char lowercase SHA-256 hex** (candidate·baseline
  digest 공통).
- JSON Canonicalization 규칙 (양쪽 동일): UTF-8, ensure_ascii=False,
  sort_keys=True, compact separators (',', ':'), whitespace 없음.
  RRSI `canonical_payload_bytes` ≡ Workbench `canonical_json` (테스트로
  교차 검증 — `test_canonicalization_matches_shared_rule`).
- 상태 분리: Evaluation Validity (COMPLETED_VALID) ≠ Improvement
  Evidence (delta>0) ≠ Promotion Eligibility (정책 통과) — 결과 스키마의
  `improvement_claim_allowed`는 유효성만 표시.

## 2. Candidate Digest 호환성 (A1)

- RRSI 내부 `sha256:<hex>` ↔ wire 64-hex 변환은 `DigestAdapter` 단일
  지점 (§C1).
- 검증: prefix 없음/대문자/잘못된 형식 → `ContractRejected`.
- Candidate/Baseline digest 구분 (동일 불허), candidate_id↔digest 결합
  (binding 불일치 → `candidate_binding_invalid`), 기존 candidate의
  digest 변경 감지 (`candidate_digest_changed` 이벤트).
- 문자열 형식 일치와 artifact 내용 검증은 별개 — binding 배치 검증은
  Workbench 소유.

## 3. Provenance 검증 결과 (Gate B — Workbench 소유)

- `provenance_digest` = 전체 정규화 Result Payload (digest 자체 제외)에
  대한 canonical sha256 — Evaluation ID, Request Identity/Digest,
  Candidate/Baseline Identity, Profile, Policy Version, Benchmark/Cohort,
  Sample Count, Quality/Evidence/Cost Metrics, Delta, Validity, Failure
  Category, Status 전부 보호.
- **변조 8종 전부 검증 실패 PASS**: quality score, evidence score, cost,
  sample count, policy version, candidate digest, evaluation status,
  benchmark cohort.

## 4. Idempotency 검증 결과 (§B2)

| 요청 | 결과 |
|---|---|
| 동일 Key + 동일 Request Digest | 기존 Evaluation 반환 (duplicate=True, 비용 0) |
| 동일 Key + 다른 Request Digest | **IDEMPOTENCY_CONFLICT** |
| 신규 Key + 승인된 Candidate | 신규 Evaluation 생성 |

- 중복 요청으로 예산 이중 청구 없음 (budget ledger 단일 실행 확인).
- 진행 중(동일 기준선) 완료 후 Cancel 시도 → `LifecycleError`
  (409 실패-닫힘), result 불변.

## 5. Promotion Guard 검증 결과 (Gate C — RRSI §D1)

`propose_promotion()` 명시적 사전조건 8종 — 하나라도 실패 시
`promotion_blocked` + 실패 항목 반환:

- 검증 PASS: 평가 없음 → 차단 / TERMINATED 상태 → 차단 / 정상
  ADVANCE 경로 → `PENDING_OWNER_APPROVAL` 제안 성공.
- HOLD·REJECT·UNDECIDABLE 상태는 제안을 생성할 수 없음 (policy PASS
  조건이 사전조건에 포함).
- 제안 이후에도 운영 승격은 Researcher Owner의 별도 승인.

## 6. Durable Resume 검증 결과 (Gate C — RRSI §D2)

- Snapshot 스키마 `rrsi-loop-snapshot/v0.2` — 13 대상 필드 전부 복원
  (baseline identity/metrics, current candidate/evaluation id, state,
  iteration/evaluation count, budget ledger, candidate·evaluation
  history, best candidate, stop reason, pending promotion request).
- **변조·구버전·불완전 Snapshot 전부 거부** (SNAPSHOT_TAMPERED /
  SNAPSHOT_VERSION_MISMATCH / SNAPSHOT_INCOMPLETE — 결정적 테스트 PASS).
- 복원 시 Workbench Job 상태·Identity 재검증 — 불일치 시
  `WORKBENCH_JOB_STATE_MISMATCH`. 재시작 후 중복 평가 없음.

## 7. Shared Contract Fixture (Gate D — §7)

- 16종 Fixture (양쪽 저장소 **바이트 동일**, copy 검증):
  valid request/result, invalid digest, idempotency conflict, missing
  binding, invalid provenance, quality/evidence/cost regression,
  insufficient evidence, budget exhaustion, cancelled evaluation,
  held-out restriction, valid improvement candidate, promotion blocked,
  resume after interruption.
- `poc/runs/recursive-loop/shared-contract-fixtures-r1.json` ≡
  `research_benchmarks/contracts/fixtures/shared-contract-fixtures-r1.json`
  — `file_digest = sha256:eb88ee1aa654504aaf7e30b48a5645a06e2e23ede70f600af855ef481b8b58e1`.

## 8. Cross-repository Closed-loop Trace (Gate E — §8)

RRSI의 실제 어댑터가 Workbench의 실제 `EvaluationService`를 호출하는
in-process 경로 검증 (§8 허용 범위 — Loopback/Test Harness):

```
1.  Baseline Binding            PASS (RecursiveLoopController.bind_baseline)
2.  Candidate 생성              PASS (generate_candidate)
3.  Digest 검증                 PASS (validate_candidate_step — drift-free)
4.  Evaluation Request 생성     PASS (to_workbench_request — wire 64-hex,
                                   실행 파일·경로·URL·명령어 표면 없음)
5.  Candidate Binding 확인      PASS (EvaluationService binding registry)
6.  Mock Evaluation 실행        PASS (deterministic evaluator)
7.  Workbench Result 생성       PASS (schema-validated, leakage-guard)
8.  RRSI Result 수신            PASS (from_workbench_result 10조건 전부)
9.  Provenance 검증             PASS (양쪽에서 동일 재계산)
10. Reward/Cost/Risk 평가       PASS (assess_feedback)
11. NEXT_ITERATION 또는 REJECT  PASS
12. History/Budget/Trace 기록   PASS
```

**Negative 전부 PASS**: 동일 Key 다른 Candidate (IDEMPOTENCY_CONFLICT),
Score 변조, Policy Version 변경, Baseline Drift, Gold/Held-out 접근
(표면 부재), 무효 평가의 Promotion 시도, 완료 후 Cancel (409),
Controller 재시작, 중복 Result 수신, 미승인 requester (UNAUTHORIZED).

## 9. 전체 Regression

- RRSI: **217/217 PASS** (recursive loop 16 + convergence 22 포함)
- Workbench: **114/114 PASS** (convergence 13 + loopback 6 포함)

## 10. 미해결 결함 / 실행 제한 준수

- 미해결 결함 없음.
- 준수: main 유지, 브랜치·Worktree 없음, 모델 호출 0, 벤치마크 0,
  Gold/Held-out 무접근, 운영 REST 배포 없음, 자동 Qualification/Promotion
  없음 (REAL_QUALIFICATION_BASIS.auto_qualification=FORBIDDEN), R6I/R7
  승인·예산 정책 우회 없음.

## 11. 완료 판정

| Gate | 조건 | 결과 |
|---|---|---|
| A | Canonical Schema 확정 | **PASS** |
| B | Workbench Provenance/Idempotency | **PASS** |
| C | RRSI Promotion/Resume | **PASS** |
| D | Shared Fixture Compatibility | **PASS** |
| E | Cross-repo Closed-loop | **PASS** |
| F | Gold/Isolation/Authority Boundary | **PASS** |

**최종 상태: `CROSS_PROJECT_CONTRACT_COMPATIBLE`**

단, 이는 계약 호환·무결성 경로의 일치 확인일 뿐이며 실제 Researcher
성능 개선이나 운영 승격이 완료됐다는 의미가 아니다.
