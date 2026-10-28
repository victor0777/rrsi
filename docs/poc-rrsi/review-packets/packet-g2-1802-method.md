# Gold Review Packet — g2-1802-method

## 1. Fixture ID
g2-1802-method

## 2. Paper Identity / Source Version
- paper: arXiv 1802.07862, version v1
- capture sha256: 9741540db1f1212fd132d7dd1b11d182a10be79732208598cf52c7c8aee004d0
- review-note digest binding: c0e89cc28dbca067…

## 3. 평가 대상 Claim / Method
modality attention selects the most informative modality (word/char/image) per decoding step

## 4. 원문 Source Sentence (anchor)
> chooses per decoding step the most informative modality among available ones
(anchor machine-verified in source: True)

## 5. 최소 주변 문맥
> nying snap image of a board game can help disambiguate among polysemous entities, thereby correctly recognizing it as a named entity.
Second, we also propose a general modality attention module which chooses per decoding step the most informative modality among available ones (in our case, word embeddings, character embeddings, or visual features) to extract context from. For example, the modality attention module lets the decoder attenuate the word-level signals for unknown word tokens (“Marshmellooooo" with trailing `o's) and am

## 6. Reader Note 해당 내용
> # 논문 읽기 노트 ## 3분 요약 This paper introduces the Multimodal Named Entity Recognition (MNER) task to address the challenges of noisy, short user-generated content. The authors propose a Bi-LSTM-CRF model that integrates visual features from InceptionNet with textual data. A key innovation is a modality attention mechanism that dynamically weights word, character, and visual inputs per token. This mechanism helps suppress noise from typos and out-of-vocabulary words by relying on character-level feat

## 7. Perturbation 내용 (p5-1901-method-removed)
- 유형: P, 5
- 요약: perturbed copy attached at poc/runs/perturbation-audit/r2-semantic/p5-1901-method-removed.md
- excerpt: # 논문 읽기 노트 ## 3분 요약 _source: Front matter_ ### Task Definition and Scope The paper addresses the specific problem of **structuring an unordered text document**. In this context, an "unordered text document" refers to a collection of sentences or text segments that lack a predefin

## 8. Original ↔ Perturbed 차이
source anchor machine-verified

## 9. 기대 판정 및 근거 (작성자 기대 — 검증이 아님)
- expected: method coverage ↓ on P5
- expected semantics: 선택적 모달 융합 기법
⚠ 작성자 기대 판정을 검증 결과로 간주하지 말 것

## 10. 검토자 판정 입력란
- Decision (Approve / Reject / Needs Revision): ______
- Approve 시 필수 조건: source_identity_match ☐ source_context_sufficient ☐ claim_evidence_relation_verified ☐ perturbation_semantic_defect_confirmed ☐ expected_direction_verified ☐
- Reviewer Comment: ______
- Review Timestamp: ______
- Reviewed Fixture Digest: ______
- Reviewer / Role (author 역할의 승인 불가): ______
