"""Functional tests: `boost run` — adapt + wire tools + (optionally) execute.

Execution needs the OpenAI Agents SDK (not installed in CI) and a key, so these
exercise the offline surface: the ``--print`` runner and the graceful
degradation when the framework is absent. They must NOT import/run the SDK.
"""
from __future__ import annotations


def test_run_print_emits_a_compilable_runner(boost, installed):
    r = boost("run", installed, "target.py", "--print")
    assert "from agents import Agent" in r.out
    assert "def read_file(" in r.out and "run_sync(" in r.out
    compile(r.out, "<printed>", "exec")           # it's valid Python


def test_run_print_wires_boost_model_by_default(boost, installed):
    r = boost("run", installed, "--print")
    assert "LitellmModel" in r.out
    assert "anthropic/" in r.out                  # boost's default model, prefixed


def test_run_print_model_none_omits_litellm(boost, installed):
    r = boost("run", installed, "--print", "--model", "none")
    assert "LitellmModel" not in r.out


def test_run_print_writes_file_with_o(boost, installed, tmp_path):
    dest = tmp_path / "runner.py"
    r = boost("run", installed, "--print", "-o", str(dest))
    assert dest.exists()
    compile(dest.read_text(encoding="utf-8"), "<file>", "exec")
    assert "wrote runner" in r.out.lower()


def test_run_target_reaches_the_prompt(boost, installed):
    r = boost("run", installed, "src/app.py", "--print")
    assert "`src/app.py`" in r.out


def test_run_print_o_write_error_is_a_clean_boosterror(boost, installed, tmp_path):
    # a path whose parent is a file (not a dir) makes the write fail with an
    # OSError, which must surface as a BoostError, not a traceback.
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    r = boost("run", installed, "--print", "-o", str(blocker / "nested.py"), expect=1)
    assert "cannot write" in (r.out + r.err).lower()


def test_run_without_framework_degrades_cleanly(boost, installed):
    # openai-agents is not installed in CI: execution must raise a helpful
    # BoostError (exit 1), never a traceback.
    r = boost("run", installed, expect=1)
    blob = (r.out + r.err).lower()
    assert "openai agents sdk" in blob or "openai-agents" in blob
    assert "pip install" in blob
    assert "--print" in blob                       # points at the offline path


def test_run_unknown_skill_errors(boost, tapped):
    boost("run", "does-not-exist", "--print", expect=1)


def test_run_missing_name_is_usage_error(boost):
    boost("run", expect=2)                         # argparse: name is required
