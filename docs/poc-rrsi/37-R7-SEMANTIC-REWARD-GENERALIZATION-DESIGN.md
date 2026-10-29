---
doc_id: poc-rrsi-37-r7-generalization-design
title: R7 Semantic Reward Generalization Evaluation Design
status: design
updated: 2026-10-29
---

# R7 — Semantic Reward Generalization Evaluation Design

**상태:** `R7_DESIGN_READY` (설계 완료 — R7-E1 실행은 별도 Owner 승인 전
금지). 기준: R6I Post-execution Audit `3fd0a11`. 모델 호출 0.

## 1. Goal — 핵심 연구 질문

> Semantic Judge는 기존 Fixture에 특화된 규칙 없이, 처음 보는 논문의
> Reader Note에서 의미적 정보 손실, 사실 오류, 근거 부족을 일관되게
> 식별할 수 있는가?

R6I의 2/2 (g4·g7 — `docs/poc-rrsi/36-…`, 봉인 raw
`poc/runs/semantic-judge-pilot/semjudge-r6i-g4g7/raw/`)는 **고정
Fixture 결과**이며 일반화 증거로 사용하지 않는다.

## 2. 기존 자산 조사

| 자산 | 실제 경로 | 재사용 | R7 역할 / 제한 |
|---|---|---|---|
| R6I 실행·감사 | `poc/runs/semantic-judge-r6i-g4g7/r6i-report.json`, `poc/runs/r6i-audit/audit-report.json` | ✓ | 판정 재현·계약 정합성의 기준 구현 (A개발집합) |
| Semantic Gold 9건 (g1–g9) | `poc/runs/perturbation-audit/r2-semantic/semantic-gold-fixture.json` | ✓ (VALID 건만) | Development Set; `BLOCKED_CONFLICTED`성 충돌 건은 집계 배제 |
| Gold Quality Gate·리뷰 패킷 | `docs/poc-rrsi/30-…`, `poc/gold_review.py`, `docs/poc-rrsi/review-packets-r5/` | ✓ | R7 Quality Gate 절차의 선례 |
| Reader Note 생성 품질 체계 | `ai_papers/docs/eval/reader-note-quality/` (GT 15건, quarantine, official-gt-fixtures.md) | 참조 | GT 형식 선례; **독립 검토 절차 이식** |
| Split freeze | `poc/runs/r0b2/split-manifest.json` (frozen `849d1431…`) | 계약 준수 | **13건 BLOCKED_CONFLICTED = 평가 금지 유지**; Evolve 2건(2508.11428 acquired, 2511.13079 미획득)은 본래 진화용 — R7에서 재사용하려면 별도 Owner 결정 필요 |
| Perturbation P1–P6 | `poc/perturbation_eval.py`, gold fixture `expected_perturbation_types` (P1 주장 변질, P2 수치, P3 근거, P4 모순, P5 방법론 제거, P6 실험) | ✓ | Challenge Set 설계 대응표; **이름만으로 정답 금지** |
| Judge 계약·판정 | `poc/semantic_pilot_r6i.py` (v2 스키마, G7_CLAIM_ITEMS), `adjudicate_response()` | ✓ | R7-D0에서 계약 확장의 기준 (운영 동작 무변경) |
| Reward·Cost Policy | `poc/poc_core.py`, `docs/poc-rrsi/26-…`(불변성 수리 보상 감사), `27-…`(보상 계약 판별 감사), `28-…`(최소 보상 판별) | 참조 | 보상 적합성 판정 지표와 비용 정책 연결 |

**핵심 제한:** R6I의 `G7_CLAIM_ITEMS`는 고정 Fixture 전용 정규식
레지스트리 — R7 Judge 계약에서 제외(§5)하며, 이는 R6I 운영 동작
변경이 아니라 R7 별도 계약이다.

## 3. 평가 대상과 데이터 분리

- **A. Development Set**: R6I g3·g4·g7 및 공개 Gold (위 표). 목적은
  인터페이스·계약 정합성 확인만. 성능 보고 대상 아님.
- **B. Unseen Evaluation Set**: R6I 계약 개발에 사용하지 않은 논문.
  **논문 단위 분리**(§4 문서의 증명 요건) — 1802.07862·1901.10133 계열
  및 R6 발췌에 사용된 모든 논문은 배제.
- **C. Challenge Set**: R6H 감사가 드러낸 실패 모드 기반 — 표현만
  변경(의미 유지), 표기만 정규화, 실제 수치 변경, 방법론 설명 부분
  삭제, 이름 잔존+기능 제거(P5 실제 형태), 근거 없는 주장 추가,
  상호 모순 설명, 판단 유보 사례. P1–P6 대응표는 문서 2에 기록하되
  perturbation 이름을 정답 근거로 쓰지 않는다.

## 4. Gold Quality Gate

Judge 성능보다 **Gold 신뢰성이 선행** (R6H 발췌 편향 사례의 교훈).
사례별 5항목 검사(원본 Note 정확성, 의도 오류 유일성, 우연 변경 부재,
기대 방향 근거, 독립 검토자 재현 가능성) → 상태 `VALID`,
`CONFLICTED`, `INSUFFICIENT_EVIDENCE`, `EXCLUDED`. **VALID만 주 집계
포함.** 기존 Gold 무변경 — R7 전용 평가 기록으로 별도 관리 (문서 2).

## 5. Judge 평가 계약

R6I 고정 레지스트리 제거. 지표(§6)를 산출하기 위한 출력: Relative
Quality Judgment, Dimension Verdict, Evidence References, Error/
Missing Claims, **Claim Verification Status**(원문 근거 위치·주장
내용·의미적 일치를 분리하는 3층 구조 — 정규식 단독 판정 금지),
Abstention Reason, Token/Latency Cost. **이 단계에서 모델 기반 검증기
구축·실행 없음** — 검증 구조의 설계·동결만.

## 6. 평가 지표

Gold Agreement, Claim Precision, Claim Recall, Evidence Grounding,
False Positive Rate, Abstention Quality, Cost per Valid Judgment
(문서 3에 분모·집계 단위·Abstain 정책·소표본 신뢰구간 정책 동결).
단순 Accuracy로 Reward 적합성을 결정하지 않는다.

## 7. 단계 및 Admission

**R7-D0**(본 설계, 호출 0) → **R7-E1**(Limited Pilot — Owner 별도
승인 필요: 대상·호출 수·토큰/GPU/Wall 예산) → **R7-E2**(E1 사전 정의
기준 충족 시만 확대; 확장·중단 기준은 E1 전 확정). Admission 8항목은
문서 3 §Admission. Admission 통과해도 자동 실행하지 않는다.

## 8. 후보 규모·비용·차단 요인 (요약 — 상세는 문서 3 §5 단일 예산표)

- R7-E1 후보: 논문 3편 × 유형 4 ≈ 12 사례 (Unseen 2편, Challenge는
  Unseen 논문 위의 별도 평가 층)
- Gold 검증 작업량: **검토자 1인당 9–12시간 (2인 기준 18–24인시)** +
  불일치 조정 별도
- 예상 호출: 12회 ≈ **15,000 tokens** (문서 3 §5 예산표로 통일)
- 차단 요인: ① Unseen 논문 확보 + **노출 이력 조사**(id 교집합만으로
  불충분) ② 독립 검토자 확보 ③ E1은 실행 가능성·계약 검증 단계로
  재정의 (성능 입증 아님)
