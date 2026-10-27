---
doc_id: poc-rrsi-18-r1-upstream-drift-and-integration-review
title: R1 Upstream Drift & Integration Review — U1 impact, isolation, work order, QASPER protocols (static only)
status: report
updated: 2026-10-28
---

# R1 Upstream Drift & Integration Review

**Summary.** 정적 분석 한정(모델 호출 0, 신규 pipeline 실행 0). Workstream A:
planning.py 변경을 **BEHAVIORAL**로 분류(계획 품질 게이트 의미 변경)하되 prompt
텍스트 무변경 — Historical Baseline 보존 무효화 없음, 즉시 재기준 불요. C:
defect work order의 Phase 1~3은 이미 소유자 실행·수용 완료로 확인. D: 두
QASPER 프로토콜 모두 **기존 frozen dataset 내 full_text·evidence 주석으로
구현 준비 완료**(신규 취득 불요). 판정: **HOLD 유지**.

---

## Workstream A — U1 Drift Impact Analysis (지시 1–6)

**비교**: `997e5a1ec` (R0-b1/b2 실행 기준) ↔ `baca09d4c` (보고 시점) — 본 검토
시점 HEAD는 `7a31ad02d`(10-28)로 재이동. planning.py의 해당 변경은 `cd48e01d1`
(10-26) 1건으로 확정(범위 내 재계산).

| 지시 항목 | 결과 |
|---|---|
| 1. 변경 함수·호출 경로 | `_section_heading_matches()` (module-private) — **planning.py:840의 계획 검증 루프에서만 사용**. workflow.py는 planning의 다른 7개 함수를 import하며 이 함수는 미사용 → 영향은 section plan 검증 경로에 한정 |
| 2. Prompt 입·출력 | **무변경** — `prompts.py`, section_plan 프롬프트 어댑터 파일은 diff 없음. 변경은 LLM 출력의 후처리(헤딩 매칭 의미) |
| 3. Section Plan 결과 | BEHAVIORAL — 기존 "부분문자열 무조건 매칭"이 **나머지가 숫자로 이어지는 suffix("page 3"≠"page 30")는 불매칭**으로 강화. matched/missing 집합이 달라질 수 있음. 커밋 메시지 명시: IncompleteReaderPlanError 수정 목적 — 의도된 동작 변경 |
| 4. Reader Note 결과 | 간접 영향 — 게이트 통과/거부 경로만 변화. r0b2-repeat-3에서 관측된 게이트 거부 클래스(`incomplete_section_strategy_fields`)의 매칭 판정이 바뀔 수 있음. 통과 후 노트 생성 경로 무변경 |
| 5. 테스트·계약 | GET/REST 계약 무변경(커밋 범위 확인). reader-note 계약 스키마 무변경 |
| 6. 승인·커밋 이력 | `cd48e01d1` — "new paper processing closure r1"(10-26, KTL Automation): 실패 신규 논문의 소스등록→extraction→reader note→KG→publication 실측 폐쇄 커밋의 일부(운영 폐쇄 성격). 소유자 승인 문구는 커밋 본문에 명시 없음 → 승인 상태 기재 없음(사실만 기록) |

**분류: BEHAVIORAL** — 근거: 게이트 경로의 매칭 의미가 바뀌었고 커밋 자체가
동작 수정 목적으로 기술. NON_BEHAVIORAL 근거 없음, UNKNOWN 아님(호출 경로
완전 추적 완료).

**Historical Baseline 보존**: R0-b1/b2 결과는 pinned `997e5a1ec` 실행으로
무효화 없음. **새 Baseline: 현재 불요** — 근거: (a) Evolution 미승인 상태에서
비교 대상이 없고, (b) 재기준 자체가 모델 호출을 요구. 단 승인 후 첫 Evolution
라운드 진입 시 `cd48e01d1` 이후 commit에서 **1-trial 재기준을 선행 조건으로
등록**(pre/post-drift 비교 무효 방지). 이 판정은 본 보고에 근거 등록 완료.

## Workstream B — 실행 환경 격리 (지시)

- Dirty worktree 현황(읽기 전용 조사, 무변경): untracked 6종 — reset 준비
  문서·스크립트(`prepare_pipeline_data_reset_r1.py`), registry-reconciliation
  리포트, dogfood 입력, 관련 테스트 3개. 운영 canonical artifact 수정 없음.
- 본 검토는 무수정 유지 — 운영 변경·초기화·삭제 0.
- **격리 재사용 가능**: 기존 RRSI 격리(run 산출물을 `rrsi/poc/runs/`에 한정,
  ai_papers는 read-only 소비)는 유효. dirty 트리 문제는 reader run에 영향을
  주지 않았던 실측 근거(r0b1/b2 성공).
- 신규 worktree: **현재 불요**(정적 분석에 파일시스템 스냅샷이 불필요). 모델
  실행 재개 시에만 별도 제안(기존 `.worktrees/` 컨벤션 재사용 — 예: pinned
  commit 스냅샷 워크트리 1개).

## Workstream C — Source Acquisition 정합성 (지시)

**Work Order 4항목 분리 검토**:

| 항목 | 상태 |
|---|---|
| Source Acquisition | **실행 완료 흔적 확인** — work order는 "정확히 3편"을 지정(2502.19645 OpenVLA-OFT, 2510.26742 Running VLAs at Real-time Speed, 2603.19199 FASTER, `data/raw/papers/<id>.pdf`, sha256 등록). 운영 커밋 `cd48e01d1`(10-26)이 신규 논문 소스 등록·파이프라인 폐쇄를 실측 — Phase 1~2에 해당하는 작업이 소유자 실행으로 존재 |
| Stuck Request Recovery | **수용 완료 흔적** — 3 stuck queued가 `source_unresolved`로 정규화(8311 재시작 검증, 리시트·감사 노트 보존, CAS/DB byte-identical) |
| Lifecycle 수정 | **구현 완료 흔적** — source_unresolved 전이 edge + 감사 리셋 검증(34/34 테스트), request-level model_call_ceiling(기본 192) |
| Evidence-ID 수정 | **미확인** — 중복 id(83개/25 unique)의 안전 소비 규약 기재는 본 검토에서 확인 불가 → 확인 필요 항목으로 등록 |

**중복 조사**: work order 3편 vs RRSI Evolve 2편 + BLOCKED 13편 — **교집합 0건**
(재계산: work order {2502.19645, 2510.26742, 2603.19199} vs gold 15 id).

**공통 관리 방안 제안(단일 권위 = ai_papers 파이프라인)**:

- ai_papers의 `data/raw/papers/` + stage-01 extraction을 소스의 유일 취득·
  등록 경로로 유지(RRSI·research_agent 모두 재취득 금지, 소비만).
- **Source Registry manifest** (ai_papers canonical 위치, append-only): 항목 =
  `{source_id, arxiv_base_id, arxiv_version, source_sha256, extraction_version
  (bundle digest), artifact_location, acquisition_request_id, registered_at}`.
  work order가 요구한 sha256 등록과 6번 문서의 규약을 흡수.
- RRSI는 라운드 시작 시 registry 스냅샷의 **hash를 freeze 문서에 등록**(기존
  dataset-manifest 규약 확장) — 분할·입력 무결성과 동일 체계.
- research_agent는 소스 관찰을 GET/observable surface로만(work order Phase 6
  지향) — 파일시스템 직접 결합 회피.
- 수용 범위: work order 전체 자동 수용 금지(지시 준수) — 본 검토는 기록만.

## Workstream D — QASPER Protocol Readiness (지시 1–6)

| 확인 항목 | Full-text QA | Reader-context QA |
|---|---|---|
| 소스 확보 | **불요** — frozen dataset에 `full_text` 필드 내장(keys: title, abstract, full_text, qas, figures_and_tables). 신규 취득 0 | 동일(dataset 재사용) |
| Reader Note artifact 경로 | 해당 없음 | 경로는 실측 확정: `02_reading_chain/output/04_reader_note.ko.md` — adapter의 경로 인자화 필요(15번 문서 변경 목록 #4, 미구현) |
| Adapter 연결 | external QA intake의 `input_mode: full_text`가 승인 모드(INPUT_MODES에 존재) — 연결 검증은 abstract_only와 동일 레인 | intake가 `selected_sections` 모드도 보유 — reader note 텍스트를 sections 소스로 전달하는 경로 설계 필요 |
| Evidence F1 계약 | `evidence-match/v0.1` 유지 — **fulltext 하에서는 구조적 불가였던 매칭이 가능**(gold highlighted_evidence가 동일 fulltext 소스). scorer 무변경 | 동일 |
| Source Reference Accuracy | 가능 — producer의 offset round-trip(span locator, fail-closed) + gold evidence 텍스트 대조로 문장-단위 정확도 산출 가능. 신규 코드 최소 | 동일(단 reader note 기반 섹션 매핑 계약 필요) |
| Split/Holdout 격리 | consumer fail-closed final 거부(실동작) — 유지 | 동일 + calibration 2편 Holdout 재사용 금지 등록(17번 문서) |

**결론**: Full-text QA는 **dataset 내장으로 즉시 준비 완료**(승인 시 실행).
Reader-context QA는 계약 설계·경로 인자화 1건 보완 후 준비. 신규 scorer 0,
기존 계약 무변경 — 구현 준비 상태 PASS/조건부 PASS.

## Workstream E — 다음 실행 판단 (지시 1–8)

1. **U1 drift 실제 영향**: 계획 품질 게이트 의미 변경( stricter digit-suffix
   매칭) — prompt 무변경, 노트 생성 경로 무변경, Historical Baseline 유효.
2. **새 Baseline**: 현재 불요 — 승인 후 라운드 진입 시 재기준 선행 등록(§A).
3. **격리 방안**: 기존 격리 재사용 — 모델 실행 재개 시 pinned worktree 제안.
4. **Source 취득 공통화**: ai_papers 단일 권위 + append-only Source Registry
   manifest + RRSI freeze hash 등록(§C 제안).
5. **Work Order 수용 가능 범위**: Phase 1~3은 소유자 실행 완료 흔적 — 본 검토의
   신규 수용 대상은 Phase 4(idempotent resume)·5(evidence id)·6(observability)
   확인 후 별도 승인. 전체 자동 수용 금지 준수.
6. **QASPER Protocol 준비**: Full-text QA 즉시 가능, Reader-context QA 조건부
   (§D).
7. **추가 모델 실행**: 0(정적 검토 준수). 이후 필요 실행은 승인 개별 연결:
   재기준 1-trial, evidence_required 검증, reader-context 프로토콜 검증.
8. **판단: HOLD 유지** — 신규 근본 결함 없음, GO 조건은 불변(evidence
   프로토콜 결정, δ 확정, 분할 해동)이며 이번 검토에서 1건 강화(evidence는
   프로토콜 선택의 문제로 재분류 — 17번 보고의 "구조적 불가"는 abstract_only
   조건 하 한정).

## 범위 준수

모델 호출 0, 신규 pipeline 실행 0, RRSI Evolution 0, Final Holdout 소비 0,
운영 승격 0, ai_papers 운영 상태 변경 0. RRSI 코어·ai_papers canonical
artifact·research_benchmarks scorer 계약 무수정.

**Committed artifacts**: 본 보고. 분석 근거: ai_papers git 히스토리
(`997e5a1ec..7a31ad02d`), research_agent work order
(`coordination/work-orders/codex-ai-papers-processing-defect-recovery-001.json`),
기존 RRSI run artifact.
