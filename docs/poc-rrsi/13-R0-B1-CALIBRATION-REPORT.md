---
doc_id: poc-rrsi-13-r0b1-calibration-report
title: R0-b1 Calibration Report — data preparation + 1-trial Reader Baseline (executed)
status: report
updated: 2026-10-24
---

# R0-b1 Calibration Report

**Summary.** Gold 데이터 준비(12번 보고 §3의 결정적 차단 해소)와 R0-b1
1-trial Reader Baseline을 **실제 실행**했다. `ai_papers` 원본 프로젝트가
`projects/` 하위에 존재함을 확인했고, GT 15편 전부 원격 존재 확인. 본 실행은
Evolve 후보 논문 1편(ImagiDrive, 2508.11428v2)에 한정됐다. **판정: GO**
(다음 단계 = δ calibration 반복 평가, 사전 조건 2건 §9).

---

## 1. ai_papers 원본 프로젝트 및 데이터 확인 결과

| 항목 | 결과 |
|---|---|
| 프로젝트 위치 | `/home/ktl/projects/ai_papers` (git, HEAD `997e5a1ec`, canonical `src/ai_papers_research/`) |
| Gold GT 15편 | **전부 존재** — `docs/eval/reader-note-quality/gold/` (10 agent-memory + 5 e2e) + quarantine 1 + 공식 레지스트리 `official-gt-fixtures.md` |
| arXiv 원문 | **부재** — `data/raw/arxiv/`에 무관 1개뿐. 과거 gold workflow 취득분은 `pipeline-data-reset-preparation-r1` 리셋으로 제거됨. 단, git 히스토리에도 없음(`git ls-tree --all` 0건) → **재취득 필요**(arXiv 공개 URL로 해소 가능) |
| 기존 extraction 결과 | **부재** — `data/processed/`는 공 디렉터, `data/runs/workflows/`는 무관 논문 1편(2605.00884)만. gold bundle 존재 흔적(goal134 매니페스트 참조)만 잔존 |
| Reader Note 평가 데이터 | **존재** — GT 15편 + 평가 CLI `scripts/evaluate_reader_note_quality.py` + 판정 정책 `docs/specs/policies/reader-note-quality-judgement-policy.md` |
| Frozen evaluation artifact | **존재** — GT fixture는 frozen 입력으로만 사용(본 실행에서 읽기 전용 접근) |
| Source/dataset manifest | GT 매니페스트는 ai_papers에 존재하나 extraction dataset manifest는 RRSI 측에서 신규 생성(§3) |
| LLM ledger | **존재** — `src/ai_papers_research/llm/call_budget.py` (env 바인딩 fail-closed, v0.2 스키마) |
| 벤치마크 프로젝트 | `/home/ktl/projects/research_benchmarks` — ai_papers/research_agent 공통 read-only 평가 프로젝트(benchmarks: qasper/scifact/scirex/scirex/evidence_inference/scholarqa/arxiv_digestables). GT 격리 원칙(정답은 benchmark 프로젝트만 관리)은 본 RRSI 연구와 별개 축이며 본 실행에서 미접촉 |

**판정 근거 수정.** 12번 보고의 "13/13 gold 논문 소스 부재 = 원본 데이터 부재"는
**"canonical 위치 + git 히스토리에 없음"** 으로 정정 — GT·파이프라인·ledger 등
나머지 자산은 전부 원격 존재·재사용 가능.

## 2. Gold 데이터 확보 방법 (Evolve 1편)

- **논문 선택**: `e2e-arxiv-2508-11428` (ImagiDrive). 근거: (a) R0-a frozen
  holdout denylist 13 id(2502.12110 등)에 **미포함** — denylist에 등록된
  어떤 논문보다 최종 holdout 축돌 위험이 낮음, (b) GT 유효(3 items, no quarantine),
  (c) R1 설계 §3.1의 "Evolve 8 = agent-memory 6 + e2e 2" 중 e2e 2가
  {2508.11428, 2511.13079}로 추정되는 유일한 denylist-안전 id.
  ⚠️ **분할 불일치 발견**: R1 설계는 "agent-memory 중심 evolve"인데 denylist가
  agent-memory 10편 전부를 등록 — Evolve agent-memory 6이 denylist와 충돌.
  이는 분할 freeze가 아직 없기 때문으로, 본 실행은 denylist-안전 1편으로 회피.
  R1 라운드 전에 분할 freeze 필요(§9 조건과 별개 결함 §10-a).
- **취득**: ai_papers의 `governed_arxiv_source_capture.py` (pre-execution
  receipt 수반) → `https://arxiv.org/html/2508.11428v2` (208,273 bytes).
- **Extraction**: ai_papers의 `arxiv_html_bundle.py` canonical bundle
  (reading.md 87,002 chars + source-map + artifact-graph, model-free).
- **소비 축소**: Validation 및 Final Holdout 논문은 미취득·미평가(지시 준수).
  승격 직전까지 GT는 출력 대조에만 사용.

## 3. Dataset manifest 및 hash

- 구현: `poc/dataset_manifest.py` (결정적 규약 사전 등록: 경로 정규화 =
  루트 상대 POSIX 경로, 정렬 = 정규화 경로 UTF-8 코드포인트 순서, 파일별
  SHA-256, canonical JSON 직렬화 후 SHA-256). 재계산 동일성 테스트 PASS.
- 대상: `poc/runs/r0b1/{source,extraction}` 전체 39 files.
- **dataset manifest SHA-256**: `57d1a501f12306a79c06fed2ea4f62dce5c82179c4bf7eddb90048a99ee0bb51`
- **source file** (retrieved-source.html) SHA-256:
  `808e4f741338cda32030ca21f8af37eb9b1bfcdaa40909319b773105f9c5699d` (v2)
- **paper ID / arXiv version**: `e2e-arxiv-2508-11428` / `2508.11428v2`
- **pipeline version**: ai_papers@`997e5a1ec` (governed capture + arxiv_html_bundle +
  reader_note cli `canonical-current` 프롬프트 체인 digest `1ad6bd5e…`)
- **생성 시각/provenance**: manifest 내 기록 (governed capture preexecution-receipt,
  extraction-manifest, chain-manifest 3중 provenance).

## 4. R0-b1 실행 여부 — 실행함

사전 검사(지시 §3) 충족:

| 검사 | 결과 |
|---|---|
| 모델 ID·revision | `qwen38-27b-fp8-vllm-tp1-ktl02` @ `http://127.0.0.1:8004/v1` (vLLM 서버 보고, FP8 27B, max_model_len 131072) |
| 입력 데이터 hash | §3 manifest (실행 전 확정) |
| 예산 강제 가능성 | ledger env 바인딩(ceiling 50) + wall-clock `timeout 1800` + GPU-h 상계 규약(§6) — 3축 모두 강제 가능 |
| 데이터 무결성 | GT↔extraction 문장 정합 검증: GT의 `source_sentence_ids`(s0001_02..08)가 신규 reading.md에 존재·내용 일치 → PASS |

실행 중 결함 1건 발견·회피(§10-b): writer가 polish 기본 모델 `qwen-coder`(서버
미등록, HTTP 404)를 사용 — `--polish-model`로 동일 모델 지정 후 재개. 자동
retry는 0회(규약 유지, 재개는 인적 결정에 따른 재실행).

## 5. 실제 모델 호출 수와 토큰 사용량

| 항목 | 값 |
|---|---|
| Model calls (ledger reserved) | **29** / ceiling 50 |
| Tokens | **미기록 — 계측 결함** (아래) |

**토큰 계측 결함(정직 보고)**: trial 출력·입력 토큰이 기록되지 않았다. 원인:
`AI_PAPERS_PROCESS_TELEMETRY_EVENTS` 싱크가 실행에 바인딩되지 않아
provider-usage telemetry가 drop됨(`append_process_event_from_environment`는
env 미설정 시 best-effort 무시). Budget policy(§1)상 토큰은 계측 지표이므로
실행 유효성에는 영향 없으나, **계측 바인딩은 다음 실행 preflight의 필수 항목으로
등록**(§9 조건 2). 추정으로 대체하지 않는다.

## 6. GPU 점유시간 및 wall-clock

| 항목 | 값 | 규약 |
|---|---|---|
| Wall-clock (실행 전체) | **21분 51초** (02:32:21Z→02:54:12Z, ledger 시계) — 30분 이내 | ledger 첫·마지막 reservation 시각 |
| GPU-hours (상계) | **≤ 0.364 GPU-h** (wall-clock × 1 GPU) — 0.5 이내 | **측정 주체 결정 등록**(11번 보고 §7 (d) 해소): 포트 8004 vLLM은 공유 서버로 per-call GPU-sec 격리 불가 → **상계 귀속**(wall-clock × 1 GPU)을 GPU-h 기록으로 사용. 실측 소계 아님 |

## 7. Reader Note 품질 평가 결과

`evaluate_reader_note_quality.py` (model-free, GT `e2e-arxiv-2508-11428`, 3 items):

| 지표 | 값 |
|---|---|
| Coverage / Core coverage | **1.0 / 1.0** |
| Open dependency retention | **1.0** (1/1) |
| High-risk missing | **0** |
| 항목별 | key_concept covered(term 4/5), mechanism covered, open_dependency retained |

본 실행의 baseline 품질 점수: S = coverage·core·open-dep 축 전부 1.0 (§3.3 다목적
정의의 L1 측정). 판정은 단일 trial이라 δ와 무관.

## 8. Ledger 정합성

- 예약 29건 / 기각 0건 / ceiling 50 미초과. `budget_scope=workflow`,
  `invocation_id=r0b1-baseline`, 스키마 v0.2 단일.
- **토큰 계측 결측**(§5)으로 ledger↔provider telemetry 대조는 미실시 — §9 조건.
- GPU-h·latency는 ledger에서 제공되지 않아 §6 규약으로 보고(§10-b에 주체
  기재는 등록 완료).

## 9. 다음 반복 평가의 예상 비용 (1-trial 실측 기반)

1 trial = 29 calls / 21m51s wall / GPU-h ≤ wall×1GPU. 반복 변동성(repeat)
1회 ≈ 동일 규모. 사전 등록 산출식(12번 보고 §5) 적용:

| 단계 | calls | wall-clock | GPU-h(상계) |
|---|---|---|---|
| δ calibration (baseline repeat ×4, `calibrate.py`) | ~116 | ~1.5 h (연속 30분×4회 — wall-clock 상한은 per-trial 적용으로 재확인 필요) | ~1.46 |
| R0-b 후속 (evolve 8편 ×1 trial) | ~232 | ~3 h | ~2.9 |

⚠️ repeat ×4 연속 실행 시 GPU-h 상계 1.46 GPU-h > 0.5 — **정책 재산정 필요**(지시
10번 항목: 실측 결과로 RRSI 전체 예산 재산정). 권고: GPU-h 상한을 per-trial 0.5
유지하되 δ calibration에 별도 상한(≈2 GPU-h) 등록, 또는 repeat을 2회로 축소.
이 결정은 다음 승인 요청에 포함.

## 10. 발견 결함 및 처리

| # | 결함 | 처리 |
|---|---|---|
| (a) | R1 설계 Evolve(agent-memory 중심 6편) ↔ R0-a holdout denylist(agent-memory 10편 전체) 충돌 — 분할 freeze 부재 | 다음 R1 라운드 전 분할 freeze(3.1 규약 #5) 필요. 본 실행은 denylist-안전 논문으로 회피 |
| (b) | writer/polish 기본 모델 `qwen-coder`가 로컬 서버에 미등록(404) — trial 중단 요인 | `--polish-model` 명시로 해소. preflight에 "writer·polish·vision·embedding 4경로 모델 등록 확인" 추가 |
| (c) | provider-usage 토큰 telemetry 싱크 미바인딩 — 토큰 계측 결측 | 다음 실행 preflight에 `AI_PAPERS_PROCESS_TELEMETRY_EVENTS` 바인딩 필수화 |
| (d) | GPU-h 격리 불가(공유 vLLM) | 상계 귀속 규약 등록 완료(§6) — 지시 측정 주체 항목 해소 |

## 11. GO / HOLD / STOP 판정 — **GO**

- 지시 범위 준수: RRSI 진화 루프 0, Candidate Prompt 생성 0, B/C 비교군 0,
  Final Holdout 소비 0, 운영 승격 0. RRSI 코어(`rrsi/` 15파일) 무수정
  (CoreSignature 유지, 전체 테스트 PASS). ai_papers canonical artifact 무수정
  (모든 산출물은 `rrsi/poc/runs/r0b1/` 하위; ai_papers 워킹 트리 변경 없음).
- **GO**: 데이터 차단이 실제로 해소됐고, 1-trial 실측(calls·wall·quality)이
  확보됐으며, fail-closed 예산 강제가 실제 동작을 확인.
- **GO의 사전 조건 (2건)**:
  1. §10 (c) — 토큰 telemetry 싱크 바인딩 (preflight 필수).
  2. §9의 GPU-h 정책 재산정 승인 (δ calibration 상한).

**Committed artifacts**: `poc/dataset_manifest.py`, 본 보고. Run 산출물
(source/extraction/manifest/reader run/quality)은 repo 규약(`.gitignore: runs/`)
에 따라 미추적 로컬 artifact로 `poc/runs/r0b1/`에 보관 — dataset manifest hash는
재산정 감사용으로 본 보고에 등록(§3).
