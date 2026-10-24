---
doc_id: poc-rrsi-14-r0b2-repeat-calibration-report
title: R0-b2 Repeat Calibration Report — telemetry fix, split freeze, baseline ×3 (executed)
status: report
updated: 2026-10-24
---

# R0-b2 Repeat Calibration Report

**Summary.** Token telemetry 결함 수정(수집·정합 fail-closed PASS), dataset split
충돌 해소(freeze `849d1431…`), GPU-hours 정책 보완(측정↔상계 분리) 후 ImagiDrive
baseline 3회 추가 실행 완료. **δ ≈ 0.19 (z=2, fine-grained 점수)**. 판정:
**GO**(RRSI Evolution PoC), 단 δ 불확실성(n=4) 해소를 위한 calibration 반복
선행 권고(§7).

---

## 1. Token Telemetry 결함 해결 — PASS (결함 1건 잔존 §6-c)

| 지시 항목 | 결과 |
|---|---|
| vLLM usage 수집 | `AI_PAPERS_PROCESS_TELEMETRY_EVENTS` 싱크 바인딩으로 provider-usage telemetry 수집. `token_usage.availability_status=reported` (per-call prompt/completion/total) |
| 전 호출 경로 조사 | reader chain 3경로: analyze/plan(writer 모델), write chunk(`--polish-model`, r0b1 404 근원), polish(polish 모델). polish fallback은 `--no-polish-fallback`으로 제외, vision·embedding은 token-mode·skip로 미사용 |
| 예약/전송/성공/실패 구분 | ledger `reserved`(네트워크 전)·`rejected`(권한 없음) + telemetry `terminal`(네트워크 후)에 `status`·`http_status`·usage 동반. `poc/r0b2_audit.py`가 per-call 정합 대조 |
| fail-closed 검증 | (1) telemetry 싱크 unwritable → preflight 차단, (2) reserved-without-terminal / terminal-without-usage → audit exit 1. 실측: 3개 성공 trial에서 0 위반 |
| 404 근원·preflight 이동 | r0b1 404 = writer·polish 경로의 기본값 모델 `qwen-coder`가 서버 미등록(vLLM은 미등록 모델에 404 반환). `poc/r0b2_preflight.py`가 writer/polish/vision/embedding 4경로 모델 등록·싱크 기록성·ledger 바인딩을 **실행 전** 검증 — r0b2에서 BLOCKED 0건 |
| RRSI 코어 | 무수정 (CoreSignature 유지) |

**실측 정합**(성공 trial): ledger reserved 25 = telemetry terminals 25, usage reported 25/25, latency mean 18.0–18.6s.

## 2. Dataset Split 충돌 해결 — PASS (freeze)

- 근거 충돌: R1 설계 Evolve(agent-memory 중심 6편) ↔ R0-a denylist(agent-memory 10편 전부). 13 id가 충돌 원인.
- 해소 규약(`poc/r0b2_split.py`, 지시 준수): denylist를 **권위·무변경**으로 유지;
  충돌 미해소 논문은 `BLOCKED_CONFLICTED`로 평가 금지; Validation·Final Holdout은
  **frozen empty**(소스 취득 + 무충돌 재분할 승인 전까지). 중복 역할 제거 검증
  (uniqueness·disjointness·denylist-leak 3건 PASS).
- **Split manifest SHA-256: `849d1431daf92c980cee6b7a190194718ae8928d34810838c12d528b65825c42`**
  (schema `rrsi-split-manifest/v0.1`, base R0-a `4e0c1e5`).
- 분할 상태: **Evolve = {2508.11428, 2511.13079}** (denylist-safe e2e 쌍, 버전은
  취득 시 기록 — 11428은 v2 확정), **Validation = ∅, Final Holdout = ∅**,
  **BLOCKED_CONFLICTED = 13**.

## 3. GPU-hours 정책 보완 — 등록 완료

`poc/budget_policy.py` 보완: `gpu_hours_upper_bound`(wall-clock × 1 GPU 귀속,
측정값으로 보고 금지)와 `gpu_hours_measured`(per-GPU 계측 바인딩 시만 산출,
공유 서버에서는 None)를 별개 필드로 분리. GPU-hours는 계측·보고 전용. 실행
차단은 **wall-clock·model calls 중심**, GPU-hours 상계 상한은 별도 fail-closed
유지(측정값과 상계값 동일 취급 금지).

## 4. R0-b2 반복 실행 결과

| Trial | calls | status | coverage | core | open-dep | term-hit S |
|---|---|---|---|---|---|---|
| r0b1-baseline (참조) | 29 | PASS | 1.0 | 1.0 | 1.0 | 0.783 |
| r0b2-repeat-2 | 25 | PASS | 1.0 | 1.0 | 1.0 | 0.783 |
| r0b2-repeat-3b | 25 | PASS | 1.0 | 1.0 | 1.0 | 0.933 |
| r0b2-repeat-4b | 25 | PASS | 1.0 | 1.0 | **0.0**(부분) | 0.700 |

- 중단 이력(정직 기록): r0b2-repeat-3은 plan 품질 게이트 거부("Incomplete Reader
  Note plan: incomplete_section_strategy_fields")로 fail-fast — 자동 retry 0 준수,
  신규 invocation(r0b2-repeat-3b)으로 재시작. r0b2-repeat-4은 실행 환경 종료로
  6 calls 후 중단, r0b2-repeat-4b로 신규 실행. 소비 호출: repeat-3 3건, repeat-4
  6건은 상한 내 계상(ledger 누적 84/120).
- 예산 준수: calls 84/120, wall-clock 누적 창(중단·대기 포함) 80.5분/120분,
  GPU-hours 상계 0.363/2.0, 동시 실행 1.

## 5. 평가 분석 (지시 §5)

1. **품질 변동성**: coarse 축(coverage/core)은 4 trial 모두 1.0 — 반복 불변.
   open-dependency retention만 변동(1,1,1,0). fine-grained S(mean term-hit
   ratio): 0.783, 0.783, 0.933, 0.700 → mean 0.80, sd 0.097.
2. **의미적 변동성**: 출력 길이 24.9–30.7k chars, 표제 수 28–40. 4-gram Jaccard
   쌍간 0.097–0.129 — 어휘 표면은 실행마다 크게 다르나 골격(섹션 구조)은 보존.
   → 판독에는 구조 안정성과 표면 자유도의 분리가 실제로 존재.
3. **Ceiling effect**: coverage·core 축은 이미 상한(1.0) — 이 축으로는 후보
   변별 불가. 변별력은 open-dependency retention과 term-hit ratio에만 존재.
   Gold 점수의 상한 효과가 실측 확인됨.
4. **호출·토큰 분포**: 성공 trial 호출 수 완전 일관(25/25/25; r0b1만 29 — 폴리시
   경로 차이). 토큰: 입력 72.9–73.1k, 출력 28.2–29.0k per trial — 입력 우세
   (72%), R1.1 §5.1 추정(300–600k)의 **약 1/8 수준**(실측 ≈101k tokens/trial).
   latency mean 18s/call.
5. **GPU-hours 상계 ↔ wall-clock**: 상계 = wall-span × 1GPU (21.8분 스팬 합 →
   0.363 GPU-h). 공유 서버로 실측 격리 불가 — 상계는 완전 선형 함수로 wall-clock
   정보 이상을 추가하지 않음(계측 한계 등록).
6. **δ 추정 가능**: coarse 점수 기준 δ = 2·sd(1,1,1,0.667) ≈ 0.33는 상한효과로
   과대. 사전 등록 형식(δ = z·sd(null ΔS))을 fine-grained S에 적용:
   **δ = 2 × 0.097 ≈ 0.19 (z=2)**. 단 n=4 (df=3) — sd의 90% CI ≈ [0.057, 0.40]
   → δ 구간 [0.11, 0.80]. **δ ≈ 0.19는 잠정값**이며, D-arm false-accept 기준
   (기대 ≤2.5%) 검증은 반복 확대 후 유효.
7. **변별력**: 후보 승격 판정은 ΔS > δ ≈ 0.19 — term-hit 19포인트 개선 요구는
   보수적. 반대로 coarse 축만 쓰면 δ가 포화로 무의미. 권고: 다목적 S는
   fine-grained 항(term-hit ratio, source-id hit) 중심으로 산출(§3.3의 L1
   측정 근거에 정합).

## 6. 발견 결함/한계

| # | 내용 | 처리 |
|---|---|---|
| (a) | split freeze로 Validation·Holdout 공측 — 승격 주기 내 재분할 금지(R1 §3.2 #5)와 긴장 | 소스 취득 후 무충돌 분할 승인을 별도 요청으로 등록 |
| (b) | plan 품질 게이트 거부 1건(비결정) — trial 낭비 요인 | fail-fast 후 신규 invocation 처리; 게이트 거부율 계측을 다음 trial부터 기록 |
| (c) | r0b1(참조 trial) 토큰 결측이므로 토큰 분포 분석은 r0b2 3 trial 근거 | r0b1 재실행 없이 참조로 유지, 토큰 상관은 n=3 |
| (d) | 공유 vLLM 실측 GPU-h 불가 | 상계 필드 분리 등록 완료(§3) |

## 7. RRSI Evolution PoC 판단 — **GO**

- 지시 준수: RRSI 후보 진화 0, 프롬프트 자동 변경 0, B/C 비교군 0, Final Holdout
  소비 0, 운영 승격 0. RRSI 코어·ai_papers canonical artifact 무수정.
- **GO**: telemetry·split·GPU 정책 3축 PASS, 반복 실측으로 δ 캘리브레이션 가능
  상태. 다음 단계(순서): ① δ 불확실성 축소를 위한 baseline repeat 추가(n≥6) —
  동일 상한 체계로 재산정 후 승인 요청, ② Evolve 8편 소스 취득(무충돌 분할
  승인 병행), ③ RRSI Evolution PoC(후보 1개, U1 프롬프트) 시작.

**Committed artifacts**: `poc/r0b2_preflight.py`, `poc/r0b2_audit.py`,
`poc/r0b2_split.py`, `poc/budget_policy.py`(보완), 본 보고. Run 산출물은
`poc/runs/r0b2/` 로컬 미추적(`.gitignore: runs/` 규약).
