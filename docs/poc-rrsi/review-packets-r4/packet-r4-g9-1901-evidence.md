# Gold Review Packet R4 — g9-1901-evidence

## 0. Revision Record (이전 검토 기록 보존)

- 이전 packet: `docs/poc-rrsi/review-packets/packet-g9-1901-evidence.md` (commit `16a1c14`) — **삭제/덮어쓰기 없음**
- R1 독립 검토 판정 (2026-10-29, 외부 AI 검토 — 최종 인간 승인 아님): **REJECT**
- 지적 사유: **cross-paper binding 오류** — 1901 fixture에 1802 perturbation(`p3ext-1802-unrelated-ref`) 연결됨
- 본 수정: 연결 해제 → 1901 reference 변형 **UNAVAILABLE**; r2의 p3ext는 1802 기반이므로 **Reference Integrity vs Semantic Evidence Grounding 평가 분리의 실증 사례로만 인용** (§10)

## 1. Fixture ID

g9-1901-evidence

## 2. Identity Blocks

| 항목 | 값 |
|---|---|
| Paper Identity / Source Version | 1901.10133, arXiv v1, capture sha256 `652151f6b22c2a972b206c7f1ba67639c0f095e5767d976b527602cbe9ac2c1a` |
| Reader Note Identity | note(1901) digest `97f5dd09a78bfb3db941999b4dc977319a2ffe25b8c5781970396f44b1122410` |
| Perturbation Identity | **UNAVAILABLE** — 1901용 P3(reference) 변형 없음 (`p3ext-1802-unrelated-ref`는 1802 note 기반 → paper identity 불일치, 연결 해제) |
| Gold Bundle Digest | `3ce9c206f4a83008cf5bd9994be64cc952981ea3ea74c16b5ffca073daf25523` (공통 bundle digest) |

## 3. 평가 대상 Claim (B-1)

note가 참조하는 `eq0001`이 artifact graph에 실존 (1901.10133)

## 4. Source Sentence + Source Reference (B-7)

- 참조 대상: **Equation 1** (결합 유사도 정의) — 원문 문장: "…$S(x,y) = t·S_1(x,y) + (1-t)·S_2(x,y)$" 형태의 결합 스코어 정의식
- Source Reference: artifact-graph(1901) `nodes.artifacts = ['eq0001','fig0001','tbl0001']` — **기계 검증: eq0001 ∈ 유효 집합 ✓**; note 추적 행: "source: `s0006_03` … artifact: `eq0001`"

## 5. Source Context (B-2)

원문 Eq.1 정의부 주변: "The combined similarity score balances relevance to the keyword with coherence to the existing cluster …" — eq0001이 정의하는 결합 유사도가 섹션 배분 점수로 사용되는 서술 (§III Proposed model)

## 6. Reader Note 실제 관련 문장 (B-3)

> **Equation 1** defines this combined score. It represents a weighted sum where the relevance to the keyword and the coherence with the existing cluster are balanced.

## 7. Perturbed Note 실제 관련 문장 (B-4)

**해당 없음 — UNAVAILABLE** (1901 기반 reference 변형 부재)

## 8. Original ↔ Perturbed 정확한 차이 (B-5)

**해당 없음 — UNAVAILABLE**

## 9. 의미적 결함인 이유 (B-6)

**해당 없음 — UNAVAILABLE** (적절한 1901 변형 확보까지 semantic gold 판정 대상에서 제외)

## 10. 평가 분리 (지시 C-g9) — Reference Integrity vs Semantic Evidence Grounding

| 축 | 판정 내용 | 결정론 가능 | 현재 상태 |
|---|---|---|---|
| **Reference Integrity** | 참조 id가 유효 집합(artifact graph)에 존재 | **가능** — r1의 dangling 감지(`fig0009` REFUSED) 실증 | READY |
| **Semantic Evidence Grounding** | 참조된 eq0001이 실제로 해당 주장을 **지지**하는가 | **불가** — r2의 p3ext 실증: 유효 id(`fig0003`)의 무관 연결이 integrity를 **통과** | UNVERIFIED — Gold/judge 영역 |

- 실증 사례(p3ext-1802, paper 불일치로 본 fixture 검증용 아님): "insert ' (evidence: `fig0003`)' 1곳" — literal 무결·integrity 통과·semantic 오연결. 이 구분이 본 fixture의 핵심 검토 포인트.
- 1901용 semantic grounding 변형 생성은 별도 지시 필요.

## 11. 기대 판정 (작성자 기대 — 검증이 아님)

- integrity는 원본 유효; grounding은 판정 불가(UNVERIFIED 유지).
⚠ 작성자 기대 판정을 검증 결과로 간주하지 말 것

## 12. 검토자 판정 입력란

- Decision (Approve / Reject / Needs Revision): ______
- Approve 시 필수 5조건: source_identity_match ☐ source_context_sufficient ☐ claim_evidence_relation_verified ☐ perturbation_semantic_defect_confirmed ☐ expected_direction_verified ☐
- Reviewer Comment: ______
- Review Timestamp: ______
- Reviewed Fixture Digest (bundle `3ce9c206…`): ______
- Reviewer / Role (author 역할의 승인 불가): ______
