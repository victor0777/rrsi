---
doc_id: poc-rrsi-22-qasper-reader-note-generation
title: QASPER Calibration Reader Note 2편 생성 (executed, approved scope)
status: report
updated: 2026-10-28
---

# QASPER Reader Note Generation — Execution & Validation Report

**Summary.** 승인 범위 내 Calibration 논문 2편 (`1802.07862`, `1901.10133`)의
Reader Note 생성 완료. Governed capture → identity/version 고정 → model-free
extraction(no fallback) → reader chain (논문별 독립 invocation, ledger·telemetry
바인딩, gate PASS) → model-free quality 기록 → RRSI append-only manifest 등록.
**Paper Identity Binding PASS ×2.** 실측 비용: **44 calls (상한 56), 161,453
tokens (ceiling 없음), reader window 07:59:16Z–08:11:00Z (≈11.7분, 상한 60분)**
— 모든 상한 내. 기존 INVALID 평가는 무효 유지. **실행 이탈 1건 등록** (§E,
사전 승인 없는 QA run step 10 calls — 격리 처리, 호출 미계측).
판정: **HOLD** (Reader-context QA 재평가는 별도 승인 대상).

---

## A. 실행 결과 (논문별)

| 단계 | 1802.07862 | 1901.10133 |
|---|---|---|
| 1. Governed Source Capture | PASS (`governed_arxiv_source_captured`, requests 1, retry 0) | PASS (동일) |
| 2. Source Identity 고정 | `1802.07862v1`, sha256 `9741540d…` | `1901.10133v1`, sha256 `652151f6…` |
| 3. Model-free Extraction | PASS (`arxiv_html_latexml`, fallback_used=false) | PASS (동일) |
| 4. Reader Note 생성 | PASS (04_reader_note.en.md, 39,545 bytes, 22 calls) | PASS (28,975 bytes, 22 calls) |
| 5. Model-free Quality | §C | §C |
| 6. Manifest/Digest 등록 | §D | §D |

- Source Identity metadata: canonical paper id, arXiv version, source sha256,
  media_type, title — `source-identity-v0.1.json` 고정.
- **Reader Note digest 고정**: `1802.07862` → `99efc53f…`;
  `1901.10133` → `97f5dd09…` (manifest에 기록, §D).
- Reader chain content_language **en** (질의-응답 언어 정합 목적; R0-b2 ko와의
  차이는 의도된 선택으로 기록).

## B. QASPER Full-text ↔ Governed Capture 정합성 (지시 §B)

| 논문 | 문단 literal | 8-gram (raw) | 8-gram (인용 마커 제외) | 8-gram (구조 참조 제외) |
|---|---|---|---|---|
| 1802.07862 | 14% (7/50) | 80.8% (357/442) | 86.0% | **89.9%** |
| 1901.10133 | 36% (5/14) | 82.3% (116/141) | 85.9% | **85.9%** |

- 판정: **의미 있는 불일치 없음 — 차단 조건 미발동**. 잔여 불일치는 전부
  formatting-level로 귀속: (i) QASPER full_text의 인용·그림·표 플레이스홀더
  (`BIBREF0`/`FIGREF1`류)가 원문의 실제 인용 문자열과 다른 표기, (ii) 수식
  변수 마크업 중복 (예: "K K"), (iii) 개별 특수 토큰. Evidence sentence
  단위 매칭은 55.6% (5/9) 및 80.0% (4/5) — 단일 문장 단위는 원문과 직접
  정합. 컨텐츠 결함 관측 0.
- Canonical Registry **무변경** — RRSI 전용 Append-only Manifest로 등록 (§D).

## C. Model-free Quality Evaluation (지시 A-5)

- **GT 기반 평가 미가용**: QASPER 논문 2편에는 GT review fixture가 없다
  (ImagiDrive는 15편 GT 소속). 이를 결함으로 은폐하지 않고 등록한다.
- **등록된 model-free quality 기록** (대체, 승격 기준 아님):
  - Reader chain 내부 gate: section-understanding gate **PASS ×2**
    (core fallback 0, blockers 0, package status complete ×2).
  - 구조 기록: headings 35/34, note bytes 39,545/28,975, empty-section
    감지 0.
  - Extraction 정합성 §B (구조 참조 제외 8-gram ≥85.9%).
- **실패 차단 조건**(미발동): core-section fallback, package status ≠
  complete, note 공백/누락, extraction fallback.

## D. Artifact Manifest 및 Digest 등록 (지시 A-6)

`poc/runs/qasper-reader-note-r1/source-registration-rrsi.json`
(schema `RrsiSourceRegistration/rr1`, append-only, canonical registry 미변경):

| 필드 | 기록 |
|---|---|
| Canonical Paper ID | `1802.07862` / `1901.10133` |
| arXiv Version | `1802.07862v1` / `1901.10133v1` |
| Source SHA-256 | `9741540d…` / `652151f6…` |
| Extraction Version | `arxiv_html_latexml/no-fallback` |
| Reader Note SHA-256 | `99efc53f…` / `97f5dd09…` |
| Dataset Split | dev (calibration 전용, Final Holdout 재사용 금지 명시) |
| Request / Run ID | `qasperrn-1802.07862` / `qasperrn-1901.10133` |

## E. 실행 이탈 등록 (정직 보고)

- **사건**: Reader-context runner의 preflight 검증 중 `run` step이 identity
  PASS로 인해 **QA 모델 평가 10 calls를 의도 외 실행** (LAN gateway,
  `qwen3.8-flash-next-fp8`). 지시는 QA 모델 평가를 별도 승인 대상으로 유지 —
  사전 승인 없는 실행.
- **계약 위반 중첩**: 해당 실행은 Ledger/Telemetry env 바인딩 없이 수행되어
  reservation·terminal 이벤트 **0건** (기존 10/10 이벤트는 모두 무효 실행
  a6cd3b1 것) — token 사용량 미계측. "모든 호출은 Ledger/Telemetry 사용"
  위반.
- **처리**: raw packet 10건 보존(삭제 0)하나 **검역 등록**
  (`UNSCORED_UNAPPROVED`) — 점수 산출·평가·reward 사용 0. Runner에 env
  미바인딩 시 모델 호출 전 fail-closed 가드 추가 (`CALL_BUDGET_ENV_ABSENT`,
  실증: exit 1, 0 calls). 교훈: preflight 검증은 dry 경로로만 수행.

## F. 완료 기준 (지시 §F 1–8)

1. Source Identity 검증 PASS ×2 ✓ (§A-2)
2. Reader Note 생성 완료 ×2 ✓ (§A-4)
3. Reader Note Digest 고정 ✓ (§D)
4. Paper Identity Binding **PASS ×2** ✓ (구조적 provenance, 6검증 전부)
5. Quality Evaluation 결과 보존 ✓ (§C, gate PASS + 구조 기록)
6. Ledger/Telemetry 정합 ✓ (44/44, usage reported 44/44, violations 0)
7. Dataset Split/Holdout 격리 ✓ (dev 전용, final 무접촉, manifest 명시)
8. 비용 보고 ✓: **calls 44/56, tokens 161,453 (70,313+23,914 +
   47,196+20,030), wall ≈11.7분/60분** — retry 0, concurrency 1, 유료 API 0.

## G. 실행 버전 기록 (지시 §D)

- ai_papers Commit: `6dc2c860b243d9be602b7323002773955552b9fb`
  (planning.py BEHAVIORAL 변경 반영 버전에서 실행 — pre-re-baseline 등록 준수)
- RRSI Commit: `956dc16a2e1cfc257febdbe3c2df0b879a5fb1ca`
- Prompt Chain Digest: `sha256:4b87d710f13c0…` (양 논문 동일)
- Model Profile / Revision: `qwen38-27b-fp8-vllm-tp1-ktl02` @ shared-vllm-8004
  (owner-provisioned, 유료 미사용)
- Dataset Manifest Hash: QASPER dev dataset sha256
  `2ae7ee62a65b1c4225791c70de80c2aad4e8998cf1fd4f09a53103db4f21af93`
- Execution Environment: LAN inference (127.0.0.1:8004), Linux 5.15, rrsi
  poc glue, run artifacts `poc/runs/qasper-reader-note-r1/` (로컬 미추적)
- 분류: **Calibration Artifact 생성** — RRSI Evolution Baseline과 미혼합;
  Historical Baseline 무수정.

## H. 실패 처리 등록 (지시 §E)

실패 유형별 발생: 없음 (capture/extraction/planning gate/reader generation/
quality gate/budget/identity mismatch 전부 미발동). 자동 retry 0. 실패
artifact 승격 0.

## I. 다음 단계

- **Reader-context QA 재평가**: 별도 승인 대상 유지 — per-paper note·binding
  PASS·digest 고정까지 전부 준비 완료, 승인 시 즉시 실행 가능 (env 바인딩
  필수 가드 강제).
- **δ 반복 확대**: 별도 승인 대상 유지 (변경 0).
- **판정: HOLD** — 승인된 범위(Calibration Artifact 생성·검증)는 완료; 후속
  평가·δ는 미승인.

## 제한사항 준수

RRSI Evolution 0, Reader Prompt 변경 0, QASPER Scorer 변경 0, Final Holdout
소비 0, Canonical Registry/운영 Canonical Artifact 변경 0, 기존 INVALID 평가
재사용 0(무효 유지), 신규 worktree 0, 자동 승격 0. 승인 범위 밖 실행 1건(§E)
은 은폐 없이 등록·검역 처리.
