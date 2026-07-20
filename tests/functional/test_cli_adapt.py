"""Functional tests: `boost adapt` — render a skill as framework source."""
from __future__ import annotations


def test_adapt_installed_skill_to_crewai_stdout(boost, installed):
    r = boost("adapt", installed, "--to", "crewai")
    assert "from crewai import Agent" in r.out
    assert "brainstorming = Agent(" in r.out
    assert 'role="brainstorming"' in r.out
    # emitted source must be valid Python
    compile(r.out, "<crewai>", "exec")


def test_adapt_to_agents_sdk(boost, installed):
    r = boost("adapt", installed, "--to", "agents-sdk")
    assert "from agents import Agent" in r.out
    assert 'name="brainstorming"' in r.out
    compile(r.out, "<sdk>", "exec")


def test_adapt_from_tap_without_installing(boost, tapped):
    # resolves via the tap clone even though nothing is installed
    r = boost("adapt", "brainstorming", "--to", "crewai")
    assert "brainstorming = Agent(" in r.out


def test_adapt_writes_file_with_o(boost, installed, tmp_path):
    dest = tmp_path / "out" / "reviewer.py"
    r = boost("adapt", installed, "--to", "crewai", "-o", str(dest))
    assert dest.exists()
    compile(dest.read_text(), "<crewai>", "exec")
    assert "adapted" in r.out  # success line


def test_unknown_framework_errors(boost, installed):
    r = boost("adapt", installed, "--to", "langchain", expect=1)
    assert "unknown framework" in (r.out + r.err).lower()


def test_missing_to_flag_errors(boost, installed):
    # --to is required
    boost("adapt", installed, expect=2)


def test_unknown_skill_errors(boost, tapped):
    boost("adapt", "does-not-exist", "--to", "crewai", expect=1)
