# Independent Gold Fixture Review Packets (독립 검토자용)

8 gold fixtures에 대한 독립 검토 패킷. 원문 전체를 읽지 않고도 각 fixture의
주장-근거 관계를 검토할 수 있도록 구성되어 있습니다. **g5는 `Evidence
Absence`로 분류되어 제외**되었습니다 (`review-packet-index.json`의
`g5_isolation` 참조).

## 검토 방법

1. 각 packet의 §1–§9를 읽고 주장→근거 관계를 스스로 검증하세요.
   - §5 주변 문맥(±200/260자)이 불충분하면 packet에 기재된 원문 위치에서
     검토 범위를 확장할 수 있습니다 (확장 가능 명시됨).
2. §9의 "기대 판정"은 **작성자의 기대이며 검증이 아닙니다** — 독립적으로
   판단하세요.
3. §10 입력란에 판정을 기록:
   - Decision: **Approve / Reject / Needs Revision**
   - Approve 시 5조건 체크박스 **전부** 확인 필요
     (source_identity_match / source_context_sufficient /
     claim_evidence_relation_verified / perturbation_semantic_defect_confirmed /
     expected_direction_verified)
   - Reviewer Comment / Timestamp / Reviewed Fixture Digest / Reviewer·Role
4. 기록 방식 (택일):
   - Markdown: packet 사본에 §10을 채워 회신
   - JSON: `record_review(fixture_path, reviewer, reviewer_role, decision,
     comment, conditions, out_path)` API 사용 — 구현은 `poc/gold_review.py`

## 무결성

- 이 디렉터리는 봉인 실행 디렉터리
  `poc/runs/perturbation-audit/r3-review-packet/`의 **사본**입니다
  (원본 무변경).
- `seal-run-dir.json`이 파일별 sha256을 고정합니다 — 사본이 원본과
  일치하는지 대조 가능.
- 검토 기록은 fixture **바이트 digest**에 귀속됩니다. fixture가 수정되면
  기존 검토는 무효화됩니다.
- author-path(작성자 자동화 경로)의 승인은 `SELF_APPROVAL_REFUSED`로
  구조적으로 거부됩니다 — 독립자만 Approve 가능.

## 관련 문서

- 보고서: `docs/poc-rrsi/30-GOLD-REVIEW-PACKET-APPROVAL-GATE.md`
- Gold fixture 원본: `poc/runs/perturbation-audit/r2-semantic/semantic-gold-fixture.json`
- 변형본: `poc/runs/perturbation-audit/r2-semantic/` (packet §7에 경로 기재)
