# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: every zizmor ignore still points at the line it was written for.

``.github/zizmor.yml`` suppresses accepted findings by ``file:LINE``. A line
number is a fragile anchor: insert anything above the construct and the ignore
silently stops applying, or — worse — starts applying to a different construct
that nobody reviewed.

The config's own comment records that this has bitten before. It bit again
here: adding a header comment to ``ci-failure-issue.yml`` moved its ``on:``
block from line 12 to line 28, and CI's ``lint`` job went red on
``dangerous-triggers`` for a trigger that had been reviewed and accepted months
earlier. Nothing local caught it, because ``make lint`` did not run zizmor at
all at the time — the Makefile's ``lint`` recipe gained it in the same change
that added this file, so the gap is closed.

Both directions matter and both are asserted:

* an ignore whose line no longer holds a trigger is **dangling** — the finding
  it was silencing is now live, and the next person sees a red gate for a
  decision that was already made;
* an ignore that has drifted onto some *other* construct is worse than
  dangling, because it suppresses a finding nobody ever accepted.

A third direction was missing and is covered here too: a *new* ``workflow_run``
workflow with no entry at all. Both of the above start from the config and ask
what the workflow says; neither notices a workflow the config never mentions,
so adding one reddens the required ``lint`` job on first push with a finding
that was never reviewed because it did not exist yet. That is exactly how
``mutation-weights-refresh.yml`` arrived.

This does not re-run zizmor (that needs the binary, and CI owns it). It checks
the cheap, mechanical property that the anchors still mean what they say.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".github" / "zizmor.yml"
WORKFLOWS = ROOT / ".github" / "workflows"

pytestmark = pytest.mark.skipif(
    not CONFIG.exists(),
    reason=".github/zizmor.yml not reachable (e.g. mutation sandbox)")

#: `dangerous-triggers` is about the `on:` block, so that is what its anchors
#: must land on. Other rules anchor elsewhere and are checked only for
#: existence, not for what they point at.
_TRIGGER_RULE = "dangerous-triggers"


def ignores() -> dict[str, list[tuple[str, int]]]:
    """``{rule: [(workflow file, line), ...]}`` parsed from zizmor.yml."""
    text = CONFIG.read_text(encoding="utf-8")
    out: dict[str, list[tuple[str, int]]] = {}
    rule = None
    for line in text.splitlines():
        m = re.match(r"^  (\S+):\s*$", line)
        if m and m.group(1) not in ("ignore",):
            rule = m.group(1)
            out.setdefault(rule, [])
            continue
        m = re.match(r"^\s*-\s+([\w.-]+\.ya?ml):(\d+)\s*$", line)
        if m and rule:
            out[rule].append((m.group(1), int(m.group(2))))
    return out


def line_of(workflow: str, number: int) -> str:
    """The 1-indexed line ``number`` of a workflow, or '' if out of range."""
    path = WORKFLOWS / workflow
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[number - 1] if 0 < number <= len(lines) else ""


class TestTheGuardCanActuallySee:
    def test_ignores_are_parsed(self):
        # Every assertion below is vacuous if the parse returns nothing.
        assert ignores(), "parsed no ignores out of .github/zizmor.yml"

    def test_the_trigger_rule_has_entries(self):
        assert ignores().get(_TRIGGER_RULE), ignores()

    def test_a_known_workflow_is_referenced(self):
        files = {f for entries in ignores().values() for f, _ in entries}
        assert files, "no workflow files referenced"
        assert all((WORKFLOWS / f).is_file() for f in files), sorted(files)


class TestEveryAnchorStillPointsAtItsTrigger:
    @pytest.mark.parametrize(
        "workflow,number",
        ignores().get(_TRIGGER_RULE, []),
        ids=lambda v: str(v))
    def test_the_line_is_the_on_block(self, workflow, number):
        text = line_of(workflow, number)
        assert text.startswith("on:"), (
            "%s:%d is ignored for %s, but that line is %r — the anchor has "
            "drifted. Editing anything above a workflow's `on:` block moves "
            "it and either un-silences an accepted finding or silences a "
            "different one nobody reviewed."
            % (workflow, number, _TRIGGER_RULE, text))

    def test_no_ignore_points_past_the_end_of_its_file(self):
        dangling = [(f, n) for entries in ignores().values()
                    for f, n in entries if not line_of(f, n)]
        assert not dangling, dangling


class TestTheConfigIsSelfConsistent:
    def test_every_referenced_workflow_exists(self):
        missing = sorted({f for entries in ignores().values() for f, _ in entries
                          if not (WORKFLOWS / f).is_file()})
        assert not missing, (
            "zizmor.yml silences findings in workflows that no longer exist: "
            "%s" % ", ".join(missing))

    def test_no_duplicate_anchor(self):
        for rule, entries in ignores().items():
            dupes = sorted({e for e in entries if entries.count(e) > 1})
            assert not dupes, (rule, dupes)


def _strip_comment(line: str) -> str:
    """``line`` without a trailing ``#`` comment.

    Deliberately naive about ``#`` inside a quoted string: no workflow here
    has one, and a false strip can only make the guard *stricter*.
    """
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == "#":
            return line[:i]
    return line


def workflow_files() -> list[Path]:
    """Every workflow in the directory, both spellings of the extension.

    GitHub honours ``.yaml`` exactly as it honours ``.yml``, and the
    config-side parser above already accepts either (``\\.ya?ml``), so
    globbing one of them was an asymmetry rather than a convention: a
    privileged ``.yaml`` workflow would have been invisible to every sweep
    in this file while the five ``.yml`` ones kept each list non-empty and
    every emptiness check green.
    """
    return sorted(set(WORKFLOWS.glob("*.yml")) | set(WORKFLOWS.glob("*.yaml")))


def triggers_of(text: str) -> set[str]:
    """Every event named by a workflow's ``on:`` key.

    Hand-rolled rather than `yaml.safe_load`, because nothing else in the
    test suite imports PyYAML and a 20-line scanner is cheaper than the
    dependency. It handles the three spellings GitHub accepts, which the
    first draft's ``^\\s*<event>:`` regex did not:

    * ``on:`` then an indented block mapping (what every workflow here uses);
    * ``on: workflow_run`` -- a bare scalar, the natural way to write a
      trigger that takes no filters, and the one that matters: it puts no
      colon after the event name, so the regex could not see it;
    * ``on: [push, pull_request_target]`` -- a flow sequence.

    ``on`` is also YAML 1.1's spelling of ``true``, so a loader would hand
    back the key ``True``; reading the text sidesteps that too.
    """
    found: set[str] = set()
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        line = _strip_comment(raw)
        m = re.match(r"^(on|\"on\"|'on'|True)\s*:(.*)$", line)
        if not m:
            continue
        inline = m.group(2).strip()
        if inline:
            found |= {t.strip().strip("'\"")
                      for t in inline.strip("[]").split(",") if t.strip()}
            continue
        for nxt in lines[i + 1:]:
            body = _strip_comment(nxt)
            if not body.strip():
                continue
            if not body[:1].isspace():      # dedent: the on: block ended
                break
            key = re.match(r"^\s+-?\s*([\w-]+)\s*:", body)
            if key and len(body) - len(body.lstrip()) <= 2:
                found.add(key.group(1))
            elif re.match(r"^\s+-\s*([\w-]+)\s*$", body):
                found.add(re.match(r"^\s+-\s*([\w-]+)\s*$", body).group(1))
    return found


def workflows_triggered_by(trigger: str) -> list[str]:
    """Workflow filenames whose ``on:`` key names ``trigger``."""
    return sorted(p.name for p in workflow_files()
                  if trigger in triggers_of(p.read_text(encoding="utf-8")))


#: The triggers ``dangerous-triggers`` fires on. Naming only one of them was
#: the first draft's gap: the docstring said "and ``pull_request_target``"
#: and the sweep looked for ``workflow_run`` alone, so half the rule was
#: still free to redden lint on first push. The repo happens to use no
#: ``pull_request_target`` today, which is exactly when a guard for it is
#: cheap to add and impossible to notice missing.
_DANGEROUS_TRIGGERS = ("workflow_run", "pull_request_target")


def dangerous_workflows() -> list[str]:
    """Every workflow naming a trigger the rule fires on, deduplicated."""
    seen: dict[str, None] = {}
    for trigger in _DANGEROUS_TRIGGERS:
        for name in workflows_triggered_by(trigger):
            seen[name] = None
    return sorted(seen)


class TestEveryDangerousTriggerIsAccountedFor:
    """The reverse direction: a workflow the config has never heard of.

    ``dangerous-triggers`` fires on ``workflow_run`` and
    ``pull_request_target``, so a new one either gets reviewed and listed or
    it fails the gate. Making that a local test turns "red CI on first push"
    into "red test before the push".
    """

    def test_the_sweep_finds_something(self):
        # Vacuous otherwise: a glob that matches nothing passes everything.
        assert dangerous_workflows()

    def test_both_triggers_are_swept(self):
        # Pins the pair, so dropping one from _DANGEROUS_TRIGGERS fails here
        # rather than silently halving the guard.
        assert set(_DANGEROUS_TRIGGERS) == {"workflow_run",
                                            "pull_request_target"}

    @pytest.mark.parametrize("workflow", dangerous_workflows())
    def test_a_workflow_run_workflow_is_listed(self, workflow):
        listed = {f for f, _ in ignores().get(_TRIGGER_RULE, [])}
        assert workflow in listed, (
            "%s triggers on one of %s but has no %s ignore in "
            ".github/zizmor.yml. CI's `lint` job runs zizmor over the whole "
            "directory and will fail on it. Review the trigger, then anchor "
            "an ignore at its `on:` line with a comment saying why it is safe."
            % (workflow, ", ".join(_DANGEROUS_TRIGGERS), _TRIGGER_RULE))


class TestAPrivilegedWorkflowRunCarriesTheForkGuard:
    """``branches: [main]`` is not a fork guard, and reads exactly like one.

    It filters on the *triggering* run's ``head_branch``. ``ci.yml`` runs
    ``on: pull_request``, so a fork PR raised from a branch named ``main``
    produces a ci run whose ``head_branch`` is ``main`` and passes that
    filter. Any ``workflow_run`` job holding ``contents: write`` is therefore
    reachable from a fork unless it also requires the triggering run to be a
    ``push`` from this repository — the pair of conditions ``publish.yml`` and
    ``sbom.yml`` document at length.

    Only the *repository* half is asserted here. The ``event == 'push'`` half
    is specific to what the upstream workflow runs on: ``ci`` runs on
    ``pull_request`` so the followers that watch it must exclude that, while
    ``sbom`` follows ``release``, which a pull request cannot trigger at all.
    Requiring ``push`` of every follower would have been a wrong assertion
    that ``sbom.yml`` fails correctly — the repository check is the one that
    is universal.

    Scoped to ``contents: write`` deliberately: ``ci-failure-issue.yml`` holds
    only ``issues: write``, checks out nothing, and composing an issue body
    from a fork-triggered run is not the same class of exposure.
    """

    def test_the_sweep_finds_something(self):
        assert self.privileged()

    @staticmethod
    def privileged() -> list[str]:
        out = []
        for name in workflows_triggered_by("workflow_run"):
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            if re.search(r"^\s*contents:\s*write\b", text, re.MULTILINE):
                out.append(name)
        return out

    @pytest.mark.parametrize("workflow", privileged.__func__())
    def test_it_requires_a_push_from_this_repository(self, workflow):
        text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
        # Match the `if:` expressions, not the file. These workflows explain
        # the guard at length in prose directly above it, so a comment could
        # satisfy the assertion with the guard itself deleted — not true of
        # any comment in the tree today, which is the point: the test must
        # still hold after someone writes one. Trailing comments are stripped
        # as well as whole-line ones, since `if: ... # fork guard` is the
        # shape that slips past a line-start check.
        code = "\n".join(_strip_comment(ln) for ln in text.splitlines())
        needed = ("github.event.workflow_run.head_repository.full_name"
                  " == github.repository")
        assert needed in code, (
            "%s runs on workflow_run and grants contents: write, but its job "
            "conditions never require %s. `branches: [main]` does not close "
            "this: it filters the triggering run's head_branch, and a fork PR "
            "from a branch called `main` satisfies it."
            % (workflow, needed))


class TestTheTriggerScannerSeesEverySpelling:
    """The scanner is the whole sweep, so its blind spots are the guard's.

    Both of these were real gaps found by review, not hypotheticals: the
    original regex matched ``^\\s*<event>:`` only, and the original glob was
    ``*.yml`` only.
    """

    def test_the_block_mapping_spelling(self):
        assert triggers_of(
            "on:\n  workflow_run:\n    workflows: [ci]\n") == {"workflow_run"}

    def test_the_scalar_spelling(self):
        assert triggers_of("on: pull_request_target\n") == {
            "pull_request_target"}

    def test_the_flow_sequence_spelling(self):
        assert triggers_of("on: [push, workflow_run]\n") == {
            "push", "workflow_run"}

    def test_the_block_sequence_spelling(self):
        assert triggers_of("on:\n  - push\n  - workflow_run\n") == {
            "push", "workflow_run"}

    def test_a_trailing_comment_is_not_an_event(self):
        assert triggers_of("on: push  # not pull_request_target\n") == {"push"}

    def test_a_nested_key_is_not_an_event(self):
        # `workflows:` and `types:` sit under the event, not beside it.
        assert triggers_of(
            "on:\n  workflow_run:\n    workflows: [ci]\n    types: [completed]\n"
        ) == {"workflow_run"}

    def test_it_stops_at_the_dedent(self):
        assert triggers_of(
            "on:\n  push:\n\npermissions:\n  contents: read\n") == {"push"}

    def test_both_extensions_are_swept(self, tmp_path, monkeypatch):
        # `sys.modules[__name__]` rather than `import <this file>`: the
        # self-import reads to test_canary_deps.py as a third-party module in
        # neither of its tables, and fails the build asking which it is.
        mod = sys.modules[__name__]
        d = tmp_path / "workflows"
        d.mkdir()
        (d / "a.yml").write_text("on: workflow_run\n", encoding="utf-8")
        (d / "b.yaml").write_text("on: workflow_run\n", encoding="utf-8")
        monkeypatch.setattr(mod, "WORKFLOWS", d)
        assert mod.workflows_triggered_by("workflow_run") == ["a.yml", "b.yaml"]

    def test_the_real_directory_agrees_with_the_old_regex(self):
        """No workflow here changes classification under the new scanner.

        The widening is for spellings the repo does not use yet, so it must
        not quietly reclassify one it does.
        """
        for path in workflow_files():
            text = path.read_text(encoding="utf-8")
            for trigger in _DANGEROUS_TRIGGERS:
                regex = bool(re.search(r"^\s*%s:" % re.escape(trigger), text,
                                       re.MULTILINE))
                assert (trigger in triggers_of(text)) == regex, (
                    path.name, trigger)
