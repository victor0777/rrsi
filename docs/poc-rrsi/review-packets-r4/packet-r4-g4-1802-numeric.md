# Gold Review Packet R4 — g4-1802-numeric

## 0. Revision Record (이전 검토 기록 보존)

- 이전 packet: `docs/poc-rrsi/review-packets/packet-g4-1802-numeric.md` (commit `16a1c14`) — **삭제/덮어쓰기 없음**
- R1 독립 검토 판정 (2026-10-29, 외부 AI 검토 — 최종 인간 승인 아님): **NEEDS_REVISION**
- 지적 사유: **10K↔10,000 동치와 10,000→12,000 오류가 구분 없이 섞임**
- 본 수정: 두 축 분리 — (a) 원본 동치 표기(허용), (b) 변형 오류(감지 대상) (§10)

## 1. Fixture ID

g4-1802-numeric

## 2. Identity Blocks

| 항목 | 값 |
|---|---|
| Paper Identity / Source Version | 1802.07862, arXiv v1, capture sha256 `9741540db1f1212fd132d7dd1b11d182a10be79732208598cf52c7c8aee004d0` |
| Reader Note Identity | note(1802) digest `99efc53f0df17bc50f4a53f0f0cf5cea63a00e6f71b2cae2b7100a61b02d9bfa` |
| Perturbation Identity | `poc/runs/perturbation-audit/r1/p2-1802-size.md` (P2), perturbed_note_digest `063d6acaaea94b5dc974ee83920b9a86e403ffad7c53bc86310aaaf5ee36f50a` |
| Gold Bundle Digest | `3ce9c206f4a83008cf5bd9994be64cc952981ea3ea74c16b5ffca073daf25523` (공통 bundle digest) |

## 3. 평가 대상 Claim (B-1)

10,000 pairs = SnapCaptions dataset size (source 표기 "10K")

## 4. Source Sentence + Source Reference (B-7)

> The SnapCaptions dataset is composed of 10K user-generated image (snap) and textual caption pairs where named entities in captions are manually labeled by expert human annotators (entity types: PER, LOC, ORG, MISC).

- Source Reference: full_text "4 Empirical Evaluation" → SnapCaptions Dataset 첫 문장

## 5. Source Context (B-2)

> …that while we apply this modality attention module to the Bi-LSTM+CRF architecture (Section SECREF4 ) for its empirical superiority, the module itself is flexible and thus can work with other NER architectures or for other multimodal applications. SnapCaptions Dataset **The SnapCaptions dataset is composed of 10K user-generated image (snap) and textual caption pairs where named entities in captions are manually labeled by expert human annotators (entity types: PER, LOC, ORG, MISC).** These captions are collected exclusively from snaps submitted to public and crowd-sourced stories (aka Snapchat Live Stories or…

## 6. Reader Note 실제 관련 문장 (B-3)

- 요약부: "The study also releases the SnapCaptions dataset, comprising 10,000 expert-annotated Snapchat image-caption pairs."
- 데이터 섹션(133행): "The SnapCaptions dataset comprises 10,000 user-generated image-caption pairs collected from public Snapchat stories…"

## 7. Perturbed Note 실제 관련 문장 (B-4, r1 `p2-1802-size.md`)

- 요약부: "…comprising **12,000** expert-annotated Snapchat image-caption pairs."
- 데이터 섹션: "The SnapCaptions dataset comprises **12,000** user-generated image-caption pairs…"

## 8. Original ↔ Perturbed 정확한 차이 (B-5)

`10,000` → `12,000` — 요약부 + 데이터 섹션 **2곳 모두** 치환 (source "10K"와 대응하는 값이 전부 변경)

## 9. 의미적 결함인 이유 (B-6)

12,000은 원문 부재 값 — source "10K"와도 unit-aware 정규화로도 일치하지 않음 (10K=10,000 ≠ 12,000) = **numeric inconsistency** (결정론 감지 — r1 PASS)

## 10. 평가 분리 (지시 C-g4) — 동치 vs 오류

| 축 | 내용 | 판정 |
|---|---|---|
| (a) 원본 동치 표기 | source "10K" ↔ note "10,000" — scale 정규화(K=×1000)로 동치 | **원본 정합** (literal 비교는 불일치 — 이는 원본 오탐이며 r1에서 문서화·회피) |
| (b) 변형 오류 | note "12,000" — 원문 부재, "10K"와도 정규화 불일치 | **불일치 감지** — 실제 numeric 결함 |

두 축은 동일 평가자에서 (a) 허용·(b) 감지로 **상반 방향**이어야 정상 동작 — r1 결과와 정합.

## 11. 기대 판정 (작성자 기대 — 검증이 아님)

- (a) normalized consistency maintained, literal mismatch documented. (b) consistency ↓.
⚠ 작성자 기대 판정을 검증 결과로 간주하지 말 것

## 12. 검토자 판정 입력란

- Decision (Approve / Reject / Needs Revision): ______
- Approve 시 필수 5조건: source_identity_match ☐ source_context_sufficient ☐ claim_evidence_relation_verified ☐ perturbation_semantic_defect_confirmed ☐ expected_direction_verified ☐
- Reviewer Comment: ______
- Review Timestamp: ______
- Reviewed Fixture Digest (bundle `3ce9c206…`): ______
- Reviewer / Role (author 역할의 승인 불가): ______
