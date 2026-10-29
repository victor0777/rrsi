---
doc_id: poc-rrsi-35-judge-pilot-r6h-audit
title: Judge Output & Evidence Audit (R6H) — zero model calls
status: report
updated: 2026-10-29
---

# R6H — Judge Output & Evidence Audit — Report

**Summary.** r6g 봉인 원본 응답만 분석(모델 호출 0). 결론:
① **g7 Agreement는 근거가 실제로 지지하지 않음** — Judge의 Document B
서술은 perturbation 효과가 아니라 **발췌 cap-10 정책이 만든 artifact**,
METHODOLOGICAL 분류기 통과만으로 성공 확정 불가 ② g4는 출력 상한 800
토큰에서 잘림(finish_reason 미영속 — length로 추정, completion ==
800 == cap), 의미상 `relative_judgment`는 완성돼 있으나 strict JSON
파싱 실패 — INCONCLUSIVE 유지 ③ Ledger의 이중 예약은 **의도된 두 단계
예약**(workstream 예약 + provider 경계 예약) — 중복 아님, 단 호출 제한
(call cap)과 예약 제한(ordinal ceiling)은 개념이 다르므로 분리 표기 권고
④ g4 재평가 계획: 신규 Invocation·신규 Permit·스키마 v2·출력 상한
명시·재시도 0. **재실행 필요: g4 필수, g7 권고**.

---

## 1. §A — g7 의미적 근거 감사

봉인 파일: `semjudge-r6g-recovery/raw/resp-g7-1901-method.json`
(usage: prompt 1,296 / completion 576).

**1. Judge가 실제 언급한 방법론 단계**
- 문제: unordered text의 section segmentation
- 방법: TextRank + USE 키워드 중심 클러스터링, 결합 유사도 지표
  (문장-키워드 유사도 + 클러스터 내 문장 간 유사도 가중)
- 평가 지표: Sim1, Sim2 / 실험: 500개 재배열 Wikipedia 문서
- 외부 의존성: TextRank·USE는 front matter에서 완전 정의되지 않음

**2. 단어 존재 vs 기능적 설명 구분** — 구분함. input_b basis가
"…methodology details **beyond naming the tools**"라고 명시하고, B가
도구를 '이름만 언급'한다고 서술 — 존재/기능 구분의 언어는 있음.

**3. Source Evidence Reference 정확성** — 인용 자체는 정확.
- A측 3개 인용: 발췌 원문 그대로 일치 (3/3 exact).
- B측 3개 인용: 2개 exact, 1개는 발췌의 마크다운 볼드(`**TextRank**`)
  에서 asterisk를 제거한 인용 — 실질 일치(포맷 수준 편차, 조작 아님).

**4. 근거가 상대 판정을 지지하는가** — **지지하지 않음 (핵심 결함).**
Judge의 B측 서술 — "B는 핵심 문제 진술, 결합 유사도 기여, 평가 지표,
실험 결과를 **생략**했다; 외부 의존성에만 집중한다" — 는 g7
perturbation(P5)의 효과가 **아니라** cap-10 발췌 정책의 산물임:

- perturbed note(`p5-1901-method-removed.md`)는 실제로 문제 진술
  (단락 idx 4–6), "Keyword Extraction and Centroids"(idx 43),
  "Initial Sentence Mapping"(idx 44), "Combined Similarity Score
  S(x,y)"(idx 45), 실험·결론 요약(idx 50–64)을 **여전히 포함**.
- P5 perturbation이 제거한 것은 TextRank 명시 서술만이며, idx 44
  ("keyword list $K$… most relevant sentence… cosine similarity") 같은
  잔존 방법론 단락은 cap-10에 의해 **발췌에서 잘려 나감**(14개 match 중
  10개 선택; idx 44·61·63·67이 잘림).
- 따라서 Judge는 발췌를 평가했을 뿐이고, "B에서 정보 손실이 크다"는
  상대 판정은 **발췌가 만든 손실**에 기반 — 봉인된 이 응답을 유효
  Agreement로 계수할 수 없음. `excerpt_caused_info_loss: false`였던
  r6g 기록의 이 필드는 **잘못 산출된 것**으로 본 감사가 정정함
  ( classification=METHODOLOGICAL만으로 의미적 성공 확정 불가 ).

## 2. §B — g4 출력 실패 분석

봉인 파일: `semjudge-r6g-recovery/raw/resp-g4-1802-numeric.json`.

| 항목 | 값 |
|---|---|
| finish_reason | **미영속** — 러너가 usage만 영속화. completion == 800 == 출력 상한이고 말줄기 종료 → `length`(추정, 근거 기재) |
| 실제 출력 토큰 | 800 (== max_tokens cap, 잘림 확정) |
| 마지막 완성 JSON 필드 | `abstention.refused` (값 `false`까지 완성). `relative_judgment`는 객체 전체 완성 — `higher_quality: "equal"` + basis 포함 |
| 파싱 실패 위치 | `abstention.reason` 문자열 도중 — "Unterminated string starting at line 24 column 15 (char 2068)" |
| 누락 필수 필드 | 스키마 필수 3키(input_a/input_b/relative_judgment)는 모두 존재 — 누락은 없음. 누락된 것은 **JSON 종결**임 (`}` 3/5, 미닫힘 문자열) |
| 과다 출력 원인 | ① basis/reason 문자열 **내부에 자기교정 사고연쇄 삽입**("\*Self-correction\*: Actually, if I must choose… Let's re-read…") ② `relative_judgment.basis`와 `abstention.reason`의 내용 중복 ③ 문장 전체를 인용하는 긴 evidence_references ④ 'internal consistency vs fidelity' 차원 모호성이 장문 변명 유발 |

**스키마 축소안(v2 — 별도 버전, 기존 응답/스키마 무수정):**

```json
{"relative": "A" | "B" | "equal" | "abstain",
 "reason": "<=200 chars (abstain 시 필수)",
 "a_verdict": "high|medium|low", "b_verdict": "high|medium|low",
 "ev_a": ["<=120-char 발췌 구절, 2개 이하"], "ev_b": ["동일"]}
```

— 자유 basis를 폐지(근거는 ev 구절이 운반), 자기교정 사고연쇄가 들어갈
여지를 제거, `max_tokens=500` 상한. 필수 키·상대 판정·evidence
참조·abstention 사유가 모두 보존되므로 Blind 계약과 사후 Gold 비교
(`compare_with_gold`)는 기존 로직 그대로 적용 가능.

## 3. §C — Ledger 예약 계약 추적

코드 추적(`ai_papers_research/llm/call_budget.py:157`, 
`llm/providers/openai_compatible.py:128-135`):

1. `reserve_model_call_from_environment(call_id)`: 봉인 ledger 파일
   오픈(O_NOFOLLOW) → flock EX → 전체 행 strict 검증 → 동일 call_id
   중복 예약 거부 → 기존 `reserved` 수 +1을 `attempted_ordinal`로 산정
   → `reserved >= ceiling`이면 `model_call_budget_rejected` 행 기록 후
   raise, 아니면 `model_call_budget_reserved` 행 기록.
2. **호출당 2 ordinal의 원인** — 의도된 두 단계 예약:
   - 1단계(workstream): 러너가 네트워크 전에 md5 call_id로 예약
     (`semantic_pilot_r6_recovery`의 예약).
   - 2단계(provider 경계): frozen call path가 `uuid.uuid4()` call_id로
     실제 HTTP 직전에 자체 예약 (openai_compatible.py:135).
   - r6f ledger의 md5+UUID 쌍과 r6g의 동일 패턴이 증거. **중복 아님.**

**판정**: 두 단계는 목적이 다름(사전 계약 예약 vs 네트워크 경계 강제).
다만 모델 **호출 수 제한**(§C의 3회)과 ledger **ordinal ceiling**은
서로 다른 단위(호출 vs 예약)이므로, 향후 permit에 `max_model_calls`
(호출)와 `max_reservation_ordinals`(예약)을 **분리 표기**할 필요가
있음 — r6f의 발급 계량 오류(ceiling=3을 호출 수로 오해)가 이 혼동의
실례. 금번 권고: ordinal ceiling = 2 × max_model_calls 로 명시적 배수.

## 4. §D — g4 최소 재평가 계획

| 항목 | 계획 |
|---|---|
| 대상 | g4-1802-numeric 1 fixture, 호출 1회 |
| Gold/발췌 보존 | `input-g4-1802-numeric.json`의 blind pair(문서 A/B)·dimension·source evidence **byte 그대로** 재사용; Gold 무변경 |
| 스키마 | 기존 v1 응답·스키마 봉인 유지, 출력 계약만 **v2 신설**(§2 축소안); 유저 프롬프트 중 evidence 부분은 동일, 출력 템플릿 절만 교체 — v1/v2 계약서 모두 별도 버전으로 영속화 |
| Invocation | `semjudge-r6i-g4` (신규; r6f/r6g RUN_DIR 재사용 없음) |
| Permit | 신규 발급(`register_permit`), 7조건 verify |
| 출력 상한 | `max_tokens=500` 명시 + 사전 `/tokenize` 계측(예약 = 입력 + 500) |
| 재시도 | 0 — 첫 실패가 최종, 응답 수신 즉시 raw+usage 영속화 후 예산 판정 |

**예상 비용**: prompt ≈ 1,043(동일 발췌) + completion ≈ 250–350(v2)
→ **실제 예상 ≈ 1,300–1,400 tokens**, 예약 상한 권고 1,600.
선택적 g7 재평가(§A 결함 해소, cap 제거): 입력 ≈ 2,800 + 출력 ≈ 600
→ **예상 ≈ 3,400 tokens** — 별도 Owner 재결정 필요.

## 5. 결론 — 재실행 필요 여부

- **필요: g4** — 위 계획대로 스키마 v2로 1회 재평가(예상 ~1,400 tok).
- **권고: g7** — 현재 Agreement는 발췌 artifact에 기반해 무효;
  cap 제거 발췌로 재평가(예상 ~3,400 tok) 또는 이 Agreements를 무효
  계수로 봉인. **Owner 재결정 항목.**
- g3 Agreement는 본 감사 대상 밖 — 파싱·근거 정합(§A 3유사 기준) 및
  r6g 기록상 문제 없음(선택적 재검토 가능).

## 6. 제한사항 준수

모델 호출 0 · Gold/Source/Reader Note 무변경 · Holdout·δ·Evolution
무관여 · main 유지 · 신규 Worktree 없음 · 기존 봉인 응답 무수정.
