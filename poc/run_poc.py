# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS.
"""RRSI PoC R0 driver: an RRSI-style self-improvement loop over a model-free
fixture harness.

    python3 -m poc.run_poc --output poc/runs/r0

Everything is written under --output. The rrsi core (selection, schedule,
history, calibrate, components, critic's deterministic layer, evaluate) is used
UNMODIFIED as the method core; the PoC supplies a scripted environment instead
of benchmarks and LLM calls. No existing runtime is modified.

Structure verified end to end:
  baseline x4 -> calibrate delta -> rounds (worktree candidates, critic screen,
  annealed budget, selection with noise floor + cost rule, prune set) ->
  holdout comparison -> re-adjudication without re-evaluation -> restore.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rrsi import gitops as G                        # noqa: E402
from rrsi.calibrate import calibrate                # noqa: E402
from rrsi.config import RRSIConfig                  # noqa: E402
from rrsi.history import History, exploration, stall_flag  # noqa: E402
from rrsi.schedule import edit_budget               # noqa: E402
from rrsi.selection import Candidate, select_round  # noqa: E402
from rrsi.evaluate import EvalResult                # noqa: E402

from poc import poc_core as F                       # noqa: E402

CONFIG = RRSIConfig(T=4, k=2, m=3, b_min=1, b_max=3, w=2, m_draft=1, n_prune=2,
                    delta_z=1.0, notes={"fixture": "model-free PoC",
                                        "delta_z": "z=1: a small fixture suite gives "
                                                   "a large sd(null); z=2 would double "
                                                   "the band above every scripted gain"})

# Rounds: each entry is (candidate names, expectation note). The note is what
# the run RECORDS as intent; the selection decides, not this table.
ROUNDS = [
    {"candidates": ["prompt_checklist", "leak_task_id", "noop_claim"],
     "note": "one real mechanism + one task-id leak + one degenerate claim"},
    {"candidates": ["retry_control_flow", "leak_answer_cache", "unbounded_loop"],
     "note": "real control-flow mechanism + per-task answer cache + unbounded loop"},
    {"candidates": ["cheap_guard", "budget_guard", "mega_bundle", "memory_journal"],
     "note": "cheap in-band gain + costly downgrade + 3-edit bundle under b_t=2 "
             "+ memory machinery to be measured and rejected"},
    {"candidates": ["memory_journal_v2", "prune_retry"],
     "note": "declined candidates on pruned / healthy components"},
]


def log(msg: str) -> None:
    print(f"[poc] {msg}", flush=True)


# ------------------------------------------------------------------- setup --

def init_repo(out: Path) -> Path:
    """A throwaway mini git repo holding the fixture harness; the rrsi
    candidate structure (branch + worktree per candidate, fast-forward on
    accept) is exercised against THIS repo, never against poc/ itself."""
    repo = out / "repo"
    if (repo / ".git").exists():
        shutil.rmtree(repo, ignore_errors=True)
    repo.mkdir(parents=True)
    G.sh(["git", "init", "-q", "-b", "main"], repo)
    seed = ROOT / "poc" / "fixture_seed"
    (repo / "fixture").mkdir()
    for rel in ("harness.py", "config.json", "prompts/instructions.md",
                "skills/retry.md"):
        dst = repo / "fixture" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(seed / rel, dst)
    G.git(repo, "add", "-A")
    G.git(repo, "commit", "-q", "-m", "H0 baseline fixture harness")
    G.ensure_branch(repo, "evolve/fixture", "main")
    return repo


def hdir_of(wt: Path) -> Path:
    return wt / "fixture"


def tree_of(repo: Path, ref: str) -> str:
    return G.tree_hash(repo, ref, "fixture")


# ------------------------------------------------------------------ rounds --

def draft_candidate(wt: Path, name: str, budget: int,
                    prune_components: set[str]) -> tuple[Candidate | None, str, str]:
    """One scripted proposer -> (Candidate | None, diff, decline_note).

    Proposer-side hard rules are enforced HERE, before any evaluation is
    spent, mirroring done() in the real loop: the annealed budget b_t, and the
    Pruner's refusals (a component in B_t is not redrawn; a prune edit needs
    its target in B_t). Over-budget or declined candidates are recorded as
    outcomes, never silently fixed."""
    if name.startswith("prune_"):
        target = name[len("prune_"):]
        if target not in prune_components:
            return None, "", (f"proposer declined: {target} is not in the prune "
                              f"set B_t ({sorted(prune_components) or 'empty'}); "
                              f"a prune edit needs history evidence")
    if name.endswith("_v2"):
        base = name[:-3]
        if base not in F.CATALOG:
            raise KeyError(f"declined-candidate base {base!r} not in catalog")
        _, declared = F.CATALOG[base]
        if declared in prune_components:
            return None, "", (f"proposer declined: {declared} is in the prune set "
                              f"B_t with recent yield <= 0; not redrawing it")
    edits_fn, _ = F.CATALOG[name[:-3] if name.endswith("_v2") else name]
    edits = edits_fn(hdir_of(wt))
    if len(edits) > budget:
        return Candidate(name, edits, gate_failure="over_budget",
                         detail=f"{len(edits)} edits exceed b_t = {budget}"), "", ""
    ok, detail = F.smoke(hdir_of(wt))
    if not ok:
        return Candidate(name, edits, gate_failure="smoke_fail",
                         detail=json.dumps(detail)), "", ""
    diff = G.diff_with_new_files(wt, "fixture")
    verdict = F.critic_review(diff, edits)
    if verdict["verdict"] != "accept":
        return Candidate(name, edits, gate_failure="critic_reject",
                         detail="; ".join(verdict["reasons"])[:600]), diff, ""
    commit = G.commit_path(wt, "fixture", f"poc candidate {name}")
    cand = Candidate(name, edits, commit=commit)
    return cand, diff, ""


def run_round(repo: Path, out: Path, history: History, t: int, names: list[str],
              frontier: dict, delta: float) -> None:
    rdir = out / "runs" / f"r{t}"
    rdir.mkdir(parents=True, exist_ok=True)
    budget = edit_budget(t, CONFIG.T, CONFIG.b_min, CONFIG.b_max)
    traj = [x["S"] for x in frontier["trajectory"]]
    sigma = stall_flag(traj, t, CONFIG.w, delta)
    tried = history.tried()
    explore = exploration(t, sigma, tried, CONFIG.m_draft)
    prune = history.prune_set(t, CONFIG.n_prune)
    prune_components = {p["component"] for p in prune}
    (rdir / "directives.json").write_text(json.dumps(
        {"t": t, "b_t": budget, "sigma_t": sigma, "explore": explore,
         "prune_set": prune, "delta": delta}, indent=1))
    log(f"round {t}: b_t={budget} sigma_t={sigma} tried={sorted(tried)} "
        f"prune={sorted(prune_components)}")

    inc_wt = G.worktree_add(repo, out / "wt" / "incumbent", "poc_inc",
                            "evolve/fixture")
    incumbent_ev = F.evaluate_fixture(hdir_of(inc_wt), f"r{t}_incumbent",
                                      F.evolve_ids(), CONFIG.k)
    G.worktree_remove(repo, inc_wt)
    (rdir / "incumbent_eval.json").write_text(json.dumps(incumbent_ev.to_json()))

    cands: list[Candidate] = []
    for name in names:
        branch = f"poc/r{t}{name}"
        wt = G.worktree_add(repo, out / "wt" / name, branch, "evolve/fixture")
        cand, diff, note = draft_candidate(wt, name, budget, prune_components)
        if diff:
            (rdir / f"{name}.diff").write_text(diff)
        if cand is not None:
            if not cand.gate_failure:
                ev = F.evaluate_fixture(hdir_of(wt), f"r{t}{name}",
                                        F.evolve_ids(), CONFIG.k)
                (rdir / name).mkdir(parents=True, exist_ok=True)
                ev.save(rdir / name / "eval.json")
                cand.ev = ev
            else:
                cand.commit = G.rev(repo, branch)
        G.worktree_remove(repo, wt)          # the candidate branch survives
        if cand is None:
            log(f"  {name}: {note}")
            history.append_candidate(t, name, [], "proposer_declined", None, None,
                                     False, None, None, None, note)
            continue
        if cand.gate_failure:
            log(f"  {name}: {cand.gate_failure}: {cand.detail[:130]}")
            history.append_candidate(t, name, cand.edits, cand.gate_failure, None,
                                     None, False, None, None, None, cand.detail)
            continue
        cands.append(cand)

    winner, decisions = select_round(cands, incumbent_ev, frontier["S_star"],
                                     delta, CONFIG,
                                     history.incumbent_component_counts(),
                                     guard_fn=F.guards_fn)
    (rdir / "decisions.json").write_text(json.dumps(
        [d.to_json() for d in decisions], indent=1))
    for name in names:
        cand = next((c for c in cands if c.variant == name), None)
        if cand is None or history.has(t, name):
            continue
        dec = next(d for d in decisions if d.variant == name)
        outcome = ("ACCEPTED" if cand is winner
                   else ("LOST" if dec.admissible else "REJECTED"))
        history.append_candidate(t, name, cand.edits, outcome, dec.delta_S,
                                 dec.delta_C, cand is winner, dec.S, dec.C,
                                 None, dec.reason)
        log(f"  {name}: S={dec.S:.4f} dS={dec.delta_S:+.4f} dC={dec.delta_C:+.3f} "
            f"nu={dec.novelty} -> {outcome}: {dec.reason}")

    if winner is not None:
        G.fast_forward(repo, "evolve/fixture", winner.commit)
        log(f"  ACCEPTED r{t}{winner.variant} -> {winner.commit}")
    else:
        log(f"  no admissible candidate; H_{t + 1} = H_{t}")
    S_new = winner.ev.S if winner else incumbent_ev.S
    C_new = winner.ev.C if winner else incumbent_ev.C
    entry = {"t": t + 1, "S": S_new, "C": C_new,
             "commit": G.rev(repo, "evolve/fixture"),
             "harness_tree": tree_of(repo, "evolve/fixture"),
             "variant": winner.variant if winner else None}
    frontier["trajectory"] = ([x for x in frontier["trajectory"] if x["t"] <= t]
                              + [entry])
    frontier["S_star"] = max(frontier["S_star"], S_new)
    frontier["incumbent"] = entry
    log(f"  H_{t + 1}: S={S_new:.4f} C={C_new} S*={frontier['S_star']:.4f}")


# ------------------------------------------------- post-run verifications --

def holdout_compare(repo: Path, out: Path, h0_commit: str) -> dict:
    """Holdout evaluation of H_final vs H_0, two job salts each. NOT part of
    any acceptance decision: the post-hoc generalization check for audit."""
    rows = {}
    for label, start in (("final", "evolve/fixture"), ("h0", h0_commit)):
        wt = G.worktree_add(repo, out / "wt" / f"heldout_{label}",
                            f"poc/heldout_{label}", start)
        evs = [F.evaluate_fixture(hdir_of(wt), f"heldout_{label}_{salt}",
                                  F.holdout_ids(), CONFIG.k) for salt in ("a", "b")]
        rows[label] = {"ref": G.rev(repo, start), "S": [e.S for e in evs],
                       "C": evs[0].C}
        G.worktree_remove(repo, wt)
    dS = (sum(rows["final"]["S"]) - sum(rows["h0"]["S"])) / 2
    note = ("holdout gain consistent with the evolve-set decision" if dS > 0
            else "HOLDOUT FLAT/NEGATIVE: the evolve-set gain did not generalize; "
                 "the adoption decision stands as decided, flagged for review")
    return {"per_ref": rows, "delta_S_mean": round(dS, 4), "note": note}


def readjudicate(repo: Path, out: Path, t: int, delta: float) -> dict:
    """Re-run Algorithm 2 on the STORED measurements of round t with a
    different noise band. No new evaluation is spent (rrsi
    Run.readjudicate's contract, exercised here)."""
    rdir = out / "runs" / f"r{t}"
    incumbent = EvalResult.load(rdir / "incumbent_eval.json")
    cands, name_of = [], {}
    for name in ROUNDS[t]["candidates"]:
        if not (rdir / name / "eval.json").exists():
            continue
        c = Candidate(name, [{"id": "C1", "component": F.CATALOG[name][1]}])
        c.ev = EvalResult.load(rdir / name / "eval.json")
        cands.append(c)
        name_of[name] = True
    S_star = max(x["S"] for x in json.loads(
        (out / "runs" / "frontier.json").read_text())["trajectory"][:t + 1]) \
        if (out / "runs" / "frontier.json").exists() else incumbent.S
    winner, decisions = select_round(cands, incumbent, S_star, delta, CONFIG,
                                     {}, guard_fn=F.guards_fn)
    return {"t": t, "delta": delta, "re_evaluated": 0,
            "decisions": [d.to_json() for d in decisions],
            "accepted": winner.variant if winner else None}


def restore_check(repo: Path, out: Path, frontier: dict, t: int) -> dict:
    """Point evolve/fixture back at trajectory[t]'s commit and verify the
    harness tree hash matches what the frontier recorded, then restore back
    to the final commit and verify again."""
    entry = next(x for x in frontier["trajectory"] if x["t"] == t)
    G.git(repo, "update-ref", "refs/heads/evolve/fixture", entry["commit"], check=True)
    ok = tree_of(repo, "evolve/fixture") == entry["harness_tree"]
    final = frontier["trajectory"][-1]
    G.git(repo, "update-ref", "refs/heads/evolve/fixture", final["commit"], check=True)
    back = tree_of(repo, "evolve/fixture") == final["harness_tree"]
    return {"restored_to": entry["commit"], "tree_match": ok,
            "restored_back_to_final": back, "ok": bool(ok and back)}


# --------------------------------------------------------------------- main --

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", default=str(ROOT / "poc" / "runs" / "r0"))
    args = ap.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    repo = init_repo(out)
    runs = out / "runs"
    runs.mkdir(exist_ok=True)
    history = History(runs / "history.jsonl")
    if history.path.exists():
        history.path.unlink()

    # ---- baseline: 4 independent evaluations of the SAME harness
    base_evs = []
    for salt in ("base", "base1", "base2", "base3"):
        wt = G.worktree_add(repo, out / "wt" / f"base_{salt}", f"poc/{salt}",
                            "evolve/fixture")
        ev = F.evaluate_fixture(hdir_of(wt), salt, F.evolve_ids(), CONFIG.k)
        ev.save(runs / f"{salt}_eval.json")
        base_evs.append(ev)
        G.worktree_remove(repo, wt)
    cal = calibrate(base_evs, z=CONFIG.delta_z)
    (runs / "calibration.json").write_text(json.dumps(cal, indent=1))
    delta = cal["delta"]
    S0 = base_evs[0].S
    log(f"baseline S={S0:.4f} C={base_evs[0].C} delta={delta:.4f} "
        f"(method: {cal['method']})")

    frontier = {"domain": "fixture", "h0_commit": G.rev(repo, "evolve/fixture"),
                "S_star": S0, "delta": delta,
                "trajectory": [{"t": 0, "S": S0, "C": base_evs[0].C,
                                "commit": G.rev(repo, "evolve/fixture"),
                                "harness_tree": tree_of(repo, "evolve/fixture")}]}
    history.append({"t": 0, "variant": "-", "edit_id": None, "component": None,
                    "hypothesis": "H_0 baseline", "outcome": "BASELINE",
                    "S": S0, "C": base_evs[0].C, "accepted": True,
                    "delta_S": None, "delta_C": None, "bundle": 0})

    # ---- rounds
    for t, rd in enumerate(ROUNDS):
        run_round(repo, out, history, t, rd["candidates"], frontier, delta)
    (runs / "frontier.json").write_text(json.dumps(frontier, indent=1))

    # ---- post-run verifications
    holdout = holdout_compare(repo, out, frontier["h0_commit"])
    (runs / "holdout.json").write_text(json.dumps(holdout, indent=1))
    log(f"holdout dS={holdout['delta_S_mean']:+.4f}: {holdout['note']}")
    readj = readjudicate(repo, out, t=2, delta=delta * 2)
    (runs / "readjudication.json").write_text(json.dumps(readj, indent=1))
    log(f"readjudication (doubled delta, 0 new evals): "
        f"accepted={readj['accepted']}")
    restore = restore_check(repo, out, frontier, t=1)
    (runs / "restore.json").write_text(json.dumps(restore, indent=1))
    log(f"restore check: {restore}")

    accepted = [r for r in history.records() if r.get("outcome") == "ACCEPTED"]
    rejected = [r for r in history.records() if r.get("outcome") == "REJECTED"]
    gated = [r for r in history.records()
             if r.get("outcome") in ("critic_reject", "over_budget",
                                     "proposer_declined", "smoke_fail")]
    summary = {
        "baseline_S": S0, "delta": delta, "calibration_method": cal["method"],
        "final_S": frontier["trajectory"][-1]["S"], "S_star": frontier["S_star"],
        "accepted": [f"r{r['t']}:{r['variant']} ({r['component']}, "
                     f"dS={r['delta_S']:+.4f})" for r in accepted],
        "rejected_measured": [f"r{r['t']}:{r['variant']}" for r in rejected],
        "gated": [f"r{r['t']}:{r['variant']} [{r['outcome']}]" for r in gated],
        "holdout_delta_S": holdout["delta_S_mean"],
        "restore_ok": restore["ok"],
        "rounds_run": len(ROUNDS),
        "model_free": True,
    }
    (runs / "summary.json").write_text(json.dumps(summary, indent=1))
    log(f"summary: {json.dumps(summary, indent=1)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
