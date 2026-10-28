# Gold Review Packet R4 — g6-1901-claim

## 0. Revision Record (이전 검토 기록 보존)

- 이전 packet: `docs/poc-rrsi/review-packets/packet-g6-1901-claim.md` (commit `16a1c14`) — **삭제/덮어쓰기 없음**
- R1 독립 검토 판정 (2026-10-29, 외부 AI 검토 — 최종 인간 승인 아님): **REJECT**
- 지적 사유: **cross-paper binding 오류** — 1901 fixture에 1802 perturbation(`p1-1802-claim-removed`) 연결됨
- 본 수정: 연결 해제. 1901 대상 P1(핵심 주장 제거) 변형 없음 → **UNAVAILABLE** (임의 연결 금지)

## 1. Fixture ID

g6-1901-claim

## 2. Identity Blocks

| 항목 | 값 |
|---|---|
| Paper Identity / Source Version | 1901.10133, arXiv v1, capture sha256 `652151f6b22c2a972b206c7f1ba67639c0f095e5767d976b527602cbe9ac2c1a` |
| Reader Note Identity | note(1901) digest `97f5dd09a78bfb3db941999b4dc977319a2ffe25b8c5781970396f44b1122410` |
| Perturbation Identity | **UNAVAILABLE** — 1901용 P1 변형 없음 (r2 보유 1901 변형: p2ext[P2확장 θ], p5[P5 방법론 단계]; p1-1802-claim-removed는 1802 note 기반 → paper identity 불일치, 연결 해제) |
| Gold Bundle Digest | `3ce9c206f4a83008cf5bd9994be64cc952981ea3ea74c16b5ffca073daf25523` (공통 bundle digest) |

## 3. 평가 대상 Claim (B-1)

structuring an unordered text document is the paper objective

## 4. Source Sentence + Source Reference (B-7)

> To structure an unordered document is an essential task in many applications.

- Source Reference: full_text "Front matter" (Abstract/Introduction 서술), QASPER dataset sha `2ae7ee62…` (frozen)

## 5. Source Context (B-2)

- 1901 full_text 서두: "To structure an unordered document is an essential task in many applications" 로 시작하는 서술이 Introduction에서 목적 진술로 전개됨. note 요약부와 대응되는 문장은:

> The paper addresses the specific problem of structuring an unordered text document … The primary objective is to segment this flat text into distinct, meaningful sections.

## 6. Reader Note 실제 관련 문장 (B-3)

> This paper proposes a method to segment unordered text documents into logical sections by clustering sentences around extracted keywords.

## 7. Perturbed Note 실제 관련 문장 (B-4)

**해당 없음 — UNAVAILABLE** (이전에 교차 연결된 `p1-1802-claim-removed`는 1802 note 기반 변형 — paper identity 불일치 → 연결 해제, 기록만 유지)

## 8. Original ↔ Perturbed 정확한 차이 (B-5)

**해당 없음 — UNAVAILABLE**

## 9. 의미적 결함인 이유 (B-6)

**해당 없음 — UNAVAILABLE** (적절한 1901 변형이 확보될 때까지 본 fixture는 semantic gold 판정 대상에서 제외)

## 10. 기대 판정 (작성자 기대 — 검증이 아님)

- 주장 소실 시 claim fidelity ↓ — 단, 검증용 변형 부재로 **판정 자체 미확정**.
⚠ 작성자 기대 판정을 검증 결과로 간주하지 말 것

## 11. 검토자 판정 입력란

- Decision (Approve / Reject / Needs Revision): ______
- Approve 시 필수 5조건: source_identity_match ☐ source_context_sufficient ☐ claim_evidence_relation_verified ☐ perturbation_semantic_defect_confirmed ☐ expected_direction_verified ☐
- Reviewer Comment: ______
- Review Timestamp: ______
- Reviewed Fixture Digest (bundle `3ce9c206…`): ______
- Reviewer / Role (author 역할의 승인 불가): ______
