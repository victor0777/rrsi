# Gold Review Packet R4 — g3-1802-result

## 0. Revision Record (이전 검토 기록 보존)

- 이전 packet: `docs/poc-rrsi/review-packets/packet-g3-1802-result.md` (commit `16a1c14`) — **삭제/덮어쓰기 없음**
- R1 독립 검토 판정 (2026-10-29, 외부 AI 검토 — 최종 인간 승인 아님): **NEEDS_REVISION**
- 지적 사유: 15,733→15,800 **실제 변형 문장 미제시**
- 본 수정: r1 실험의 실제 변형본 문장 제시 + paper 일치 확인

## 1. Fixture ID

g3-1802-result

## 2. Identity Blocks

| 항목 | 값 |
|---|---|
| Paper Identity / Source Version | 1802.07862, arXiv v1, capture sha256 `9741540db1f1212fd132d7dd1b11d182a10be79732208598cf52c7c8aee004d0` |
| Reader Note Identity | note(1802) digest `99efc53f0df17bc50f4a53f0f0cf5cea63a00e6f71b2cae2b7100a61b02d9bfa` |
| Perturbation Identity | `poc/runs/perturbation-audit/r1/p2-1802-vocab.md` (P2), perturbed_note_digest `cac6ae09c5d83aff8664079dc9a4fcd6fd02d07f67bc08ca72df8f6cb2400531` |
| Gold Bundle Digest | `3ce9c206f4a83008cf5bd9994be64cc952981ea3ea74c16b5ffca073daf25523` (공통 bundle digest) |

- **Identity 대조**: fixture(1802) = note(1802) = perturbation(1802) ✓ (이전 packet은 perturbation 지정 없음/불명확 → 본 수정에서 r1 변형으로 확정)

## 3. 평가 대상 Claim (B-1)

SnapCaptions vocabulary size is **15,733** tokens

## 4. Source Sentence + Source Reference (B-7)

> The captions data have average length of 30.7 characters (5.81 words) with vocabulary size 15,733, where 6,612 are considered unknown tokens from Stanford GloVE embeddings BIBREF22 .

- Source Reference: full_text "4 Empirical Evaluation" → SnapCaptions Dataset 데이터 통계 문단

## 5. Source Context (B-2)

> …ted visual descriptor features extracted from the pre-trained InceptionNet are available). We split the dataset into train (70%), validation (15%), and test sets (15%). **The captions data have average length of 30.7 characters (5.81 words) with vocabulary size 15,733, where 6,612 are considered unknown tokens from Stanford GloVE embeddings BIBREF22 .** Named entities annotated in the SnapCaptions dataset include many of new and emerging entities, and they are found in various surface forms (various nicknames, typos, etc.) T…

## 6. Reader Note 실제 관련 문장 (B-3)

> Captions average 30.7 characters (5.81 words) in length, with a vocabulary size of 15,733 tokens; of these, 6,612 are unknown to the Stanford GloVE embeddings.

## 7. Perturbed Note 실제 관련 문장 (B-4, r1 `p2-1802-vocab.md`)

> Captions average 30.7 characters (5.81 words) in length, with a vocabulary size of **15,800** tokens; of these, 6,612 are unknown to the Stanford GloVE embeddings.

## 8. Original ↔ Perturbed 정확한 차이 (B-5)

`15,733` → `15,800` — §6/§7 문단(133행) 단일 위치 치환, 나머지 문장 동일 (문장 구조·토큰 수 변화 없이 수치 1곳만 변경)

## 9. 의미적 결함인 이유 (B-6)

15,800은 원문에 부재하는 값(source literal: "vocabulary size 15,733") — note가 source의 실제 통계와 다른 어휘 크기를 전달 = **numeric inconsistency** (designated_numeric_consistency로 결정론 감지 가능 — r1 PASS)

## 10. 기대 판정 (작성자 기대 — 검증이 아님)

- numeric consistency ↓ (designated 값 불일치 감지).
⚠ 작성자 기대 판정을 검증 결과로 간주하지 말 것

## 11. 검토자 판정 입력란

- Decision (Approve / Reject / Needs Revision): ______
- Approve 시 필수 5조건: source_identity_match ☐ source_context_sufficient ☐ claim_evidence_relation_verified ☐ perturbation_semantic_defect_confirmed ☐ expected_direction_verified ☐
- Reviewer Comment: ______
- Review Timestamp: ______
- Reviewed Fixture Digest (bundle `3ce9c206…`): ______
- Reviewer / Role (author 역할의 승인 불가): ______
