---
doc_id: poc-rrsi-38-r7-dataset-gold-readiness
title: R7 Dataset and Gold Readiness
status: design
updated: 2026-10-29
---

# R7 — Dataset & Gold Readiness (R7-D0 문서 2)

## 1. 기존 Gold 인벤토리 (재사용 가능 여부)

### Semantic Gold (RRSI, 9건)
`poc/runs/perturbation-audit/r2-semantic/semantic-gold-fixture.json`

| Fixture | 유형 | R6 사용 이력 | R7-D0 상태(초기) |
|---|---|---|---|
| g1-1802-claim | P1/P4 claim | R6 admission | CONFLICTED 후보 — 기계검증만, 독립검토 미완 |
| g2-1802-method | P5 method | — | CONFLICTED 후보 |
| g3-1802-result | P2 numeric | r6g Agreement | Gate 통과 후 VALID |
| g4-1802-numeric | P2 numeric | r6i Agreement+VERIFIED | Gate 통과 후 VALID |
| g5-1802-evidence | P3 grounding | — | CONFLICTED 후보 |
| g6-1901-claim | P1/P4 claim | — | CONFLICTED 후보 |
| g7-1901-method | P5 method | r6i VERIFIED | Gate 통과 후 VALID |
| g8-1901-result | P2 numeric | — | CONFLICTED 후보 |
| g9-1901-evidence | P3 grounding | — | INSUFFICIENT_EVIDENCE 후보 (semantic grounding UNVERIFIED 명시) |

- `BLOCKED_CONFLICTED` 상속 검사: 상기 논문(1802.07862·1901.10133)은
  R0-a denylist 13건과 **무관** → 세트 충돌 없음 (추적 기록 유지).
- 위 상태는 R7-D0 Gate 결과가 아니라 **초기 가정** — Gate 실행 후 확정.

### Reader Note GT (ai_papers, 15건)
`ai_papers/docs/eval/reader-note-quality/gold/*.reader-note-quality-gt.json`
— split freeze(`poc/runs/r0b2/split-manifest.json`): **13건
BLOCKED_CONFLICTED (평가 금지 유지)**, EVOLVE 2건(2508.11428 획득됨,
2511.13079 미획득). **R7이 이 집합을 평가 자료로 소비하지 않는다** —
EVOLVE 재할당은 별도 Owner 결정 사항.

## 2. Unseen Evaluation Set 선정 절차 (D1 강화 계약)

**분리는 두 축으로 별도 관리** — 논문 분리 축(id·이력)과 평가 유형 축
(Development / Unseen-eval / Challenge 레이어). Challenge는 **Unseen
논문 위의 별도 평가 층**으로 정의 (집합 상호배타가 아니라 논문 축을
공유하는 유형 층) — 사례는 이 두 축의 조합으로 소속이 결정되며,
Development 논문으로 Challenge를 만들 수 없다.

논문 분리 축 검증 (id 일치만으로 불충분 — 아래 전부 확인):

1. **논문 ID·버전 중복**: Development 논문과 ID·버전 교집합 ∅.
2. **Reader Note 생성·평가 이력**: 후보 논문이 이전 `ai_papers` 실험
   (reader-note-quality GT, calibration, reader-context 등 —
   `ai_papers/docs/eval/reader-note-quality/`,
   `poc/runs/qasper-*-calibration/`)에서 사용됐는지 이력 조사 →
   사용 이력이 있으면 Unseen 제외.
3. **Judge Prompt 개발 노출 이력**: R5–R6 계약·발췌·디버깅에 노출된
   논문 전부 배제 (1802.07862·1901.10133 계열).
4. **Gold·Perturbation 설계 자료 중복**: semantic gold fixture
   설계·리뷰 패킷(`docs/poc-rrsi/review-packets*/`,
   `poc/runs/perturbation-audit/`)에 사용된 논문 배제.

절차:

1. 후보 풀: QASPER dev-v0.3(`research_benchmarks/benchmarks/qasper/`,
   sha256 `2ae7ee62…`)에서 위 4항목 이력 조사 후 무노출 논문만.
2. 2–3편 선정, 선정 근거(길이·주제 다양성) 기록.
3. **분리 증명 산출물**: 교집합 ∅ 스크립트 결과 + 논문별 노출 이력
   조사 기록을 `poc/runs/r7-evaluation/separation-proof.json`으로
   고정 (Admission ①의 증명 — id 교집합과 노출 이력 둘 다 포함).
4. 각 논문의 Reader Note는 R6I 노트 생성 파이프라인과 동일 조건으로
   생성 후 원본 확정 — 생성 자체는 E1 별도 승인 사항.

## 3. Gold Quality Gate 절차 (사례당)

1. 원본 Reader Note 정확성: 원문 근거와 대조(사실 오류·누락 없음).
2. Perturbation 단일성: diff 기준 **의도 오류 1개만** 발생하는지
   (R6H `p5-1901`은 11개 라인 제거 — 다중 편집 사례는 Challenge로만).
3. 우연 변경 부재: 의도 외 토큰 변조 0건 확인.
4. 기대 평가 방향의 근거: 원문 근거 위치 + 방향 논증이 gold에 기록.
5. 독립 검토자 재현: 검토자가 동일 판정 도달 가능(검토 기록으로 증명).

상태: `VALID` / `CONFLICTED` / `INSUFFICIENT_EVIDENCE` / `EXCLUDED`.
**VALID만 주 집계.** 기존 Gold 무변경, R7 기록은
`poc/runs/r7-evaluation/` 이하 별도 영속화(append-only).

## 4. Challenge Set — P1–P6 대응표 (이름 ≠ 정답)

| Challenge 사례 | P 대응 | 판정 기준 |
|---|---|---|
| 표현만 변경(의미 유지) | (P1 반사례) | FP로 집계 — Judge가 오류로 비판하면 FP |
| 표기만 정규화(10K↔10,000) | (P2 반사례) | FP로 집계 — 정규화 동치 인식 요구 |
| 실제 수치 변경 | P2 | 수치 불일치 식별 |
| 방법론 설명 일부 삭제 | P5 | 기능 손실 식별 |
| 이름 잔존+기능 제거 | P5 | **R6H 핵심 모드** — 이름 존재만으로 무오류 판정하면 FN |
| 근거 없는 주장 추가 | P3 | 근거 대조 식별 |
| 상호 모순 설명 | P4/P1 | 모순 감지 |
| 판단 유보 대상 | (전부 반사례) | Abstention Quality 지표로만 집계 |

Challenge 집계는 주 지표와 **분리 보고** (혼합 금지).

## 5. Gold 검증 작업량 (R7-E1 규모 — 재산정)

- 사례 12건 × 5항목 수동 검토: 사례당 ~30–45분
- 원본 Note 정밀 검토 3편: 편당 ~1시간
- **검토자 1인당 약 9–12시간**; 검토자 2인 기준 **18–24인시**
- 의견 불일치 조정(adjudication) 시간은 별도 (사례당 +15분 가정)

## 6. 차단 요인 및 해소 경로

| 차단 | 영향 | 해소 |
|---|---|---|
| Unseen 논문·Note 미확보 | B/C 세트 부재 | E1 전 논문 확보 + Note 생성(별도 승인) |
| 독립 검토자 미확보 | Gate 5항목 불성립 | Owner 지정 검토자 2인 |
| `insufficient evidence` 상태 이월 | 유효 표본 감소 | 사례별 보강 근거 또는 EXCLUDED 처리 |
| 후보 논문의 숨은 노출 이력 | 실질 Unseen 상실 | §2 4항목 이력 조사 (D1 계약) |
| EVOLVE 세트 재할당 요청 시 | split freeze 계약 | Owner 결정 없이는 접촉 금지 |
