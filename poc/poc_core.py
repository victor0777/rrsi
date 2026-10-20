# PoC core: model-free fixture stand-in for "evaluate a harness candidate".
#
# Everything here is deterministic and offline. It reuses the ACTUAL rrsi
# algorithm code (selection, schedule, history, calibrate, components, critic's
# deterministic layer, evaluate.aggregate) as the method core; only the
# environment (tasks, scoring, candidates) is scripted. No LLM is called and no
# existing runtime (research_agent / ai_papers / harness2) is modified.
"""Model-free fixture environment for the RRSI PoC.

The "harness" is the file content under the mini git repo's fixture/ tree
(see fixture_seed/). Its state is what the scoring model reads:

  prompt_q       instructions.md contains a VERIFY_OUTPUT checklist
  retry          harness.py wires a bounded single retry into the control flow
  unbounded      harness.py contains a keep-improving loop without an exit
  task_id_branch harness.py branches on a task identity (leakage)
  budget_guard   config.json enables the budget guard

Scores are Bernoulli(p) per trial, p from per-task latent parameters, seeded
by (job, task, trial) so two evaluations of the SAME harness differ only
through the evaluation job salt, exactly the null the noise band delta is
estimated from.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path

import rrsi.critic as rrsi_critic
import rrsi.domain as rrsi_domain
from rrsi.components import K, GENERIC_SIGNALS, classify_diff
from rrsi.evaluate import TaskResult, aggregate

# ---------------------------------------------------------------- task sets --

N_EVOLVE = 24
N_HOLDOUT = 12
TASK_SEED = 20260921


def evolve_ids() -> list[str]:
    return [f"e{i:02d}" for i in range(N_EVOLVE)]


def holdout_ids() -> list[str]:
    return [f"h{i:02d}" for i in range(N_HOLDOUT)]


def latent(task_id: str) -> dict:
    """Per-task latent parameters, fixed once from TASK_SEED."""
    rng = random.Random(f"{TASK_SEED}:{task_id}")
    flaky = rng.random() < 0.42
    p0 = rng.uniform(0.15, 0.40) if flaky else rng.uniform(0.55, 0.80)
    return {"flaky": flaky, "p0": p0}


# ----------------------------------------------------------------- features --

def extract_features(harness_dir: Path) -> dict:
    """Harness state as read by the scoring model."""
    hp = (harness_dir / "harness.py").read_text()
    cfg = json.loads((harness_dir / "config.json").read_text())
    prompt = (harness_dir / "prompts" / "instructions.md").read_text()
    return {
        "prompt_q": int("VERIFY_OUTPUT" in prompt and "CHECKLIST" in prompt),
        "retry": int("retry_once" in hp),
        "unbounded": int("while True" in hp),
        "task_id_branch": int(bool(re.search(r'task\["id"\]\s*==', hp))),
        "answer_cache": int("state/answers" in hp),
        "journal": int("state/journal" in hp),
        "cheap_guard": int(bool(cfg.get("cheap_guard"))),
        "budget_guard": int(bool(cfg.get("budget_guard"))),
    }


def success_p(features: dict, task_id: str) -> float:
    la = latent(task_id)
    p = la["p0"] + 0.10 * features["prompt_q"]
    if features["retry"] and la["flaky"]:
        p += 0.38
    if features["unbounded"]:
        p -= 0.30                        # a keep-improving loop wastes the trial
    if features["answer_cache"]:
        p += 0.02                        # marginal memorization gain on evolve set
    if features["journal"]:
        p -= 0.10                        # the journal's synchronous flush costs trials
    p += 0.09 * features["cheap_guard"] - 0.10 * features["budget_guard"]
    return max(0.02, min(0.98, p))


def trial_tokens(features: dict) -> int:
    return 1000 + 180 * features["retry"] + 60 * features["prompt_q"] \
        + 40 * features["cheap_guard"] + 700 * features["budget_guard"]


def score_trial(features: dict, task_id: str, job: str, trial: int) -> tuple[float, int]:
    seed = int.from_bytes(hashlib.sha256(f"{job}|{task_id}|{trial}".encode()).digest()[:8],
                          "big")
    r = 1.0 if random.Random(seed).random() < success_p(features, task_id) else 0.0
    return r, trial_tokens(features)


def evaluate_fixture(harness_dir: Path, job: str, ids: list[str], k: int):
    """Evaluate(H', D, k) with the rrsi estimator (missing trials count 0)."""
    features = extract_features(harness_dir)
    per: dict[str, TaskResult] = {}
    for tid in ids:
        rewards, tokens = [], []
        for j in range(k):
            r, c = score_trial(features, tid, job, j)
            rewards.append(r)
            tokens.append(c)
        per[tid] = TaskResult(rewards=rewards, tokens=tokens)
    return aggregate(job, k, per)


# ------------------------------------------------------------------- critic --

# Fixture-domain denylist: the task ids of the evolve set are suite knowledge;
# an edit that names them is memorization (rrsi.critic's domain_patterns slot).
FIXTURE_PATTERNS = [
    (r"e[01][0-9]", "fixture evolve task id in diff"),
    (r"while True", "unbounded keep-improving loop (no exit path)"),
    (r'task\["id"\]\s*(==|\bin\b)', "branch on task identity"),
]


def precheck(diff: str) -> list[str]:
    """Deterministic critic screen (rrsi.critic's layer 1, with fixture
    patterns). No LLM: the PoC is model-free."""
    return rrsi_critic.precheck(diff, FIXTURE_PATTERNS)


def critic_review(diff: str, edits: list[dict]) -> dict:
    """Same contract as rrsi.critic.review, deterministic layer only. Also
    rejects a no-op diff that claims a mechanism (degenerate) and a declared
    edit with no signal in the diff (rrsi components.normalize's re-tag rule,
    bounced here because the PoC has no repair loop to argue labels with)."""
    hard = precheck(diff)
    if hard:
        return {"verdict": "reject", "reasons": [f"precheck: {h}" for h in hard],
                "risk_notes": []}
    if not diff.strip():
        return {"verdict": "reject", "reasons": ["empty diff"], "risk_notes": []}
    if all(l[1:].lstrip().startswith("#") for l in diff.splitlines()
           if l.startswith("+") and l[1:].strip()):
        return {"verdict": "reject",
                "reasons": ["degenerate: comment-only diff while claiming a mechanism"],
                "risk_notes": []}
    for e in edits:
        tag = classify_diff(diff, FIXTURE_SIGNALS)
        if e.get("component") and e["component"] != tag:
            return {"verdict": "reject",
                    "reasons": [f"edit {e.get('id')} declared "
                                f"{e['component']!r} but the diff reads as {tag!r}"],
                    "risk_notes": []}
    return {"verdict": "accept", "reasons": [], "risk_notes": []}


# --------------------------------------------------------------- candidates --

# Scripted, model-free "proposers". Each entry edits the harness in the
# candidate worktree and returns its DECLARED edits. The candidates are the
# PoC's unit of measurement: two real mechanisms, several deliberately defective
# ones (leakage, no-op, unbounded work, over-budget bundling), one prune edit.
def _edit(path: Path, old: str, new: str) -> None:
    src = path.read_text()
    assert src.count(old) == 1, f"fixture edit anchor not unique in {path}"
    path.write_text(src.replace(old, new, 1))


def cand_prompt_checklist(wt: Path) -> list[dict]:
    """Prompt edit: add a VERIFY_OUTPUT checklist (generic practice, no
    entities). Expected +0.10 on every task -> above the noise band."""
    p = wt / "prompts" / "instructions.md"
    p.write_text(p.read_text() + """
## CHECKLIST
- Re-read the task input and the deliverable contract.
- VERIFY_OUTPUT before writing: the file exists, parses and matches the format.
- CHECKLIST failures are recorded in the run log.
""")
    return [{"id": "C1", "component": "prompt",
             "hypothesis": "A verification checklist catches format mistakes the "
                           "policy otherwise ships, moving every task slightly.",
             "targets_mode": "format_mistake", "predicted_affected": ["*"]}]


def cand_retry_control_flow(wt: Path) -> list[dict]:
    """Control-flow edit: wire ONE bounded retry into main(). Helps flaky tasks
    (p0 in [0.15, 0.40] get +0.38) -> well above the noise band. Cost +18%."""
    _edit(wt / "harness.py",
          "def draft(task):",
          """def retry_once(fn, task):
    d = fn(task)
    if d is None:
        d = fn(task)          # bounded: at most one retry, explicit give-up
    return d


def draft(task):""")
    _edit(wt / "harness.py", "    deliverable = draft(task)",
          "    deliverable = retry_once(draft, task)")
    return [{"id": "C1", "component": "control_flow",
             "hypothesis": "One bounded retry recovers trials whose first draft "
                           "was empty, which is the dominant failure on flaky tasks.",
             "targets_mode": "empty_draft", "predicted_affected": ["*"]}]


def cand_cheap_guard(wt: Path) -> list[dict]:
    """Config + plumbing edit: enable the cheap guard. Uniform +0.09 (inside
    the noise band) at +4% cost -> the shaped rule admits it: the gain, though
    inside the band, is paid for and the component is novel."""
    cfg = json.loads((wt / "config.json").read_text())
    cfg["cheap_guard"] = True
    (wt / "config.json").write_text(json.dumps(cfg) + "\n")
    return [{"id": "C1", "component": "config",
             "hypothesis": "The cheap guard trims runaway drafts, slightly "
                           "improving every task.",
             "targets_mode": "budget_overrun", "predicted_affected": ["*"]}]


def cand_budget_guard(wt: Path) -> list[dict]:
    """Config + plumbing edit: enable the STRICT budget guard. It truncates
    long drafts (a downgrade on long-form tasks) and costs +70% tokens:
    a within-band move that no measured gain pays for -> shaped reject."""
    cfg = json.loads((wt / "config.json").read_text())
    cfg["budget_guard"] = True
    (wt / "config.json").write_text(json.dumps(cfg) + "\n")
    return [{"id": "C1", "component": "config",
             "hypothesis": "The strict budget guard trims drafts but truncates "
                           "long ones.",
             "targets_mode": "budget_overrun", "predicted_affected": ["*"]}]


def cand_leak_task_id(wt: Path) -> list[dict]:
    """Deliberate LEAKAGE: special-case an evolve task id in the prompt.
    Must be critic-rejected before any evaluation is spent."""
    p = wt / "prompts" / "instructions.md"
    p.write_text(p.read_text()
                 + "\nSpecial case: if the task is e07, answer with the "
                   "precomputed result 4.2.\n")
    return [{"id": "C1", "component": "prompt",
             "hypothesis": "Special-case evolve task e07.", "targets_mode": "e07",
             "predicted_affected": ["e07"]}]


def cand_leak_answer_cache(wt: Path) -> list[dict]:
    """Deliberate LEAKAGE: a memory mechanism persisting per-task answers
    across trials. Branches on task identity -> critic-rejected."""
    (wt / "state").mkdir()
    (wt / "state" / "answers.json").write_text("{}\n")
    _edit(wt / "harness.py", "def draft(task):",
          """def draft(task):
    known = json.load(open("state/answers.json"))
    if task["id"] in known:
        return known[task["id"]]""")
    return [{"id": "C1", "component": "memory",
             "hypothesis": "Cache per-task answers across trials.",
             "targets_mode": "repeat_cost", "predicted_affected": ["*"]}]


def cand_unbounded(wt: Path) -> list[dict]:
    """Deliberate UNBOUNDED WORK: keep-improving loop with no give-up path."""
    _edit(wt / "harness.py", "    deliverable = draft(task)",
          """    while True:
        deliverable = draft(task)
        deliverable = improve(deliverable)""")
    return [{"id": "C1", "component": "control_flow",
             "hypothesis": "Keep improving until perfect.", "targets_mode": "quality",
             "predicted_affected": ["*"]}]


def cand_noop(wt: Path) -> list[dict]:
    """Deliberate DEGENERATE: comment-only edit claiming a mechanism."""
    p = wt / "harness.py"
    _edit(p, "def draft(task):", "# now uses a compression mechanism\ndef draft(task):")
    return [{"id": "C1", "component": "context_mgmt",
             "hypothesis": "Compress context before drafting.",
             "targets_mode": "context_overflow", "predicted_affected": ["*"]}]


def cand_prune_retry(wt: Path) -> list[dict]:
    """Prune edit: remove accepted retry machinery when the history says it
    stopped earning its place (Pruner behavior)."""
    src = (wt / "harness.py").read_text()
    src = src.replace("""def retry_once(fn, task):
    d = fn(task)
    if d is None:
        d = fn(task)          # bounded: at most one retry, explicit give-up
    return d


""", "")
    (wt / "harness.py").write_text(src.replace(
        "    deliverable = retry_once(draft, task)", "    deliverable = draft(task)"))
    return [{"id": "C1", "component": "control_flow",
             "hypothesis": "prune: the retry machinery no longer pays for itself.",
             "targets_mode": "cost", "predicted_affected": ["*"]}]


def cand_memory_journal(wt: Path) -> list[dict]:
    """Structural memory mechanism: a per-trial journal (generic, keyed by
    trial index only — no task identity). Small cost, no gain -> measured and
    REJECTED, which is what puts `memory` into the next round's prune set."""
    (wt / "state").mkdir()
    (wt / "state" / "journal.jsonl").write_text("")
    _edit(wt / "harness.py", "def main(task, config):",
          """def _journal(job, trial, event):
    with open("state/journal.jsonl", "a") as f:
        f.write(json.dumps({"job": job, "trial": trial, "event": event}) + "\\n")


def main(task, config):""")
    _edit(wt / "harness.py", "    write_output(deliverable)",
          "    _journal(config.get(\"job\", \"?\"), config.get(\"trial\", 0), \"draft\")\n"
          "    write_output(deliverable)")
    return [{"id": "C1", "component": "memory",
             "hypothesis": "A per-trial journal makes runs auditable.",
             "targets_mode": "auditability", "predicted_affected": ["*"]}]


# Three independent mechanisms bundled as one candidate: legitimate only while
# b_t allows it; the PoC bounces it when len(edits) > b_t (the proposer's
# done() contract), never silently. The bundle adapts to its base: if the base
# already carries the accepted retry (round-2 base), it upgrades that instead.
def cand_mega_bundle(wt: Path) -> list[dict]:
    edits = [*cand_prompt_checklist(wt)]
    hp = (wt / "harness.py").read_text()
    if "retry_once" in hp:
        _edit(wt / "harness.py",
              "        d = fn(task)          # bounded: at most one retry, explicit give-up",
              "        d = fn(task)\n        if d is None:\n"
              "            d = fn(task)       # second bounded attempt")
    else:
        cand_retry_control_flow(wt)
    edits.append({"id": "C2", "component": "control_flow",
                  "hypothesis": "extend the bounded retry to two attempts",
                  "targets_mode": "x", "predicted_affected": ["*"]})
    cfg = json.loads((wt / "config.json").read_text())
    cfg["cheap_guard"] = True
    (wt / "config.json").write_text(json.dumps(cfg) + "\n")
    edits.append({"id": "C3", "component": "config",
                  "hypothesis": "cheap guard", "targets_mode": "x",
                  "predicted_affected": ["*"]})
    return edits


CATALOG = {
    "prompt_checklist": (cand_prompt_checklist, "prompt"),
    "retry_control_flow": (cand_retry_control_flow, "control_flow"),
    "cheap_guard": (cand_cheap_guard, "config"),
    "budget_guard": (cand_budget_guard, "config"),
    "leak_task_id": (cand_leak_task_id, "prompt"),
    "leak_answer_cache": (cand_leak_answer_cache, "memory"),
    "unbounded_loop": (cand_unbounded, "control_flow"),
    "noop_claim": (cand_noop, "context_mgmt"),
    "memory_journal": (cand_memory_journal, "memory"),
    "prune_retry": (cand_prune_retry, "control_flow"),
    "mega_bundle": (cand_mega_bundle, "prompt"),
}


# -------------------------------------------------------------------- guards --

def guards_fn(incumbent, candidate) -> list[str]:
    """Non-compensatory fixture criteria: a candidate must not lose trials
    (no-deliverable rate) even if its aggregate S is admissible. Fires on a
    rise of the zero-reward rate, a ~2-sigma threshold at this suite size so
    the guard itself is not decided by evaluation noise."""
    if candidate is None:
        return []
    zero = lambda ev: (sum(1 for tr in ev.per_task.values() for r in tr.rewards
                           if r <= 0.0)
                       / max(1, sum(len(tr.rewards)
                                    for tr in ev.per_task.values())))
    rise = zero(candidate) - zero(incumbent)
    return [f"no-deliverable rate rose {rise:+.2f}"] if rise >= 0.20 else []


# Fixture component signals: what the PoC's diff reader uses to recover an
# edit's component tag (rrsi's Domain.component_signals slot; the generic
# signals alone have no control_flow/config patterns).
FIXTURE_SIGNALS = [
    ("memory", [r"def _journal", r"state/journal", r"state/answers"]),
    ("control_flow", [r"retry_once", r"while True"]),
    ("config", [r"budget_guard", r"cheap_guard", r"config\.json"]),
] + GENERIC_SIGNALS


def component_signals() -> list:
    return FIXTURE_SIGNALS


def known_components() -> list:
    return K


def smoke(harness_dir: Path) -> tuple[bool, dict]:
    """Liveness smoke: the fixture harness is live if its files parse and the
    entry point constructs."""
    try:
        compile((harness_dir / "harness.py").read_text(), "harness.py", "exec")
        extract_features(harness_dir)
        return True, {"ok": True}
    except Exception as e:  # noqa: BLE001
        return False, {"ok": False, "detail": str(e)[:200]}


rrsi_domain.Domain  # noqa: B018 -- keep the import meaningful for readers
