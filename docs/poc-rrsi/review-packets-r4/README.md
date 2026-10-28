# Independent Gold Review R4 — Revised Packets (독립 재검토용)

R1 독립 검토(REJECT 3 / NEEDS_REVISION 5 / APPROVE 0)에 따른 수정 패킷 8건.
**기존 패킷은 변경·삭제되지 않았습니다** — 이전 검토 기록과의 연결은 각 packet §0의
Revision Record로 보존됩니다.

## 기존 자료 (보존)

- 이전 패킷: [review-packets/](../review-packets/) (commit `16a1c14`) — 무변경
- R1 판정: 외부 AI 검토 의견 — 시스템의 최종 인간 승인으로 자동 간주하지 않음

## 본 수정 요약

| 지시 | 반영 |
|---|---|
| A. Cross-paper binding | g2·g6·g9 오연결 해제 → **UNAVAILABLE** 기록 (적절한 변형 부재, 임의 연결 금지) |
| B. Evidence 보강 | 8건 전부: ① Source Sentence ② 충분한 문맥 ③ note 실제 문장 ④ perturbed 실제 문장 ⑤ char-level 차이 ⑥ 의미 결함 이유 ⑦ Source Reference (첫머리 500자 발췌 대체 아님 — 대상 문장 주변 전용 발췌) |
| C. Fixture별 수정 | g1 제거 여부 실증 / g3 실제 변형 문장 / g4 동치·오류 분리(§10) / g7 잔존 정보(§10) / g8 θ 정의·0.25 근거·0.75 출처 / g9 integrity·grounding 분리(§10) |
| D. Digest binding | bundle digest(`3ce9c206…`, 9건 공통 — 필드명 `gold_bundle_digest`로 명시)와 note digest(`99efc53f…`/`97f5dd09…`, 실제 note와 대조 검증 OK)·capture digest 별도 필드로 분리 |
| E. 이전 판정 보존 | 각 packet §0에 R1 판정 + 수정 근거 기재 |

## 검토 방법

1. 각 packet §0(R1 판정) → §4–§9(실제 근거) 순으로 검증 후 §말미 입력란에 판정 기록.
2. Approve는 5조건 체크박스 **전부** + 독립자 신원 필요 (author-path 승인은 `SELF_APPROVAL_REFUSED`로 구조적 거부).
3. UNAVAILABLE 3건(g2·g6·g9)은 perturbation 부재로 semantic-defect 확인 자체가 불가 — 판정은
   "신규 변형 생성 필요" 쪽이어야 하며, 승인으로 처리하면 안 됩니다.
4. 파일 무결성: `seal-run-dir.json`이 각 파일 sha256을 고정 (r4 복사본 대조 검증 ALL OK).

## 재검토 요청 대상

- **g1·g3·g4·g7·g8** (Needs Revision → 재판정)
- **g2·g6·g9** (Reject → 해소 방향 판정: UNAVAILABLE 확정이 적절한지)
- g5는 r3에서 `Evidence Absence`로 제외 확정 — 대상 아님
