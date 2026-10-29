---
doc_id: poc-rrsi-32-judge-pilot-admission
title: Limited Semantic Judge Pilot Admission (prepared, 0 model calls)
status: report
updated: 2026-10-29
---

# Limited Semantic Judge Pilot — Admission Report

**Summary.** 3건 Gold 후보의 **Fixture별 독립 승인 기록** 생성(`rrsi-fixture-
approval/v0.1` — fixture_id·fixture_digest(per-fixture content digest)·
approved_scope; bundle digest는 context-only로 명시, 개별 승인으로 해석
금지). **Blind Judge 계약 구현**(`poc/semantic_pilot.py`) — Original/
Perturbed를 seed=42 고정 무작위 순서로 제공, gold·기대 방향 미노출(게이트
검증 PASS), 출력 5요소(개별 판정·차원 근거·Evidence Reference·상대 판단·
Abstention+사유) 계약화, post-hoc Gold 대조로 Agreement 기록(Disagreement는
자동 정답 처리 없음). 실행 제한 상수화(≤3호출·6,000 tokens·300s·재시도 0·
승인 로컬 profile `qwen38-27b-fp8-vllm-tp1-ktl02` @ 127.0.0.1:8004).
**호출 0·토큰 0** — 예산·허가는 사용자 최종 승인 후 발급. Marked
**81/81 PASS**. 판정: **HOLD 유지**.

---

## A. Fixture별 승인 (지시 §A) — 독립 관리

| Fixture | fixture_digest (per-fixture, 앞 16자) | approved_scope |
|---|---|---|
| g3-1802-result | `48c5a0e48559d667…` | Numeric Fidelity |
| g4-1802-numeric | `e07ee6dbcc9a2dca…` | Normalized Numeric Fidelity |
| g7-1901-method | `e0ec0e4da80b38f6…` | Partial Required Information Coverage Loss |

- 승인 기록: `r6-pilot-admission/approval-{fid}.json` + 인덱스
  (`admission-summary.json`). 승인자: owner-directive(독립 검토 r5 권고 +
  본 지시 범위 확정 근거), fixture별 독립 레코드.
- **bundle digest(`3ce9c206…`)는 context-only 필드로 기록** — fixture 개별
  승인 식별자가 아님을 스키마에 명시. g9(Unavailable)로 승인 레코드 생성
  시도 → ValueError 실증(등록 스코프 없음). 기존 Gold Bundle·Review Records
  무변경.

## B. Pilot 평가 방식 (지시 §B) — Blind 계약

- 제공: Original + Perturbed, **동일 judge**, seed=42 고정 무작위 A/B 순서
  (unblind map은 별도 봉인 — 판정 후에만 사용).
- 미노출 게이트: `blind_prompt_is_blind()` — prompt에 gold·expected
  direction·↓ 화살표 포함 시 False. 3건 전부 PASS.
- Judge 출력 5요소 계약(`validate_judge_output`): ① 개별 품질 판정 ② 평가
  차원 근거 ③ Evidence Reference(부재 시 invalid) ④ 상대 판단(A/B/equal)
  ⑤ Abstention — 사유 없는 중단은 invalid(묵과 채점 금지).
- 대조는 평가 후(`compare_with_gold`) — perturbed lower 기대와 판정이
  반대면 **Disagreement 기록**, gold/judge 어느 쪽도 자동 정답화 안 함.
  Abstention은 ABSTAINED로 별도 기록.

## C. 실행 제한 (지시 §C) — 상수화 + fail-closed

`PILOT_LIMITS = {max_eval_calls: 3, max_total_tokens: 6000, max_wall_seconds:
300, retry: 0, endpoint: http://127.0.0.1:8004/v1, model:
qwen38-27b-fp8-vllm-tp1-ktl02}` (Reader chain에서 승인 사용된 로컬 profile).
`run()`은 예산 환경 부재 시 `EXECUTION_BUDGET_NOT_ISSUED` — 호출·토큰 0
(테스트 실증). Final Holdout·δ·Evolution 미실행.

## D. 결과 판정 설계 (지시 §D)

- Fixture별 Gold Agreement 레코드 필드: agreement / gold_expected_direction
  / judge_observed / disagreement_auto_truth:false / note.
- **g7 전용 검토**(`g7_methodological_loss_check`): 근거 텍스트를 단어
  존재(marker: "the name", "word", "mentions textrank") vs 방법론 정보
  손실(step·extraction·clustering·centroid·pipeline·coverage)로 분류 —
  `WORD_PRESENCE_ONLY`·`AMBIGUOUS`는 **flag**(방법론 판단 실패로 간주,
  재검토 트리거). 키워드 부분열 오탐 방지를 위한 단어경계 매칭.
- 3건 결과를 일반 Semantic Reward 정확도로 해석하지 않음 — 보고는
  사례별 Descriptive에 한정.

## E. 보고 (지시 §E)

| 항목 | 값 |
|---|---|
| Fixture별 승인 상태 | 3건 APPROVED (scope-limited, fixture-level) / 타 5건 미승인 |
| Judge Profile | 미확정 — 실행 승인 후 PILOT_LIMITS profile 사용 예정 |
| 실제 호출 수·토큰 | **0 / 0** (예산 미발급) |
| Original/Perturbed 판정 | 미실행 — pair manifest 3건 준비 완료(prompt digest 고정) |
| Gold Agreement | 미측정 — 계약·기록 구조 준비 완료 |
| 오류·불일치 분석 | 준비 단계 버그 3건 수정: relative 판정 방향 반전, g7 부분열 오탐(keyword⊂word), seal API 호출부 — 회귀 테스트로 고정 |
| 다음 실험 필요성 | Pilot 실행(별도 승인) → g7 분류 결과에 따라 judge 프롬프트 보강 또는 gold 재검토 → n≥6 반복 승인 후 δ 진입 재평가 |

## 제한사항 준수

신규 모델 호출 **0**, Reader Pipeline 0, QA 재실행 0, δ 0, RRSI Evolution 0,
Final Holdout 0, Scorer 수정 0, Split 무변경(freeze `849d1431…`), Gold
Bundle·Review Records 무변경, Reader Note 원본 무변경, main 브랜치 작업,
신규 worktree 0.
