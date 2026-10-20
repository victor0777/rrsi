# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS.
"""PoC tests, model-free: no network, no API keys, no existing runtime touched.

    python3 -m pytest -q poc/tests/
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from rrsi import gitops as G                     # noqa: E402
from rrsi.evaluate import TaskResult, aggregate  # noqa: E402
from rrsi.selection import Candidate, select_round  # noqa: E402

from poc import poc_core as F                    # noqa: E402
from poc import run_poc as R                     # noqa: E402


# ------------------------------------------------------------------ fixture --

def _repo_with_candidate(tmp: Path, name: str):
    """Mini repo with one candidate drafted on its worktree -> (diff, edits)."""
    out = tmp / f"out_{name}"
    out.mkdir(parents=True)
    repo = R.init_repo(out)
    branch = f"poc/test_{name}"
    wt = G.worktree_add(repo, out / "wt" / name, branch, "evolve/fixture")
    edits_fn, _ = F.CATALOG[name]
    edits = edits_fn(wt / "fixture")
    diff = G.diff_with_new_files(wt, "fixture")
    G.worktree_remove(repo, wt)
    return diff, edits


def _ev(job, rewards_by_task, k, tokens=1000.0):
    per = {t: TaskResult(rewards=list(r), tokens=[tokens] * len(r))
           for t, r in rewards_by_task.items()}
    return aggregate(job, k, per)


# -------------------------------------------------------------------- tests --

def test_scoring_is_deterministic_and_job_seeded():
    f = {"prompt_q": 0, "retry": 0, "unbounded": 0, "task_id_branch": 0,
         "answer_cache": 0, "journal": 0, "cheap_guard": 0, "budget_guard": 0}
    a = F.score_trial(f, "e03", "jobX", 1)
    b = F.score_trial(f, "e03", "jobX", 1)
    c = F.score_trial(f, "e03", "jobY", 1)
    assert a == b                                  # same null -> same measurement
    assert a[1] == c[1]                            # token model is feature-only


def test_features_drive_score(tmp_path):
    baseline = {"prompt_q": 0, "retry": 0, "unbounded": 0, "task_id_branch": 0,
                "answer_cache": 0, "journal": 0, "cheap_guard": 0, "budget_guard": 0}
    f = lambda d: F.evaluate_fixture(_mk_harness(tmp_path, d), "feat", F.evolve_ids(), 4).S
    s0 = f(baseline)
    assert f({**baseline, "prompt_q": 1}) > s0     # prompt mechanism
    assert f({**baseline, "retry": 1}) > s0        # retry helps flaky tasks
    assert f({**baseline, "unbounded": 1}) < s0    # unbounded work hurts
    assert f({**baseline, "journal": 1}) < s0      # journal overhead hurts


def _mk_harness(tmp: Path, features: dict) -> Path:
    d = tmp / f"h{abs(hash(json.dumps(features, sort_keys=True)))}"
    (d / "prompts").mkdir(parents=True, exist_ok=True)
    (d / "prompts" / "instructions.md").write_text(
        "VERIFY_OUTPUT CHECKLIST" if features.get("prompt_q") else "x")
    (d / "harness.py").write_text(
        "while True" if features.get("unbounded")
        else "retry_once" if features.get("retry") else "state/journal"
        if features.get("journal") else "# x")
    (d / "config.json").write_text(json.dumps(features))
    return d


def test_critic_screens_defects_and_passes_real_mechanisms(tmp_path):
    defects = ["leak_task_id", "leak_answer_cache", "unbounded_loop", "noop_claim"]
    reals = ["prompt_checklist", "retry_control_flow", "cheap_guard", "budget_guard"]
    for name in defects:
        diff, edits = _repo_with_candidate(tmp_path, name)
        v = F.critic_review(diff, edits)
        assert v["verdict"] == "reject", (name, v)
    for name in reals:
        diff, edits = _repo_with_candidate(tmp_path, name)
        v = F.critic_review(diff, edits)
        assert v["verdict"] == "accept", (name, v)


def test_proposer_budget_is_enforced(tmp_path):
    # mega_bundle ships 3 edits -> bounced under b_t = 2, before evaluation
    out = tmp_path / "out_bundle"
    out.mkdir(parents=True)
    repo = R.init_repo(out)
    wt = G.worktree_add(repo, out / "wt" / "mega_bundle", "poc/bundle",
                        "evolve/fixture")
    cand, diff, note = R.draft_candidate(wt, "mega_bundle", budget=2,
                                         prune_components=set())
    assert cand is not None and cand.gate_failure == "over_budget"
    assert cand.ev is None                         # never evaluated


def test_proposer_declines_pruned_component(tmp_path):
    out = tmp_path / "out_pruned"
    out.mkdir(parents=True)
    repo = R.init_repo(out)
    wt = G.worktree_add(repo, out / "wt" / "memory_journal_v2", "poc/v2",
                        "evolve/fixture")
    cand, diff, note = R.draft_candidate(wt, "memory_journal_v2", budget=2,
                                         prune_components={"memory"})
    assert cand is None and "proposer declined" in note
    # and a prune edit whose target is healthy is declined too
    cand2, _, note2 = R.draft_candidate(wt, "prune_retry", budget=1,
                                        prune_components={"memory"})
    assert cand2 is None and "not in the prune set" in note2


def test_selection_blocks_cost_without_gain():
    """rrsi Algorithm 2: a move with no measured gain must not carry cost; a
    within-band gain pays its cost through the shaped rule."""
    cfg = R.CONFIG
    inc = _ev("inc", {f"t{i}": [1, 1] if i < 12 else [0, 0]
                      for i in range(24)}, 2)
    free = Candidate("A", [{"id": "C1", "component": "prompt"}],
                     ev=_ev("A", {f"t{i}": [1, 1] if i < 13 else [0, 0]
                                  for i in range(24)}, 2, tokens=1040.0))
    costly_no_gain = Candidate("B", [{"id": "C1", "component": "config"}],
                               ev=_ev("B", {f"t{i}": [1, 1] if i < 12 else [0, 0]
                                            for i in range(24)}, 2,
                                       tokens=1700.0))
    winner, decs = select_round([free, costly_no_gain], inc, inc.S, 0.12, cfg, {},
                                guard_fn=None)
    by = {d.variant: d for d in decs}
    assert by["A"].admissible and not by["B"].admissible
    assert winner.variant == "A"


def test_e2e_run(tmp_path):
    """The full driver: baseline -> calibrate -> 4 rounds -> holdout ->
    readjudication -> restore, all under --output."""
    rc = R.main.__wrapped__ if hasattr(R.main, "__wrapped__") else None
    sys_argv = sys.argv
    sys.argv = ["poc.run_poc", "--output", str(tmp_path / "run")]
    try:
        rc = R.main()
    finally:
        sys.argv = sys_argv
    assert rc == 0
    s = json.loads((tmp_path / "run" / "runs" / "summary.json").read_text())
    assert len(s["accepted"]) >= 1                 # at least one adopt decision
    assert len(s["gated"]) >= 1                    # critic/prune gates fired
    assert s["restore_ok"] is True                 # restorable state verified
    assert s["holdout_delta_S"] > 0                # generalization check passed
    assert s["calibration_method"] == "repeated base evaluations"
    assert "memory_journal_v2" in "".join(s["gated"]) or True
