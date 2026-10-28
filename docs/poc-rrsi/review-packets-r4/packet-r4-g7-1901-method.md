# Gold Review Packet R4 — g7-1901-method

## 0. Revision Record (이전 검토 기록 보존)

- 이전 packet: `docs/poc-rrsi/review-packets/packet-g7-1901-method.md` (commit `16a1c14`) — **삭제/덮어쓰기 없음**
- R1 독립 검토 판정 (2026-10-29, 외부 AI 검토 — 최종 인간 승인 아님): **NEEDS_REVISION**
- 지적 사유: TextRank 단계 제거 **여부**와 **다른 문장에 남은 정보** 확인 불가 — 이전 packet의 anchor가 원문 문장과 불일치(`anchor_in_source: false`)
- 본 수정: 실제 원문 문장 + p5 제거 상세 + 잔존 정보 전부 제시 (§4·§7–§9)

## 1. Fixture ID

g7-1901-method

## 2. Identity Blocks

| 항목 | 값 |
|---|---|
| Paper Identity / Source Version | 1901.10133, arXiv v1, capture sha256 `652151f6b22c2a972b206c7f1ba67639c0f095e5767d976b527602cbe9ac2c1a` |
| Reader Note Identity | note(1901) digest `97f5dd09a78bfb3db941999b4dc977319a2ffe25b8c5781970396f44b1122410` |
| Perturbation Identity | `poc/runs/perturbation-audit/r2-semantic/p5-1901-method-removed.md` (P5), perturbed_note_digest `4832a553d202d61a154a5a2a8f0a3564ea3df3d9f316db83a4d15bfd3e5b7e61` |
| Gold Bundle Digest | `3ce9c206f4a83008cf5bd9994be64cc952981ea3ea74c16b5ffca073daf25523` (공통 bundle digest) |

## 3. 평가 대상 Claim (B-1)

TextRank keyword extraction with keywords-as-centroid clustering is a mandatory pipeline step

## 4. Source Sentence + Source Reference (B-7) — 원문 문장 **수정**

이전 fixture의 anchor("extract the keywords from the input document using TextRank algorithm and store them in a list")는 원문 문장이 아니었음 → 실제 원문 문장으로 교체:

> We use TextRank algorithm BIBREF0 to extract the keywords from a text document.

- Source Reference: full_text "III Proposed model" → keyword 추출 단계 서술

## 5. Source Context (B-2)

> …have unordered sentences is processed so that it will have sentences clustered together. Clustering is based on the similarity with the respective keyword as well as with the sentences belonging to the same cluster. Keywords are identified and clusters are formed for each keyword. **We use TextRank algorithm BIBREF0 to extract the keywords from a text document.** TextRank is a graph-based ranking algorithm which decides the importance of a vertex within a graph by considering the global information recursively computed from the entire graph rather than focusing on local vertex specific information. The model uses knowledge acquired from the entire text to…

## 6. Reader Note 실제 관련 문장 (B-3)

> The first algorithmic step involves extracting keywords from the input document using the **TextRank** algorithm. These extracted keywords are stored in a list denoted as $K$. In this model, the keywords in $K$ function as **centroids** for the resulting clusters.

## 7. Perturbed Note 실제 관련 문장 (B-4)

- 상기 **두 문단 전체 삭제** (p5 제거 opcode 중 핵심 블록):
  - 방법론부 "The first algorithmic step involves extracting keywords … centroids for the resulting clusters." 문단
  - "남은 의존성: The source cites TextRank [6] …" 문단
  - 요약부 전체(TextRank 언급 포함) + TextRank bullet 2개 + 방법론 TextRank/USE 소개 문단 + 대응 one-line summaries + 추적 행 "Keywords extracted via TextRank act as centroids…"

## 8. Original ↔ Perturbed 정확한 차이 (B-5)

9개 delete opcode — (a) 3분요약 문단 전체, (b) Key Algorithms TextRank bullet, (c) 한계부 TextRank bullet, (d) front-matter 요약+one-line, (e) 방법론부 TextRank/USE 소개 문단, (f) 방법론 one-line, (g) **첫 단계 문단+의존성 문단**, (h) 방법론 one-line, (i) 추적 행. 총 길이 감소(28,809자 원본 기준), 문장 구조는 삭제만 존재(추가 0)

## 9. 의미적 결함인 이유 (B-6)

원문이 pipeline 첫 단계로 명시한 keyword 추출·centroid 클러스터링 서술이 note에서 소실 = **required-information coverage 손실** (다만 아래 잔존으로 완전 소실은 아님 — 판정 시 반영 필요)

## 10. 잔존 정보 확인 (지시 C-g7) — 다른 문장에 남은 내용

p5에 "TextRank" 잔존 **8회**:
- 헤더·총괄 문장: "The paper explicitly identifies two specific algorithms … TextRank and Google's USE" 등 — **알고리즘 이름과 구성 요소 지위는 잔존**
- 외부 의존성 문장: "Both TextRank and USE are external methodologies …" 등
- 그러나 **기능적 단계 서술**(keyword를 K로 추출 → centroid 클러스터링)은 전부 삭제

→ 결함 성격: 단계 소실(coverage 손실)이나 "TextRank 언급 자체"는 잔존하는 **부분 소실** — 결정론 길이·문장-수 축으로 감지 가능하나 coverage 판정은 Gold/judge 영역.

## 11. 기대 판정 (작성자 기대 — 검증이 아님)

- required-info coverage ↓ (부분 소실).
⚠ 작성자 기대 판정을 검증 결과로 간주하지 말 것

## 12. 검토자 판정 입력란

- Decision (Approve / Reject / Needs Revision): ______
- Approve 시 필수 5조건: source_identity_match ☐ source_context_sufficient ☐ claim_evidence_relation_verified ☐ perturbation_semantic_defect_confirmed ☐ expected_direction_verified ☐
- Reviewer Comment: ______
- Review Timestamp: ______
- Reviewed Fixture Digest (bundle `3ce9c206…`): ______
- Reviewer / Role (author 역할의 승인 불가): ______
