---
doc_id: poc-rrsi-25-same-paper-readercontext-calibration
title: Same-paper Reader-context QA Calibration (executed, approved scope)
status: report
updated: 2026-10-28
---

# Same-paper Reader-context QA Calibration Report

**Summary.** 승인 범위 내 Same-paper Reader-context QA 1회 실행 완료. Permit
발급(`0be5783c…`, owner-directive) → 발급 ledger 등록 → preflight READY →
**10 calls / 0 unauthorized**, ledger 10 = terminal 10 = usage 10/10,
violations 0. **Same-paper Answer F1 0.3729, Evidence F1 0.0** — 3조건 중
최초로 실내용 정답 기여가 실측됨(3.729 중 1.729, 47%: yn 정답 2·abstractive
부분 1·데이터 크기 정답 1). 잔여 53%는 여전히 중단-매핑 credit. 판정:
**HOLD 유지** (δ n≥6·분할 해동·scorer 매핑 왜곡 미해소).

---

## A. Permit 발급 및 검증 (지시 §A·§B)

- Permit: `poc/runs/qasper-readercontext-samepaper-r1/execution-permit.json`
  (schema `rrsi-execution-permit/v0.1`, sha256 `0be5783c…`), workstream
  `reader_context_qa` / call_type `qa_inference`, dataset `2ae7ee62…`(frozen
  v0.3), papers {1802.07862, 1901.10133}, model `qwen3.8-flash-next-fp8` @
  `http://192.168.0.199/v1`, **max_calls 12 / wall 900초**, retry 0,
  concurrency 1, paid_api forbidden. 발급 ledger 등록
  (`execution_permit_issued`, `issued_by=owner-directive`,
  `issued_at=2026-10-28T11:55:24Z`) — **invocation_id
  `qasperrc-samepaper-r1` 바인딩**.
- 실행 전 검증 7항목(§B): permit 등록·digest 일치·identity PASS ×2·note
  digest 일치·split/holdout·model/endpoint·budget+ledger probe → **preflight
  READY** (exit 0, 호출 0). 실패 항목 없음 → 실행 개시.

## B. 실행 계측 정합성 (지시 §D)

Permit → Identity → Ledger Reservation → Invocation → Telemetry Terminal →
Reconciliation 순서 실측: **calls 10 = reservations 10 = terminals 10**,
usage reported 10/10 (http 200 전건), **unauthorized calls 0**, violations 0.
**Tokens: 입력 72,270 + 출력 815 = 73,085**, latency mean 1,729ms / max
3,203ms, wall 17.8초. Reconciliation (`poc/r0b2_audit.py`) PASS.

## C. Same-paper QA 결과 (지시 §C·§E)

**공식 점수: Answer F1 0.3729, Evidence F1 0.0 (측정 8건), 중단 4/10.**

질문별 표(Gold 가답성 / Note 커버리지 / 응답 / 근거 / 공식 F1):

| # | 질문(축약) | Gold | Note 커버리지 | 응답 | F1 |
|---|---|---|---|---|---|
| 1 | SnapCaptions 데이터 크기 | 10000 (ff) | **1/1 (있음)** | "10,000 user-generated image-caption pairs" — **내용 정답** | 0.4 |
| 2 | image-word 연관 검사 | yn:True | 1/4 (부분) | "no" — **오답** | 0.0 |
| 3 | SnapCaptions 비연속 가능 | yn:False | 1/2 (부분) | 중단 | 1.0 (매핑credit) |
| 4 | text+image 모두 학습 | yn:True | **1/1 (있음)** | "yes" — **정답** | 1.0 |
| 5 | 인식 개체 유형 | 공란 주석 | **있음** | "PER, LOC, ORG, MISC" — **내용 정답, 공란 매핑으로 0** | 0.0 |
| 6 | 코드 release | yn:False | **없음** | 중단 — note 정보 부재 | 0.0 |
| 7 | 어떤 모델 사용 | 공란 주석 | 있음 | note 내용 그대로 응답 — gold 공란 | 0.0 |
| 8 | unordered text document | ff (자유서술) | **3/3 (있음)** | abstractive — **내용 정합** | 0.329 |
| 9 | 데이터셋 release | yn:False | **없음** | 중단 — note 정보 부재 | 0.0 |
| 10 | 평가 언어 | UNANS | 없음 | 중단 — **올바른 중단** | 1.0 |

**Answerability Confusion Matrix** (gold-unans 성향 = UNANS 또는 공란 참조):
Correct Answerability **3** / False Abstention **2** / False Answer **2** /
Correct Abstention **3** (consumer 상세: false_unanswerable_claims 2,
missed_unanswerable 3).

## D. 3-way 비교 (지시 §E 1–3) — cross-paper(INVALID) 미포함

| 지표 | Abstract-only | Full-text | **Same-paper Reader-context** |
|---|---|---|---|
| Answer F1 | 0.50 | 0.30 | **0.3729** (내용 기여 47% — 최초 실측) |
| Evidence F1 | 0.0 | 0.30 | **0.0** |
| 중단(응답 축) | 8/10 | 5/10 | **4/10** |
| False Abstention | 4 | 3 | **2** (모두 note 정보 부재 원인) |
| False Answer | (미분리) | (미분리) | **2** (모두 gold 공란 주석 원인) |
| Token 비용 | (기록) | 37,517 | **73,085** (note 39.5KB·29KB 주입) |

- Cross-paper Reader-context(20번 보고)는 **INVALID_CONTEXT_MISMATCH 유지**,
  비교 지표에서 제외.

## E. 정보 누락 vs QA 모델 실패 분리 (지시 §E·§G-7)

- **Note 정보 누락 (구조적)**: #6·9 (release 정책이 note에 없음) → False
  Abstention 2건 전액이 note 압축 정보 손실 원인. #3 (비연속성 부분 누락).
- **QA 모델 실패**: #2 ("no" 오답 — note 부분 정보로 추론 실패, 근거 무관).
- **Gold 매핑 문제 (모델 실패 아님)**: #5 (정답이 공란 주석 매핑으로 0점),
  #7 (note 정보에 근거한 응답 vs gold 공란 → False Answer), #3·10 (중단이
  공란/UNANS 매핑 참조와 일치해 1.0 credit).

## F. Scorer Mapping 진단 (지시 §E 4, scorer 무수정)

1. **공란 주석 → Unanswerable 매핑**: Answer F1 3.729 중 중단-매핑 credit
   2.0 (53%) — 항상-중단 정책은 본 세트에서 0.5 획득 가능 (hacking 표면
   유지). 동시에 **실내용 기여 1.729 (47%)가 최초로 분리 관측**됨 — 조건
   선택(같은 논문의 note)이 매핑 왜곡 아래에서도 내용 신호를 만들어냄.
2. **`10,000` vs `10000`**: #1에서 정확히 이 왜곡 재현 — 내용 정답("10,000")
   ↔ gold("10000") 표기 차이로 token F1 0.4 (fulltext의 `10K` 사례와 동일
   계열). 표기 정규화가 scorer 무수정 하에서는 reward로 회수 불가.
3. **장문형**: #8 abstractive 부분 점수(0.329) — 요약형 응답에 실제 credit.
4. Diagnostic Correctness(별도 계산): note 정보 기준 응답 자격 — 내용 정답
   4건/10 (공란 매핑 제외 시). 공식 점수 대체 금지 유지.

## G. Reward Validity (지시 §F, 가중치 미확정)

- **Answer F1 변별력**: same-paper 조건에서 내용 신호 분리 관측(47%) —
  abstract/fulltext보다 행동 민감. 그러나 여전히 53% 중단 credit → 주 reward
  자격은 공란 주석 매핑 왜곡 해소 전까지 유지 보류.
- **Evidence F1 변별력**: reader-context에서 0 (구조적 — 예측 근거는 note
  문서, gold 근거는 fulltext 문서; 서로 다른 digest). **full_text 조건에서만
  유효**(19번 실증 유지).
- **Abstention Reward Hacking**: 표면 유지(항상-중단 0.5) — 완화는 scorer
  수정 불가 원칙 하에서 (i) 중단을 독립 지표로 분리 보고, (ii) 주 reward
  승인 전 mapping 왜곡 해소.
- **Reader Note Coverage**: 내용 정답 4건 전부 note 커버리지 존재와 일치,
  False Abstention 2건 전부 누락과 일치 — **note 정보 손실이 본 조건의 지배적
  오류 원인**(reader 품질 개선이 직접 이어지는 축 — reader-note δ 목표와
  정합).
- **Source Reference Accuracy**: 근거는 note 문장 id + note digest 바인딩으로
  유효 provenance. 단 ref_kind는 note layout 기준 — paper 문장 참조 아님
  (별도 등록).
- **Gold Annotation Mapping 문제**: 공란 주석 매핑이 방향 왜곡(정답 0점 +
  중단 credit)의 원천 — 19·20번 등록 유지, scorer 무수정.

## H. Artifact 보존 위반 등록 (정직 보고)

- Runner의 `RUN_DIR`이 공유 dir(`poc/runs/qasper-readercontext-calibration/`)
 로 고정되어 있어, 본 실행의 raw packet이 동일 slug(sha256(case_id))로 기존
  packet을 **덮어쓴 충돌**이 발생: a6cd3b1(cross-paper) → 사건(22번 §E) →
  본 실행 3세대 충돌. 덮어쓰기 이전 packet은 미추적 경로라 복구 불가 —
  **artifact 보존 규약 위반**으로 등록(삭제 의도 0, 통제 미비). 이전 세대의
  내용은 20번·22번 보고 표(질문별 F1·근거·digest·latency)로 보존. 완화: 본
  실행 산출물은 별도 dir(`poc/runs/qasper-readercontext-samepaper-r1/`)로
  복제 보존, 후속 runner는 실행 dir를 permit에서 강제하도록 개선 권고.

## I. 완료 보고 (지시 §G 1–10)

1. Permit: §A (발급+7검증 READY).
2. 정합성: §B (10=10=10, unauthorized 0, in 72,270 + out 815).
3. Same-paper Answer F1: **0.3729**.
4. Same-paper Evidence F1: **0.0** (측정 8건).
5. Confusion: §C (3/2/2/3).
6. Note Coverage: §F (내용 정답=커버리지 존재, False Abstention=누락 —
   정합).
7. 실패 분리: §E (정보 누락 2-3건, 모델 실패 1건, gold 매핑 2건).
8. Mapping 영향: §F (53% 중단 credit, 10,000 표기, abstractive credit).
9. Reward Validity: §G — same-paper 축은 내용 신호 보유, 주 reward 자격은
   매핑 왜곡 해소 전까지 보류, 중단 독립 지표 병행.
10. **Evolution GO/HOLD/STOP: HOLD 유지** — 근거 갱신: same-paper
    reader-context는 매핑 왜곡 아래에서도 내용 신호(47%)를 실증 — reader
    품질(δ 목표량)과 직접 연결되는 최초의 평가 축. 잔여 HOLD 사유 불변:
    ① δ 확정(n≥6, 반복 확대는 별도 승인), ② 분할 해동 승인, ③ 공란 주석
    매핑 왜곡 하의 주-reward 자격. STOP 아님: 계약·계측 전건 fail-closed
    실동작, 결함 0(보존 위반 §H는 별도 등록).

## 제한사항 준수

RRSI Evolution 0, Reader Prompt 변경 0, δ 반복 확대 0, Final Holdout 소비 0,
Dataset Split 변경 0, Official Scorer 수정 0, 기존 Artifact 의도 삭제 0
(§H 충돌 별도 등록), ai_papers 운영 상태 변경 0, 신규 worktree 0. 본 승인은
Same-paper QA Calibration 1회(10 cases)에 한정되어 소진됨.
