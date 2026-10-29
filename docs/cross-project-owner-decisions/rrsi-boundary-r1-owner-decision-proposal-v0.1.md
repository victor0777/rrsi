---
doc_id: rrsi-boundary-r1-owner-decision-proposal-v0.1
title: RRSI Owner Decision Proposal — Four-Project Architecture Boundary R1
status: PROPOSED
decision_proposal: ACCEPT_WITH_CHANGES
owner_confirmation: PENDING — 본 기록은 작성자(agent) 승인안이며 Owner 승인
  완료로 기록하지 않는다. 확정은 본 기록에 대한 Owner 명시 승인 커밋으로만
  성립한다.
updated: 2026-10-29
append_only: true
authority_note: 기존 기술 검토(rrsi 독자 분석 + 검토의견 2026-10-29, workbench
  접수 0610d81/75c713c)를 재사용 — 재검토 반복 없음. 타 repo read-only.
approval_request:
  workbench_commit: f22f7fc
  request_doc: docs/cross-project-owner-approval-request-r1.md
  review_basis: Architecture Boundary R1 v1.0.2
  basis_blob_sha256: 6739b576a0692d5b156dc2f5a8c34b08e58efa049d9544f4d02d58d48a1d88a9
  basis_blob_commit: f9b1008
  current_blob_sha256_at_f22f7fc: b0f281da4feb6425 — v1.0.2 이후 상태 갱신
  커밋(9168d2c, 6a340b6) 포함으로 요청 문서 §1 표기와 정합
---

# RRSI Owner Decision Proposal — Boundary R1 (Q3·Q4)

## 1. 공식 결정 제안 — **ACCEPT_WITH_CHANGES**

### 결정 근거 (재사용 근거 요약 — 신규 반복 검토 없음)

1. 역할 매핑 1:1 수렴 — rrsi 독자 분석(§1 매핑, RewardContribution 규약)과
   workbench 경계안이 독립적으로 동일 결론. 양측 근거 접수 완료
   (0610d81 독립 검증 포함).
2. 무쓰기·무삭제 원칙(테스트 포함, 무예외) **수용** — 실제 workspace
   destruction 사고(auditd 적발, workbench `417f674`/`020f284`,
   ai_papers `d5c5657e1`)에 대한 정합 처방.
3. Gold 격리·요약 metric 소비 — rrsi PoC의 실제 운용(frozen fixture bytes
   read-only, sha256 준수)과 이미 일치.
4. **이전 검토의 C1–C3는 workbench가 이미 반영**(75c713c: rrsi 행 frozen
   fixture bytes 명시, 인접 repo 등재, Q4 책임 인수) — 잔여 변경 요청 없음.

### 수용 상태 표현 (지시 §2-3)

| 항목 | 수용 |
|---|---|
| 책임 매트릭스(4-project) | **수용** |
| 운영 데이터 무쓰기·무삭제(테스트 포함, 무예외) | **수용** — rrsi 운영 경로도 동일 규약 적용 |
| 공식 제공 API | History JSONL, 후보 규약, RewardContribution 소비면 (설계 확정) |
| 공식 소비 API | workbench 경유 요약 metric(`BenchmarkScore`, Q3 계약) + frozen fixture bytes |

## 2. Q 항목별 결정 (지시 §4)

### Q3 — Gold-free Evaluation Result(`BenchmarkScore`) 소비 계약: **수용**

- Gold bytes·비공개 평가 세부 미제공 규약 **수용** — rrsi는 요약 metric만
  소비하며 scorer·gold·fixture 분할을 복제하지 않는다(기존 규약 유지).
- 필수 필드 수용: `{benchmark_id, split, answer_f1, evidence_f1,
  case_count, scorer_policy_version, computed_at}`.
- **조건**: 모든 record에 `scorer_policy_version` 필수 — 버전 부재
  record는 무효로 처리하며 δ 소비에서도 제외.

### Q4 — Improvement Candidate / Promotion 계약: **수용 + 승인 책임 인수 확정**

- 제출면: History JSONL(edit별 component/hypothesis/score/cost/verdict) +
  후보 규약 — 기존 실존 산물 재사용.
- **운영 승격은 대상 프로젝트 Owner 단독 권한 — 수용**(rrsi는 승격 요청만).
- 조건: Promotion 스키마 초안은 rrsi 소관 문서 WO로 별도 작성(신규 API
  구현 없음, 본 결정의 병목 아님).

### Workbench 독립 평가 권한: **수용**

- 채점·비교·qualification 판정은 workbench 단독 — rrsi 산출 개입 없음.

### 개선 후보 실행 격리: **수용**

- 후보 편집은 격리 공간(worktree 등)에서만, 검증용 운영 경로와 결과
  artifact를 혼합하지 않는다 — 기존 perturbation-audit 격리 운용과 동일.

## 3. 승인 조건과 미해결 의존성 (지시 §5)

### 승인(확정 시) 조건

1. `scorer_policy_version` 필수 규약이 workbench 계약 스키마에 명시될 것
   (Q3).
2. Promotion 승격은 대상 Owner 승인 기록 없이는 실행 불가할 것 — fail-closed
   (Q4).
3. CI Isolation Guard·Runtime Isolation 미구현 기간에 boundary를 강제
   통제가 아닌 문서화된 계약으로 표기할 것 — 완전성 주장 금지 유지.

### 다른 Owner 결정이 필요한 항목 (rrsi가 갈음 불가)

| 항목 | 대기 |
|---|---|
| Q7 — workbench의 POST 소비 허용 | ai_papers Owner (rrsi는 POST에 직접 의존 없음) |
| Q8 — 공급자 내부 CLI와 외부 소비자 경계 | ai_papers Owner |
| Q5 — Agent Task REST API 계약 | researcher Owner (rrsi는 workbench 경유 소비가 현재 설계 — 직접 의존 없음) |

### 현재 구현과의 차이

- rrsi PoC는 fixture bytes를 workbench dataset 경로에서 직접 독해(C1으로
  명시된 read-only frozen bytes) — "요약 metric만"은 δ 이후 단계 구현 계약.
  차이는 R1 본문(상태 표기)과 일치, 신규 격차 없음.
- `BenchmarkScore`·Promotion 면은 NOT_READY(문서 WO 대기) — rrsi 현재 HOLD
  판정과 무관.

## 4. 기록 방법

- 본 기록은 append-only 결정 기록으로 커밋 — workbench가 provenance와 함께
  registry에 접수하는 선례(researcher `a4b147ee`)를 따름.
- **상태: PROPOSED — Owner 승인 확정 아님.** Owner 명시 승인 후에만
  registry formal 승인으로 등록 가능.
