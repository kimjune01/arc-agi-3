"""reasoner harness — checkpoint save/restore (the durable-memory continuation).

The agentic loop itself needs the live API + claude, so it isn't unit-tested here; this pins the
memory-checkpoint plumbing that lets learning compound across runs.
"""

from arc_agi_3.agents import reasoner


def test_checkpoint_round_trip(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setattr(reasoner, "STATE_DIR", state)
    (state / "notes.md").write_text("ACTION1 = up\n")
    (state / "transitions.jsonl").write_text('{"action":"ACTION1"}\n')

    cp = tmp_path / "ckpt"
    reasoner._save_checkpoint(cp)
    assert (cp / "notes.md").read_text() == "ACTION1 = up\n"          # memory snapshotted
    assert (cp / "transitions.jsonl").exists()

    # a later run starts blank, then resumes from the checkpoint
    (state / "notes.md").unlink()
    (state / "transitions.jsonl").unlink()
    n = reasoner._restore_checkpoint(cp)
    assert n == 2                                                     # both memory files restored
    assert (state / "notes.md").read_text() == "ACTION1 = up\n"      # continuation


def test_restore_is_noop_for_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(reasoner, "STATE_DIR", tmp_path / "state")
    assert reasoner._restore_checkpoint(tmp_path / "empty-ckpt") == 0  # nothing to resume
