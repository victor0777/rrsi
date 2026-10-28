# Gold Review Packet — g4-1802-numeric

## 1. Fixture ID
g4-1802-numeric

## 2. Paper Identity / Source Version
- paper: arXiv 1802.07862, version v1
- capture sha256: 9741540db1f1212fd132d7dd1b11d182a10be79732208598cf52c7c8aee004d0
- review-note digest binding: c0e89cc28dbca067…

## 3. 평가 대상 Claim / Method
10,000 pairs is the SnapCaptions dataset size (source notation "10K")

## 4. 원문 Source Sentence (anchor)
> The SnapCaptions dataset is composed of 10K user-generated image (snap) and textual caption pairs where named entities in captions are manually labeled by expert human annotators
(anchor machine-verified in source: True)

## 5. 최소 주변 문맥
> architecture (Section SECREF4 ) for its empirical superiority, the module itself is flexible and thus can work with other NER architectures or for other multimodal applications.
SnapCaptions Dataset
The SnapCaptions dataset is composed of 10K user-generated image (snap) and textual caption pairs where named entities in captions are manually labeled by expert human annotators (entity types: PER, LOC, ORG, MISC). These captions are collected exclusively from snaps submitted to public and crowd-sourced stories (aka Snapchat Live Stories or Our Stories). Examples of such public crowd-sourced stories are “New York Story” or “Thanksgiv

## 6. Reader Note 해당 내용
> # 논문 읽기 노트 ## 3분 요약 This paper introduces the Multimodal Named Entity Recognition (MNER) task to address the challenges of noisy, short user-generated content. The authors propose a Bi-LSTM-CRF model that integrates visual features from InceptionNet with textual data. A key innovation is a modality attention mechanism that dynamically weights word, character, and visual inputs per token. This mechanism helps suppress noise from typos and out-of-vocabulary words by relying on character-level feat

## 7. Perturbation 내용 (p2-1802-size)
- 유형: P, 2
- 요약: perturbed copy attached at poc/runs/perturbation-audit/r2-semantic/p2-1802-size.md
- excerpt: (not generated — see r2 dir)

## 8. Original ↔ Perturbed 차이
release/annotation anchor verified; 10K↔10,000 equivalence human-judged

## 9. 기대 판정 및 근거 (작성자 기대 — 검증이 아님)
- expected: normalized consistency maintained; literal mismatch documented
- expected semantics: 규모 변환(10K→10,000)의 동치
⚠ 작성자 기대 판정을 검증 결과로 간주하지 말 것

## 10. 검토자 판정 입력란
- Decision (Approve / Reject / Needs Revision): ______
- Approve 시 필수 조건: source_identity_match ☐ source_context_sufficient ☐ claim_evidence_relation_verified ☐ perturbation_semantic_defect_confirmed ☐ expected_direction_verified ☐
- Reviewer Comment: ______
- Review Timestamp: ______
- Reviewed Fixture Digest: ______
- Reviewer / Role (author 역할의 승인 불가): ______
