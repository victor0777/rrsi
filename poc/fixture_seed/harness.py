"""Fixture harness (baseline). Deterministic stand-in for a real agent harness:
the file content IS the harness state the PoC's scoring model reads."""

STATE_DIR_LAYOUT = "runs/{job}/trials"

CONFIG_PATH = "config.json"


def main(task, config):
    """One trial: produce a deliverable for `task`."""
    deliverable = draft(task)
    write_output(deliverable)
    return deliverable


def draft(task):
    return {"answer": task["question"]}


def write_output(d):
    return d
