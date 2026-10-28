---
doc_id: poc-rrsi-28-minimal-reward-discrimination
title: Controlled Perturbation & Minimal Reward Discrimination (executed, 0 model calls)
status: report
updated: 2026-10-28
---

# Controlled Perturbation & Minimal Reward Discrimination Report

**Summary.** Reader Note 2편 원본 무변경, 평가 전용 RUN_DIR
(`poc/runs/perturbation-audit/r1/`, invocation-bound + seal)에서 P2·P3·P6
변형본 6건 생성, **Discrimination Matrix 6/6 PASS** — 결정론적 평가 함수가
명백한 품질 저하를 감지함을 최소 실험으로 실증. 핵심 근거 사례: note의
"10,000" ↔ 원문 "10K"(normalized 일치, literal 불일치) — **엄격 literal
평가는 원본을 오탐(false positive)으로 판정할** 사례를 실제 데이터에서 확인하고
unit-aware 정규화로 회피. False Negative 0. 점수 임의 생성 없음; semantic
grounding은 UNVERIFIED 유지. 판정: **HOLD 유지** — P1·P4·P5(내용·의미 축)는
Model Judge/GT 필요, δ Calibration 진입은 아직.

---

## A. 실제 생성한 변형본 목록 (지시 §F-1)

원본 digest 바인딩: `discrimination-matrix.json`의
`original_artifact_sha256` = reader-note digest(`99efc53f…`/`97f5dd09…`,
22번 등록과 일치). 원본 artifact 무변경, 변형본은 별도 경로 + seal 완료.

| 파일 | 변형 유형 | 내용 |
|---|---|---|
| `p2-1802-vocab.md` | P2 수치 | "15,733"(어휘 크기) → "15,800" |
| `p2-1802-size.md` | P2 수치 | "10,000"(데이터 크기) → "12,000" |
| `p2-1901-theta.md` | P2 수치 | "0.25"(파라미터 θ) → "0.40" |
| `p3-1802-ref.md` | P3 근거 오연결 | artifact id `fig0001` → 존재하지 않는 `fig0009` |
| `p6-1802-filler.md` | P6 filler | 무정보 문장 추가 (39,209→39,354 chars) |
| `p6-1901-filler.md` | P6 filler | 무정보 문장 추가 (28,809→28,954 chars) |

## B. 변형별 Ground Truth (지시 §F-2)

- **P2**: QASPER full_text (dataset sha `2ae7ee62…`, frozen) — 사전 검증:
  ① 15,733은 원문 literal 존재 ✓, ② 10,000은 원문에 literal 부재·"10K"로
  존재(unit-aware 일치 ✓), ③ 0.25는 원문 literal 존재 ✓. 원본 수치가
  Source와 불일치하는 사례는 없음 — 사용 사례 사용 자격 만족(지시 조건).
- **P3**: `extraction/1802.07862/artifact-graph.json`의
  `nodes.artifacts` = {fig0001, fig0002, tbl0001, fig0003, tbl0003} —
  note의 전체 참조가 유효 집합 내(원본 무결성)임을 사전 확인.
- **P6**: 결정론적 text stats(chars·whitespace tokens).

## C. Evaluator 구현 범위 (지시 §C, `poc/perturbation_eval.py`)

| 함수 | 용도 | 재사용/신규 | 한계(계약 일부) |
|---|---|---|---|
| `designated_numeric_consistency` | P2 지정 수치의 source 일치(literal+unit-aware) | 신규(최소) | 지정값 존재만 판정 — 주장의 의미 판단 없음 |
| `numeric_source_consistency` | 전체 수치 비교 | 신규 | **noise 발견**: 인용 연도·섹션 번호는 원문에 없어 전체 비교는 무효 신호 → 실험에서는 지정값 방식 채택 |
| `reference_integrity` | P3 참조 존재성 | 신규 | 존재만 — 해당 주장 지지 여부 미판정 |
| `literal_evidence` | 근거 literal 검증 | **재사용**(`normalized_find`) | — |
| `length_stats` | P6 길이·토큰 비용 | 신규 | whitespace tokens는 proxy |

- Semantic grounding은 **임의 점수 생성 없이 UNVERIFIED로 유지**(지시 조건).

## D. Discrimination Matrix (지시 §D) — **6/6 PASS**

| Paper | Original digest | Perturbed digest | Type | Ground Truth | Expected | Observed | 판정 |
|---|---|---|---|---|---|---|---|
| 1802.07862 | `99efc53f…` | (matrix.json 바인딩) | P2 | full_text "15,733" | 일치→불일치 | 일치→불일치 감지 | **PASS** |
| 1802.07862 | `99efc53f…` | 〃 | P2 | full_text "10K" | 일치→불일치 | **literal 오탐 회피** + 변형 감지 | **PASS** |
| 1901.10133 | `97f5dd09…` | 〃 | P2 | full_text "0.25" | 일치→불일치 | 감지 | **PASS** |
| 1802.07862 | `99efc53f…` | 〃 | P3 | artifact-graph 유효 집합 | 무결→파손 | `fig0009` dangling 감지 | **PASS** |
| 1802.07862 | `99efc53f…` | 〃 | P6 | text stats | 길이↑·비용↑ | chars+145·tokens+19 감지 | **PASS** |
| 1901.10133 | `97f5dd09…` | 〃 | P6 | text stats | 길이↑·비용↑ | chars+145·tokens+19 감지 | **PASS** |

- 원본 vs 변형본 동일 평가 함수 직접 비교. P6의 품질 reward 상승 검사:
  **UNVERIFIED** — 구현된 품질 reward가 없어 측정 불가(한계 명시).

## E. False Positive / False Negative (지시 §F-5)

- **False Negative: 0** — 6건 변형 전부 감지.
- **False Positive 회피 사례(실데이터)**: 원본 "10,000" ↔ 원문 "10K" —
  엄격 literal 비교는 **원본을 오탐**으로 판정했을 사례이며, 이는 25번 보고의
  QASPER gold "10000" 매핑 사례와 동일 구조. unit-aware 정규화로 회피.
  반대 방향 한계도 명시: 정규화는 값 존재만 판정하므로 수치가 같아도 주장의
  의미가 다르면(단위·맥락 혼동) 미감지 — **수치 의미 판단은 Model Judge 영역**.
- 결정론 평가자의 한계 요약: 존재성·정합성 검출만 가능, 의미·지지 관계 검출
  불가.

## F. Reward Hacking 검출 결과 (지시 §F-6)

- **P6 길이 해킹**: 길이 증가만으로 상승하는 품질 reward는 현재 구현되지
  않았으므로 해킹 표면도 없음 — 다만 coverage·정확 기반 reward 도입 시
  filler는 자동 감지 가능(length_stats가 비용 악화를 즉시 표시). 품질 reward는
  길이와 무관하게 coverage·정합 기반으로 설계할 것(26·27번 권고 유지).
- **P3 오연결**: dangling 참조는 결정론 감지 — **주제 불일치**
  (cross-paper 사건 유형)는 identity binding이 계약으로 차단(23번) — 두 축의
  Gate 실동작 확인.
- **P2 수치 해킹**: 값 존재 기반 검증은 원문 수치의 동의 표기(10K↔10,000)를
  허용하는 정규화가 필수 — 정규화 도입 시 동치 표기를 오도하지 않도록
  literal/normalized 결과를 병행 보고하는 설계로 확정.

## G. Reward Contract 판정 (지시 §E)

1. **Numeric Fidelity 결정론 평가**: **가능**(지정값·unit-aware 방식) — 단
   주장 의미는 미판정.
2. **Evidence Grounding의 결정론 한계**: (i) literal 일치 — 완전 가능,
   (ii) 참조 존재 — 완전 가능, (iii) 해당 주장의 실제 지지(semantic
   grounding) — **결정론 불가** (UNVERIFIED 고정).
3. **길이 해킹 방지**: 가능 — 품질 축을 길이와 무관한 coverage·정합 기반으로
   설계 + 비용 지표 병행.
4. **Model Judge 필요 축**: Unsupported Claim Detection, Scientific
   Understanding, Abstention Calibration(§A의 규약-의존 판정), Claim Fidelity
   중 문맥 정합.
5. **Hard Gate 적절 축**: Evidence Grounding(literal), Paper Identity/
   Reference 존재성, Dataset/Split 정책 — **fail-closed 실동작 확인됨**.
6. **Soft Reward 적절 축**: QA Utility, Execution Cost(품질 축과 짝지을 때),
   Claim Fidelity(문맥 정합 제외), Abstention Calibration.
   가중치 미확정(지시).

## H. 추가 평가 필요 축 / δ 진입 (지시 §F-7·§F-8)

- **추가 평가 필요**: Claim Fidelity 문맥 정합·Unsupported Claim·Scientific
  Understanding·Abstention Calibration — GT 확보 또는 Model Judge 승인 전제.
- **δ Calibration 진입 가능 여부**: **아직** — 본 실험은 "명백한 품질 저하
  감지"의 결정론 실증이며, δ는 candidate 간 미세 품질 차이를 요구 — P1·P4·P5
  축의 판정자(g GT 또는 Model Judge)와 반복 실행(δ 반복 확대 — 별도 승인)이
  선행되어야 진입 가능. 결정론 Gate·P2/P3/P6 소관은 δ 대상에서 제외(Gate는
  문턱 요건).

## I. 완료 보고 및 판정 (지시 §F)

1. 변형본: §A (6건). 2. Ground Truth: §B. 3. Evaluator: §C. 4. Matrix: §D
   (6/6 PASS). 5. FP/FN: §E (FN 0, FP 회피 사례 실증). 6. Hacking 검출:
   §F. 7. 추가 평가 축: §H. 8. δ 진입: 아직(§H).
9. **Evolution GO/HOLD/STOP: HOLD 유지** — 근거 갱신: reward가 명백한 품질
   저하를 감지함이 **결정론으로 최초 실증**(27번의 "전 축 UNVERIFIED" 중
   P2·P3·P6 축 해제). 잔여 HOLD 사유: ① 내용·의미 축(P1·P4·P5)의 판정자
   미확정, ② δ 반복(n≥6) 승인 대기, ③ 분할 해동 승인. STOP 아님: 격리·permit
   규약 준수, 원본 artifact 무변경, 점수 임의 생성 0.

## 제한사항 준수

신규 모델 호출 **0**, Reader Pipeline 실행 **0**, QA 재실행 0, δ 반복 확대 0,
RRSI Evolution 0, Final Holdout 소비 0, Official Scorer 수정 0, Reader Note
원본 변경 0, ai_papers 운영 상태 변경 0, 신규 worktree 0.
