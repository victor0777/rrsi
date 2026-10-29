---
doc_id: poc-rrsi-41-r7-d2-unseen-candidate-audit
title: R7-D2 Unseen Candidate Audit
status: report
updated: 2026-10-29
---

# R7-D2 — Unseen Candidate Audit (문서 41)

읽기 전용 조사, 모델 호출 0, Reader Note 생성 없음.
Manifest: `poc/runs/r7-evaluation/unseen-candidates.json`,
`poc/runs/r7-evaluation/separation-proof.json`.

## 1. 후보 논문 (QASPER dev-v0.3, 281편 중 8편)

| Paper ID | 원문 길이(chars) | 주제 | 후보 근거 |
|---|---|---|---|
| 1912.01214 | 25,990 | 언어쌍 간 전이학습 | 다양성(다국어), 무노출 |
| 1810.08699 | 17,939 | 아르메니아 NER | 저자원 언어, 무노출 |
| 1704.06194 | 29,150 | 관계 탐지 | 정보 추출 과제, 무노출 |
| 1809.04267 | 24,368 | 기계 독해(MRC) | 추론 과제, 무노출 |
| 1912.04961 | 29,279 | 임상 대화 정보 추출 | 실용 도메인, 무노출 |
| 2004.03354 | 17,525 | PTLM 도메인 적응 | 사전학습 모델, 무노출 |
| 1909.08089 | 28,109 | 단일 문서 추출 요약 | 요약 과제, 무노출 |
| 1801.05147 | 35,284 | 크라우드소싱 라벨 획득 | 데이터 구축, 무노출 |

전원: 원문 확보 ✓ (frozen QASPER dev, dataset digest `2ae7ee62…`), 기존
Reader Note 없음, Locator 지원(단락 기준) ✓. **예상 입력 토큰은
chars/4 하한 추정치이며 실측 아님** (Reader Note가 아직 없음).

## 2. 제외 후보 (EXPOSED)

| Paper ID | 사유 |
|---|---|
| 1911.06964 | QA fixture final 세트에 사용 (`research_benchmarks/…/fixture/final/`) |
| 1808.09111 | QA fixture dev 세트에 사용 |

## 3. 4축 노출 이력 Matrix (요약 — 상세는 manifest)

| 축 | 검사 범위 | 결과 (8후보 전원 공통) |
|---|---|---|
| ID·버전 중복 | Development(1802.07862/1901.10133) 계열 | 무충돌 |
| ai_papers Note 생성·평가·Calibration 이력 | `ai_papers/docs/eval/reader-note-quality/` (GT 15), `ai_papers/data/runs/` 전체 스윕 | 무적중 |
| Judge Prompt 개발·디버깅 노출 | `poc/runs/` 전체 스윕 (dataset 파일 자체 제외) | 무적중 |
| Gold·Perturbation 설계 자료 | `review-packets*`, `perturbation-audit` 원문 출처 | 무적중 |

**주의 (§B2):** "증거 없음 ≠ 미노출" — 스윕은 구조화된 레지스트리·
Manifest·Run Metadata를 포함하나 커버리지에 한계가 있고, 각 후보
manifest에 `caveat`으로 기록. 확정 판정은 Owner 검토 시점 자료 기준.

## 4. 데이터 분리 증명 (§B3)

- Development = {1802.07862, 1901.10133}; Unseen 후보 8편 — **교집합 ∅**,
  버전·계열 중복 없음 (`separation-proof.json`).
- Challenge는 Unseen 후보 논문 위의 별도 평가 층 (문서 38 §2 계약 유지).
- **BLOCKED_CONFLICTED 13건·EVOLVE 2건·Final Holdout: 소비·재할당 0.**

## 5. 판정

| 상태 | 수 | 대상 |
|---|---|---|
| `UNSEEN_CANDIDATE` | 8 | 위 8편 (E1 Admission을 의미하지 않음) |
| `EXPOSED` | 2 | 1911.06964, 1808.09111 |
| `INSUFFICIENT_EVIDENCE` | 0 | — |
| `EXCLUDED` | Development 2편 (설계상 배제) | — |
