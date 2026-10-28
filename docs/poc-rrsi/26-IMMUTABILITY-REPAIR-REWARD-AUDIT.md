---
doc_id: poc-rrsi-26-immutability-repair-reward-audit
title: Artifact Immutability Repair & Reward Signal Audit
status: report
updated: 2026-10-28
---

# Artifact Immutability Repair & Reward Signal Audit Report

**Summary.** Invocation ID 기반 독립 RUN_DIR 계약(`poc/run_dir_isolation.py`)
을 runner에 통합 — collision·재사용·덮어쓰기를 호출 전 fail-closed 차단,
실행 후 seal로 digest 고정. Negative regression **7/7 PASS**(호출 0·기존
artifact 변경 0), 전체 **56/56 PASS**. Score Decomposition: 총점 **3.7294
정확 일치**(중단 credit 2.0 + 내용 credit 1.7294). **25번 보고 정정**:
Correct Abstention은 3이 아니라 **2** — 1591068(데이터 크기)은 중단이 아니라
**응답**(0.4 내용 credit)이므로 False Answer 3 / Correct Abstention 2가
정확하며, credit 2.0과 정확히 일치. False Abstention 2건은 note 정보 누락이
아니라 **note가 보존한 근거 기반 침묵**(release 관련 명시 정보 없음을 note가
기록)을 QA가 활용하지 못한 행동 차원 실패 — note 품질 차원은 UNVERIFIED 유지.
판정: **HOLD 유지**.

---

## A. Artifact Immutability Repair (지시 §A)

`poc/run_dir_isolation.py` (schema `rrsi-run-dir-seal/v0.1`) — 필수 6조건
구현:

| 조건 | 구현 |
|---|---|
| 1. Invocation ID ↔ RUN_DIR 1:1 바인딩 | `run_dir_for` — run dir는 정확히 `<root>/<invocation_id>` (경로 조작 문자열 거부) |
| 2. 타 Invocation RUN_DIR 재사용 금지 | dir 이름이 invocation_id와 동일해 구조적으로 불가 + permit invocation_id 대조 (`INVOCATION_ID_MISMATCH`) |
| 3. 기존 Raw Packet 덮어쓰기 금지 | `raw/packet-*.json` 선존재 → `RAW_PACKET_COLLISION` |
| 4. Output Collision 검사 (호출 전) | `resolve_run_dir` — 완료 run-summary·기존 artifact 선존재 → `RUN_DIR_REUSED_COMPLETED`/`RUN_DIR_ALREADY_USED` |
| 5. 실행 후 Manifest/Artifact Digest 고정 | `seal_run_dir` — per-artifact sha256 기록, artifact 자체는 미변경; `verify_seal` 재검증 |
| 6. 기존 기록 삭제·변경 금지 | 격리 dir 구조상 구조적으로 불가 + negative test로 확인 |

- **runner 통합**: `run()`의 preflight READY 직후 `resolve_run_dir` 강제 —
  collision 시 모델 호출 전 `FAIL_CLOSED`(0 calls). 실행 완료 후
  `seal_run_dir` 자동 수행.
- permit의 invocation_id가 RUN_DIR의 단일 권위 — runner 상수·파일명은 식별
  근거 아님(24번 원칙과 정합).

## B. Negative Regression (지시 §B) — 7/7 PASS

전건: 모델 호출 0회, 기존 artifact 변경 0건(테스트 후 byte 비교 검증):

| 조건 | 결과 |
|---|---|
| 새 Invocation + 새 RUN_DIR | **PASS** (dir 미생성 상태로 진입만) |
| 타 Invocation RUN_DIR 재사용 | **BLOCK** (`RUN_DIR_REUSED_COMPLETED`) |
| 기존 Raw Packet 선존재 | **BLOCK** (`RAW_PACKET_COLLISION`) |
| Invocation ID 불일치 (permit 대조) | **BLOCK** (`INVOCATION_ID_MISMATCH`) |
| Manifest Digest 불일치 (seal 후 변조) | **BLOCK** (`verify_seal=False`) |
| 기존 실행 결과 덮어쓰기 시도 | **BLOCK** (`RUN_DIR_ALREADY_USED`) |
| Seal 동작 (positive) | digest 고정, artifact 미변경 |

전체 PoC 테스트: **56/56 PASS**. 기존 공유 dir(`qasper-readercontext-calibration/`)의 현물은 25번 §H로 복제 보존 완료 — 본 계약으로 후속 실행의 충돌은 구조적으로 차단.

## C. Score Decomposition (지시 §C) — 공식 Scorer 무수정

Same-paper 10질문의 공식 Answer F1 분해(총점 **3.7294 = official 0.3729×10,
정확 일치**):

| # | 질문(축약) | Gold 가답성 | 생성 응답 | 공식 F1 | 중단 Mapping Credit | 내용 기반 Credit | Mapping Distortion |
|---|---|---|---|---|---|---|---|
| 1 | SnapCaptions 크기 | 가답 (ff:10000) | "10,000 … pairs" | 0.4 | 0 | **0.4** | 표기 차이("10,000"↔"10000")로 −0.6 |
| 2 | image-word 연관 검사 | 가답 (yn:True) | "no" | 0.0 | 0 | 0 | (추론 실패) |
| 3 | 비연속 가능 | 가답+불가 혼합 | 중단 | 1.0 | **1.0** | 0 | 중단이 UNANS 참조와 일치 |
| 4 | text+image 학습 | 가답 (yn:True) | "yes" | 1.0 | 0 | **1.0** | 0 |
| 5 | 개체 유형 | 공란 주석 | "PER, LOC, ORG, MISC" | 0.0 | 0 | 0 | **−1.0** (정답 zeroing) |
| 6 | 코드 release | 가답 (yn:False) | 중단 | 0.0 | 0 | 0 | (False Abstention) |
| 7 | 어떤 모델 | 공란 주석 | note 내용 응답 | 0.0 | 0 | 0 | (gold 공란) |
| 8 | unordered text document | 가답 (ff) | abstractive | 0.3294 | 0 | **0.3294** | 부분 중복(요약형) |
| 9 | 데이터 release | 가답 (yn:False) | 중단 | 0.0 | 0 | 0 | (False Abstention) |
| 10 | 평가 언어 | 불가 (UNANS) | 중단 | 1.0 | **1.0** | 0 | 중단이 UNANS 참조와 일치 |

**합계 검증**: 중단 Mapping Credit 2.0 + 내용 기반 Credit 1.7294 = **3.7294**
= 총점 정확 일치(질문별 기여 합계와 1:1 대조 완료).

**Diagnostic Correctness (별도 계산, 공식 대체 금지)**: note 정보 기준 내용
자격 — 정답 4건/10 (공란 매핑 제외 기준: #1·4·5 내용 정답 + #8 내용 정합),
오답 1건 (#2), 근거 기반 올바른 중단 1건 (#10).

### Correct Abstention Credit 설명 (지시 §C-2, 25번 보고 정정)

- 25번 보고 §C의 사분면(3/2/2/3) 중 **Correct Abstention 3 / False Answer 2는
  분류 오류**였다. 재계산: 중단 4건(a0543, 68cd84, 0a0134, a8c862) 중
  gold-unans 참조와 일치한 것은 **a0543·a8c862 = 2건**뿐이고, **1591068은
  중단이 아니라 "10,000 …"로 응답**했다(0.4는 중단 credit이 아니라 내용
  credit). 따라서 정확한 사분면은 **Correct Answerability 3 / False Abstention
  2 / False Answer 3 / Correct Abstention 2**이다.
- "Correct Abstention 3 vs Abstention Credit 2.0 차이"의 해답: 차이가 아니라
  **credit 2.0이 정확히 Correct Abstention 2건과 일치**하며, 3이라는 값이
  잘못된 것이었다. 본 문서로 25번 §C를 정정(기존 문서는 무변경 보존, 정정
  판정만 추가). consumer 상세(missed_unanswerable 3 = f7a89·43f563·1591068)와
  정확히 정합.
- 교훈 등록: 사분면 분류는 중단/응답 행동과 gold-unans 참조를 **case별로**
  대조해야 하며 집계 시 행동 축을 혼용하면 오류가 재현된다(본 정정의 오류
  경로).

## D. Reader Note Omission Classification (지시 §D)

False Abstention 2건(#6 코드 release, #9 데이터 release) 대상 분류:

- **핵심 관측**: 두 case 모두 note는 release 정책 정보가 "없음"이 아니라
  **"없음"이라는 근거 기반 침묵을 명시적으로 보존**하고 있다 — 예: "The source
  statements do not contain any explicit information regarding the release of
  the dataset. There is no mention of whether the SnapCaptions dataset is
  publicly …". gold "No"는 원문의 침묵으로부터의 추론이며, note는 그 침묵
  자체를 기록했다.
- 분류: 두 case 모두 **Required Information Omission 아님**, Optional Detail
  Omission도 아님(침묵 메타정마저 보존됨), Incorrect Information/Unsupported
  Claim 아님. → **QA Reasoning Failure**: note가 보존한 근거 기반 침묵을
  "No"로 활용하지 못한 행동 차원 실패. 단 literal-evidence 규약 하의 중단은
  계약-준수 응답이므로 규약 변경 요구는 아님.
- **UNVERIFIED 유지**: note 품질(침묵 보존이 gold review 관점에서 올바른
  보존인지)은 GT 부재로 판정 불가 — 24번 보고의 CONDITIONAL 유지. "QASPER
  질문에 등장했다는 이유만으로 필수 보존 대상"이라는 가정은 하지 않음(지시
  준수): reader note 요구사항은 근거-추적 요약이지 사전(事前) fact 리스트가
  아님.

## E. Reward Signal Audit (지시 §E, 가중치 미확정)

1. **공식 Answer F1의 Reward Hacking**: 표면 유지 — 항상-중단 0.5 (5/10
   gold-unans-side). 중단 credit 2.0이 총점의 53%를 차지하므로 주 reward
   승인 전 mapping 왜곡 해소 전제는 불변.
2. **Abstention Mapping의 점수 기여**: 2.0/3.7294 (53%) — 전부 a0543·a8c862의
   gold-unans 참조 일치 credit. False Abstention(68cd84·0a0134)은 0 credit —
   매핑은 불가 판정 방향으로도 정확히 작동(이번 세트 한정).
3. **Note Coverage ↔ 실제 정답 기여**: 내용 credit 3건 전부 coverage 존재와
   일치, False Abstention 2건 전부 침묵 보존 사례 — **note 정보 축과 Answer F1
   내용 credit의 상관이 본 세트에서 1:1**. 단 n=10·1회 실행이라 일반화 전
   반복 필요(δ 반복 확대는 별도 승인).
4. **Evidence F1의 Cross-document 한계**: reader-context에서 구조적 0 —
   예측 근거(note digest)와 gold 근거(fulltext digest)가 다른 문서.
   containment 매칭은 이종 문서 간에 기대 점수가 0에 수렴 → Evidence F1은
   **full_text 조건 전용 지표**로 정책 고정 권고(권고만, 계약 변경 없음).
5. **Note 길이 증가에 따른 Reward 왜곡**: 등록 — note가 길어지면 (i) token
   비용 상승(본 실행 73k, fulltext 37.5k 대비), (ii) literal 인용 기회 증가로
   중단 감소(행동 시프트), (iii) distorting도 없는 풍부 컨텍스트로 hacking
   표면 확대. 길이는 자체적으로 품질이 아니므로 reward 축에서 제외하고
   coverage·정확 기반 축만 사용 권고.
6. **Candidate 간 품질 차이 측정 가능성**: same-paper 축은 내용 credit
   1.7294를 분리 관측했으므로, reader 품질 차이가 내용 credit·coverage
   상관을 통해 측정 가능해질 개연성 확보. 그러나 확정 판정은 δ 반복(n≥6)과
   분할 해동 승인 후 — 현재는 개연성 등록만.

## F. 잔여 위험 (지시 §F-7)

① 공란 주석 매핑 왜곡(주 reward 자격 보류 근거, 유지), ② 항상-중단 0.5
(hacking 표면, 유지), ③ n=10·단일 실행의 coverage 상관 일반화 미완,
④ ai_papers 측 직접 호출 가능성(rrsi 소관 밖, 유지), ⑤ seal 검증은
로컬 미추적 artifact에 한정(외부 보관 무결성은 별도).

## G. 완료 보고 (지시 §F) 및 판정

1. RUN_DIR 격리: §A. 2. Collision Negative: §B (7/7). 3. Decomposition: §C
   (3.7294 정확 일치). 4. Correct Abstention Credit: §C (2건=credit 2.0 —
   25번 정정). 5. Omission: §D (QA Reasoning Failure, UNVERIFIED 유지).
6. Reward Signal Audit: §E. 7. 잔여 위험: §F.
8. **Evolution GO/HOLD/STOP: HOLD 유지** — 본 단계는 보존 계약·신호 검증
   소관이며, 잔여 HOLD 사유 불변(① δ n≥6, ② 분할 해동, ③ mapping 왜곡 하의
   주-reward 자격). STOP 아님: 격리 계약 실동작 + 25번 오류의 자체 정정
   완료.

## 제한사항 준수

신규 모델 호출 **0**, Reader Pipeline 실행 **0**, Same-paper QA 재실행 0,
RRSI Evolution 0, Final Holdout 소비 0, Official Scorer 수정 0, 기존 Artifact
삭제·변경 0, ai_papers 운영 상태 변경 0, 신규 worktree 0.
