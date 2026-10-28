# Gold Review Packet R4 — g2-1802-method

## 0. Revision Record (이전 검토 기록 보존)

- 이전 packet: `docs/poc-rrsi/review-packets/packet-g2-1802-method.md` (commit `16a1c14`) — **삭제/덮어쓰기 없음**
- R1 독립 검토 판정 (2026-10-29, 외부 AI 검토 — 최종 인간 승인 아님): **REJECT**
- 지적 사유: **cross-paper binding 오류** — 1802 fixture에 1901 perturbation(`p5-1901-method-removed`) 연결됨
- 본 수정: 연결 해제. 1802 대상 P5(방법론 단계 제거) 변형은 존재하지 않음 → **UNAVAILABLE** (임의 연결 금지). 신규 변형 생성은 별도 지시 필요.

## 1. Fixture ID

g2-1802-method

## 2. Identity Blocks

| 항목 | 값 |
|---|---|
| Paper Identity / Source Version | 1802.07862, arXiv v1, capture sha256 `9741540db1f1212fd132d7dd1b11d182a10be79732208598cf52c7c8aee004d0` |
| Reader Note Identity | note(1802) digest `99efc53f0df17bc50f4a53f0f0cf5cea63a00e6f71b2cae2b7100a61b02d9bfa` |
| Perturbation Identity | **UNAVAILABLE** — 1802용 P5 변형 없음 (r2 보유 변형: p1[P1], p3ext[P3], p4[P4] 전부 1802이나 g2의 방법론-단계 검증과 유형 불일치; p1은 우연히 g2 관련 요약 문장도 포함 삭제하지만 g1 주장 검증용이므로 g2 검증으로 재배정 불가) |
| Gold Bundle Digest | `3ce9c206f4a83008cf5bd9994be64cc952981ea3ea74c16b5ffca073daf25523` (공통 bundle digest) |

## 3. 평가 대상 Claim (B-1)

modality attention selects the most informative modality (word/char/image) per decoding step

## 4. Source Sentence + Source Reference (B-7)

> Second, we also propose a general modality attention module which chooses per decoding step the most informative modality among available ones (in our case, word embeddings, character embeddings, or visual features) to extract context from.

- Source Reference: full_text "Front matter" 기여 제2항 관련 서술 (§3 Proposed Methods에서 확장 서술), QASPER dataset sha `2ae7ee62…` (frozen)

## 5. Source Context (B-2)

> …an accompanying snap image of a board game can help disambiguate among polysemous entities, thereby correctly recognizing it as a named entity. **Second, we also propose a general modality attention module which chooses per decoding step the most informative modality among available ones (in our case, word embeddings, character embeddings, or visual features) to extract context from.** For example, the modality attention module lets the decoder attenuate the word-level signals for unknown word tokens ("Marshmellooooo" with trailing `o's) and amplifies character-l…

## 6. Reader Note 실제 관련 문장 (B-3)

> A key innovation is a modality attention mechanism that dynamically weights word, character, and visual inputs per token.

## 7. Perturbed Note 실제 관련 문장 (B-4)

**해당 없음 — UNAVAILABLE** (교차 연결이었던 `p5-1901-method-removed`는 1901.10133 note 기반 변형으로 paper identity 불일치 → 연결 해제, 기록만 유지)

## 8. Original ↔ Perturbed 정확한 차이 (B-5)

**해당 없음 — UNAVAILABLE**

## 9. 의미적 결함인 이유 (B-6)

**해당 없음 — UNAVAILABLE** (검증 가능한 perturbation이 확보될 때까지 본 fixture는 semantic gold 판정 대상에서 제외)

## 10. 기대 판정 (작성자 기대 — 검증이 아님)

- 방법론 단계 소실 시 method coverage ↓ — 단, 검증용 변형이 없어 **판정 자체 미확정**.
⚠ 작성자 기대 판정을 검증 결과로 간주하지 말 것

## 11. 검토자 판정 입력란

- Decision (Approve / Reject / Needs Revision): ______
- Approve 시 필수 5조건: source_identity_match ☐ source_context_sufficient ☐ claim_evidence_relation_verified ☐ perturbation_semantic_defect_confirmed ☐ expected_direction_verified ☐
- Reviewer Comment: ______
- Review Timestamp: ______
- Reviewed Fixture Digest (bundle `3ce9c206…`): ______
- Reviewer / Role (author 역할의 승인 불가): ______
