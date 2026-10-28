# Gold Review Packet R4 — g8-1901-result

## 0. Revision Record (이전 검토 기록 보존)

- 이전 packet: `docs/poc-rrsi/review-packets/packet-g8-1901-result.md` (commit `16a1c14`) — **삭제/덮어쓰기 없음**
- R1 독립 검토 판정 (2026-10-29, 외부 AI 검토 — 최종 인간 승인 아님): **NEEDS_REVISION**
- 지적 사유: θ 정의·0.25 원문 근거·0.75 출처 미제시
- 본 수정: 세 항목 전부 제시 (§3–§9)

## 1. Fixture ID

g8-1901-result

## 2. Identity Blocks

| 항목 | 값 |
|---|---|
| Paper Identity / Source Version | 1901.10133, arXiv v1, capture sha256 `652151f6b22c2a972b206c7f1ba67639c0f095e5767d976b527602cbe9ac2c1a` |
| Reader Note Identity | note(1901) digest `97f5dd09a78bfb3db941999b4dc977319a2ffe25b8c5781970396f44b1122410` |
| Perturbation Identity | `poc/runs/perturbation-audit/r2-semantic/p2ext-1901-other-metric.md` (P2확장), perturbed_note_digest `f17f1cccd5e4023bf2e6e99a7852fe880757a64db15a7952e79cb41de8b75682`; 참조: r1 `p2-1901-theta.md` (0.25→0.40), digest `aacc994e757c9544ef05459858ab878d62a1e2d64e411b69d171cefcbb14199e` |
| Gold Bundle Digest | `3ce9c206f4a83008cf5bd9994be64cc952981ea3ea74c16b5ffca073daf25523` (공통 bundle digest) |

## 3. 평가 대상 Claim (B-1) — θ 정의

θ는 Eq.1 결합 유사도 $S(x,y) = t·S_1 + (1-t)·S_2$의 **가중치 $t$** — keyword 유사도($S_1$)와 클러스터 응집 유사도($S_2$)의 균형을 정하는 실험 파라미터로, 실험에서 **0.25**로 고정.

## 4. Source Sentence + Source Reference (B-7)

> The value of $t$ signifies the importance to be given to the keyword and its associated sentences respectively. In our experiments, we empirically fix the value of $t$ to $0.25$.

- Source Reference: full_text "III Proposed model" → Eq.1 직후 가중치 서술 (source literal "$0.25$" 존재 확인)

## 5. Source Context (B-2)

> …other sentence $x$ to the keyword with which they have maximum similarity $Max_y (S(x,y))$ . Later, we cluster the keywords along with the sentences mapped to them. **The value of $t$ signifies the importance to be given to the keyword and its associated sentences respectively. In our experiments, we empirically fix the value of $t$ to $0.25$ .** Metrics to evaluate our algorithm To evaluate our algorithm, we propose two similarity metrics, $Sim1$ and $Sim2$…

## 6. Reader Note 실제 관련 문장 (B-3)

> In the experiments, $t$ is empirically fixed at **0.25**. This specific value suggests that the model places greater emphasis on the similarity to the keyword ($S_1$) than on the cluster coherence ($S_2$), as $1-t = 0.75$.

## 7. Perturbed Note 실제 관련 문장 (B-4, `p2ext-1901-other-metric`)

> In the experiments, $t$ is empirically fixed at **0.75**. This specific value suggests that the model places greater emphasis on the similarity to the keyword ($S_1$) than on the cluster coherence ($S_2$), as $1-t = 0.75$.

## 8. Original ↔ Perturbed 정확한 차이 (B-5)

`0.25` → `0.75` 2곳 치환 (Eq.1 해설 문장 113행 + one-line summary 121행의 "$t=0.25$" → "$t=0.75$"). **0.75는 원문 노트에 이미 존재하는 값**(§6의 "$1-t = 0.75")이라 변형 후에도 노트 내 일관성 검사로는 드러나지 않는 은닉 치환.

## 9. 의미적 결함인 이유 (B-6) — 0.75의 출처 포함 (지시 C-g8)

- 0.75는 **원문에 부재** (1901 full_text에 literal "0.75" 0건 — 기계 확인).
- 0.75의 출처: **note가 자체 계산해 기재한 여수 "$1-t = 0.75$"** (source 값 0.25의 보수) — 원문 수치가 아니라 note-side 파생값.
- 결함 성격: 노트 내 타 수치(파생 여수)로의 치환 → note-internal value 흔적만 남고 source 대조로만 감지 = **silent misattribution** (designated_numeric_consistency가 지정값 방식으로 감지 — r2 준비 완료)

## 10. 기대 판정 (작성자 기대 — 검증이 아님)

- numeric consistency ↓ (지정값 0.25 부재 + 0.75 source 부재 확인).
⚠ 작성자 기대 판정을 검증 결과로 간주하지 말 것

## 11. 검토자 판정 입력란

- Decision (Approve / Reject / Needs Revision): ______
- Approve 시 필수 5조건: source_identity_match ☐ source_context_sufficient ☐ claim_evidence_relation_verified ☐ perturbation_semantic_defect_confirmed ☐ expected_direction_verified ☐
- Reviewer Comment: ______
- Review Timestamp: ______
- Reviewed Fixture Digest (bundle `3ce9c206…`): ______
- Reviewer / Role (author 역할의 승인 불가): ______
