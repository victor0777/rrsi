# Gold Review Packet R4 — g1-1802-claim

## 0. Revision Record (이전 검토 기록 보존)

- 이전 packet: `docs/poc-rrsi/review-packets/packet-g1-1802-claim.md` (commit `16a1c14`) — **삭제/덮어쓰기 없음**
- R1 독립 검토 판정 (2026-10-29, 외부 AI 검토 — 최종 인간 승인 아님): **NEEDS_REVISION**
- 지적 사유: 핵심 주장 제거 여부의 실제 검증 근거 부족 — 원문/note/변형의 실제 문장 미제시
- 본 수정에서 반영: 실제 문장·char-level diff·의미 결함 근거 전부 제시 (§6–§9)

## 1. Fixture ID

g1-1802-claim

## 2. Identity Blocks (별도 검증 — Bundle Digest 필드명 명시)

| 항목 | 값 |
|---|---|
| Paper Identity / Source Version | 1802.07862, arXiv v1, capture sha256 `9741540db1f1212fd132d7dd1b11d182a10be79732208598cf52c7c8aee004d0` |
| Reader Note Identity | `poc/runs/qasper-reader-note-r1/reader/1802.07862/02_reading_chain/output/04_reader_note.en.md`, reader_note_digest `99efc53f0df17bc50f4a53f0f0cf5cea63a00e6f71b2cae2b7100a61b02d9bfa` |
| Perturbation Identity | `poc/runs/perturbation-audit/r2-semantic/p1-1802-claim-removed.md` (P1), perturbed_note_digest `7eefc0d3c45582999ea5bc01e33950e7c6e323de135de62c7e2042c6dfc74958`; `p4-1802-contradiction.md` (P4), digest `035a940766b3b96e4a89e4219a5ae1e5cb0d707e51d7703d4275fa59ac31958d` |
| Gold Bundle Digest | `3ce9c206f4a83008cf5bd9994be64cc952981ea3ea74c16b5ffca073daf25523` — **공통 bundle digest** (9 fixtures가 단일 파일 `semantic-gold-fixture.json`에 등록되어 fixture별 개별 digest가 아니라 공통 값; fixture별 개별 digest는 파일 내 record + 본 packet 고유 digest로 대신 검증) |

- **Identity 대조**: fixture paper(1802) = note paper(1802) = perturbation paper(1802) ✓ — cross-paper 없음

## 3. 평가 대상 Claim (B-1)

proposed approaches **outperform** state-of-the-art NER models on SnapCaptions

## 4. Source Sentence + Source Reference (B-7)

> (3) We show that the proposed approaches outperform the state-of-the-art NER models (both with and without using additional visual contexts) on our new MNER dataset SnapCaptions, a large collection of informal and extremely short social media posts paired with unique images.

- Source Reference: full_text "Front matter" 기여 목록 제3항, QASPER dataset sha `2ae7ee62…` (frozen), capture digest 상기

## 5. Source Context (B-2)

> …d entity recognition tasks. (2) We propose a general modality attention module that selectively chooses modalities to extract primary context from, maximizing information gain and suppressing irrelevant contexts from each modality (we treat words, characters, and images as separate modalities). **(3) We show that the proposed approaches outperform the state-of-the-art NER models … on our new MNER dataset SnapCaptions, a large collection of informal and extremely short social media posts paired with unique images.** Related Work Neural models for NER have been recently prop…

## 6. Reader Note 실제 관련 문장 (B-3)

note 요약부("## 3분 요약", 4행) 실제 문장:

> Experimental results show that the proposed model significantly outperforms state-of-the-art text-only NER baselines.

## 7. Perturbed Note 실제 관련 문장 (B-4)

- **P1** (`p1-1802-claim-removed`): 요약부 **전체 990자 문단 삭제** — 상기 outperform 문장 포함 소실. 변형 후 요약 섹션은 `## 3분 요약` 제목 직후 빈 상태로 시작.
- **P4** (`p4-1802-contradiction`): 노트 끝에 실제 추가된 문장:

> The proposed model underperforms the state-of-the-art NER baselines across all evaluation settings in this study.

## 8. Original ↔ Perturbed 정확한 차이 (B-5)

| 변형 | char-level 차이 |
|---|---|
| P1 | 단일 delete opcode 990자: "This paper introduces … outperforms state-of-the-art text-only NER baselines. … may limit generalizability to other platforms." (요약 문단 전체) / ADDED: 없음 |
| P4 | insert: 빈 행 2개 + `### Contradicting Claim` + 상기 underperforms 문장 (노트 말미) |

## 9. 의미적 결함인 이유 (B-6)

- P1: 원문이 명시적으로 주장하는 내용(§4 anchor)을 note가 전달하지 않게 됨 — source는 유지되고 note-side 주장만 소실 = **의도된 claim fidelity 손실**.
- P4: 원문은 outperform만 서술(원문 전체에서 underperform/negation 0 — r2 전수 검색), 추가 문장은 source 주장의 직접 부정 = **모순 삽입**.

## 10. 기대 판정 (작성자 기대 — 검증이 아님)

- P1: claim fidelity ↓. P4: 모순 검출 (consistency ↓).
⚠ 작성자 기대 판정을 검증 결과로 간주하지 말 것

## 11. 검토자 판정 입력란

- Decision (Approve / Reject / Needs Revision): ______
- Approve 시 필수 5조건: source_identity_match ☐ source_context_sufficient ☐ claim_evidence_relation_verified ☐ perturbation_semantic_defect_confirmed ☐ expected_direction_verified ☐
- Reviewer Comment: ______
- Review Timestamp: ______
- Reviewed Fixture Digest (bundle `3ce9c206…` + 본 packet digest는 index 참조): ______
- Reviewer / Role (author 역할의 승인 불가 — `SELF_APPROVAL_REFUSED`): ______
