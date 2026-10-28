# Gold Review Packet — g3-1802-result

## 1. Fixture ID
g3-1802-result

## 2. Paper Identity / Source Version
- paper: arXiv 1802.07862, version v1
- capture sha256: 9741540db1f1212fd132d7dd1b11d182a10be79732208598cf52c7c8aee004d0
- review-note digest binding: c0e89cc28dbca067…

## 3. 평가 대상 Claim / Method
SnapCaptions vocabulary size is 15,733 tokens

## 4. 원문 Source Sentence (anchor)
> 15,733
(anchor machine-verified in source: True)

## 5. 최소 주변 문맥
> d InceptionNet are available). We split the dataset into train (70%), validation (15%), and test sets (15%). The captions data have average length of 30.7 characters (5.81 words) with vocabulary size 15,733, where 6,612 are considered unknown tokens from Stanford GloVE embeddings BIBREF22 . Named entities annotated in the SnapCaptions dataset include many of new and emerging entities, and they are found in various surface forms (various nicknames, typos, etc.) T

## 6. Reader Note 해당 내용
> # 논문 읽기 노트 ## 3분 요약 This paper introduces the Multimodal Named Entity Recognition (MNER) task to address the challenges of noisy, short user-generated content. The authors propose a Bi-LSTM-CRF model that integrates visual features from InceptionNet with textual data. A key innovation is a modality attention mechanism that dynamically weights word, character, and visual inputs per token. This mechanism helps suppress noise from typos and out-of-vocabulary words by relying on character-level feat

## 7. Perturbation 내용 (p2-1802-vocab)
- 유형: P, 2
- 요약: perturbed copy attached at poc/runs/perturbation-audit/r2-semantic/p2-1802-vocab.md
- excerpt: (not generated — see r2 dir)

## 8. Original ↔ Perturbed 차이
value present in full_text; semantic meaning of "vocabulary size" human-judged

## 9. 기대 판정 및 근거 (작성자 기대 — 검증이 아님)
- expected: numeric consistency ↓ on P2
- expected semantics: 데이터 통계 규모
⚠ 작성자 기대 판정을 검증 결과로 간주하지 말 것

## 10. 검토자 판정 입력란
- Decision (Approve / Reject / Needs Revision): ______
- Approve 시 필수 조건: source_identity_match ☐ source_context_sufficient ☐ claim_evidence_relation_verified ☐ perturbation_semantic_defect_confirmed ☐ expected_direction_verified ☐
- Reviewer Comment: ______
- Review Timestamp: ______
- Reviewed Fixture Digest: ______
- Reviewer / Role (author 역할의 승인 불가): ______
