---
doc_id: poc-rrsi-33-judge-pilot-execution
title: Limited Semantic Judge Pilot Execution (halted — token budget exceeded)
status: report
updated: 2026-10-29
---

# Limited Semantic Judge Pilot — Execution Report

**Summary.** Pilot을 실행하였으나 **1호출차 token 상한 초과로 중단** —
실제 소비 **18,004 tokens**(상한 6,000): Original+Perturbed note 전문
2건(~39k chars×2)의 입력만으로 상한 초과. **Fixture 판정 0건**(g3 응답은
수신되었으나 halt 순서 버그로 유실), **Gold Agreement 미측정**. 실행 중
실패 3유형 기록: ① 수동 예약 행 3건이 봉인 ledger 검증 오염(아카이브
보존·무효) ② 격리 계약의 재사용 거부 2건(정상 동작) ③ halt 전 기록
버그로 응답 유실. 자동 재시도·재실행 0, Gold/원본/Scorer/Split 무변경.
판정: **HOLD 유지** — 재개에는 Owner의 상한 재결정 또는 입력 축소 설계가
필요. **이번 결과를 Semantic Reward 일반화 성능으로 해석하지 않는다.**

---

## 1. 실행 계약 준수

| 항목 | 값 |
|---|---|
| Permit | `semjudge-pilot-r6e` (issued by owner-directive; sha256 `fbd00644…`) — 7조건 verify PASS 후 진입 |
| Model/Endpoint | `qwen38-27b-fp8-vllm-tp1-ktl02` @ `127.0.0.1:8004` — /v1/models로 승인 profile 일치 확인 |
| Blind prompt | r6 봉인 manifest의 `user_prompt_sha256`와 재구축 digest 일치 검증 PASS (evidence integrity) |
| 동시성/재시도 | 1 / retry 0 |

## 2. Fixture별 결과 — 0건

| Fixture | 호출 | 판정 | Agreement |
|---|---|---|---|
| g3-1802-result | 1회 (응답 수신) | **유실** (halt 전 기록 버그) | 미측정 |
| g4-1802-numeric | 미실행 | — | 미측정 |
| g7-1901-method | 미실행 | — | 미측정 |

## 3. 실제 비용

- **Model calls(서버 도달): 1** — tokens **18,004**(note 전문 입력 2건;
  예산 6,000 초과 → 즉시 중단). Wall: <1분.
- 서버 미도달 시도 3회(r6·r6b·r6c — env binding 오류로 네트워크 전 차단,
  토큰 0).

## 4. 실패 유형 및 근거 품질

| 유형 | 내용 | 처리 |
|---|---|---|
| **Ledger 오염** | runner의 수동 예약 행 3건(schema 불일치)이 frozen ledger 검증 실패 유발 — 서버 도달 전 차단 | 무효 행 아카이브(`…invalid-attempt-r6b-r6c.jsonl`, 보존) + 새 ledger로 재개; 예약은 이후 frozen machinery(`reserve_model_call_from_environment`) 경유 |
| **격리 거부 2건** | `RAW_PACKET_COLLISION`(r6b·r6c), `RUN_DIR_ALREADY_USED`(r6d) — 중단된 invocation의 run dir 재사용 차단 | 계약의 정상 fail-closed 동작; 신규 invocation(r6e)으로 진행 |
| **Halt 전 기록 버그** | token 상한 체크가 패킷 기록보다 앞서, 수신된 g3 응답 유실 | 버그 등록; 재개 전 기록-후-halt 순서로 수정 필요 |
| **근거 품질** | 판정 산물이 없어 측정 불가 — g7 단어존재/방법론 분류도 미측정 | 재개 필요 |

## 5. 구조적 원인 — 상한 vs 입력 크기

6,000-token 상한은 note **전문 2건 비교**(≈18k tokens 입력)와 **구조적으로
양립 불가**. 재개 옵션: (a) 상한 재결정(≥20,000 tokens) — Owner 승인 필요,
(b) **입력 축소** — 평가 대상 문장 주변 blind 발췌 제공(전문 대신, blind
유지) — 이 경우 token 수십 배 절감·계약(B) 유지. 권고: (b).

## 6. 다음 실험 필요성

1. 기록-후-halt 버그 수정 + (b) 입력 축소 설계 → 별도 지시로 재실행.
2. g7 판정 시 방법론 손실 분류(기존 계약) 그대로 적용.
3. n≥6 반복·δ 진입 재평가는 Pilot 3건 완료 후에만.

## 제한사항 준수

Gold·원본 Reader Note·Scorer·Split(freeze `849d1431…`)·Final Holdout 무변경
및 미실행, δ 0, RRSI Evolution 0, 자동 재시도/재실행 0, main 브랜치 작업,
신규 worktree 0.
