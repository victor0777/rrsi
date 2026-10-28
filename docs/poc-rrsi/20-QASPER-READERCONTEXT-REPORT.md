---
doc_id: poc-rrsi-20-qasper-readercontext-report
title: Reader-context QASPER Calibration Report (executed) + Reward Validity Review
status: report
updated: 2026-10-28
---

# Reader-context QASPER Calibration Report

**Summary.** 승인 범위 내 Reader-context QA 1회 실행 (2편/10 cases, 모델
`qwen3.8-flash-next-fp8` 고정). **Answer F1 0.4, Evidence F1 0.0, 중단 9/10**.
단, **핵심 조건 발견**: 주입 대상 고정 artifact `04_reader_note.ko.md`
(sha256 `bffb8b75…`)는 **ImagiDrive(2508.11428) 노트**이며 QASPER 2편
(`1802.07862`/`1901.10133`)의 노트는 미산출 상태 — 본 실행은 **cross-paper
reader-context 조건**(노트 주제 불일치)이다. 이 조건에서 중단 9건은 note 정보
부재에 의한 것(모델 실패 아님)이며, 모델 실패(잉여 응답) 1건뿐이다. 공란 주석
매핑이 중단에 점수를 주어 공식 0.4가 산출 — 실내용 정답 기여 0. 판정:
**HOLD 유지**.

---

## A. 실행 결과 (지시 §A)

- 대상: `1802.07862`, `1901.10133` × 10 cases, input_mode `reader_context`
  (고정 artifact `04_reader_note.ko.md` 46,248 bytes, sha256
  `bffb8b75381222904d04eeb7c3a3c9d29422ca9a9a488caa475231b111d834dc` —
  adapter 준비 시 바인딩된 것과 동일, full-text 추가 주입 0).
- 모델/설정 고정: `qwen3.8-flash-next-fp8`, temperature 0.0, max_output 1024,
  json_mode off, case당 1 documented attempt, fulltext 실행과 동일 call 경로
  (`call_model` direct backend).
- 예산 준수: **calls 10/12, wall 13.3초/900초**. Ledger 10 예약 = telemetry
  10 terminal, usage reported 10/10, status completed 10/10 (http 200),
  **violations 0** (`poc/r0b2_audit.py` 재조정 PASS).
- 실측 비용: **입력 107,170 + 출력 510 = 107,680 tokens**, latency mean
  1,277ms / max 3,845ms. 유료 API 미사용(owner-provisioned LAN gateway).
- Scorer·dataset·split freeze 무변경. RRSI 코어·ai_papers 운영 변경 0.

## B. 조건 규정 — cross-paper reader-context (중요)

- `04_reader_note.ko.md`는 R0-b2 Reader Baseline(r0b2-repeat-4b)이 ImagiDrive
  (arXiv 2508.11428)에 대해 산출한 노트다. Calibration 논문 2편에 대한 reader
  note는 어떤 경로로도 산출된 바 없다(본 지시에서 신규 노트 생산 금지).
- 따라서 본 실행의 질의-문서 쌍은 **주제가 불일치**(MNER·문장순서 논문 질문 ↔
  자율주행 노트)이며, "note가 질문에 답할 수 있는가"라는 관점의 조건으로서
  **note 정보 존재 = 0/10**이다. 이는 결함이 아니라 승인된 artifact 바인딩의
  결과이며, reader-context 축을 reward로 쓰기 위한 전제(논문별 노트 필요성)를
  실증하는 관측값이다.
- 리터럴 검증은 주입 문서(노트) 기준으로 수행됨 — 한 건의 응답도 노트의
  literal substring으로 검증 통과했으나, 그 내용은 제3 논문(ImagiDrive)의
  것이다.

## C. 질문별 커버리지 (지시 §B, 8 fields)

| # | 질문(축약) | Gold 가답성 | Fulltext 근거 | Note 정보 | QA 판정 | 응답 | Answer F1 |
|---|---|---|---|---|---|---|---|
| 1 | model이 image-word 연관을 검사했나 | yn:True | 주석 있음 | **없음** | 불가 | 중단 | 0.0 |
| 2 | text+image 모두로 NER 학습하나 | yn:True | 주석 있음 | **없음** | 불가 | 중단 | 0.0 |
| 3 | 인식하는 개체 유형은 | 공란 주석 | 주석 있음 | **없음** | 불가 | 중단 | **1.0 (매핑credit)** |
| 4 | SnapCaptions 개체 비연속 가능 | yn:False | 주석 있음 | **없음** | 불가 | 중단 | **1.0 (매핑credit)** |
| 5 | SnapCaptions 데이터 크기 | 10000 (ff) | 답은 fulltext 미인치 | **없음** | 불가 | 중단 | **1.0 (매핑credit)** |
| 6 | unordered text document란 | ff (자유서술) | 답은 fulltext 미인치 | **없음** | 불가 | 중단 | 0.0 |
| 7 | 어떤 모델 사용 | 공란 주석 | 주석 있음 | **없음** | 불가 | **응답(VLM+DWM — 제3논문 내용)** | 0.0 |
| 8 | 데이터셋 release하나 | yn:False | 주석 있음 | **없음** | 불가 | 중단 | 0.0 |
| 9 | 코드 release하나 | yn:False | 주석 있음 | **없음** | 불가 | 중단 | 0.0 |
| 10 | 평가 언어 | UNANS | 주석 없음(2편) | **없음** | 불가 | 중단 | **1.0 (매핑credit)** |

- Gold 근거 주석 존재: 8/10 (2건은 해당 논문에 근거 주석 없음).
- Gold 답이 fulltext에 literal 존재: 검사한 2건 모두 미인치(자유서술형) —
  17번 보고의 프로토콜 불일치 관측과 정합.
- **Note 정보 존재: 0/10 — "정보 부재"가 전건 중단의 원인. 모델 실패는 #7
  1건(주제 불일치 노트에서 답을 만들어 응답).** #1·2·6·8·9의 중단은 공식
  gold 기준으로는 False Abstention이지만, 본 조건(주제 불일치)의 관점에서는
  올바른 중단이다 — 두 프레임은 분리 보고되며 혼용 금지(§F).

## D. Answerability Confusion Matrix (지시 §C) + 용어 정정

| | Gold 가답 (5) | Gold 불가 성향 (5) |
|---|---|---|
| **모델 응답 (1)** | Correct Answerability **0** | False Answer **1** |
| **모델 중단 (9)** | False Abstention **5** | Correct Abstention **4** |

- 소비자 키 용어 정정(등록, scorer 무수정): 기존 `false_unanswerable_claims`(5)는
  실제로는 **False Abstention**(gold 가답인데 중단)이며, `missed_unanswerable`(1)은
  실제로는 **False Answer**(gold 불가 성향인데 응답)이다. "False Unanswerable"라는
  단일 축 용어는 2×2 사분면으로 재정의된다: **Correct Answerability / False
  Abstention / False Answer / Correct Abstention**.
- `gold_unanswerable_count 5`의 의미도 명시: 공란 주석을 Unanswerable 참조로
  매핑하는 scorer 규칙(§E) 때문에 "불가 성향"에는 실제 UNANS 주석 2건 + 공란/혼합
  주석 3건이 포함된다.

## E. Scorer Mapping 진단 (지시 §D, scorer 무수정)

1. **공란 주석 → Unanswerable 매핑의 점수 왜곡**: Answer F1 1.0을 받은 4건
   (#3·4·5·10) 전부 중단 응답("Unanswerable")이 매핑된 참조와 token-F1 1.0으로
   일치한 케이스다. 즉 공식 0.4의 전액이 중단-매핑 credit이며, 실내용 정답
   기여는 0 (#7의 유일한 실응답은 0점). 항상-중단 정책이 본 스코어에서
   0.5~0.8을 받을 수 있다는 구조적 관측(R0-b2 이래 반복 확인)의 재확인.
2. **`10K` vs `10000` 표현 차이**: 본 실행에서는 모델이 #5를 중단하여 미발화 —
   fulltext 실행(19번 보고)의 −1.0 왜곡 사례는 유지(불변, 이월).
3. **장문형 span 왜곡**: 본 실행 미발화(중단뿐) — 이월.
4. **Diagnostic Correctness (별도 계산, 공식 점수 대체 금지)**: 주제 불일치
   조건에서 이상적 행동은 10/10 중단이므로 "조건-적합 올바름"은 9/10(중단 9
   올바름 + 응답 1 부적합). 이는 진단 지표일 뿐이며 공식 Answer F1 0.4와
   방향이 다르고(중단=0점 아님), 어떤 reward 계약에도 투입되지 않는다.
5. 공식 scorer 무수정 유지. Breakdown: none 0.8, boolean 0.0, abstractive 0.0.

## F. 3-way 비교 (Abstract / Full-text / Reader-context)

| 지표 | Abstract-only | Full-text | **Reader-context** |
|---|---|---|---|
| Answer F1 | 0.50 | 0.30 | **0.40** (전액 매핑credit) |
| Evidence F1 | 0.0 | 0.30 | **0.0** |
| Evidence literal 생성 | 2/10 | 5/10 | **1/10** |
| 중단(응답 축) | 8/10 | 5/10 | **9/10** |
| False Abstention | 4 | 3 | **5** |
| False Answer | (미분리) | (미분리) | **1** (사분면 신설로 최초 분리) |
| 실측 호출 비용 | 10 calls | 10 calls / 37.5k tok | 10 calls / **107.7k tok** (노트 46KB/건 주입) |

- 세 조건 모두에서 공식 Answer F1은 행동 개선과 무관하게 매핑 왜곡이 지배 —
  조건 비교로는 reward 축 자격을 만들 수 없다(§G).

## G. Reward Validity (지시 §E, 가중치 미확정)

- **Reader Gold 상한 효과**: note 정보 0/10 → reader-context 축은 reader 노트
  품질(δ 목표량)에 대해 판별력 0. 노트가 아무리 좋아도 질문 논문과 주제가
  다르면 F1은 불변(중단 최대). → reward 자격: **부적격 (현재 scope)**.
- **공식 Answer F1 판별력**: 0.4 전액 매핑credit → 행동 개선 비-민감. 19번
  보고의 자격 재검토 사유 유지·강화.
- **Diagnostic Correctness 사용처**: reward 아닌 회귀 진단용으로만 유효.
- **Evidence F1 판별력**: 본 실행 측정 match 0 → 판별 관측 없음. fulltext
  조건에서만 동작 검증됨(19번).
- **Source Reference Accuracy**: 근거 참조는 노트 문장 id(ev_000…)로 리터럴
  검증·digest 바인딩은 정상(provenance 추적 가능). 그러나 참조 대상 문서
  (ImagiDrive 노트)가 record의 source_id(QASPER 논문)와 의미적으로 불일치 —
  **주제 일치 게이트(노트 논문 == 질문 논문)** 가 reader-context lane의
  reward 전제로 등록됨.
- **중단 독립 지표**: 채택 가능(응답 축과 분리 보고). 단 항상-중단으로 최대
  달성 가능하므로 단독 reward로는 hackable — 보조 지표로만.
- **Reward Hacking 표면 (등록)**: ① 항상-중단 credit(§E-1, 구조적 — scorer
  매핑 왜곡이 만드는 표면), ② cross-context 인용(주제 불일치 문서에서 리터럴
  검증을 통과하는 답/근거 인용 — 본 실행 #7이 실증). 완화: 문서 digest 바인딩
  (기완료), 주제 일치 게이트 (신규 등록), 공식/diagnostic 분리 보고 (기완료).

## H. Reader-context 정보 손실 vs QA 모델 실패 (지시 §B 분리 원칙)

- 정보 손실/부재: **10/10** — 대상 노트가 아예 없어 "노트 내 정보 부재"가
  전건. 노트 압축에 의한 정보 손실 관측은 이번 실행으로 측정 불가(대상 노트
  부재가 상위 조건).
- QA 모델 실패: **1/10** (#7 False Answer). 중단 오류 5건(False Abstention)은
  공식 gold 프레임의 오류지만 본 조건 프레임에서는 올바른 행동 — 두 프레임의
  혼용이 reward 왜곡의 핵심 경로이므로 금지(§C·§G와 연결).

## I. 최종 보고 (지시 §F 1–10)

1. Reader-context Answer F1: **0.4** (전액 중단-매핑 credit, 실내용 기여 0).
2. Reader-context Evidence F1: **0.0** (측정 8건, match 0).
3. 3-way 비교: §F (Answer 0.5/0.3/0.4, Evidence 0.0/0.3/0.0).
4. 질문별 커버리지: §C 표.
5. Confusion matrix: §D (0/5/1/4 사분면) + 용어 정정 등록.
6. Mapping 영향: §E (공란 주석 매핑이 0.4 전액 생성; 10K·장문형은 이월).
7. 정보 손실 case: 노트 자체 미존재(§H) — 정보 손실 측정 불가, 정보 부재
   10/10.
8. QA 모델 실패 case: 1건 (#7 False Answer, 주제 불일치 노트에서 응답).
9. Reward 적합성: reader-context 축 현재 scope에서 **부적격**(§G) — 전제는
   ① 대상 논문별 reader note 산출, ② scorer 매핑 왜곡 해소, ③ 주제 일치
   게이트. 가중치 미확정 유지.
10. **Evolution GO/HOLD/STOP: HOLD 유지** — 신규 근거: reader-context lane은
    adapter(`5038b87`)→glue→consumer→scorer까지 fail-closed로 **운영 연결
    완료**(ledger·telemetry 0 violation). 잔여 HOLD 사유 불변(δ n≥6, 분할 해동,
    scorer 매핑 왜곡) + 신규 전제 등록(논문별 노트, 주제 일치 게이트). STOP
    아님: 계약·구현 실동작 검증, 결함 0.

## 제한사항 준수

RRSI Evolution 0, Reader Prompt 변경 0, Final Holdout 소비 0, Scorer 수정 0,
RRSI 코어 수정 0, ai_papers 운영 상태 변경 0, Dataset Split 변경 0, 신규
worktree 0, **δ 반복 확대 0**. 신규 파이프라인 실행은 승인된 Reader-context
QA 1회(10 cases)뿐.

**Committed artifacts**: `poc/qasper_readercontext_calibration.py`(rrsi), 본
보고. Run 산출물은 `poc/runs/qasper-readercontext-calibration/` 로컬 미추적
(r0b2-split 규약 동일).
