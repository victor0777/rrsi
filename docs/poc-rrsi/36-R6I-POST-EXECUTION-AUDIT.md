---
doc_id: poc-rrsi-36-r6i-post-execution-audit
title: R6I Post-execution Evidence Audit (AUDIT_VERIFIED — zero model calls)
status: report
updated: 2026-10-29
---

# R6I Post-execution Evidence Audit — Report

**Summary.** 실행 종료 후 봉인 증거·판정 재현을 감사 (모델 호출 0).
판정: **`AUDIT_VERIFIED`** — 증거 10종 전부 존재, 체인 검증 전부 통과,
오프라인 재판정이 기존 adjudication과 **완전 일치** (차이 0). Raw
Evidence는 기존 보존 위치에서 불변; 인용 상세는 감사본에만 기록.

---

## 1. 증거 검증 (§A)

| 파일 | SHA-256 (앞 16) | 검증 |
|---|---|---|
| Owner Approval Record (`owner-approval-r6i.json`) | `ed930f48970d6727…` | ✓ digest가 Permit에 바인딩 |
| Permit (`permit-semjudge-r6i-g4g7.json`) | `9575ceb4a1e7a2fb…` | ✓ 발급 Ledger 등록 확인 |
| Issuance Ledger | `e707b4636d034227…` | ✓ |
| Manifest g4 / g7 | `91633df7…` / `2585d356…` | ✓ |
| Raw g4 / g7 | `c59070b8…` / `0aa7b50a…` | ✓ |
| Reservation Ledger | `c0de2ae8…` | ✓ 4행 (runner 2 + call path 2), ceiling 4 |
| Adjudication Report | `f198c575…` | ✓ |
| Seal | `7a4a8e75…` | ✓ seal 검증 PASS |

전체 Manifest: `poc/runs/r6i-audit/evidence-manifest.sha256` (10행).

**Scope·호출·예산·순서 일치**: 승인 scope(invocation/workstream/call_type/
papers) = 실제 호출 대상 = g4·g7 2회; 토큰 4,976/6,000; 실행 순서 g4 → g7
(순차, 동시성 1) — 모두 일치.

## 2. 판정 재현 (§B)

봉인 Raw Response만 사용해 `adjudicate_response()`로 오프라인 재판정:

| Fixture | 재현 | 기존과 비교 |
|---|---|---|
| g4 | AGREEMENT (10,000 동치 인식·12,000 오류 식별) | **일치** |
| g7 | AGREEMENT + VERIFIED + semantic_success True | **일치** |

**차이: 없음.**

## 3. g7 인용 상세 (§C)

| # | 인용 (요약) | 원본 구절 | byte-exact | 정규화 후 | 내용 변경 |
|---|---|---|---|---|---|
| 1 | "TextRank: This is a statistical method originally designed…" | 원본 note `*   **TextRank**: This is…` | ✗ | ✓ | 없음 |
| 2 | "The first algorithmic step involves extracting keywords…" | 원본 note `…using the **TextRank** algorithm.` | ✗ | ✓ | 없음 |
| 3 | "The paper explicitly identifies two specific algorithms…" | perturbed note (동일 문장) | ✗ | ✓ | 없음 |
| 4 | "The combination of these two methods suggests a hybrid…" | perturbed note (동일 문장) | ✓ | ✓ | 없음 |

4/4 정규화 일치, 정규화 외 내용 변경 0. 기존 r6i-report의 byte-exact
`citation_accuracy` 필드는 **덮어쓰지 않음** — 본 감사에 별도 기록.

## 4. 결론

**AUDIT_VERIFIED** — 증거 체인·예산·판정 재현이 모두 일치. 민감정보
(승인 기록 원문 내용 등) 제외 후 보고서·Manifest는 `poc/runs/r6i-audit/`
에 보존 및 main 커밋. Raw Evidence 위치 불변. Evolution·δ Calibration
**HOLD 유지**, 추가 모델 호출 없음.
