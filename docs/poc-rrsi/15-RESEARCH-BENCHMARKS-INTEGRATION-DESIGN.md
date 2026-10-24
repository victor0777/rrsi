---
doc_id: poc-rrsi-15-research-benchmarks-integration-design
title: RRSI × research_benchmarks Integration Design (design and static review only)
status: design
updated: 2026-10-24
---

# RRSI × research_benchmarks Integration Design

**Summary.** research_benchmarks 실제 코드 기반의 재사용 분석, RRSI↔Benchmark
Adapter 인터페이스 설계, QASPER 실행 준비 상태, 데이터 누출·중복 검사, 최소
코드 변경 목록, 실행 순서. **이번 작업은 설계·정적 검토에 한정** — QASPER 신규
모델 평가·RRSI 진화·Holdout 소비·운영 승격 없음. **판정: GO**(QASPER Calibration
Workstream, 별도 진행; 선행 차단 3건 §6).

---

## 1. 프로젝트 책임 분리 (지시 §1)

| 프로젝트 | 책임 | RRSI 연계점 |
|---|---|---|
| ai_papers | 논문 수집(stage-01)·분석 실행(Reader Note, Analysis/KG) | 최적화 **대상** 런타임 (U1 표면 보유) |
| research_agent | 연구 추론·판단 | 후속 라운드 대상 (R2+) |
| research_benchmarks | 독립 dataset·fixture·Adapter·Scorer·평가 결과 관리 | 외부 유효성 **축**(level1_external) 소유 |
| RRSI (rrsi/) | 후보 생성·보상 계산·최적화·승격 제안 | 판정 규칙의 소유자 |

원칙: RRSI는 benchmark gold·scorer를 복제하지 않는다. Benchmark 점수는
research_benchmarks가 산출하고, RRSI는 요약 metric을 소비한다(research_benchmarks
의 "scorer 출력에 gold bytes 미포함" 규칙이 이 분리를 이미 강제).

## 2. 기존 Benchmark Adapter 분석 (지시 §2) — 실제 코드 근거

**QASPER Reader Note Adapter** (`adapters/ai_papers/reader_note/`, 317+312+84+181 LOC):

| 검토 항목 | 실제 상태 |
|---|---|
| Mock executor 계약 | 입력: case(question) + PaperPayload(abstract). 출력: 항상 `unanswerable_claimed`·빈 evidence — gold 미독, pipeline 격리 검증용. 결정론 |
| CLI executor 계약 | fail-closed preflight: fixture→source-id 매핑 + `data/runs/workflows/<source>/01_extraction_bundle` 존재 요구, 부재 시 구조화 BLOCKED exit 1. `--dry-run`으로 명령 확인. 단, 기본 bundle 경로를 ai_papers canonical 위치로 고정 — **RRSI run 위치(poc/runs) 미대응** |
| Reader Prompt 변경 주입 | U1 프롬프트는 ai_papers `reader_note/prompts.py`에 상주 — CLI executor가 동일 repo로 실행하므로 주입 가능. 단 adapter 명령 구성에 prompts 인자 노출 없음(미구현 경로) |
| QASPER record 추출 | **미구현**(adapter 명시: "record extraction from the standard-understanding-qa artifact is not wired yet"). CLI replay 산출 → intake record 사이의 결속 없음 |
| 대체 결속 경로(실존) | ai_papers에 benchmark-native external QA intake(`external_qa.py`, schema `ai-papers-external-qa-intake/v0.1`, gold-independent, abstract_only input 모드 지원) + replay CLI(`external_qa_replay_d1.py`)가 이미 존재. research_benchmarks의 `external_qa_consumer.py`가 이 intake를 record로 투영해 공식 QASPER F1 + 별도 Evidence F1로 채점하는 **완성 lane이 실존**(WO-4, real-inference lane) |
| Scorer→RRSI Reward 인터페이스 | 없음(신규 설계 필요, §4) |
| Gold 격리 | consumer fail-closed: gold 미독 레인 + final split 거부 + gold는 scorer만 접촉. RRSI가 gold에 접근하는 경로는 설계상 없음 — 격리 원칙 준수 |

## 3. QASPER 데이터 준비 조사 (지시 §3)

| 항목 | 상태 |
|---|---|
| 원문 확보 | **dataset 확보 완료**: `benchmarks/qasper/dataset/qasper-dev-v0.3.json`(fixture manifest에 byte digest 등록, CC BY 4.0). 논문 원문 fulltext도 dataset 내 포함(QASPER는 fulltext dataset) |
| Stage-01 extraction | adapter가 요구하는 것은 ai_papers canonical bundle. QASPER 논문 20편(dev fixture)은 미취득 상태 — ai_papers stage-01 승인 선행(README 명시). 다만 external QA lane은 **fulltext가 아니라 abstract_only 조건**이므로 full-text bundle 없이 실행 가능(§6 참고) |
| Hash | dataset 파일 sha256 manifest 등록; case digest + cases_sha256 + gold_sha256 검증 완료(frozen readiness matrix) |
| ai_papers Gold 중복 | **dev·final 모두 교집합 0건**(본 검토에서 프로그램 검증 — gold 15 arxiv id vs QASPER fixture 논문 id). 시대·도메인도 불일치(2016-19 NLP vs 2025-26 agent/E2E) |
| 분할 가능성 | fixture 자체가 dev(20 papers/70 cases)/final(40 papers/159 cases) 분할 보유 — research_benchmarks의 평가 분리 원칙(§4: dev 사용, final 별도 기록)과 직접 정합. rrsi split manifest에는 **BENCHMARK 축으로 등록하지 않음** — gold 15편 분할과 독립 축으로 유지(§5) |

## 4. RRSI U1 평가 체계 설계 (지시 §4)

| 지표 | 소유·계산 위치 | 데이터 접근 |
|---|---|---|
| Reader Gold (필수 개념 충족) | **research_benchmarks 아님** — ai_papers GT 평가(`evaluate_reader_note_quality.py`, model-free). RRSI는 요약 S 소비 | GT: ai_papers docs/eval (frozen) |
| QASPER (논문 QA) | **research_benchmarks**: intake→consumer→`qasper_scorer.py` (Answer F1) | gold: benchmark store만 접촉 |
| Evidence Integrity (근거 정확도) | **research_benchmarks**: `evidence-match/v0.1` 별도 F1 — Answer F1과 혼합 금지(기존 정책 유지) | 동일 |
| Cost (추론 자원) | **rrsi**: ledger(reserved/rejected) + telemetry(usage/latency) 소비 — 토큰·호출·wall-clock 상계 | RRSI run artifact |
| Pipeline Regression (하류 품질) | **ai_papers**: Analysis/KG 지표(`analysis_kg` adapter, `kg_scorer.py`는 Cross-KG용이며 별도) — L2 무하락 규약(R1 §4) 산출 | ai_papers 하류 artifact |

**RRSI Reward 최소 인터페이스** (신규, 소유=rrsi):

```
BenchmarkScore (research_benchmarks 요약)
  {benchmark_id, split: "dev", answer_f1, evidence_f1, case_count,
   scorer_policy_version, computed_at}      # gold bytes 없음
→ RewardContribution (rrsi 포용)
  {"axis": "qasper", "weight": w_q, "value": answer_f1,
   "source_ref": {run_id, scorer_policy_version}}
```

- 다목적 S = Reader Gold(§3.3) + w_q·QASPER F1 + w_e·Evidence F1 − 규약상 비용
  항(cost rule L1 유지). 가중치·포용 시점은 freeze 문서에 사전 등록 후 실험.
- ΔS 판정은 기존 δ(≈0.19, 14번 보고) 재사용 — benchmark 축 추가 시 δ 재산정
  요구(R1 §3.1 규약).

## 5. Gold와 QASPER의 평가 역할 구분 (지시 §6-5)

- **Reader Gold**: "무엇을 반드시 설명했는가"(개념 충족, GT 항목 기반) — 승격
  주 판정 축, within-paper 반복 변동성의 δ 근거.
- **QASPER**: "질문에 답했는가"(독립 벤치마크 F1) — 외부 유효성 상관
  (§3.4 GT 과적합 방지 축). 라운드 argmax 조건에 넣기 전 상관 검증(스피어만 ≥0)
  선행(R1 §3.4 승격 조건 준수).
- 혼합 금지: 두 축의 점수는 절대 합산해 단일 수치로 보고하지 않고 축별 보고.

## 6. QASPER Calibration 실행 차단 요인 (지시 §6-3, §6-7)

1. **intake lane의 현행 fixture 연결**: `external_qa_replay_d1.py`가 본 목적의
   producer이나, QASPER abstract_only 조건 70 case에 대한 replay 실행 기록 미존재(실제 모델 평가 미실시 — 본 작업 범위 밖 준수).
2. **RRSI run 위치 대응**: benchmark adapter/consumer가 ai_papers canonical 경로
   가정 — `poc/runs/` 산출물에 대한 경로 인자화 필요.
3. **가중치·δ 재산정**: benchmark 축 포용 시 S 정의 변경 → freeze hash 갱신 승인.

**실행 순서** (지시 §6-7): ① R0-b2 후속 δ 확정(baseline repeat n≥6) → ②
QASPER replay dry-run(preflight BLOCKED 해소 검증) → ③ QASPER Calibration
(abstract-qa dev 70 case, 별도 승인·상한) → ④ 상관 검증 후 RRSI Evolution PoC
판정 갱신. QASPER Workstream은 R0-b2/Evolution과 병행하지 않고 단계 분리.

## 7. 최소 코드 변경 목록 (지시 §6-6)

| # | 변경 | 위치 | 규모 |
|---|---|---|---|
| 1 | external QA replay의 fixture 경로·abstract_only 조건 바인딩 확인 | ai_papers `scripts/external_qa_replay_d1.py` (기존 기능, 변경 최소) | ~0-20 LOC |
| 2 | BenchmarkScore 요약 export(`score_records().summary()`의 rrsi 소비용 스키마 고정) | research_benchmarks `evaluation/qasper_scorer.py` 요약 경로 | ~20 LOC |
| 3 | RewardContribution 스키마 + S 포용 경로 | **rrsi poc** (`poc/` 신규, 코어 불변 — R1 매개변수 선택 규약) | ~80-120 LOC |
| 4 | adapter/consumer 경로 인자화(rrsi run dir 대응) | research_benchmarks `adapters/ai_papers/reader_note/*` | ~30 LOC |
| 5 | preflight에 QASPER 조건 추가(fixture 매핑·abstract 조건) | rrsi `poc/r0b2_preflight.py` 확장 | ~20 LOC |

코어 수정 0 (rrsi/ 15파일, ai_papers 파이프라인 코어, research_agent 모두 불변).

## 8. GO / HOLD / STOP — **GO** (QASPER Calibration Workstream)

- 실존 코드 기반 재사용 확정: producer(external QA intake)·consumer·scorer 모두
  기존 구현 — 중복 구현 불요. 누출·중복 검사 PASS(§3). 격리 원칙 기존 규약 유지.
- 본 검토는 설계·정적 검토 한정: QASPER 신규 모델 평가 0, RRSI Evolution 0,
  Holdout 소비 0, 운영 승격 0, 제안 코드 변경 실시 0.

**Committed artifacts**: 본 문서.
