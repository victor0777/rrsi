# Gold Review Packet — g9-1901-evidence

## 1. Fixture ID
g9-1901-evidence

## 2. Paper Identity / Source Version
- paper: arXiv 1901.10133, version v1
- capture sha256: 652151f6b22c2a972b206c7f1ba67639c0f095e5767d976b527602cbe9ac2c1a
- review-note digest binding: c0e89cc28dbca067…

## 3. 평가 대상 Claim / Method
note references eq0001 which exists in the artifact graph

## 4. 원문 Source Sentence (anchor)
> eq0001
(anchor machine-verified in source: True)

## 5. 최소 주변 문맥
> (source location provided for expanded review)

## 6. Reader Note 해당 내용
> # 논문 읽기 노트 ## 3분 요약 This paper proposes a method to segment unordered text documents into logical sections by clustering sentences around extracted keywords. The approach utilizes the TextRank algorithm to identify keywords and Google’s Universal Sentence Encoder (USE) to calculate semantic similarities. A key contribution is a combined similarity metric that weights both the similarity between a sentence and its keyword and the similarity between the sentence and other sentences in the same clu

## 7. Perturbation 내용 (p3ext-1802-unrelated-ref)
- 유형: P, 3
- 요약: perturbed copy attached at poc/runs/perturbation-audit/r2-semantic/p3ext-1802-unrelated-ref.md
- excerpt: # 논문 읽기 노트 ## 3분 요약 This paper introduces the Multimodal Named Entity Recognition (MNER) task to address the challenges of noisy, short user-generated content. The authors propose a Bi-LSTM-CRF model that integrates visual features from InceptionNet with textual data. A key innov

## 8. Original ↔ Perturbed 차이
artifact-graph membership machine-verified

## 9. 기대 판정 및 근거 (작성자 기대 — 검증이 아님)
- expected: literal integrity intact on valid-but-unrelated ref — semantic grounding UNVERIFIED
- expected semantics: 유효 참조 존재
⚠ 작성자 기대 판정을 검증 결과로 간주하지 말 것

## 10. 검토자 판정 입력란
- Decision (Approve / Reject / Needs Revision): ______
- Approve 시 필수 조건: source_identity_match ☐ source_context_sufficient ☐ claim_evidence_relation_verified ☐ perturbation_semantic_defect_confirmed ☐ expected_direction_verified ☐
- Reviewer Comment: ______
- Review Timestamp: ______
- Reviewed Fixture Digest: ______
- Reviewer / Role (author 역할의 승인 불가): ______
