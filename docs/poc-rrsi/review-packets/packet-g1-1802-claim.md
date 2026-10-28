# Gold Review Packet — g1-1802-claim

## 1. Fixture ID
g1-1802-claim

## 2. Paper Identity / Source Version
- paper: arXiv 1802.07862, version v1
- capture sha256: 9741540db1f1212fd132d7dd1b11d182a10be79732208598cf52c7c8aee004d0
- review-note digest binding: c0e89cc28dbca067…

## 3. 평가 대상 Claim / Method
proposed approaches outperform state-of-the-art NER models on SnapCaptions

## 4. 원문 Source Sentence (anchor)
> (3) We show that the proposed approaches outperform the state-of-the-art NER models
(anchor machine-verified in source: True)

## 5. 최소 주변 문맥
> chooses modalities to extract primary context from, maximizing information gain and suppressing irrelevant contexts from each modality (we treat words, characters, and images as separate modalities). (3) We show that the proposed approaches outperform the state-of-the-art NER models (both with and without using additional visual contexts) on our new MNER dataset SnapCaptions, a large collection of informal and extremely short social media posts paired with unique images.
Related Work
Neural models for NER have been recently proposed, pro

## 6. Reader Note 해당 내용
> # 논문 읽기 노트 ## 3분 요약 This paper introduces the Multimodal Named Entity Recognition (MNER) task to address the challenges of noisy, short user-generated content. The authors propose a Bi-LSTM-CRF model that integrates visual features from InceptionNet with textual data. A key innovation is a modality attention mechanism that dynamically weights word, character, and visual inputs per token. This mechanism helps suppress noise from typos and out-of-vocabulary words by relying on character-level feat

## 7. Perturbation 내용 (p1-1802-claim-removed)
- 유형: P, 1, /, P, 4
- 요약: perturbed copy attached at poc/runs/perturbation-audit/r2-semantic/p1-1802-claim-removed.md
- excerpt: # 논문 읽기 노트 ## 3분 요약 _source: Front matter_ ### Front Matter Context and Scope The source material for this section is limited to the paper's title and abstract. Consequently, specific metadata regarding author names, institutional affiliations, and the exact publication venue (co

## 8. Original ↔ Perturbed 차이
source anchor machine-verified; outperform wording present in both

## 9. 기대 판정 및 근거 (작성자 기대 — 검증이 아님)
- expected: claim fidelity ↓ on P1, contradiction detected on P4
- expected semantics: 성능 우위 주장
⚠ 작성자 기대 판정을 검증 결과로 간주하지 말 것

## 10. 검토자 판정 입력란
- Decision (Approve / Reject / Needs Revision): ______
- Approve 시 필수 조건: source_identity_match ☐ source_context_sufficient ☐ claim_evidence_relation_verified ☐ perturbation_semantic_defect_confirmed ☐ expected_direction_verified ☐
- Reviewer Comment: ______
- Review Timestamp: ______
- Reviewed Fixture Digest: ______
- Reviewer / Role (author 역할의 승인 불가): ______
