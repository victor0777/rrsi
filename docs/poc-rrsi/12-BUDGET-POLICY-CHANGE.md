---
doc_id: poc-rrsi-12-budget-policy-change
title: Budget Policy Change (token hard ceiling abolished) — applied to R0-b Calibration
status: report
updated: 2026-10-23
---

# Budget Policy Change — R0-b Calibration 적용

**Summary.** 지시에 따라 Token Hard Ceiling 정책을 폐지하고, 토큰 사용량을 실행
차단 기준이 아닌 계측·최적화 지표로 전환했다. Ledger(`call_budget`)는 유지하되
token ceiling 차단만 비활성화했다. 기계 검증 가능한 형태로 `poc/budget_policy.py`
+ 테스트 8건을 추가했다(전체 31 tests PASS, 코어 무수정 유지).

**실행 결과(정직 보고): R0-b는 여전히 실행되지 않았다 — model call 0, token 0,
GPU 0, 실측치 없음.** 정책 변경은 §2 1-trial 실측 검사에서 발생하던 토큰 충돌을
해소하는 것(§8 해소 조건 2의 "token 상한 개정" 분기)이지만, 결정적 차단인
**gold 논문 소스 부재(13/13)** 는 데이터 준비 문제로서 본 정책 변경으로 해소되지
않는다(§3, §4). 실측치 없이 R1 전체 예산을 수치로 재산정하는 것은 불가하며,
§5는 조건부 산출식만 확정한다.

---

## 1. 변경 정책 (사전 등록)

| 항목 | 값 | 비고 |
|---|---|---|
| Token ceiling | **없음** | 입력·출력·총량은 계속 기록(계측) |
| Paper-trials | 1 (초기 Calibration) | reader trial 1회 |
| Model calls | 최대 50 | 초과 fail-closed |
| Wall-clock time | 최대 30분 | 초과 fail-closed |
| GPU-hours | 최대 0.5 | 초과 fail-closed |
| 자동 Retry | 0회 | 첫 실패는 최종이며 보고 대상 |
| 동시 실행 | 1개 | 병렬도 상향 전제 없음 |
| 외부 유료 API | 별도 비용 상한 필수 | 미등록 시 정책 자체 fail-closed |

**측정 분리(지시 사항).** GPU-hours와 wall-clock은 별개 필드로 기록하며 서로에게서
도출하지 않는다. 다중 GPU 사용 시 GPU-hours는 **합산**한다(예: GPU 2개 × 20분 =
0.667 GPU-h, wall-clock 20분 — max 아님, 합산). `gpu_hours_sum()`이 이 규약을
검증 가능한 형태로 고정한다.

**Fail-closed 유지(지시 사항 9).** wall-clock·model calls·GPU-hours 초과는
`BudgetExceeded`로 안전 정지(진행 무효). 단, 토큰 초과는 더 이상 정지 사유가
아니며, 토큰 계측 기록 부재는 오히려 계약 위반으로 fail-closed한다.

## 2. Ledger 변경 (코어 무수정)

- `call_budget` ledger 자체는 **무수정 유지**. 변경은 R0-b 운영 계층의 차단 구성만:
  `blocking_disabled = [token_ceiling]`, `blocking_kept = [wall_clock_minutes,
  model_calls, gpu_hours]`.
- per-call 레코드 스키마(R1.1 §5.6)는 그대로 — token·latency·GPU time 기록 의무 유지.
- RRSI 알고리즘 코어(`rrsi/` 15파일) 무수정: CoreSignature + 전체 테스트 PASS.
  예산 정책은 코어가 아닌 freeze/운영 문서의 매개변수 선택이다(R1.1 §8.1 #9의
  "매개변수 선택 vs 코어" 구분과 동일).

## 3. R0-b 실행 상태 — 여전히 미실행 (차단 원인 갱신)

11번 보고(§2)의 차단 2건 중 **1건 해소, 1건 잔존**:

| 차단 | 상태 |
|---|---|
| 사전 사용량 검사 충돌 (추정 2.4–4.8M vs ceiling 3M) | **해소** — token ceiling 폐지로 1-trial 시작의 토큰 근거 불필요. `check_prestart`는 이제 blocking 축만 검사 (테스트 `test_prestart_token_estimate_never_blocks`) |
| Gold 논문 소스 부재 13/13 (결정적) | **잔존** — `source_ref: 01_extraction_bundle/reading.md` 입력이 로컬에 없음. 본 저장소에는 `ai_papers_research` 파이프라인·data/raw·data/processed·docs/eval이 아예 없어 소스 취득(arxiv fetch + extraction)은 승인이 필요한 별도 작업 |

**해소 조건 갱신(11번 보고 §8 대비):**

1. Gold 논문 소스 취득 승인 + dataset hash 등록 — **잔존** (조건 1 그대로).
2. 1-trial calibration으로 실측 단위비용 확보 **또는 token 상한 개정** — token 개정
   분기는 이행됨. 단, R1 확정에는 "실측" 분기가 필요하므로 조건 1이 해소되면
   1-trial을 실행해 실측을 채워야 함.
3. Freeze 문서 기재 사항: GPU time 기록 주체(§7 (d)) — **부분 해소**: GPU-hours는
   본 정책에 따라 GPU별 accelerator 점유 시간의 합산으로 정의(주체는 측정 장치의
   per-GPU 계측). dataset hash 다중 파일 병합 해시 계산식(§7 (e))과 모델·revision
   고정 — **잔존**.

## 4. 실측 결과 — 없음

R0-b 미실행으로 model call·token·latency·GPU·wall-clock 실측치는 전부 0 또는
부재다. 품질 점수·반복 변동성·δ도 미측정. 수치를 추정으로 대체해 보고하지 않는다.

## 5. RRSI 전체 실험 예산 재산정 — 조건부 산출식 확정

실측 부재로 R1 상한(R1.1 §5.2)의 **수치 재산정은 보류**하되, 1-trial 실측이
확보되는 즉시 적용하는 산출식을 사전 등록한다(상한은 실측 단위비용 u의 비율로
선행 선언 — R1.1 §5.2 원칙 유지):

| 항목 | 산출식 | 비고 |
|---|---|---|
| 단위비용 u | 1-trial 실측(calls, tokens, GPU-min, wall-clock) | R1.1 §5.1의 추정 12–20 calls, 300–600k tokens를 대체 |
| R0-b 후속(8 trials) | 8 × u | 산출식은 R1.1 §5.1 그대로 |
| R1 전체(≈248 trials) | 248 × u, calls = 248 × u_calls | tokens는 계측만, 차단 없음 |
| calls 상한 | 248 × u_calls × 1.2 | 비율 선행 선언 |
| GPU-h 상한 | 248 × u_gpu × 1.2 | 다중 GPU 합산 규약 적용 |
| wall-clock | 라운드 종단 상한 유지, 병렬도 결정 시 재산정 | GPU-h와 분리 보고 |

**tokens 상한 폐지의 의미.** R1.1 §5.2의 "tokens 100M 즉시 중단"은 R1 적용 시에도
폐지 대상이다. 비용 폭주에 대한 실질 안전장치는 (a) model calls 상한(비용 상관이
가장 강한 결정론적 축), (b) 유료 API 별도 비용 상한, (c) GPU-hours·wall-clock
fail-closed로 대체된다. 이 구성은 11번 보고 §2의 문제(추정 불확실성이 token
축에서만 시작을 막는 구조)를 제거한다.

## 6. 본 지시 범위 준수 확인

- RRSI 알고리즘 코어 무수정: **예** (31 tests, CoreSignature).
- Ledger 유지, token 차단만 비활성화: **예** (`LEDGER` 검증 테스트).
- wall-clock·calls·GPU fail-closed 유지: **예** (테스트 3건).
- 자동 retry 0·동시 실행 1·유료 API 상한 강제: **예** (테스트 3건).
- R0-b 실측 결과 보고: **해당 없음 — 미실행, 실측치 없음** (본 보고 §4).

**Committed artifacts**: `poc/budget_policy.py`, `poc/tests/test_budget_policy.py`,
본 문서.
