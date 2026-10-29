---
doc_id: poc-rrsi-47-r7-d2b-reviewer-evidence-governance
title: R7-D2B Reviewer & Evidence Governance
status: contract
updated: 2026-10-29
---

# R7-D2B — Reviewer & Evidence Governance (문서 47)

구현: `poc/r7_contract.py` · 테스트: `poc/tests/test_r7_contract.py`
(162/162 — 기존 148 보존, 신규 14건). R6I 운영 코드 무변경.

## 1. Synthetic / Evaluation Context 분리 (C1)

`VERIFICATION_CONTEXTS = ("TEST", "EVALUATION")` —
`resolve_verification_context()`:

| 항목 | TEST | EVALUATION |
|---|---|---|
| Synthetic Reviewer | 허용 | **금지** (`REGISTERED`여도 승격 거부 → PENDING) |
| 실제 Reviewer | 선택적 | 필수 (`REGISTERED` 비합성) |
| Synthetic Fixture | 허용 | 금지 |
| 실제 Gold 접근 | 금지 | 승인된 Adjudicator만 |
| Verification 결과 | TEST 전용 (`evaluation_eligible=False`) | 평가용 (`evaluation_eligible` = VERIFIED 시에만 True) |

- Context 누락 → **TEST 기본값, 절대 EVALUATION 암묵 승격 없음**.
- `evaluation_request=True` + 비-EVALUATION context → `blocked=True`
  (T03: `EVALUATION_REQUEST_WITHOUT_EVALUATION_CONTEXT`).
- EVALUATION context는 `evaluation_request=True`와만 양립 (무요청
  EVALUATION도 blocked).

## 2. Reviewer Registry 운영 계약 (C2)

- 메모리 registry는 **테스트 스캐폴드** — 운영 registry로 간주 금지.
- `PERSISTENT_REGISTRY_CONTRACT`: 레코드 필드 (reviewer_id,
  reviewer_status, synthetic, approved_by, approved_at, revoked_at) +
  레지스트리 필드 (registry_version, registry_digest, change_history).
- `registry_version()` = `rv-<n>` (변경 시 증가), `registry_digest()`
  = canonical JSON sha256, 변경 이력 레코드별 누적.
- 실제 검토자 ID 임의 생성 금지, Owner 승인 전 Evaluation claim
  VERIFIED 승격 금지. 본 단계에서 운영 Reviewer 등록·승인 없음.
- 영속 저장소 제안(최소 범위): JSON 파일 1개 + version 카운터 +
  digest + append-only 변경 이력 (owner 승인 후 구현).

## 3. Review Record Binding (C3)

기록에 `reviewer_registry_version`·`verification_context` 필드 결합:

- **Registry Version 불일치** → `REVIEW_REGISTRY_VERSION_MISMATCH` →
  PENDING (검토 당시 버전 ≠ 현재 상태 구분).
- **철회(Revoked) 정책 (기본 권고)**: 신규 검증에 철회 검토자 사용
  금지 / 기존 기록 삭제하지 않음 / 재검증 필요 여부는 철회 사유·평가
  정책으로 판정 / 판단 불가 → `PENDING_HUMAN_REVIEW`.

## 4. Residual Location Manifest (D2) — `build_residual_manifest`

| 필드 | 내용 |
|---|---|
| `probe_id` / `location_id` | 정규화 ID `document_id:keyword:span_start` 로 중복 제거 |
| `document_id` / `document_digest` | 문서 버전 결합 — **버전 변경 시 재사용 금지 (digest-bound)** |
| `keyword` / `locator` / `matched_text` / `match_span` | 위치·적중 문자·char span |
| `probe_method` | 라틴 어휘 프로브, 보조 검색 전용 명시 |

## 5. Location-level Review (D3)

각 위치 기록: `location_id`, `reviewer_id`, `review_status`
(`REVIEWED/NOT_REVIEWED/INSUFFICIENT_EVIDENCE`),
`semantic_equivalence_verdict` (`EQUIVALENT/NOT_EQUIVALENT/UNCERTAIN`),
`rationale`, `review_evidence_refs`.

| 조건 | 결과 |
|---|---|
| 위치 일부라도 미검토 | `PENDING_HUMAN_REVIEW` |
| 동등 정보(EQUIVALENT) 확인 | **`FAILED`** (전체 소실 주장 기각) |
| 불확실(UNCERTAIN) | `PENDING_HUMAN_REVIEW` |
| 전부 검토 + 동등 정보 없음 + 나머지 조건 충족 | `VERIFIED` 가능 |
| 부분 소실 | **claim의 정보 단위 기준** 동등성 — 용어·상위 개념 잔존만으로 부분 소실 부정 금지 |

- `lexical_probe_reviewed` boolean: TEST 경로에서만 하위 호환 유지,
  **EVALUATION에서 승인 근거로 불인정** (T06/T07으로 기계 강제).

## 6. Probe Coverage 한계 (D4)

Probe는 보조 검색 수단 — 무적중이 전체 부재를 입증하지 않음. 인간
검토는 전체 Perturbed Note 대상. Coverage 한계는 평가 기록
(`probe_method`·`probe_coverage_limits`)에 보존.

## 7. Gold Independence Policy (Workstream B4)

독립 검토자 2명 절차: ① 검토자별 독립 판정 ② 상호 비공개 1차 검토
③ 불일치 기록(평균·삭제 금지) ④ Adjudication ⑤ 최종 Gold 확정
⑥ Gold Freeze ⑦ Judge 평가 이후 Gold 변경 통제(신규 버전 + 변경 사유
유지, 기존 버전 불변). **Gold 미생성·미검증 상태에서 `DATASET_READY`
승격 금지.**
