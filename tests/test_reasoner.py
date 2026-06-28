"""reasoner harness — checkpoint save/restore (the durable-memory continuation).

The agentic loop itself needs the live API + claude, so it isn't unit-tested here; this pins the
memory-checkpoint plumbing that lets learning compound across runs.
"""

import re

from arc_agi_3.agents import reasoner


def _permitted(cmd: str, allow: list[str]) -> bool:
    """Does the allowlist grant `cmd` (e.g. 'uv run arcg notes')? Mirrors Claude Code's
    token-boundary prefix match: `Bash(uv run arcg note:*)` grants `uv run arcg note [args]` but
    NOT the distinct subcommand `uv run arcg notes`. A trailing `:*` is a whole-token prefix."""
    for entry in allow:
        m = re.fullmatch(r"Bash\((.*?)(:\*)?\)", entry)
        if not m:
            continue
        prefix = m.group(1)
        if cmd == prefix or cmd.startswith(prefix + " "):
            return True
    return False


def _instructed_cmds(task: str) -> set[str]:
    """The tool invocations a task tells the agent to run, as `uv run <tool> <subcmd>`. The task
    writes them both fully (`uv run arcg forget`) and bare (`arcg notes` in the re-hydrate list),
    so the `uv run` prefix is optional."""
    return {f"uv run {tool} {sub}"
            for tool, sub in re.findall(r"(?:uv run )?(arcg|jotter|simmer|dagger) (\w+)", task)}


def test_consolidate_pass_may_read_the_commands_it_is_told_to():
    """The sleep pass is instructed to re-hydrate with `arcg notes` before remediating, but the
    backward allowlist must actually grant it — otherwise remediation silently fails ('notes
    unreadable') and the note corpus grows unbounded, defeating 'memory is a cache'."""
    for cmd in _instructed_cmds(reasoner.CONSOLIDATE_TASK):
        assert _permitted(cmd, reasoner._BACKWARD_ALLOWED), f"backward pass can't run: {cmd}"


def test_wake_commands_are_permitted_too():
    """Same check for the forward pass: every tool command its map names must be granted."""
    for cmd in _instructed_cmds(reasoner.FORWARD_TASK):
        assert _permitted(cmd, reasoner._FORWARD_ALLOWED), f"wake pass can't run: {cmd}"


def test_simmer_is_available_to_both_passes():
    """simmer is the FREE deduction third of the architecture: the wake pass predicts in it before
    spending a real action (plan in simmer, commit in piper), the sleep pass tests the engine vs the
    corpus. Both maps must name it and both allowlists must grant it — locking it out forces every
    hypothesis onto real budget."""
    assert "simmer" in reasoner.FORWARD_TASK and "simmer" in reasoner.CONSOLIDATE_TASK
    assert _permitted("uv run simmer predict", reasoner._FORWARD_ALLOWED)
    assert _permitted("uv run simmer test", reasoner._BACKWARD_ALLOWED)


def test_prompts_are_light_goal_based_maps():
    """Progressive disclosure: each role-scoped prompt is a MAP that defers specifics to `--help`,
    bounded by its GOAL — not a manual, and not a hard turn-count cap."""
    for task in (reasoner.FORWARD_TASK, reasoner.CONSOLIDATE_TASK):
        assert "--help" in task                       # hands off to the next disclosure layer
        assert "GOAL" in task and "STOP" in task       # goal-based, self-terminating
        assert "tool calls" not in task                # no hard-coded turn cap in the prompt
        assert not re.search(r"~?\d+\s+tool", task)
        assert len(task.splitlines()) < 24             # a map, not a manual


def test_wake_map_has_a_soft_self_stop_forcing_function():
    """With no hard turn cap, the wake pass must self-terminate at its goal — without a forcing
    function it re-inspects memory until the wall-clock timeout (observed: both wake units timed out
    at 0 actions). The bound is the ATTEMPT: act once, record the episode, STOP — not a polished
    finding (over-optimizing for a clean result is what made it dither). epmem may accumulate."""
    assert "SELF-STOP" in reasoner.FORWARD_TASK
    assert "ATTEMPT" in reasoner.FORWARD_TASK            # the bound is one attempt, not a count
    assert "ACCUMULATING" in reasoner.FORWARD_TASK       # an episode need not consolidate this cycle


def test_no_hard_turn_cap_by_default():
    """The unit runners impose no `--max-turns`: the session is bounded by its goal, timeout is the
    only backstop. (A hard cap once starved the sleep pass before remediation.)"""
    cmd = reasoner._build_cmd("t", ["Bash(uv run jotter:*)"], model="sonnet", max_turns=None)
    assert "--max-turns" not in cmd
    capped = reasoner._build_cmd("t", [], model="sonnet", max_turns=9)
    assert capped[capped.index("--max-turns") + 1] == "9"   # still honored when explicitly set


def test_decompose_help_carries_the_attribution_discipline():
    """Keep `--help` healthy: the consolidation discipline (the contrast-pair self-check and the
    leave-ambiguous rule) lives in `dagger decompose --help`, not in the prompt. This is what the
    light prompt points at, so it must actually be there."""
    import subprocess

    out = subprocess.run(["uv", "run", "dagger", "decompose", "--help"],
                         capture_output=True, text=True, cwd=reasoner.PROJECT_ROOT).stdout.lower()
    assert "contrast pair" in out
    assert "differs" in out                            # the jotter-show self-check
    assert "open" in out and "ambiguous" in out        # leave the unsettled ones for the next pass


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
