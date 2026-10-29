---
doc_id: poc-rrsi-43-r7-d2-pipeline-separation
title: R7-D2 Pipeline Separation & Independent Verification Contract
status: contract
updated: 2026-10-29
---

# R7-D2 — Pipeline Separation & Independent Verification Contract (문서 43)

구현: `poc/r7_contract.py` (확장) · 테스트: `poc/tests/test_r7_contract.py`
(122/122 전체 스위트 통과 — 신규 10건). R6I 운영 코드 무변경.
모델 호출 0회. **지시문이 §B2 중간에서 잘려 전달됨 — §B2 목록 이후
(Workstream C/D, 수용 기준 등)는 미확인이며 본 문서는 전달된 범위
(§A1–A3, §B1–B2)만 구현한다.**

## 1. 5단계 파이프라인 구조 (§A1)

```
SemanticJudge → EvidenceResolver → ClaimVerifier → GoldAdjudicator
                                                       ↓
                                              EvaluationReporter
```

| 구성 요소 | 책임 |
|---|---|
| `SemanticJudge` | 상대 품질 판정, 오류/소실 claim 제기, 관찰된 증거 인용, 판정 불가 시 abstain |
| `EvidenceResolver` | Judge 인용을 실제 위치로 해석, 문서 digest 검증, byte/markdown 일치 확인 |
| `ClaimVerifier` | 원문 논문 + FULL Reader Note 대비 claim 검증, 부분 vs 전체 소실, 의미적 불확실 → 인간 검토 |
| `GoldAdjudicator` | 검증된 claim과 독립 Gold 비교 (Agreement/FP/FN), Gold 불확실성 통제 |
| `EvaluationReporter` | 독립 지표 집계 (e2e/조건부 Agreement, precision/recall, FPR, abstention, grounding, cost) |

## 2. 입력 권한 행렬 (§A2 — `PIPELINE_ROLES`)

| Role | A/B Note | Source Paper | Gold | Perturbation Truth |
|---|---|---|---|---|
| SemanticJudge | allowed | **denied** | **denied** | **denied** |
| EvidenceResolver | allowed | locator-check only | denied | denied |
| ClaimVerifier | allowed | allowed | **denied** | denied |
| GoldAdjudicator | allowed | allowed | allowed | allowed |
| EvaluationReporter | verdicts | verification results | aggregation only | aggregation only |

- R6I Blind Evaluation 계약 유지: Gold 방향은 Judge 입력에서 제외.
- Source paper는 Judge에게 **기본 금지** — 중립성 훼손 요인 제거.

## 3. Judge 출력 스키마 v0.3 (§A3 — `validate_judge_output`)

```json
{"relative": "A|B|EQUAL|UNDECIDABLE",
 "a_verdict": "VALID|INVALID|ABSTAINED",
 "b_verdict": "VALID|INVALID|ABSTAINED",
 "claims": [{"claim_id": "c-<seq>",
             "kind": "numeric_error|info_loss|missing_evidence|contradiction",
             "target_side": "A|B",
             "claim_text": "<= 판정 가능한 구체적 주장",
             "observed_evidence_refs": ["e-…"]}],
 "evidence_refs": ["e-…"], "abstention": bool,
 "schema_version": "r7-judge-output/v0.3"}
```

- Judge는 **관찰 수준 필드만** 출력 — 원문 논문 중요도 판단·Gold 정보
  요구 없음.
- 기계 강제: Judge가 `importance_evidence`·`verification_status` 등
  자신이 수행 불가능한 검증을 주장하면 `JUDGE_FORBIDDEN_FIELD`로
  스키마 탈락; `abstention: true`는 `relative: UNDECIDABLE`과만
  양립.

## 4. 독립 Verification Evidence 스키마 (§B1 — `resolve_claim_evidence`)

| 필드 | 설명 |
|---|---|
| `claim_id` | Judge claim 연결 (필수) |
| `document_id` / `document_digest` | 문서 등록 키 + `sha256:<원문 텍스트>` |
| `document_role` | `source_paper` / `original_note` / `perturbed_note` |
| `locator` / `quote` / `match_policy` | 위치 식별자 / ≤120 chars 인용 / byte·markdown·semantic_review |
| `verification_status` | `UNVERIFIED/VERIFIED/FAILED/PENDING_HUMAN_REVIEW` |
| `verification_method` / `verification_evidence` | 검증 방법·근거 (Resolver 기록) |

- Fail-closed: 미해석 참조 (`UNRESOLVED_REF`)·digest 불일치·quote 부재
  → `FAILED`; `semantic_review` → `PENDING_HUMAN_REVIEW`.

## 5. info_loss 3-증거 검증 (§B2 — `verify_info_loss`)

1. **Original Note Evidence** — anchor quote가 원본 Note에 존재
   (digest-bound, fail-closed).
2. **Perturbed Note Absence** — Local: 정규화 기준 부재 확인 /
   Global: perturbed note **전체**에 동등 정보 잔존 없음 — 기계층은
   어휘 프로브만 수행하며 어휘 부재는 의미적 부재가 아님 ⇒ 기록된
   인간 검토(human review) 없이는 VERIFIED 금지.
3. **Source Paper Importance** — 원문 논문 대비 의미적 중요도 ⇒
   기계층은 기록된 인간 검토와 결합할 때만 결정 가능, 미기록 시
   `PENDING_HUMAN_REVIEW`.

- 규칙: 증거 중 `FAILED` ⇒ `FAILED`; 미결정 존재 ⇒
  `PENDING_HUMAN_REVIEW`; 세 증거 모두 확인 시에만 `VERIFIED`.
  어휘 적중 >0인 정보 잔존은 인간 검토 기록이 있어도 VERIFIED 금지.

## 6. 정적 테스트 (신규 10건)

| 사례 | 결과 |
|---|---|
| Judge v0.3 유효 출력 | PASS → valid |
| Judge 금지 필드 (importance/verification 주장) | PASS → `JUDGE_FORBIDDEN_FIELD` |
| `abstention=true` + UNDECIDABLE 아님 | PASS → 스키마 탈락 |
| 파이프라인 권한 행렬 | PASS → 행렬 고정 |
| Resolver 미해석 참조 | PASS → fail-closed |
| Resolver digest-bound 기록 | PASS → VERIFIED + 10필드 |
| info_loss 3-증거 전체 경로 (검토 미기록) | PASS → PENDING |
| info_loss + 기록된 인간 검토 | PASS → VERIFIED |
| 정보 타처 잔존 + 검토 기록 | PASS → VERIFIED 금지 (PENDING) |
| 허위 anchor (원본에 없음) + 검토 기록 | PASS → FAILED |
