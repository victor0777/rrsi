---
doc_id: poc-rrsi-46-r7-d2b-unseen-dataset-audit
title: R7-D2B Unseen Dataset Audit R1
status: report
updated: 2026-10-29
---

# R7-D2B — Unseen Dataset Audit R1 (문서 46)

읽기 전용 재검증, 모델 호출 0, Reader Note·Gold 생성 없음.
기존 증거 재사용 원칙 — 전면 재스윕 없이 부족 항목만 보완.

## 1. 기존 후보 재검증 (A1)

기존 Manifest 확인 완료 — 숫자를 확정 사실로 간주하지 않고 원본 대조:

| Manifest | 내용 확인 |
|---|---|
| `poc/runs/r7-evaluation/unseen-candidates.json` | 8편 `UNSEEN_CANDIDATE` (four_axis_matrix 포함), 2편 `EXPOSED` 제외 (1911.06964, 1808.09111 — QA fixture 근거) |
| `poc/runs/r7-evaluation/separation-proof.json` | 스키마 `r7-separation-proof/v0.2`, Development {1802.07862, 1901.10133}, 교집합 ∅ |
| 문서 40/41/42 | 계약·감사·예산 문서와 manifest 일치 |

## 2. 4축 Exposure Audit — R1 보완 (A2)

기존 4축 기록에 **보완 스윕** 추가 (file 내용 grep + git history):

| Axis | 보완 검사 방법 | 결과 (8편 전원) |
|---|---|---|
| E1 ID/Version/계열 | registry/manifest 구조 확인 + poc/runs·docs 내용 grep | 무적중 |
| E2 ai_papers Note 이력 | `ai_papers/data/runs`, `docs/eval/reader-note-quality` (GT 15) grep | 무적중 |
| E3 Judge Prompt 개발 노출 | poc/runs 내용 grep + `git log --all -S <paper_id>` | dataset manifest 커밋(2967056) 자체만 적중 — 해당 커밋은 후보 발견 자료이며 judge 설계 노출 아님 |
| E4 Gold/Perturbation 설계 | review-packets*, perturbation-audit 원문 grep | 무적중 |

**확인되지 않은 영역 (전원 공통):** 구조화 레지스트리 밖의 비공식
사본·로컬 캐시·대화형 세션 이력. **"증거 없음 ≠ 미노출" caveat 유지.**

## 3. 후보 판정 (A3) — 변동 없음

`UNSEEN_CANDIDATE` 8 · `EXPOSED` 2 · `INSUFFICIENT_EVIDENCE` 0 ·
`EXCLUDED`(Development) 2. 판정 이유·Evidence Reference는
`exposure-evidence-matrix-r1.json` 참조. 후보 자격만 의미.

## 4. Dataset Separation Proof R1 (A4)

`separation-proof-r1.json`: 집합 정의 + 기계 검증
(Development/Calibration/JudgeDebug/GoldPerturbation ∩ Unseen = ∅,
버전·계열 포함). **범위 한정 명시: 구조화된 노출 이력에 대한 분리
증명일 뿐, 검색되지 않은 이력의 부재 증명이 아님.**

## 5. Unseen 데이터 보호 (A5)

본 작업에서 두 역할(Curator/Designer)을 동일 실행 주체가 수행:

| 기록 항목 | 내용 |
|---|---|
| 접근 자료 범위 | 후보 paper_id·제목·주제·글자수·digest (manifest 레벨) |
| 접근 목적 | 독립성 재검증, Reader Note/Gold 준비 상태 조사 |
| 작업 순서 | 계약 구현(D2A.1) → 감사(D2B) — Unseen 내용이 계약 변경에 선행 |
| 평가 계약 변경 여부 | D2A.1에서 변경; Unseen 논문 내용·Gold·Perturbation 미참조 |
| Unseen 내용 개발 유입 | **없음** — 논문 전문을 읽지 않았고 prompt·Gold·fixture에 반영 안 함 |

## 6. Reader Note / Gold 준비 (Workstream B 요약)

- Reader Note: 전원 `MISSING` (생성 이력·모델·run id·digest 전무)
- Gold: 전원 `ABSENT`, Quality Gate `NOT_PERFORMED`, Freeze `NOT_FROZEN`
- 노출 이력 있는 Note 표시: 해당 없음 (Note 자체가 없음)

상세: `candidate-audit-r1.json` §reader_note_gold_availability.
