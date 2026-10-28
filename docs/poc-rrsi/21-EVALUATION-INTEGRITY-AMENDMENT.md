---
doc_id: poc-rrsi-21-evaluation-integrity-amendment
title: Paper Identity Binding contract, a6cd3b1 invalidation, Reader Note readiness
status: report
updated: 2026-10-28
---

# Evaluation Integrity Amendment — Paper Identity Binding

**Summary.** 커밋 `a6cd3b1`의 Reader-context QA는 실행·계측 계약은 PASS였으나
**Paper Identity 불일치 상태에서 모델 호출을 수행** — 평가를
**INVALID_CONTEXT_MISMATCH**로 분류하고 Reward Calibration·δ 추정·Evolution
Candidate 비교에서 **제외**한다. 신규 계약
`poc/paper_identity_binding.py`(구조적 provenance 전용, fail-closed 사전
검증)를 등록하고 Negative Test 9건을 PASS로 검증한다. Calibration 논문 2편은
ai_papers Source Registry **미등록** 상태이며 Reader Note 미생성 — 본 단계에서
생산은 수행하지 않고 준비 상태만 확정한다. 판정: **HOLD** (Reader Note 생산
승인 전제).

---

## A. Paper Identity Binding 계약 (Workstream A)

- 신규 모듈 `poc/paper_identity_binding.py` — 사전 실행(preflight) 계약,
  모델 호출 전 fail-closed 차단. 제한사항 준수: 신규 모델 호출 0, 신규
  Reader Pipeline 실행 0.
- **식별 근거는 구조적 provenance 전용**: reader run-manifest `source_id`
  → extraction `source.json`(동일 source_id 대조) → `source-identity-v0.1.json`
  (canonical arxiv base id + version + sha256). Markdown 제목·헤딩·파일명은
  식별 근거로 **불인정**(Negative Test로 강제).
- 6필수 검증 항목과 대응:

| 필수 항목 | 계약 검증 |
|---|---|
| 1. QASPER Question Paper ID | `QUESTION_PAPER_ID_PRESENT` + 형식 검사 |
| 2. Reader Note Source Paper ID | `NOTE_SOURCE_PAPER_ID_RESOLVED` (run↔extraction source_id 상호 대조) |
| 3. Source Version | `SOURCE_VERSION_CONSISTENT` (note version == 바인딩된 기대값; question 측은 fixture snapshot `v0.3` — 존재·기록 필수, 이종 scheme 간 비교 없음) |
| 4. Reader Note Artifact Digest | `NOTE_ARTIFACT_DIGEST_VERIFIED` (sha256 == adapter 바인딩 digest) |
| 5. Source Registry / Artifact Manifest 연결 | `REGISTRY_LINK_PRESENT` (`ai_papers/data/source-registration-r1.json` 항목 존재 + version·sha256 정합) |
| 6. Dataset Split / Holdout 정책 | `SPLIT_NOT_ALLOWED`(final 거부) + `FINAL_HOLDOUT_REFUSED` + `PAPER_IDENTITY_MISMATCH`(note paper == question paper) |

- `poc/qasper_readercontext_calibration.py`의 `run()`에 preflight 삽입
  (additive). 차단 시 `FAIL_CLOSED/PAPER_IDENTITY_BINDING` 출력, exit 1.

## B. Negative Test 결과 (Workstream B)

`poc/tests/test_paper_identity_binding.py` — **9/9 PASS**, 전건 차단 조건에서
모델 호출 0회·신규 Ledger 예약 0건 확인:

| 조건 | 결과 |
|---|---|
| 동일 논문·동일 버전 | **PASS** (binding 완성) |
| 다른 논문 | **BLOCK** (`PAPER_IDENTITY_MISMATCH`) |
| Paper ID 누락 | **BLOCK** (`QUESTION_PAPER_ID_PRESENT`) |
| Source Version 불일치 | **BLOCK** (`SOURCE_VERSION_MISMATCH`) |
| Artifact Digest 불일치 | **BLOCK** (`NOTE_ARTIFACT_DIGEST_MISMATCH`) |
| Source Registry 연결 불가 | **BLOCK** (`REGISTRY_LINK_ABSENT`) |
| Final Holdout 입력 | **BLOCK** (`FINAL_HOLDOUT_REFUSED`) |
| final split 자체 | **BLOCK** (`SPLIT_NOT_ALLOWED`) |
| Markdown 제목으로만 일치(파일 수정·digest 재바인딩) | **BLOCK** (`PAPER_IDENTITY_MISMATCH`) |

전체 PoC 테스트 33/33 PASS (기존 24 + 신규 9).

## C. 기존 평가 INVALID 등록 (Workstream C)

커밋 `a6cd3b1` Reader-context QA 분류:

| 축 | 판정 |
|---|---|
| Execution Integrity | **PASS** |
| Telemetry / Ledger | **PASS** (10/10, violations 0) |
| Paper Identity | **FAIL** (ImagiDrive 2508.11428 노트 ↔ QASPER 1802.07862/1901.10133 질의) |
| Evaluation Validity | **INVALID_CONTEXT_MISMATCH** |
| Reward Eligibility | **BLOCKED** |

- 기존 실행 기록(`poc/runs/qasper-readercontext-calibration/`, 보고 20번,
  커밋 a6cd3b1)은 **삭제·덮어쓰기 없이 보존** — 본 문서가 별도의 정정·무효화
  판정 기록이다.
- 무효 결과는 Reward Calibration, δ 추정, Evolution Candidate 비교 어디에도
  투입되지 않는다(사용 등록 0). 20번 보고의 진단 테이블은 "조건 관측"으로만
  가치가 있으며 점수로서는 무효.
- 참고: 동일한 binding 계약은 본 단계의 실상태에서 즉시 차단한다
  (`REGISTRY_LINK_ABSENT` — 2508.11428 미등록, `PAPER_IDENTITY_MISMATCH` —
  논문 불일치). 실증 실행으로 확인 (exit 1, 신규 예약 0건).

## D. QASPER 논문 2편 준비 상태 (Workstream D)

대상: `1802.07862` (SnapCaptions/MNER), `1901.10133` (unsupervised sentence
ordering). **본 단계에서 Reader Note 신규 생성 0.**

| 확인 항목 | 1802.07862 | 1901.10133 |
|---|---|---|
| 1. ai_papers Source Registry 등록 | **미등록** (registry keys: 2502.19645, 2510.26742, 2603.19199만) | 동일 |
| 2. Full-text Source 접근 | ai_papers canonical raw 미보유; **research_benchmarks dataset 내장 `full_text` 존재**(qasper-dev-v0.3, frozen) — QA 조건으로는 접근 가능하나 ai_papers pipeline 입력으로는 governed capture 필요 | 동일 |
| 3. Extraction Artifact | **없음** (`ai_papers/data/runs/workflows/`에 해당 source 없음) | 동일 |
| 4. Reader Note 생성 가능 | **가능** — R0-b에서 실증된 경로(governed capture → model-free extraction(arxiv_html_latexml) → reader chain) 재사용, content_language en | 동일 |
| 5. 소요 모델 호출·비용 | capture 0 + extraction 0(모델 불필요) + **reader chain ~25 calls/paper, ~101k tokens/paper** (R0-b2 실측) + 품질 평가 0(모델 불필요) | 동일 |
| 6. Split / Contamination | dev fixture 전용; final cohort 무접촉; Calibration 논문은 Final Holdout 재사용 금지 기등록(17번 보고) — **Contamination 위험 낮음**(fixture 준비 시 0 확인) | 동일 |

- 합계 추정: **2편 ≈ 50 calls / ≈ 202k tokens / wall ≈ 45분**(단일 논문
  21m51s × 2, R0-b2 실측치의 단순 외삽 — 사전 등록된 조건부 추정이며
  승인 전 생산 없음).
- 전제 실패 시 fail-closed: capture 불가·extraction 저품질·quality gate
  미통과 시 해당 논문의 reader-context 평가는 생산 중단(차단).

## E. 보고 (Workstream E)

1. Binding 계약: §A. 2. Negative Test: §B (9/9). 3. INVALID 등록: §C.
4. Source 준비 상태: §D (미등록 — capture부터 필요). 5. **Reader Note 생성
   실행 계획**: (i) governed source capture ×2 (0 calls), (ii) canonical
   extraction ×2 (0 calls, 모델 불필요), (iii) reader chain ×2 (~25
   calls/paper, ledger+telemetry 바인딩, retry 0, concurrency 1), (iv)
   model-free quality evaluation (coverage/gate) → PASS 시에만 reader-context
   재평가 후보로 등록. 6. **추가 모델 호출 예산**: ≈50 calls / ≈202k tokens /
   wall ≈45분 (calls fail-closed cap 권장 56, wall cap 60분) — 승인 시
   ledger-ceiling으로 강제. 7. **다음 단계: HOLD** — Reader Note 생산·재평가는
   본 지시 제한(신규 호출 0)으로 승인 대기; 승인 시 §E-5 계획을 그대로 실행
   가능.

## 제한사항 준수

신규 모델 호출 **0**, 신규 Reader Pipeline 실행 **0**, RRSI Evolution 0, Final
Holdout 소비 0, Scorer 수정 0, 기존 실행 결과 삭제 0(보존), ai_papers 운영
Canonical Artifact 변경 0(registry는 읽기만), RRSI 코어 수정 0, 신규 worktree 0.
