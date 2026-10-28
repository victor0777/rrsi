---
doc_id: poc-rrsi-29-semantic-gold-fixture-readiness
title: Semantic Reward Gold Fixture & Evaluator Readiness (executed, 0 model calls)
status: report
updated: 2026-10-28
---

# Semantic Gold Fixture & Evaluator Readiness Report

**Summary.** 2편 대상 **Semantic Gold Fixture 9건** 등록 — 전건의 source
anchor를 기계 대조로 검증(`SOURCE_VERIFIED`), **APPROVED 0** — anchor와 주장의
의미적 대응은 판단이므로 독립 인간 검토 전까지 `HUMAN_REVIEW_REQUIRED`로
유지(작성자 자체 기대 판정을 검증 결과로 간주하지 않음). Semantic 변형본
5건(P1·P2확장·P3확장·P4·P5)을 평가 전용 봉인 RUN_DIR에 생성, source 근거와
대조해 의도한 결함임을 확인. Evaluator Readiness: 결정론 가능 2건(P2확장 감지·
길이 비용), semantic 축 5건 전부 **Model Judge 또는 GT 필요 — 미실행**.
δ Calibration 진입 조건 6항목 중 충족 0. 판정: **HOLD 유지**.

---

## A. Semantic Gold Fixture 등록 (지시 §B) — 9건

`poc/runs/perturbation-audit/r2-semantic/semantic-gold-fixture.json`
(schema `rrsi-semantic-gold-fixture/v0.2`). 각 건에 필수 9필드(Paper Identity,
Source Identity·Version, Source Sentence Reference, Reader Note 위치, 검증
대상, 기대 의미, 예상 변형, 기대 평가 방향, 판정 근거) 포함.

| Fixture | 논문 | 유형 | 검증 대상(축약) | anchor 기계 검증 |
|---|---|---|---|---|
| g1 | 1802 | 핵심 주장 | proposed approaches **outperform** state-of-the-art NER on SnapCaptions | ✓ (원문 §claims) |
| g2 | 1802 | 방법론 | modality attention이 decoding step마다 최적 모달 선택 | ✓ |
| g3 | 1802 | 실험 결과 | 어휘 크기 **15,733** tokens | ✓ (full_text 존재) |
| g4 | 1802 | 수치·의미 | **10,000** pairs = 데이터 크기 (원문 표기 "10K") | ✓ (release/annotation anchor) |
| g5 | 1802 | 주장-근거 | release 주장의 근거 = dataset-composition 문장 | ✓ |
| g6 | 1901 | 핵심 주장 | 문서 구조화가 논문 목적 | ✓ (Introduction) |
| g7 | 1901 | 필수 단계 | TextRank 키워드 추출·centroid 클러스터링 | ✓ |
| g8 | 1901 | 실험 결과 | θ = **0.25** (empirical) | ✓ |
| g9 | 1901 | 주장-근거 | eq0001 참조 유효 | ✓ (artifact-graph) |

- **등록 배제 규약**: Source에서 확인 불가한 내용은 Gold로 등록하지 않음 —
  §A(27번)의 "silence→No" gold 추론은 AMBIGUOUS 판정 유지로 fixture에서
  제외.

## B. Source Verification 결과 (지시 §H-2)

- 전건의 `source_sentence_reference.anchor`가 full_text(flatten)에
  존재 — **9/9 기계 검증 PASS**.
- anchor → 주장의 **의미적 대응**(기대 의미)은 기계 대조로 확정 불가 —
  state는 SOURCE_VERIFIED(anchor 차원)이며, Gold 사용을 위한 최종 상태는
  독립 인간 검토 후에만 APPROVED 승격 가능.

## C. Human Review 필요 사례 (지시 §H-3) — 9건 전부

- 27번 원칙 유지: 작성자(본 실행 에이전트)의 기대 판정을 검증 결과로 간주하지
  않음. 필요한 검토 관점: ① claim→anchor 지지 관계, ② "필수" 판정의 기준,
  ③ 수치-의미 매핑(10K↔10,000)의 동치성, ④ 근거 문장의 문맥 정합.
- **독립 검토를 거치지 않은 fixture는 최종 Reward 검증의 Gold로 사용하지
  않음**(계약으로 등록).

## D. Controlled Semantic Perturbation (지시 §C) — 5건 생성·봉인

원본 digest 바인딩(`semantic-discrimination.json`),
`poc/runs/perturbation-audit/r2-semantic/` invocation-bound + seal.

| 실험 | 변형 | 결정론 확인 | 의도 결함의 Source 근거 대조 |
|---|---|---|---|
| p1-1802-claim-removed | outperform 주장 문장 제거 | 주장 문장 부재·길이 ↓ | source g1 anchor는 유지 — note-side 주장만 소실(의도된 fidelity 손실) ✓ |
| p2ext-1901-other-metric | 0.25 → **0.75**(note에 존재하는 타 수치) | 지정값 0.25 소실 감지 | 0.75는 원문의 타 양 — 무음 오귀속 생성 ✓ |
| p3ext-1802-unrelated-ref | 유효하지만 **무관한** `fig0003`을 주장에 연결 | **reference_integrity 통과 — literal 무결** | 유효 id + 무관 근거 = semantic 오연결 — **literal 평가자의 한계 표면화** ✓ |
| p4-1802-contradiction | 모순 주장 추가 ("underperforms …") | 문장 존재·원문에 부정 표현 0 | source가 outperform 주장(g1) — 직접 모순 ✓ |
| p5-1901-method-removed | TextRank 필수 단계 문장 제거 | TextRank 문장 수 ↓·길이 ↓ | source g7 anchor 유지 — 필수 단계 소실(의도된 coverage 손실) ✓ |

## E. Evaluator Readiness Matrix (지시 §E)

| 축 | 결정론 | Gold 기반 | Model Judge | 판정 |
|---|---|---|---|---|
| Numeric Consistency | **가능**(구현·PASS) | — | 불필요 | READY |
| Reference Integrity | **가능**(구현) — dangling만 | — | 연결 정합은 불필요 | READY(존재성) |
| Literal Evidence Consistency | **가능**(재사용 `normalized_find`) | — | 불필요 | READY |
| Length / Cost | **가능**(구현) | — | 불필요 | READY |
| Semantic Claim Fidelity | 불가 | **Gold 필요(독립 검토 전까지 사용 금지)** | 필요 | UNVERIFIED |
| Semantic Evidence Grounding | 불가(literal 무결로도 오연결 가능 — p3ext 실증) | Gold 필요 | **필요** | UNVERIFIED |
| Required Information Coverage | 불가(필수 정의 부재) | Gold 필요 | 필요 | UNVERIFIED |
| Unsupported Claim Detection | 불가 | Gold 필요 | **필요** | UNVERIFIED |
| Scientific Understanding | 불가 | review GT 필요 | **필요** | UNVERIFIED |

- Model Judge는 **실행하지 않음**(지시). 필요 방식만 분류.

## F. Reward Discrimination 준비 상태 (지시 §F)

| Perturbation | Gold | Expected | Available Evaluator | Readiness | 미검증 의존 |
|---|---|---|---|---|---|
| p1 | g1 | fidelity ↓ | 없음(semantic) | **UNVERIFIED** | judge/GT |
| p2ext | g8 | consistency ↓ | designated_numeric_consistency | **READY(결정론)** | — |
| p3ext | g5·g9 | grounding ↓(semantic) | reference_integrity(무결로 통과 — blind) | **UNVERIFIED** | semantic grounding judge |
| p4 | g1 | 모순 검출 | 없음(semantic) | **UNVERIFIED** | judge/GT |
| p5 | g7 | coverage ↓ | 없음(semantic) | **UNVERIFIED** | 필수 정의 + judge |

- 점수 임의 생성 없음. 결정론 검증(P2확장)은 수행·감지 PASS.

## G. δ Calibration 진입 조건 (지시 §G)

| # | 조건 | 상태 |
|---|---|---|
| 1 | 최소 의미 평가 fixture 확보 | **부분** — 9건 등록·SOURCE_VERIFIED |
| 2 | Gold Review 완료 | **미완료** — APPROVED 0 (독립 검토 전) |
| 3 | Reward Discrimination 실행 가능 | **부분** — 결정론 축만(P2확장 감지 PASS) |
| 4 | Model Judge | **필요** (semantic 5축 — 미실행) |
| 5 | δ용 Reward 정의 안정성 | **미확보** — semantic 축 정의·판정자 미확정 |
| 6 | Split/Holdout 제약 | 유지 — dev 전용, final 무접촉, freeze `849d1431…` |

- **δ 반복 확대: 실행하지 않음** — 진입 조건 미충족(2·4·5가 병목).

## H. 완료 보고 (지시 §H) 및 판정

1. Semantic fixture: **9건**. 2. Source verification: 9/9 anchor 기계 검증
   PASS. 3. Human review: **9건 전부 필요**(APPROVED 0, 독립 검토 전 Gold
   사용 금지). 4. Semantic perturbation: 5건 생성·봉인, source 근거 대조
   완료 — **p3확장이 literal-blind 한계를 실증**. 5. Readiness: 결정론 4축
   READY, semantic 5축 UNVERIFIED. 6. Discrimination 준비: 결정론 1건 READY,
   semantic 4건 대기. 7. δ 진입: **미충족**(Gold review·판정자·정의 안정성
   병목).
8. **Evolution GO/HOLD/STOP: HOLD 유지** — semantic 축의 해제 조건이 구체화됨:
   (i) 9건 fixture의 독립 인간 검토 → APPROVED 승격, (ii) Model Judge 승인·
   실행, (iii) δ용 reward 정의 안정성 확정, (iv) δ 반복(n≥6) 승인, (v) 분할
   해동 승인. STOP 아님: 원본 artifact 무변경, anchor 기계 검증 9/9, 결정론
   감지 실동작, 점수 임의 생성 0.

## 제한사항 준수

신규 모델 호출 **0**, Reader Pipeline 실행 **0**, QA 재실행 0, δ 반복 확대 0,
RRSI Evolution 0, Final Holdout 소비 0, Official Scorer 수정 0, Reader Note
원본 변경 0, ai_papers 운영 상태 변경 0, 신규 worktree 0.
