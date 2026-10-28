---
doc_id: poc-rrsi-27-reward-contract-discrimination-audit
title: Reward Contract & Discrimination Audit (static analysis, 0 model calls)
status: report
updated: 2026-10-28
---

# Reward Contract & Discrimination Audit Report

**Summary.** (1) False Abstention 2건에 대한 Gold "No"의 원문 근거 검증 —
**원문에 명시적 부정이 존재하지 않음**(full_text·captured source 전수 검색
확인) → 두 case는 **ANSWERABILITY_POLICY_AMBIGUOUS**로 분류. 이전의 "QA
Reasoning Failure" 판정은 gold와의 불일치만으로 확정된 것이었으므로 **철회**
(행동 차원 관찰로 격하). (2) Reward 계약 초안 8축을 결정론 검증성·GT 요구·
hacking 경로별로 정의(가중치 미확정). (3) 통제 변형 설계 6유형 행렬 등록.
(4) **변별력 검증: 전 축 UNVERIFIED** — 구현된 결정론적 note 품질 평가 함수가
이 2편에 적용 불가(GT 기반 평가는 GT fixture 필요, gate 재실행은 pipeline
실행 금지에 충돌)이며 점수를 임의 생성하지 않음. 이것이 본 감사의 핵심 공백
발견이다. (5) RUN_DIR 계약 최소 보강(원자적 생성·symlink 거부·seal 내
symlink 검사) — **59/59 PASS**. 판정: **HOLD 유지**.

---

## A. Answerability Policy 재검토 (지시 §A)

대상: #68cd84 "Do they release a data set?", #0a0134 "Do they release code?"
(gold 둘 다 yn:False="No").

| 확인 항목 | 판정 |
|---|---|
| 1. 질문의 정확한 의미 | "논문이 코드/데이터셋을 공개하는가" — release 정책 여부 질의 |
| 2. Gold "No"의 annotation 근거 | **원문에 근거 문장 없음** — full_text 전수 검색에서 release·공개 관련 명시 서술이 전무(부정 서술도 없음) |
| 3. 원문 명시적 부정 존재? | **없음** (1802.07862 full_text + captured arXiv HTML v1 검색: "release" 명시 서술 0, 부정 표현 0) |
| 4. 침묵만으로 "No" 도출 가능? | **annotation 규약 의존** — QASPER 주석 규약(침묵→No) 지식이 있어야 도출 가능한 추론이며 literal substring 근거로는 불가. 본 검증에서 규약 문서를 보유하지 않으므로 규약 존재 자체는 관측된 주석 패턴으로부터의 정합 추정 |
| 5. Reader Note 실제 기술 내용 | release 정책에 대한 "명시 정보가 없음"을 **침묵으로서 명시 기록**("The source statements do not contain any explicit information regarding the release…") — 정보가 침묵으로서 보존된 것은 사실 |
| 6. QA Abstention이 Evidence 정책에 부합? | **부합** — literal-evidence 규약 하, "No"에 대응하는 근거 substring이 note에 존재하지 않음 → 중단은 계약-준수 응답 |

**판정: `ANSWERABILITY_POLICY_AMBIGUOUS` ×2** — gold 도출이 규약-의존 추론이고
원문 명시 부정이 없는 상태에서, gold 불일치만으로 QA를 오류로 확정할 근거가
불충분하다. **철회 사항 등록**: (i) 26번의 "QA Reasoning Failure" 분류 —
행동 차원 관찰로 격하, (ii) 25번의 "note 정보 누락 가설" — 사용자 철회 수용,
정보 누락이 아니라 "침묵-의존 gold 정책"의 모호성이 원인.

## B. Reward Contract 초안 (지시 §B, 가중치 미확정)

| 축 | 평가 대상 | 입력 Artifact | 필요한 GT | 결정론 검증 | Model Judge | Hacking 경로 | Gate/Soft |
|---|---|---|---|---|---|---|---|
| Claim Fidelity | note 주장과 원문 일치 | note digest + source digest | 원문(보유 — governed capture) | **가능**(문장 대조) | 부분 | 문구 재배치로 표층 정합 위장 | Soft |
| Required Information Coverage | 필수 정보 보존 | note | **필수 정보 정의 필요**(현재 부재) | 정의 확보 후 가능 | 정의에 따름 | 질문 목록에만 맞춘 복사(note→QA 과적합) | Soft (정의 부재 시 검증 불가) |
| Evidence Grounding | 근거가 note literal | note + evidence spans | note 자체(digest) | **가능**(normalized_find) | 불필요 | 문맥 무관 substring 인용 | **Hard Gate** |
| Unsupported Claim Detection | 근거 없는 주장 | note | 원문(보유) | 부분(문장 귀속) | **필요** | 침묵을 근거로 주장 은폐 | Soft |
| Scientific Understanding | 개념·구조 이해 | note | **review GT 필요**(부재) | 불가 | **필요** | 판단 기준 정규화 언어 학습 | Soft |
| QA Utility | note로 답 가능한 질문 비율 | note + QA set | gold QA(보유 — dev) | **가능**(단, 재실행 필요 — 현재 금지) | 모델 응답 필요 | 자기-충족 질문 선택 | Soft |
| Abstention Calibration | 중단 판정의 근거 정합 | note + QA 응답 | gold answerability | 부분(침묵-의존 gold는 AMBIGUOUS — §A) | **필요** | 규약 남용: 애매 시 항상 중단 | Soft |
| Execution Cost | calls·tokens·wall | ledger·telemetry | 불필요 | **가능** | 불필요 | 낮은 비용 = 높은 품질 혼동(품질 미검증 상태에서) | Soft (품질 축과 짝지을 때만) |

- 가중치 미확정(지시). 현재 **구현-완료 축**: Evidence Grounding(literal 검증),
  Execution Cost(ledger/telemetry) — 나머지 축은 GT·정의·재실행 요구로 미구현.

## C. Controlled Perturbation 설계 (지시 §C) — 실행 계획(미실행)

대상: `04_reader_note.en.md` 2편. 원본 무변경, 변형본은 평가 전용 경로
(`poc/runs/perturbation-audit/`)에 별도 생성(추후 승인 시). 본 단계는 계획만:

| 유형 | 변형 내용 | 기대 Reward 변화 | 판단 근거 |
|---|---|---|---|
| P1 핵심 주장 제거 | abstract 대응 연구 주장 문장 삭제 | Claim Fidelity ↓·QA Utility ↓·Answer F1 ↓ (내용 credit 소실) | 주장이 QA 근거의 직접 출처(25번: 내용 정답=커버리지 존재) |
| P2 실험 수치 변경 | "10,000"→"12,000"류 | Answer F1 ↓ (정답 불일치)·Claim Fidelity ↓ | 원문과 불일치(25번 §F: 표기 왜곡도 방향은 동일) |
| P3 Source 오연결 | 타 논문 근거 id 주입 | Source Reference Accuracy ↓·**identity Gate** (`PAPER_IDENTITY_MISMATCH` 차단) | 23번: 주제 일치 게이트 — 오연결은 cross-paper 사건의 재현 |
| P4 근거 없는 주장 추가 | 원문에 없는 문장 삽입 | Unsupported Claim ↑·Claim Fidelity ↓ (판정은 Model Judge) | §B: 근거-귀속 검증 필요 축 |
| P5 방법론 설명 제거 | 방법 섹션 핵심 문장 삭제 | Scientific Understanding ↓·QA Utility ↓ (일부 질문 불가 전환) | 26번: False Abstention의 근원은 방법·실험 축 |
| P6 무의미 문장 추가 | 중복 filler 삽입으로 길이 증가 | Answer F1 불변(최악)·비용 ↑ — **길이 자체는 품질 아님**(26번 권고) | 커버리지·정확 기반 축만이 품질 축 |

- 원본 artifact 무변경·별도 경로 생성 규약 명시(§A 격리 계약과 결합 — 변형본
  run dir도 invocation-bound).

## D. Reward Discrimination 검증 (지시 §D) — 전 축 UNVERIFIED

**점수 임의 생성 없음.** 구현된 결정론적 평가 함수 재점검 결과:

| 축 | Original | Perturbed | Expected | Observed | Discrimination |
|---|---|---|---|---|---|
| Claim Fidelity | — | — | ↓ | **UNVERIFIED** | **UNVERIFIED** (구현 함수 없음 — GT-기반 평가는 GT fixture 필요) |
| Required Information Coverage | — | — | ↓ | **UNVERIFIED** | **UNVERIFIED** (필수 정보 정의 부재) |
| Evidence Grounding | gate PASS(원본, 25번 산출) | — | ↑ | **UNVERIFIED** | **UNVERIFIED** (gate 재실행은 pipeline 실행 금지 충돌) |
| Unsupported Claim | — | — | ↑ | **UNVERIFIED** | **UNVERIFIED** (Model Judge 필요 — 미실행) |
| Scientific Understanding | — | — | ↓ | **UNVERIFIED** | **UNVERIFIED** (review GT 부재) |
| QA Utility | Answer F1 0.3729(원본) | — | ↓ | **UNVERIFIED** | **UNVERIFIED** (변형본 QA는 모델 재호출 필요 — 금지) |
| Abstention Calibration | 중단 4/10(원본) | — | — | **UNVERIFIED** | **UNVERIFIED** (§A: gold 정책 AMBIGUOUS) |
| Execution Cost | 73,085 tok(원본) | — | ↑ | **UNVERIFIED** | **UNVERIFIED** (변형본 미실행) |

- **핵심 발견**: 이 2편에 대해 "구현 완료된" 결정론적 note 품질 평가 함수는
  원본 artifact의 정적 관측(heading 수·gate PASS)뿐이며, 변형본 점수를 내는
  함수는 미구현이다. → reward 변별력 검증의 전제는 (i) 필수 정보 정의 확정 +
  (ii) GT 확보 또는 Model Judge 승인 + (iii) 변형 평가 실행 승인 — 세 가지가
  다음 단계 승인 대상으로 등록된다. "Reward가 품질 저하를 감지할 수 있는가"에
  대한 현재 답: **검증 불가(미검증) — 가능성 설계만 존재**.

## E. Artifact Immutability 보강 (지시 §E) — 최소 수정

| 항목 | 상태 |
|---|---|
| 원자적 디렉터리 생성 | **추가** — `create_run_dir_atomic` (exclusive mkdir, mode 0o700; 중복 생성 실패) |
| 동시 실행 Collision | mkdir 원자성으로 경합 차단 + per-invocation dir로 상호 간섭 구조적 불가 |
| Symlink 경로 우회 | **추가** — `SYMLINK_PATH_REFUSED` (run dir 경로), `SYMLINK_IN_SEALED_TREE` (seal scan 내 symlink 거부) |
| Sealed Artifact 재사용 | seal 존재 dir은 `RUN_DIR_REUSED_COMPLETED`로 진입 거부 + `verify_seal` 재검증 |
| Manifest Digest 검증 | `verify_seal` — per-artifact sha256 대조, 불일치 False |

- 신규 negative test 3건(원자적 배타성·symlink bypass·seal 내 symlink) —
  **59/59 PASS**.
- **PoC 봉인 vs 운영 쓰기 방지 (구분 기록)**: PoC seal은 digest 고정·변조
  검출이지 **쓰기 방지가 아니다**(로컬 사용자는 seal 파일 자체를 재작성할 수
  있음). 운영 수준 보장은 별도: seal 디렉토리 읽기 전용 마운트, 서명
  (issued-by 키), WORM 스토리지 — 승인자 권한 하 도입 권고(24번 §B와 동일
  원칙). 본 PoC에서 구현하지 않음.

## F. Reward Hacking 위험 (지시 §F-5)

1. **항상-중단 0.5** — 유지(주 reward 전제 불변).
2. **literal 인용 표면 인용** — 문맥 무관 substring 인용(Evidence Grounding은
   literal만 검증 — 문맥 정합은 Model Judge 영역).
3. **질문 과적합** — Required Information Coverage 정의가 질문 목록에 귀속될
   경우 note→QA 세트 과적합(§B hacking 경로) — 정의는 질문 독립적으로 확정
   권고.
4. **저비용=고품질 혼동** — Execution Cost를 단독 soft reward로 쓸 경우 품질
   미검증 상태에서 변별력 없음 — 품질 축과 짝지을 때만 유효.

## G. δ 반복 확대 필요성 (지시 §F-7)

- 본 감사 결과, 변별력 검증은 **δ 반복과 직접 연결**된다: same-paper QA의
  내용 credit이 reader 품질과 1:1 상관을 보인 관측(25번)을 n≥6에서 반복해야
  candidate 간 품질 차이 측정 가능성(26번 §E-6)이 확정된다.
- 현재 δ 반복 확대는 **금지 유지**(별도 승인 대상) — 필요성은 등록, 실행은
  승인 대기.

## H. 완료 보고 (지시 §F) 및 판정

1. Answerability Policy: §A — `ANSWERABILITY_POLICY_AMBIGUOUS` ×2, 이전
   오류-확정 철회. 2. Reward Contract 초안: §B (8축, 구현-완료 2축). 3.
   Perturbation Matrix: §C (6유형, 실행 계획). 4. Discrimination: §D — **전
   축 UNVERIFIED**(점수 임의 생성 없음; 이것이 감사의 핵심 공백 발견). 5.
   Hacking 위험: §F (4경로 등록). 6. Immutability 잔여 위험: §E (PoC seal은
   변조 검출이지 쓰기 방지 아님 — 운영 정책 별도). 7. δ 필요성: §G (등록,
   금지 유지).
8. **Evolution GO/HOLD/STOP: HOLD 유지** — 이번 단계의 결론이 HOLD를 강화:
   reward의 품질 감지 능력이 **미검증**임이 명시화되었고, 해제 조건이 명확
   (① 필수 정보 정의, ② GT 또는 Model Judge 승인, ③ 변형 평가 실행 승인,
   ④ δ n≥6 반복, ⑤ 분할 해동). STOP 아님: 격리 계약 보강 실동작 + 오류-확정
   자체 철회(26번에 이어 2차 자체 정정).

## 제한사항 준수

신규 모델 호출 **0**, Reader Pipeline 실행 **0**, QA 재실행 0, δ 반복 확대 0,
Final Holdout 소비 0, Scorer 수정 0, Reader Note 원본 변경 0, ai_papers 운영
상태 변경 0, 신규 worktree 0. 본 단계는 정적 분석·계획 등록으로 한정됨.
