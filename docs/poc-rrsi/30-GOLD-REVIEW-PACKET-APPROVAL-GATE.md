---
doc_id: poc-rrsi-30-gold-review-packet-approval-gate
title: Semantic Gold Review Packet & Approval Gate (executed, 0 model calls)
status: report
updated: 2026-10-28
---

# Gold Review Packet & Approval Gate Report

**Summary.** 독립 검토용 **Review Packet 8건 생성**(g5 제외) — 각 packet에
10필수 항목(문맥 포함 원문 근거·note 해당 내용·변형 차이·판정 입력란)을 담아
원문 전체 없이도 주장-근거 관계를 검토 가능. **g5 격리 검토: `Evidence
Absence` 확정 → Semantic Reward 평가 대상에서 제외** — source는 dataset
composition만 서술(release 동작 0), note 자체가 release 정보 부재를 기록
(내부 비정합), gold "No"는 양측 모두 자동 채택 금지 유지. **Independent
Review Contract**를 구현(`poc/gold_review.py`) — author-path 자체 승인 거부
(`SELF_APPROVAL_REFUSED`, 실증)·5조건 미충족 승인 거부(실증)·digest 귀속.
Marked **70/70 PASS**. 승인 대기 fixture 8건. 판정: **HOLD 유지**.

---

## A. Gold Review Packet (지시 §A) — 8건 + 1건 제외

`poc/runs/perturbation-audit/r3-review-packet/` (invocation-bound + seal).
`packet-g1-1802-claim.md` … `packet-g9-1901-evidence.md` 중 g5 제외 8건.
10필수 항목: ① Fixture ID ② Paper Identity·Source Version(capture sha256) ③
평가 대상 ④ 원문 Source Sentence(anchor) ⑤ 최소 주변 문맥(±200/260자 —
불충분 시 원문 위치 제공·검토 범위 확장 가능 명시) ⑥ Reader Note 해당 내용 ⑦
Perturbation 내용(r2 변형본 경로+excerpt) ⑧ Original↔Perturbed 차이 ⑨ 기대
판정·근거("작성자 기대 — 검증이 아님" 경고 명시) ⑩ 검토자 판정 입력란.

## B. g5 격리 검토 (지시 §B) — `Evidence Absence` 확정

| 확인 | 결과 |
|---|---|
| Source 문장 분석 | "The SnapCaptions dataset is **composed of** 10K … manually labeled by expert human annotators" — **composition 서술뿐** |
| release 동작 명시 여부 | **원문 전체에서 0** (전수 검색) |
| note 내부 정합성 | note 자체가 "release에 대한 명시 정보 없음"을 기록 — **note의 release 주장은 내부 비정합** |
| 기존 AMBIGUOUS 판정과의 충돌 | gold "No"(silence→No)와 release 주장의 근거 관계는 양립 불가 — **gold 자동 채택 금지 유지**(양측 모두) |
| 분류 | **`Evidence Absence`** — g5의 근거 전제(source 문장이 release 주장을 지지)가 성립하지 않음 |

- **처리: g5를 Semantic Reward 평가 대상에서 제외**(분류 확정에 따른 격리) —
  gold fixture 9건 → 유효 8건. 제외 사유는 dbe2d21 이래 반복 관측된
  release-정책 침묵 구조와 정합.

## C. Independent Review Contract (지시 §C) — 구현 + 실증

- 상태: `DRAFT → SOURCE_VERIFIED → HUMAN_REVIEW_REQUIRED → {APPROVED |
  REJECTED | NEEDS_REVISION}` (schema `rrsi-gold-review-record/v0.1`).
- **APPROVED 필수 5조건**: source_identity_match / source_context_sufficient /
  claim_evidence_relation_verified / perturbation_semantic_defect_confirmed /
  expected_direction_verified — 전부 true인 signed 기록만 승인.
- **권한 경계 (자동화 경로 분리)**: `reviewer_role=author` 계열의 Approve는
  **구조적으로 거부** (`SELF_APPROVAL_REFUSED`) — fixture 작성자와 동일한
  자동화 경로가 승인까지 수행할 수 없음. 실증: 자체 승인 시도 → 거부, 조건
  1개 미충족 독립자 승인 시도 → 거부 (`APPROVAL_CONDITIONS_INCOMPLETE`).
- **digest 귀속**: 검토 기록은 fixture 바이트 digest에 귀속 — fixture 수정
  시 기존 검토 무효.

## D. Review Interface (지시 §D) — Markdown Form

각 packet §10에 검토자 입력란 내장:
`Decision (Approve/Reject/Needs Revision)` / `Reviewer Comment` /
`Review Timestamp` / `Reviewed Fixture Digest` / `Reviewer·Role` + Approve 시
5조건 체크박스. JSON 대응: `record_review()` API가 동일 필드를 받아 append-only
`review-records.jsonl`에 기록 — 별도 UI 불필요.

## E. Semantic Evaluator Input/Output Contract (지시 §E) — 정의만, 미실행

**입력**: ① Approved Gold Fixture (APPROVED 상태 + digest 바인딩 검증) ②
Original Reader Note (digest) ③ Perturbed Reader Note (digest) ④ Source
Evidence (capture digest).

**출력**:
```
{ "schema": "rrsi-semantic-evaluation/v0.1",
  "dimension": "...",                       // 평가 축
  "gold_expected_direction": "...",          // Gold 기대 방향
  "evaluator_observed_direction": "...",     // 관측 방향
  "agreement": "Agreement|Disagreement",     // 대조
  "confidence": 0.0-1.0 | "unverified_reason": "...",  // 둘 중 하나 필수
  "evidence_references": [...] }             // 근거 참조
```
- 계약 제약: confidence 미산출 시 `unverified_reason` **필수** — 점수 임의
  생성 금지의 계약화. Model Judge 호출은 본 단계 미실행.

## F. 승인 대기 Fixture (지시 §F-6)

- **8건 승인 대기** (9건 − g5 제외 1건) — 전부 packet·form 준비 완료, 독립
  검토 대기.

## G. Semantic Discrimination 실행 준비 상태 (지시 §F-7)

| 단계 | 상태 |
|---|---|
| 결정론 축 (numeric/reference/literal/length) | **READY — 실동작 검증 완료**(28번) |
| semantic 축 | **대기** — ① 8건 독립 검토(APPROVED) → ② approved gold로 evaluator 실행(contract 정의 완료, judge 호출은 별도 승인) |
| δ Calibration | 대기 — gold review→judge→정의 안정성 순서 |

## H. 완료 보고 (지시 §F) 및 판정

1. Review Packet 8건 생성 (10항목 전부 포함). 2. g5: `Evidence Absence`
   확정·**제외**. 3. Independent Review Contract 구현·실증(5조건+author-path
   분리). 4. Review Form: Markdown 내장 + JSON API. 5. Evaluator I/O contract
   정의. 6. 승인 대기 **8건**. 7. 준비 상태: 결정론 READY, semantic 대기.
8. **Evolution GO/HOLD/STOP: HOLD 유지** — semantic 축의 해제는 이제 ① 독립
   검토자의 packet 심사(APPROVED 8건)와 ② judge 승인·실행만 남음. δ는 그
   이후. STOP 아님: 원본 artifact 무변경, author-path 승인 경로 실증적으로
   차단, 점수 임의 생성 0.

## 제한사항 준수

신규 모델 호출 **0**, Reader Pipeline 실행 **0**, QA 재실행 0, δ 반복 확대 0,
Fixture 자동 승인 0, RRSI Evolution 0, Final Holdout 소비 0, Scorer 수정 0,
Reader Note 원본 변경 0, ai_papers 운영 상태 변경 0, 신규 worktree 0.
