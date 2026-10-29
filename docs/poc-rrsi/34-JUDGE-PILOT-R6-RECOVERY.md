---
doc_id: poc-rrsi-34-judge-pilot-r6-recovery
title: Evidence-Bounded Semantic Judge Pilot Recovery (complete — within budget)
status: report
updated: 2026-10-29
---

# R6 Recovery — Evidence-Bounded Semantic Judge Pilot — Execution Report

**Summary.** 중단된 `semjudge-pilot-r6e`(commit 1197d4d, 18,004 tokens,
FAILED 봉인)를 **사후 생성 없이 그대로 수용**하고, §A의 Evidence-bounded
입력으로 신규 Invocation `semjudge-r6g-recovery`로 재실행 — **완료**.
3 fixture 호출, 실제 소비 **5,147 / 6,000 tokens**(입력 3,148 + 출력 1,999),
wall **29.2s / 300s**, retry 0, 동시성 1. Gold Agreement: g3 **Agreement**,
g7 **Agreement**, g4 **미판정** — 출력 상한(800 tok)에서 JSON이 잘려
PARSE_FAILURE(재시도 금지, 그대로 기록). 중간 시도 `semjudge-r6f-recovery`
는 frozen call path가 모델 호출당 자체 ordinal을 예약함이 확인되어
ceiling 3으로는 1 fixture만 허용됨 — **retired**(g3 응답 수신·봉인,
판정하지 않음, 재사용 없음). **이번 결과를 Semantic Reward 일반화
성능으로 일반화하지 않는다.**

---

## 1. 실행 계약 준수

| 항목 | 값 |
|---|---|
| 수용 | r6e halt 그대로 — RUN_DIR 봉인 유지, Agreement 등 사후 생성 0 |
| Permit | `semjudge-r6g-recovery` (issuer: owner-directive; 발급 ledger에 `register_permit` 기록) |
| Ledger | 공식 예약 API만 사용(`reserve_model_call_from_environment`); 수동 행 삽입 0 |
| Model/Endpoint | `qwen38-27b-fp8-vllm-tp1-ktl02` @ `127.0.0.1:8004` — permit 7조건 verify PASS |
| Ceiling | 6 ordinals (모델 호출당 2 ordinal: runner 예약 + call path 자체 예약) — 모델 호출 실제 3회 |
| 재시도/동시성 | 0 / 1 — 순차 실행 |

## 2. §A Evidence-bounded 입력

동일 발췌 정책을 Original과 Perturbed에 적용(단락 단위 regex; g7은 문서
순서 기준 최초 10단락 cap). Gold Expected Direction과 A/B 정답 역할은
Judge 입력에서 제외. 발췌 정책·원문 위치·선택/누락 구간·digest 전부
`poc/runs/semantic-judge-r6g-recovery/inputs/input-*.json`에 기록.

## 3. §B 사전 토큰 검증 — PASS

served tokenizer `/tokenize`로 전체 요청 계측(System + Judge Contract +
Source Evidence + A/B 입력 + tool schema 96 + chat template margin 64 +
출력 예약 800). 호출 전 합계 **예약 5,882 ≤ 6,000** → 호출 진행. 계측
실패 시 fail-closed였음(코드 경로 존재, 미발동).

## 4. Fixture별 결과

| Fixture | 입력 tok | 출력 tok | 비용 tok | 예약 tok | Judge 판정 | Gold Agreement |
|---|---|---|---|---|---|---|
| g3-1802-result | 809 | 623 | 1,432 | 1,752 | B(15,800) lower than A(15,733) | **Agreement** |
| g4-1802-numeric | 1,043 | 800(=상한, 잘림) | 1,843 | 1,986 | 미판정 — PARSE_FAILURE | 미측정 |
| g7-1901-method | 1,296 | 576 | 1,872 | 2,239 | B(P5 방법론 누락) lower | **Agreement** |

Evidence Reference: g3 = 원문 char 15,733 앵커 오프셋(±300자); g4 = "10K
user-generated…" 문장; g7 = "extract the keywords … TextRank" 단락 1,100자.
raw 응답은 수신 즉시 `semjudge-r6g-recovery/raw/resp-*.json`에 영속화 후
예산 판정 → seal-run-dir seal 검증 PASS.

## 5. g7 발췌 누락 분석

`g7_methodological_loss_check` = **METHODOLOGICAL**(flag False → 요구 충족).
판정 basis가 방법론 단계 수준의 정보 손실을 논증 — 발췌 정책이 "방법론
재구성 가능성" 평가에 필요한 정보를 누락하지 않음
(`excerpt_caused_info_loss: false`). 잔존 설명은 perturbed 측 10단락 cap
안에서 일부만 포함되나, 판정에 영향을 주는 잔존 단락은 포함됨.

## 6. 중간 시도 `semjudge-r6f-recovery` (retired)

첫 발급(ceiling 3)은 각 모델 호출이 runner 예약과 call path 자체 예약으로
2 ordinal을 소비함을 사전에 몰랐던 발급 측 계량 오류. g3 예약+호출 성공,
g4 예약은 ordinal 4에서 거부 → HALTED. g3 응답은 수신 즉시 raw 영속화·
seal되었으나 **판정하지 않음**; 이 Invocation/RUN_DIR은 재사용하지 않음.

## 7. 실제 비용 및 제한사항

| 항목 | 값 |
|---|---|
| 총 토큰 | **5,147 / 6,000** (within budget) |
| Wall clock | 29.2s / 300s |
| Gold Agreement | g3 Agreement, g7 Agreement, g4 미판정(잘림) |

Source / Reader Note / Gold / Official Scorer / Final Holdout / δ
Calibration / Evolution / 신규 Worktree: **무변경**. 자동 재시도 0.
판정: **HOLD 유지** — g4 잘림으로 Fixture 완판은 아니며, 상한 확대 없이
해결 불가한 항목(출력 길이)은 Owner 재결정 필요. **두 Agreement를
Semantic Reward 성능 입증으로 일반화하지 않는다.**
