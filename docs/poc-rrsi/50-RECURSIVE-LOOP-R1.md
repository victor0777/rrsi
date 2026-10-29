---
doc_id: poc-rrsi-50-recursive-loop-r1
title: RRSI-RECURSIVE-LOOP-R1 — Recursive Improvement Controller
status: contract
updated: 2026-10-29
---

# RRSI-RECURSIVE-LOOP-R1 — Candidate Generation, Evaluation Feedback & Recursive Improvement (문서 50)

구현: `poc/recursive_loop_r1.py` · 테스트:
`poc/tests/test_recursive_loop_r1.py` (195/195 전체 스위트 — 신규
16건). 모델 호출 0, 벤치마크 실행 0, 운영 Researcher 무변경.

## 1. 기존 RRSI 구성요소 재사용 Matrix (산출물 1)

`REUSE_MATRIX` 상수 (코드 내):

| 구성요소 | 재사용 내용 |
|---|---|
| `poc_core.py` | cand_* 변형 생성기·guards_fn·critic_review·evaluate_fixture → CandidateContract |
| `budget_policy.py` | check_prestart·assert_within_budget — **동일 총량 정책** 사용, 병렬 정책 없음 |
| `execution_permit.py` | 실제 평가 실행은 R6I Owner permit 경로 유지 |
| `dataset_manifest.py` | canonical digest 규율 재사용 |
| `gold_review.py` | 승인 게이트 시맨틱 — Gold/Held-out 경계 |
| `r7_contract.py` | Evaluation Policy 버전·Admission 게이트 |
| 문서 26–28 | Reward regularization 우선 |
| 문서 37–39 | 지표 분모·승격 증거 요건 |

## 2. Candidate Contract (산출물 2) — `validate_candidate`

필수 11필드: `candidate_id`(cand- 접두), `parent_candidate_id`,
`target_project`, `target_version`, `candidate_digest`(sha256,
description+profile+envelope 결합 서명), `change_type`, `change_scope`,
`change_description`, `execution_profile`, `resource_envelope`
(max_eval_tokens 필수), `generation_provenance`.

- **변경 범위는 Harness 설정 6종 한정**: system/task prompt, tool
  selection policy, context planning policy, retrieval strategy,
  memory/evidence selection, reasoning control parameters.
- `production_source_code` 등 타 scope → `FORBIDDEN_CHANGE_SCOPE`
  (기계 차단).

## 3. Workbench Evaluation Client 계약 (산출물 3) — `MockWorkbenchClient`

| 동작 | 계약 |
|---|---|
| 평가 요청 | candidate 검증 후 submit — Mock Job (실 API 부재, §4 허용) |
| 상태 조회 | `status(job_id)` — REQUESTED→(tick)→COMPLETED |
| Result 수신 | `result(job_id)` — 미완료 시 `PendingResult` |
| Provenance 검증 | self-excluding canonical digest — **정책 버전 포함**, 변조 시 검증 실패 |
| Budget 정산 | `settle` — 토큰 원장 누적, 초과 시 `BUDGET_EXHAUSTED` |
| Retry/Timeout/Cancel | `PendingResult` 상위 처리, `cancel(job_id)` |
| 중복 방지 | request_key = f(digest, policy_version) → **Idempotent** (T07) |
| 오류 처리 | 무효 평가·provenance 실패 → TERMINATED, 승격 금지 (T05) |

- **경계**: Workbench scorer import 없음, Gold/Held-out 저장소 직접
  접근 없음 — 상세 피드백 요청은 `HELD_OUT_DETAIL_ACCESS_DENIED`
  차단 (T11).

## 4. Recursive Loop State Machine (산출물 4)

`STATES`: BASELINE_BOUND → CANDIDATE_GENERATED → CANDIDATE_VALIDATED →
EVALUATION_REQUESTED → EVALUATION_COMPLETED → FEEDBACK_ASSESSED →
REJECTED / REVISE_CANDIDATE / NEXT_ITERATION / PROMOTION_PROPOSED /
TERMINATED.

| 상황 | 처리 |
|---|---|
| Evaluation 실패/무효 | TERMINATED (`EVALUATION_INVALID`) |
| Provenance 실패 | TERMINATED |
| Candidate Digest Drift | TERMINATED (`CANDIDATE_DIGEST_DRIFT`) (T06) |
| Baseline 변경 | TERMINATED (`BASELINE_CHANGED`) |
| Budget 소진 | `BUDGET_EXHAUSTED` — 반복 종료 (T08) |
| 중복 평가 | Idempotent — 동일 job 반환 (T07) |
| 반복 정체 | TERMINATED (`IMPROVEMENT_STAGNATION`, ε=0.005, 3회 창) (T09) |
| 동일 Candidate 재생성 | `REVISE_CANDIDATE` — 재평가 금지 |
| 과적합 위험 | 표본 <3 또는 baseline 불일치 → UNDECIDABLE — 승격 확정 금지 |
| 재시작 Resume | snapshot/resume — history·budget·state 보존 (T12) |

## 5. Reward / Cost / Risk Decision Policy (산출물 5) — `assess_feedback`

7축: answer_quality, evidence_quality, token_cost, gpu_cost, latency,
reliability, regression_risk.

| 규칙 (우선순위) | 결과 |
|---|---|
| 표본 <3 또는 비교 baseline 버전 불일치 | UNDECIDABLE |
| answer_quality delta ≤ 0 | REJECT |
| evidence_quality delta < 0 | REJECT (regression 차단) |
| reliability delta < −0.02 | REJECT |
| token/gpu/latency 상대 악화 > 10%/10%/15% | HOLD → REVISE |
| 통과 | ADVANCE → 다음 Iteration |

- 문서 26–28 regularization 정책 우선 — 단일 점수 최대화 아님.
- **품질 개선 + 비용 초과 → 승격 추천 안 함** (T03).

## 6. Promotion Request Contract (산출물 6) — `propose_promotion`

9필수: baseline_identity, candidate_identity, evaluation_evidence,
quality_delta, cost_delta_tokens, regression_summary,
evaluation_policy_version, residual_risks, rollback_plan —
status **PENDING_OWNER_APPROVAL** 고정. RRSI는 운영 승격 권한 없음;
Workbench 통과도 자동 승격 아님 (T10).

## 7. Mock Closed-loop 테스트 (산출물 7) — 16건

§9 시나리오 12건 전부 PASS: 개선→Advance(T01), 악화→Reject(T02),
품질↑비용악화→HOLD(T03), Evidence regression→차단(T04), 무효→금지(T05),
Drift→차단(T06), 중복→Idempotent(T07), Budget→종료(T08), 정체→종료(T09),
Proposal→Owner 대기(T10), Held-out→차단(T11), Resume→보존(T12) +
계약 테스트 4건.

## 8. Researcher 적용 범위 (산출물 8)

- 적용: Researcher **Harness 설정** (6 scope) — 후보 생성·평가 요청·
  개선 제안.
- 제외: Production Source Code 수정, 운영 Registry 변경, 자동 승격,
  자동 Researcher 변경 — 전부 경계 밖.

## 9. 변경 파일 / Commit (산출물 9)

- `poc/recursive_loop_r1.py` (신규), `poc/tests/test_recursive_loop_r1.py`
  (신규), 본 문서, README — Commit SHA는 커밋 후 보고.

## 10. 후속 승인 요청 (산출물 10)

실제 개선 실험 실행 전 Owner 승인 필요:

1. **Workbench 실제 Candidate Evaluation API 확정 여부** 확인
   (Mock → Real client 교체 시점).
2. Evaluation Policy 버전·지표 스키마 동결 (R7 문서 39 계승).
3. 예산: 반복당 평가 호출 수, 총 토큰/GPU/Wall 상한.
4. 기준 Baseline identity 스냅샷 및 Rollback 계획 승인.
5. Gold/Held-out 접근 계속 금지 확인.
6. 승격은 대상 Researcher Owner의 별도 결정 — 본 컨트롤러는 제안만.

**본 단계에서 실제 개선 Iteration은 실행되지 않았다.**
