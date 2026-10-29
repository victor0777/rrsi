---
doc_id: poc-rrsi-40-r7-d2-evaluation-contract
title: R7-D2 Evaluation Contract (Claim Anchor & Semantic Verification)
status: contract
updated: 2026-10-29
---

# R7-D2 — Evaluation Contract (문서 40)

구현: `poc/r7_contract.py` · 테스트: `poc/tests/test_r7_contract.py`
(112/112 전체 스위트 통과, 본 계약 9건). R6I 운영 코드 무변경.

## 1. Claim Schema (A1 — 자리표시자 없음)

```json
{"claim_id": "c-<seq>",
 "kind": "numeric_error" | "info_loss" | "missing_evidence" | "contradiction",
 "target_note": "original" | "perturbed",
 "anchors": [{
   "anchor_role": "required-role per kind (A2 계약)",
   "document_id": "doc registry key",
   "document_digest": "sha256:<exact document text>",
   "document_role": "source_paper" | "original_note" | "perturbed_note",
   "locator": "section/paragraph/sentence/span identifier",
   "quote": "<=120 chars",
   "match_policy": "byte_exact" | "markdown_normalized" | "semantic_review",
   "verification_status": "UNVERIFIED|VERIFIED|FAILED|PENDING_HUMAN_REVIEW"
 }]}
```

- `info_loss` 3-anchor 유지, 역할 고정: `original_note_anchor`(원본 Note
  내 정보 위치) / `absence_evidence`(대상 Note의 인접 문맥 — 삭제된
  문장 자체는 존재하지 않음) / `importance_evidence`(원문 논문 근거).
- `contradiction`은 인용 2건 필수.

## 2. Anchor 검증 규칙 (fail-closed)

| 조건 | 결과 |
|---|---|
| 필수 필드 누락 (id/digest/role/locator/quote/policy) | `FAILED` |
| document 미등록 | `FAILED` (`DOCUMENT_ABSENT`) |
| **digest 불일치** | `FAILED` (`DOCUMENT_DIGEST_MISMATCH`) |
| quote 부재 (byte/markdown policy) | `FAILED` (`QUOTE_ABSENT`) |
| `match_policy: semantic_review` | **`PENDING_HUMAN_REVIEW`** (기계 결정 불가 — FAILED 아님) |

Claim 전체: 필수 anchor 역할 누락 → `FAILED`; FAILED anchor 없고
PENDING 있으면 `PENDING_HUMAN_REVIEW`; 모두 VERIFIED일 때만
`VERIFIED`.

## 3. Absence Evidence — Local vs Global 분리 (A2)

- **Local Evidence**: original_note_anchor 인용이 perturbed note에
  정규화 기준 부재함을 확인 (삭제 위치 대응).
- **Global Absence**: perturbed note **전체**에서 동일 의미 정보의
  다른 위치 잔존 확인 — 본 계약은 어휘 키워드 프로브만 수행하며,
  **어휘 부재는 의미적 부재가 아님** → 어떤 프로브 결과든
  `PENDING_HUMAN_REVIEW`. 의미적 부재의 기계 확정은 E2 후보로만 기록.
- 기록 항목: 검증 범위, 비교 대상 digest(원본/대상 note), 검증 방법,
  프로브 키워드·적중 수, 검토 결과 — `verify_absence()` 반환 구조에
  전부 포함.

## 4. 정적 테스트 결과 (A3)

| 사례 | 결과 |
|---|---|
| 유효 Numeric Error Claim | PASS → VERIFIED |
| 유효 Partial Info Loss Claim | PASS → contract valid, semantic layer PENDING |
| 원본에 없는 정보의 허위 소실 주장 | PASS → FAILED (QUOTE_ABSENT) |
| 다른 위치에 정보 잔존 | PASS → PENDING_HUMAN_REVIEW (어휘 적중 >0) |
| 근거 위치가 잘못된 Claim | PASS → FAILED |
| 문서 Digest 불일치 | PASS → FAILED (fail-closed) |
| Markdown 정규화 필요 인용 | PASS → VERIFIED (`**15,733**`) |
| 필수 Anchor 누락 | PASS → FAILED (REQUIRED_ANCHOR_MISSING) |
| 문자열 부재만으로 VERIFIED 금지 | PASS → PENDING 유지 |

Fixture: 승인된 Development Fixture(R6I g4/g7) 텍스트 기반 합성 — 신규
Gold 생성 없음.
