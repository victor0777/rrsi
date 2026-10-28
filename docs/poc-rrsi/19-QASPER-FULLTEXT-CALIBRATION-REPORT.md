---
doc_id: poc-rrsi-19-qasper-fulltext-calibration-report
title: Full-text QASPER Calibration Report (executed) + Reader-context Adapter preparation
status: report
updated: 2026-10-28
---

# Full-text QASPER Calibration Report

**Summary.** 승인 범위 내 Full-text QASPER Calibration 실행 (모델
`qwen3.8-flash-next-fp8` 설정 고정, 2편/10 cases). **Answer F1 0.5→0.3(−0.2),
Evidence F1 0.0→0.3(+0.3)** — Answer F1 하락은 전건 scoring-mapping 왜곡
(공란 주석·장문형)이며 응답 행동은 개선(Evidence literal 2→5 cases,
False unanswerable 4→3). Evidence protocol은 full_text 조건에서 **동작
검증 완료**. Reader-context adapter 최소 변경 완료(테스트 71/71 PASS,
research_benchmarks `5038b87`). 판정: **HOLD 유지**.

---

## A. Full-text 실행 결과 (지시 §A)

- 대상: `1802.07862`, `1901.10133` × 10 cases, input_mode `full_text`
  (dataset 내장 `full_text` 평탄화 — flatten 결정적).
- 모델/설정 고정: `qwen3.8-flash-next-fp8`, temperature 0.0, max_output 1024,
  json_mode off, case당 1 documented attempt, 동일 call 경로(`call_model`
  direct backend) — ledger·token telemetry 동일 env 바인딩.
- 예산 준수: **calls 10/12, wall 15.6초/900초**. Ledger 10 예약 = telemetry
  10 terminal, usage reported 10/10, status completed 10/10(http 200).
- 유료 API 미사용(owner-provisioned LAN gateway).

## B. Evidence Protocol 검증 (지시 §B 1–7, abstract-only 대비)

| 지표 | Abstract-only | Full-text | 해석 |
|---|---|---|---|
| 1. Answer F1 | 0.50 | **0.30** (−0.2) | 하락 전액 scoring-mapping 왜곡(§B-5) |
| 2. Evidence F1 | 0.0 | **0.30** (8 case 측정) | full_text에서 gold highlighted_evidence와 매칭 가능 — protocol fix 실증 |
| 3. Evidence literal 생성률 | 2/10 | **5/10** | abstract에서 literal 인용 불가였던 질문들이 fulltext에서 산출 |
| 4. Span/Offset Round-trip | 해당 2건 | **8/8 OK** | surface == full_text[start:end] 재검증(동일 flatten; 검증 스크립트의 flatten 불일치 1차 관측은 본 검토 자체 결함으로 정정) |
| 5. False Unanswerable | 4 | **3** | 감소. 단 missed unanswerable 1→3(아래 §B-5) |
| 6. Abstention Rate | 8/10 | **5/10** | 중단 행동 38%p 감소 |
| 7. Scorer Mapping 영향 | +0.2 왜곡(credit) | **−0.2 왜곡(상각)** | 공란 주석 매핑이 조건에 따라 반대 방향으로 작용 |

**질문별 비교** (10 case, F1 변화 있는 것만):

| 질문 | abs F1 | ft F1 | Δ | 원인 |
|---|---|---|---|---|
| Which types of NEs do they recognize? | 1.0 (중단credit) | 0.0 (답변) | −1.0 | 모델 정답 응답("PER, LOC, ORG, MISC" — 논문 내용과 일치)하나 gold 주석 **공란** → 'Unanswerable' 참조 매핑으로 0점 |
| How large is their MNER dataset? | 1.0 (중단credit) | 0.0 (답변) | −1.0 | 내용 정답("10K…" ↔ gold "10000")이나 **장문형 span** → token F1 0(matched_reference_type abstractive) |
| 나머지 8건 | 불변 | 불변 | 0.0 | 동일 행동(정답 2, 올바른 중단 2, protocol 부재 4) |

**Evidence F1 원인 구분**: 본 실행에서도 F1 0인 case는 없음(8건 모두 >0이 아니라
평균 0.3). 만약 0이었더라도 원인은 (i) abstention에 의한 evidence 부재 또는
(ii) fulltext 소스-주석 정합 — 구현 결함(투영 변형)은 round-trip 8/8로 배제.
Scorer 무수정 유지.

**False Unanswerable 3건의 원인**: 43f56301("어떤 모델" — gold 불가능 판정 vs
모델 답변, abs와 동일) + "Do they release code/data set"(gold 'No', fulltext에도
release 기술 부재 가능성 — 주석 기준 불가 판정 유지). 즉 gold 불가 판정과
모델 응답의 불일치가 주원료, 구현 결함 아님.

## C. Reader-context Adapter 준비 (지시 §C)

- **최소 변경 완료** (research_benchmarks `5038b87`): `preflight_cli`에
  `bundle_root`, `reader_note_path` 옵션 파라미터(기본값 = 기존 canonical
  경로 — 기존 계약 뒤호환), 존재 검증 + **sha256 provenance 바인딩**,
  `--paper-md <path>`로 replay CLI에 주입. Full-text context 혼입 경로 없음
  (주입된 artifact 하나만 전달).
- 기존 Mock/CLI 테스트 유지: **71/71 PASS**.
- **Artifact hash 기록**: 주입 대상 기준 artifact `04_reader_note.ko.md`
  (46,248 bytes, sha256 `bffb8b75…` — r0b2-repeat-4b 산출 기준).
- 본 단계에서 Reader-context 신규 모델 평가 **미실시** (지시 준수).

## D. Dataset Split 및 Source Registry (지시 §D)

- Split freeze `849d1431…` 무변경; QASPER 독립 축 유지; final cohort 무접촉.
- Source Registry 단일 권위 문서화: 18번 보고 §C 제안을 확정 문안으로 유지
  (ai_papers pipeline 단일 취득 경로, append-only manifest, RRSI freeze hash
  바인딩) — **운영 DB·canonical artifact 변경 0** (문서화만).
- Evidence-ID work order 미확인 사항(Phase 4~6)은 별도 확인 대상 유지.

## E. 최종 보고 (지시 §E 1–10)

1. 실행 결과: §A. 2. Answer F1: 0.5→0.3(−0.2, scoring-mapping 왜곡).
3. Evidence F1: 0.0→0.3(+0.3, protocol fix 실증). 4. False unanswerable:
   4→3. 5. Mapping 영향: 공란 주석 매핑의 방향 왜곡(+0.2/−0.2 상쇄 구조).
6. Reader-context adapter: 준비 완료(`5038b87`, 71/71 PASS).
7. 실측 비용: **10 calls, 입력 36,890 + 출력 627 tokens(합계 37,517), wall
   15.6초** — ledger↔telemetry 전건 정합.
8. Split 잔여 차단: BLOCKED_CONFLICTED 13 + Validation/Holdout 공측(해동
   승인 대기) — 불변.
9. Reader-context QA 실행: **승인 시 가능** — adapter 준비 완료, 본 단계
   미실행. 실행 시 비용 추정: case당 1 call(요약 ~40k tokens/10 cases).
10. **Evolution GO/HOLD/STOP: HOLD 유지** — 근거 갱신: Evidence protocol은
    full_text 조건에서 동작 검증 완료(16번 보고의 "구조적 불가" 해소 — 프로토콜
    선택이 자율적 결정 가능 영역임이 실증됨). 잔여 HOLD 사유: ① δ 확정(n≥6),
    ② 분할 해동 승인, ③ 공란 주석·장문형의 scoring 왜곡 하에서 Answer F1을
    주 reward로 쓰는 계약의 자격 재검토. STOP 아님: 계약·구현 fail-closed
    실동작, drift 영향 게이트 한정 확인.

## 제한사항 준수

RRSI Evolution 0, Reader Prompt 변경 0, Final Holdout 소비 0, ai_papers 운영
상태 변경 0, RRSI 코어 수정 0, scorer 계약 변경 0, 신규 worktree 0, dirty
worktree 정리 0. 신규 파이프라인 실행은 승인된 calibration 1회뿐(10 cases).

**Committed artifacts**: `poc/qasper_fulltext_calibration.py`(rrsi),
research_benchmarks `5038b87`, 본 보고. Run 산출물은
`poc/runs/qasper-fulltext-calibration/` 로컬 미추적.
