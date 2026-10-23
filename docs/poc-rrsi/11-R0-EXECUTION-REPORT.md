---
doc_id: poc-rrsi-11-r0-execution-report
title: R0 Execution Report (R0-a full; R0-b not executed — HOLD)
status: report
updated: 2026-10-20
---

# R0 Execution Report

**Summary.** R0-a PASS (23 tests). R0-b **NOT EXECUTED**: the paper-trial input
does not exist locally for any gold paper (13/13 sources missing), and the
pre-start usage check conflicts with the approved ceiling pair. Recommendation:
**HOLD** for R0-b pending three unblock conditions (§7, §8).

---

## 1. R0-a 검증 결과와 실패 항목

| 검증 항목 | 방법 | 결과 |
|---|---|---|
| 기존 코어 무수정 | `git diff be50316 -- rrsi/` 공백 + core 15파일 SHA-256 서명 기록(`poc/r0a_checks.py::CoreSignature`) + upstream 테스트 무수정 통과 | **PASS** |
| 알고리즘 호출 경로 | R1.1 §8.1의 11개 매핑을 vendored 함수 존재·시그니처와 대조(정적) | **PASS** (11/11) |
| U1 변경 범위 격리 | freeze glob 테이블 + `scope_violations` 테스트(U1 허용 2경로, frozen 침범 4경로 거부) | **PASS** |
| State Machine 전이·거부 | 전이 테이블 + 법정 경로(EVALUATED→…→CANONICAL) + 거부 4경로(APPROVAL_WITHOUT_HOLDOUT·ILLEGAL·NOOP·NON_MONOTONIC) 테스트 | **PASS** (검증 중 결함 1건 발견·수정 — §7) |
| Holdout 접근 차단·누출 | holdout 논문 13개 id denylist가 diff 텍스트를 검사하는 테스트(포함 diff 거부 확인) + R1.1 §3.2 proposer 격리 규약 재확인 | **PASS** (논리 검증; 데이터 부재로 실데이터 테스트 불가는 §7 (d)) |
| Ledger fail-closed | `ai_papers_research.llm.call_budget` 실제 호출: 무결 바인딩 → `ModelCallBudgetContractError`(네트워크 이전); 유효 바인딩 → 예약 성공 | **PASS** (로컬 기계 한정 — §5) |

실패 항목: **없음**. R0-a 조건 충족으로 R0-b 진입 자격은 확보. 단, §2의 사전 검사
결과에 따라 trial 시작은 보류했다.

## 2. R0-b trial별 사용량 — 미실행

R0-b는 시작되지 않았다(model call 0, token 0, GPU 0). 사전 검사가 지시("실행 전에
예상 사용량으로 상한 초과 가능성을 확인하고, 초과가 예상되는 trial은 시작하지 않는다")의
두 요건을 충족하지 못했다:

1. **trial 입력 부재 (결정적)**. 13개 gold 논문 전부 소스 부재 —
   `data/raw/`는 관련 없는 파일 2개뿐, `data/processed/`는 공 디렉터.
   GT의 `source_ref: 01_extraction_bundle/reading.md`가 가리키는 입력이 로컬에 없어
   reader trial 1회도 실행 불가. 소스 확보는 arxiv 취득 + extraction 실행을 수반하며
   이는 본 승인 범위 밖("운영 설정 변경 및 신규 파이프라인 실행 불가").
2. **사전 사용량 검사 충돌**. 추정 단위비용(300–600k tokens/trial) × 8 trials =
   2.4–4.8M vs token ceiling 3M — 중·상한 추정이 ceiling 초과. 실측 없이 8 trial의
   시작을 정당화할 수 없고, 초과 예상 trial은 시작 금지 규약에 따라 전량 보류.

## 3. 품질 점수 및 반복 변동성 — 미측정

trial 미실행으로 실측 없음. 채점 근거는 실재 확인: `reader_note/quality.py`
(`build_reader_note_coverage`, `build_reader_note_quality`),
`reader-note-coverage/quality/provenance-quality-report` 스키마, gold GT 항목
(논문당 6개, category key_concept/mechanism/artifact/claim_evidence).

## 4. δ 산정 가능 여부와 불확실성 — 불가(데이터) / 설계 확정

δ 산정 불가: baseline 반복 측정이 없음. **불확실성 구조는 §3 지시대로 사전 등록**:

- **96 항목을 독립 표본으로 취급하지 않음** — 판정은 논문 내 상관. 추정 단위는 논문.
- **Cluster bootstrap (논문 단위)**: 논문 8개를 복원 추출(B=1,000), S 재계산,
  null ΔS의 cluster sd로 δ = z·sd. 이분형 항목에서 paper-trial 16개는
  논문 cluster 8개로 축약 → 실효 표본은 8.
- **Paired difference와 Welch의 조건 구분**: paired per-task diff는 동일 논문 집합을
  양팔이 쓸 때(논문 내 상관 ρ>0) 유효 — paired sd 사용. 논문 집합이 분리되거나
  패어링이 깨진 경우 Welch(비쌍)로 전환. 선택은 freeze 문서에 사전 등록.
- **Baseline 반복 변동성 ↔ 논문 간 변동성 분리**: 반복 변동성(within-paper,
  trial·seed·서비스 상태)은 δ의 근거, 논문 간 변동성(between-paper)은 cluster sd에
  반영. ICC 보고; 반복 sd만으로 δ를 잡는 것을 금지.
- **D-arm false-accept 판정 기준**: D-arm은 무처치 재평가만 수행. false-accept =
  D-arm null 쌍이 floor+cost를 통과하는 사건. 기대치 ≤ 2.5%(z=2). R null 쌍 중
  관측률 > 10% → δ 캘리브레이션 기각(밴드 과소폭가), z 상향 또는 trial 증가.

## 5. Ledger와 실제 사용량 정합성 — 기계 검증 PASS, 운영 검증 미실시

- fail-closed: 불완전 바인딩에서 네트워크 이전 `ModelCallBudgetContractError` (실제 실행).
- 유효 바인딩에서 call_id 예약 성공 (실제 실행).
- model ID·revision·prompt hash·dataset hash·run ID·token·latency·GPU time을 기록하는
  per-call 레코드 스키마는 R1.1 §5.6으로 사전 등록되어 있으며, R0-b 실행 시
  `provider_usage` telemetry(`extract_openai_compatible_response_observations`)와
  ledger를 대조하는 정합 감사가 종료 보고의 구성 요소다. **모델 호출이 없어 운영
  정합성은 미검증** — 이는 R0-b 종료 시점에만 확정 가능하다.

## 6. R0-b 및 R1 예상 비용 재산정

| 항목 | R1.1 추정 | 재산정(차이) |
|---|---|---|
| R0-b (8 trials) | 2.4–4.8M tokens | **+ 소스 취득 8편**: arxiv fetch + extraction ≈ +8 runs(취득 실행이 승인되면 실측) |
| R1 전체 (≈248 paper-trials) | 75–150M tokens, 3.0–5.0k calls, 8–21 GPU-h | 유지 — 재산정 근거: trial 산출식은 R1.1 §5.1 그대로, R0-b 정체는 비용이 아니라 데이터 준비 문제 |
| 지연시간 | 라운드 종단 8 h 상한 | 유지 — 병렬도 상향 전제 |

## 7. 발견된 결함과 수정 필요사항

| # | 결함 | 처리 |
|---|---|---|
| (a) | State Machine에서 승인-선-홀드아웃 순서 규칙이 전이 테이블 검사보다 뒤에 있어, 특정 경로에서 ILLEGAL로 가려져 순서 규칙 자체가 검증되지 않음 | **수정 완료**(`r0a_checks.assert_transition` 검사 순서 재배치) + 전용 테스트 추가. 검증 과정에서 발견된 실 결함 |
| (b) | R1 비용 추정의 trial 산출 오류(20–28 runs) | R1.1 §5.1에서 정정 완료; 본 보고 §6 재확인 |
| (c) | **Gold 논문 소스 부재 (13/13)** — R0-b의 하드 차단 | 해소 필요: R1 종료 후 취득(E1 규약) 또는 취득 승인 별도 요청. 취득 시 논문·extraction 산출의 dataset hash 등록 |
| (d) | GPU time 기록 주체 미확정 — pipeline이 기록하는 것은 host측 소요이며 provider GPU-sec 아님 | 결정 필요: local GLM bounded run(provider 측 정합) 또는 provider telemetry 소비. R0-b 전 freeze 문서에 명시 |
| (e) | trial 입력 hash 규약(`dataset hash`)이 다중 파일(extraction bundle) 대응 필요 — 단일 해시의 계산 방식(파일 목록 정렬 + 병합 해시) 미확정 | R0-b 전 확정 (schema에 사전 등록) |

## 8. 권고: HOLD

R0-a는 PASS이나 R0-b는 승인 범위 내에서 실행 불가(데이터 차단). **GO/HOLD/STOP 중
HOLD**를 권고한다. STOP이 아닌 이유: 안전 위반이 아니라 준비도 문제이며, 실행
장치(정적 검증 테스트 23건, 전이 테이블, denylist, ledger 검증)는 완비되어 있다.

**해소 조건 (3개, 충족 시 R0-b 재요청):**
1. Gold 논문 소스 취득 방법 승인(어느 분할 논문을 먼저 확보할지 포함) + dataset hash 등록.
2. 1-trial calibration으로 실측 단위비용 확보 → `per-trial ≤ 375k` 확인 또는 token 상한 개정.
3. §7 (d)(e)의 freeze 문서 기재 사항 확정(GPU time 주체, dataset hash 계산식, 모델·revision 고정).

**본 승인 범위 준수 확인**: 후보 진화 0, 프롬프트 자동 변경 0, B/C 비교군 0,
Final Holdout 소비 0(접촉 로그 공), 운영 설정 변경 0, 자동 승격 0.
R0-b가 시작되지 않은 것은 승인 범위 내 안전 규약(§2 지시)의 이행이다.

**Committed artifacts**: `poc/r0a_checks.py`, `poc/tests/test_r0a.py` (R0-a 검증 코드·테스트), 본 보고.
