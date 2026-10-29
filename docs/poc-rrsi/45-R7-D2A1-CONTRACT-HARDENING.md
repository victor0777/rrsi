---
doc_id: poc-rrsi-45-r7-d2a1-contract-hardening
title: R7-D2A1 Verification Contract Hardening
status: contract
updated: 2026-10-29
---

# R7-D2A1 — Verification Contract Hardening (문서 45)

구현: `poc/r7_contract.py` · 테스트: `poc/tests/test_r7_contract.py`
(148/148 전체 스위트 통과 — 기존 131건 보존, 신규 17건). R6I 운영
코드 무변경, Gold/Raw Evidence 무변경. 모델 호출 0회. 최종 상태:
**R7_D2A1_CONTRACT_HARDENED**.

## 1. 변경 전후 계약 비교

| 영역 | D2A (문서 44) | D2A.1 (본 계약) |
|---|---|---|
| Judge 입력 방어 | dict 전제 — None/list 등에서 예외 위험 | fail-closed 가드 — 모든 비정형 입력이 명시적 실패 반환 |
| Lexical Probe | `global_absence_machine and local_absence` 필수 승인 조건 | **제거** — 검토 보조 수단 전용 (§3) |
| VERIFIED 조건 | 기계 어휘 부재 + bool 검토 | 인간 판정 중심 7조건 + 잔존 위치 검토 기록 (§3) |
| Review Record | 7필드 | **11필드 provenance** (§5), v1 별칭 호환 |
| Reviewer | registry 없음 (reviewer-1 임의 사용) | **Reviewer Registry 계약** — 비어 있는 채로 시작, 무작위 검토자 생성 금지 (§6) |
| Claim Verification fixture | 실제 검토 기록과 구분 없음 | 합성 Fixture(`synthetic=True`) 명시적 구분 |

## 2. Judge Schema Fail-Closed 결과 (§2 Workstream A)

| 입력 | 결과 (예외 없음) |
|---|---|
| `validate_judge_output(None)` / `[]` / `0` / `""` / `"invalid"` | `INVALID_OUTPUT_TYPE` |
| `{"claims": None}` / `123` / `"invalid"` / `{}` | `CLAIMS_NOT_LIST` (claim 반복 수행 안 함) |
| `evidence_refs`가 list[str] 아님 | `EVIDENCE_REFS_NOT_LIST_OF_STR` |
| Claim 원소 비객체 | `CLAIM[i]:CLAIM_NOT_OBJECT` |
| Claim ID 중복 / Evidence 중복 | `DUPLICATE_CLAIM_ID` / `DUPLICATE_EVIDENCE_REF` |
| claim_id 패턴 위반 (`^c-…`) | `CLAIM_ID_MALFORMED` |
| 빈 claim_text / 빈 evidence ref | 기각 |
| 자료형 확정 전 후속 연산 | 수행하지 않음 (가드 상태로 반복 진입 차단) |

- 스키마는 **v0.3 유지** — 변경 불필요했으므로 Migration Policy 없음
  (정책: 변경 시 버전 사유·Migration 문서화 의무는 유지).
- 속성 테스트: 19종 수작업 비정형 shape + 고정 seed(`20261029`) fuzz
  300회 — 전부 예외 없이 `valid=False`·결정론적 재현 확인.

## 3. Semantic Verification Policy 변경 (§3 Workstream B)

**B1 — Lexical Probe 역할 수정**: probe 결과는 (a) 동일 용어 잔존
위치 탐색, (b) 검토자 후보 위치 제공, (c) 잔존 가능성 경고, (d) 검토
범위·근거 기록에만 사용. 의미적 존재/부재의 최종 판정이 아님.
`global_absence_machine and local_absence`는 승인 조건에서 **삭제**.

**B2 — VERIFIED 조건 (전부 충족)**: ① Original Note Anchor 유효
② Perturbed/Source 문서 결합 유효 ③ 기록이 현재 claim·문서 버전에
결합 ④ `global_absence_verdict == CONFIRMED` ⑤
`source_importance_verdict == IMPORTANT` ⑥ 근거·검토 범위 유효
⑦ 다른 필수 증거 FAILED 없음 + reviewer `REGISTERED` + 기록 digest
무결성 + 잔존 위치 검토 완료.

**B3 — Partial Information Loss**: 잔존 용어 존재만으로 소실 주장을
거부하지 않음. 지시문 예시(Original: "TextRank extracts keywords,
which are then used to construct the initial representation." /
Perturbed: "TextRank is used in the pipeline.")를 그대로 정적 테스트로
반영 — 검토자가 소실 확인 + Source Importance 인정 시 `VERIFIED`
가능 (T09).

**B4 — 모순된 검토 기록**: 잔존 위치가 검토되지 않았으면
`PENDING_HUMAN_REVIEW`; 키워드 존재만으로 `FAILED` 반환 금지.

## 4. Human Review Provenance 계약 (§4 Workstream C)

- **11필드**: `review_id`, `reviewer_id`, `claim_id`,
  `reviewed_document_digests`, `review_timestamp`, `review_scope`,
  `global_absence_verdict`, `source_importance_verdict`, `rationale`,
  `evidence_refs`, `review_record_digest`.
- **호환성 정책**: v1 `document_digests`는 `reviewed_document_digests`
  별칭으로 수용 (기존 7필드 기록 호환); 신규 기록은 전부 v2 이름.
- **Integrity 검증** (C2): review ID 존재, claim ID 일치, reviewer
  유효성, 검토 대상 digest 일치, evidence reference가 실제 문서에
  존재, scope가 전체 Perturbed Note + Source Importance 검토 포함,
  기록 digest 무결성(자기 자신 제외 정규화 payload —
  `finalize_review_record`, canonical JSON sort_keys).
- **신원 경계 명시**: digest는 데이터 무결성 수단이지 검토자 신원
  인증 수단이 아님 — 신원 확인은 Reviewer Registry·승인된 검토 기록
  연결로 처리 (신뢰된 로컬 실행 환경 전제).

## 5. Reviewer Registry 상태 (§4 C3)

- 상태 집합: `REGISTERED` / `UNREGISTERED` / `REVOKED` /
  `PENDING_ASSIGNMENT`.
- Registry는 **비어 있는 채로 시작** — 실제 검토자 미지정 시 어떤
  검토자도 생성하지 않고, 실제 평가 claim을 `VERIFIED`로 승격 금지
  (T07: registry 비움 → PENDING 확인).
- 합성 Fixture 검토자(`register_reviewer(..., synthetic=True)`)는
  정적 테스트 전용이며 실제 검토자 승인 기록과 구분됨 — T09/T14는
  합성 Fixture 한정 정적 테스트로, 실제 평가 데이터 검증 성공이
  아님을 문서로 명시.

## 6. 신규 테스트 및 전체 회귀 (§5 Workstream D)

| 범주 | 건수 | 결과 |
|---|---|---|
| T01–T14 필수 회귀 (§D1 표) | 14 | 전부 PASS |
| A3 속성 테스트 (shape·fuzz·스키마 호환) | 3 | PASS |
| 기존 테스트 보존 | 131 | 전부 PASS |
| **합계** | **148** | **148/148 PASS** |

**정책 변경으로 기대 결과가 바뀐 기존 테스트 (변경 이유 기록)**:
`test_info_loss_info_present_elsewhere_never_machine_verified` —
구 의미 "어휘 적중 >0 ⇒ PENDING(VERIFIED 금지)"은 새 정책에서 "잔존
위치 미검토 ⇒ PENDING"으로 재표현됨 (T10과 동일 사례). 기존 실패
방지 목적(어휘 존재만으로 VERIFIED 금지 + 미검토 승격 금지)은 유지.
`test_info_loss_verified_with_structured_review_record` — v2 필수
필드 + REGISTERED reviewer를 사용하도록 갱신 (T14).

## 7. R6I 호환성 확인 (D3)

- R6I 운영 코드 무변경 (`git status`: `poc/r7_contract.py`·테스트만 수정)
- Gold / Raw Evidence 무변경
- Blind Evaluation 계약 유지 (Judge 입력 경계 재확인 — neg8/T08 경로)
- R7-E1 실행 없음, EVOLVE/Holdout 소비 없음, Evolution/δ HOLD

## 8. 잔여 위험 및 후속 작업

1. **Reviewer Registry는 계약만 구현** — 실제 검토자 지정(Owner) 및
   영속 레지스트리 저장 위치 미정 (E1 전 Owner 결정).
2. **record scope 문자열 검사는 정적 휴리스틱** — 구조화 dict가
   정규 형식; 자유 문자열 수용은 키워드 존재 확인에 한정 (위험 낮음,
   문서화됨).
3. **Lexical probe는 영어 어휘 기반** (`[a-zA-Z]{6,}`) — 한국어 등
   비라틴 텍스트에서 후보 위치 미탐색 가능 (probe는 보조 수단이므로
   판정 영향 없음).
4. E1 전: Reader Note 생성 승인, 독립 검토자 2인 지정, 토큰 상한
   결정, 노출 caveat 확인 (문서 42 차단 요인 유지).
5. D2A.1 완료는 **R7-E1 Admission이 아님**.
