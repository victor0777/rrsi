---
doc_id: poc-rrsi-23-unauthorized-qa-incident
title: Unauthorized QA Execution Incident 등록 및 재개 자격 검증
status: report
updated: 2026-10-28
---

# Unauthorized QA Execution Incident — Accounting, Permit Contract, Resume Eligibility

**Summary.** `3d74ad8` 실행의 호출을 **Authorized 44 + Unauthorized 10 = Total
Observed 54**로 구분 집계(제외 없음). Unauthorized 10건의 token usage는 packet·
ledger·telemetry 어디에도 계측값이 없어 **UNKNOWN**으로 기록(복구 시도 0건 —
usage 정보 부재 확인). Budget Environment 존재만으로는 실행을 승인하지 않는
**Execution Permit 계약**(`poc/execution_permit.py`)을 등록하고 Negative
Regression **12/12 PASS**(모델 호출 0, reservation 0). Reader Note는
**CONDITIONAL**(Content Quality UNVERIFIED 유지). Evidence 불일치 6건 전부
**formatting-level**(content 차이 0). 판정: **HOLD** — Same-paper QA 재개는
Permit 승인 후 가능.

---

## A. Incident Accounting (Workstream A)

| 구분 | Calls | Token Usage |
|---|---|---|
| Authorized Reader Calls (ledger·telemetry 바인딩, paper별 invocation) | **44** (22+22) | **161,453** (in 117,509 + out 43,944, terminal에서 회복) |
| Unauthorized QA Calls (env 미바인딩, `run` step 이탈) | **10** | **UNKNOWN** (미계측) |
| **Total Observed Calls** | **54** | authorized 161,453 + unknown |

- **제외 없는 집계**: Unauthorized 10건은 전체 자원 소비 집계에 포함된다.
- **Usage 복구 시도**: raw packet 10건 검사 → `token_usage`/`usage` 필드 부재
  (call_model이 raw text만 반환, usage 저장 경로 없음). Ledger reservation 0건
  (env 미바인딩), telemetry terminal 0건. → **UNKNOWN 확정**, 실시간 Ledger
  계측값과 혼용 금지. 존재하지 않는 근사치로 채우지 않는다.
- 기존 기록 삭제·덮어쓰기 0 (raw packet·telemetry·reports 전부 보존).

## B. Execution Authorization Permit Contract (Workstream B)

`poc/execution_permit.py` (schema `rrsi-execution-permit/v0.1`) — 첫 모델 호출
전 fail-closed 검증, 7조건:

1. `PERMIT_REQUIRED` — env `AI_PAPERS_EXECUTION_PERMIT`로 지정된 permit 존재
2. `PERMIT_WORKSTREAM` — 실행 workstream == 허용 workstream (알 수 없는
   workstream 자체 거부)
3. `PERMIT_CALL_TYPE` — call type == 허용 (`reader_chain` vs `qa_inference`)
4. `PERMIT_DATASET_PAPERS` — dataset sha256 + **전체** case paper가 허용 집합 내
5. `PERMIT_MODEL_ENDPOINT` — model profile·endpoint 일치
6. `PERMIT_BUDGET` — call/wall 예산 명시 + ledger ceiling 상한 준수
7. `PERMIT_LEDGER` — permit의 ledger 경로 == env ledger 경로 (reservation
   가능성 귀속)

**핵심 원칙**: bound Budget Environment(ledger/telemetry env 존재)는 아무것도
승인하지 않는다 — permit 없거나 scope 불일치면 env가 완비되어도 차단.
invocation_id까지 permit-bound(사건의 "같은 runner, 다른 승인" 재발 차단).

## C. Negative Regression Results (Workstream C) — 12/12 PASS

실제 모델 호출 0회·네트워크 접촉 0으로 검증, 전건 0 reservation:

| 조건 | 결과 |
|---|---|
| Permit 없음 | **BLOCK** (`PERMIT_REQUIRED`) |
| Budget Environment 없음 | **BLOCK** (ledger mismatch) |
| 승인되지 않은 QA 실행 (reader permit + QA scope) | **BLOCK** (`PERMIT_WORKSTREAM_MISMATCH`) |
| Reader 승인 invocation에서 QA 시도 | **BLOCK** (`PERMIT_CALL_TYPE_MISMATCH`) |
| Dataset 불일치 | **BLOCK** (`PERMIT_DATASET_MISMATCH`) |
| Paper Identity 불일치 | **BLOCK** (`PERMIT_PAPERS_MISMATCH`) |
| Budget 초과 (permit > ceiling) | **BLOCK** (`PERMIT_BUDGET_EXCEEDED`) |
| Final Holdout 입력 (미허용 paper) | **BLOCK** (`PERMIT_PAPERS_MISMATCH`) |
| Model Endpoint 불일치 | **BLOCK** (`PERMIT_ENDPOINT_MISMATCH`) |
| Model Profile 불일치 | **BLOCK** (`PERMIT_MODEL_MISMATCH`) |
| Permit 파일 디스크 부재 | **BLOCK** (`PERMIT_FILE_MISSING`) |
| 전 조건 정합 (positive) | **PASS** (7 checks 완성) |

기존 Paper Identity Binding negative tests와 합쳐 **45/45 PASS**.

## D. Reader Note Artifact 판정 (Workstream D)

| 축 | 1802.07862 | 1901.10133 |
|---|---|---|
| Source Identity | **PASS** | **PASS** |
| Artifact Integrity (digest 고정·manifest 등록) | **PASS** | **PASS** |
| Structural Gate (chain 내부 gate, 0 fallback) | **PASS** | **PASS** |
| Content Quality | **UNVERIFIED** | **UNVERIFIED** |
| Calibration Eligibility | **CONDITIONAL** | **CONDITIONAL** |

- GT 기반 Reader Quality 평가 미수행 사실은 **유지**된다(2편 GT fixture 부재,
  22번 보고 §C). "Model-free 기록 = 품질 검증"으로 승격하지 않는다.
- CONDITIONAL의 의미: identity·integrity·gate가 PASS여도 GT 검증이 없는 한
  reader 품질 의존 평가(reader-context QA의 reward 측 재사용)는 GT 확보 또는
  승인자 명시적 수용을 전제로 한다.

## E. Evidence Alignment (Workstream E) — Scorer 무수정

QASPER highlighted_evidence ↔ Governed arXiv HTML v1 정합 조사:

| 논문 | Evidence 문장 | Full-match | 불일치 | 분류 |
|---|---|---|---|---|
| 1802.07862 | 9 | 5 | 4 | 전부 formatting-level |
| 1901.10133 | 5 | 4 | 1 | formatting-level |

**불일치 6건의 구체 귀속 (content 차이 0)**:

1. `1802.07862` (3건): QASPER full_text의 **플레이스홀더 표기** — gold
   "upper row in Figure FIGREF19" ↔ 원문 "upper row in Figure 3" (dataset이
   그림 번호를 FIGREF로 대체). 검사 결과 문장 내용은 원문에 존재.
2. `1802.07862` (token-format 3건): 인용 마커(`BIBREF27`류)·수식 마크업 중복
   등 token 정규화로 해소되는 표기 차이.
3. `1901.10133` (1건): gold "FLOAT SELECTED: Fig. 1. Proposed methodology" ↔
   원문 "Fig. 1: Proposed methodology" — "FLOAT SELECTED:"는 dataset 측
   extraction artifact(플로트 캡션 라벨), 실제 캡션 내용은 원문 존재.

**Offset / Source Reference 비대응 기록 (별도)**:

- 본 lane에 **공유 offset 공간이 없다**: gold evidence offset은 dataset
  full_text(flatten) 기준, 예측 evidence offset은 note artifact 기준 — 서로
  다른 문서·다른 digest. (full_text flatten round-trip 8/8, note 기준
  literal 검증 — 각자 유효.)
- **비대응 항목**: gold `highlighted_evidence` 문자열은 arXiv HTML v1 원문에
  대해 **offset binding이 없다**(위 표기 차이로 literal/offset 어느 쪽으로도
  직접 대응 불가). 이는 dataset↔원문 계층의 비대응이며 rrsi glue 구현 결함이
  아니다. 별도 기록으로 유지, 향후 evidence 정합 work order의 입력.
- Scorer 무수정. Scorer mapping 왜곡(공란 주석→Unanswerable)은 19·20번 보고의
  등록 상태 그대로 유지.

## F. 재개 판단 (Workstream F)

1. **Unauthorized QA 10건 비용**: §A — calls 10 (집계 포함), tokens UNKNOWN
   (미계측, 근사 대체 없음).
2. **Execution Permit 계약**: §B (7조건, environment 독립, invocation-bound).
3. **Negative Regression**: §C — 12/12 PASS, 호출 0·reservation 0.
4. **Reader Note Artifact**: §D — Source/Integrity/Gate PASS, Content
   Quality UNVERIFIED, Calibration Eligibility CONDITIONAL.
5. **Evidence Alignment**: §E — 불일치 6건 전부 formatting-level, content
   차이 0, gold↔원문 offset 비대응 별도 기록.
6. **Same-paper Reader-context QA 재개 가능 여부**: **가능 — 단 Permit 승인
   전제**. 준비 완료: per-paper note(digest 고정), binding PASS ×2, env
   fail-closed 가드(`CALL_BUDGET_ENV_ABSENT`), permit 계약. 승인 시 실행
   순서: permit 발급 → env 바인딩 → identity+permit 검증 → 10 calls.
7. **잔여 위험**: ① Unauthorized token usage UNKNOWN(집계 불완전 유지),
   ② GT 미검증 reader note(CONDITIONAL), ③ scorer mapping 왜곡(등록 유지),
   ④ permit 계약이 runner 코드에 wire된 상태가 아님(계약·테스트 등록 단계 —
   본 지시 제한 내, next permit 발급 시 wire 필요).
   **판정: HOLD** — 위험 ①④가 계약·집계 완전성에 남아 STOP 아님.

## 제한사항 준수

신규 모델 호출 **0**, Reader Pipeline 실행 **0**, RRSI Evolution 0, Final
Holdout 소비 0, Scorer 수정 0, Artifact 삭제 0, ai_papers 운영 상태 변경 0,
신규 worktree 0.
