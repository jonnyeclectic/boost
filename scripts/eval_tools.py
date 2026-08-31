#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Tier 3: does an agent CALL boost's tools when it should — and stay away when
it should not.

Tiers 1 and 2 grade what boost returns *once it is asked*: recall@k, hit@1, MRR
and nDCG over a 91-query golden set. Nothing measured whether an agent asks,
and that is the step everything downstream depends on. A gate flooring
recall@k at 0.78 reports nothing when retrieval is never invoked.

TWO NUMBERS, NEVER ONE. A tier that scores call rate alone rewards making the
tool descriptions maximally assertive, which is precisely the capture
`core/mcp.py` is written to avoid — and boost already learned this one tier
down: flooring recall without hit@1 passed a ranker that found the answer every
time and never ranked it first. So the set has two halves, and this reports a
floor on the should-call half AND a ceiling on the should-not-call half. One
number without the other is an incentive to ship the thing boost refuses to be.

PER HOST, NEVER AVERAGED. The registered hosts do not see the same boost text:
Claude Code puts server `instructions` in the system prompt, and Gemini CLI
never delivers them in interactive mode at all. One averaged score would hide a
host where the guidance is simply absent, and would credit or blame wording for
a delivery failure.

AN INTERVAL, NOT A VERDICT PER RUN. The outcome is stochastic, so a single
replay cannot tell a wording regression from a sampling wobble. Every rate is
reported with a Wilson score interval over N runs, and a floor is judged
against the interval bound rather than the point estimate.

WHAT THIS MEASURES, AND THE CONFOUND TO CONTROL FOR. The host reads more than
the MCP tool descriptions: an installed boost RULE is standing instructions in
the agent's own context file, and `boost-first` says in as many words to call
these tools. A run on a machine where that rule is installed is measuring
rule + descriptions, and attributing the result to wording alone would be
wrong. `--report-context` prints what was in scope so a number is never read
without it; compare hosts and wordings only across runs with the same answer.

FIRST REAL RUN, and it is why the ceiling exists. Four prompts, one run each,
against Claude Code on a machine with the `boost-first` rule installed:
should-call 1/1, should-NOT-call **3/3**. The host called boost for "What is
the difference between a Python list and a tuple?" — a question, which boost's
own skip list excuses by name. A call-rate-only tier would have reported a
perfect 1.00 and called it a triumph.

Opt-in and key-gated like the other Tier 2/3 evals — it drives a real host and
spends real tokens, so it must NOT join the required `check` gate, and it
degrades cleanly when no host is reachable.

Usage:
  python3 scripts/eval_tools.py --dry-run           # show the plan, call nothing
  python3 scripts/eval_tools.py --runs 3            # 3 runs per prompt
  python3 scripts/eval_tools.py --floor-call 0.60 --ceiling-false-call 0.20
  python3 scripts/eval_tools.py --strict-mcp-config # only boost on the MCP surface
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SET = ROOT / "tests" / "eval" / "tool_calls.jsonl"

sys.path.insert(0, str(ROOT))
from boost_cli.core import mcphost  # noqa: E402

#: Tool names that count as "the agent asked boost". Prefixed forms are matched
#: too — hosts namespace MCP tools differently (`mcp__boost__boost_search`,
#: `mcp_boost_boost_search`), and matching the bare suffix keeps one list
#: correct across all of them.
BOOST_TOOLS = ("boost_search", "boost_list", "boost_info", "boost_read",
               "boost_install", "boost_doctor", "boost_discover_github")

#: Only these count as *consulting the shelf*. `boost_install` is downstream of
#: a decision already made, and scoring it as a check would let a run that
#: installed without looking count as a success.
CONSULT_TOOLS = ("boost_search", "boost_list", "boost_info", "boost_read")


# ----------------------------------------------------------------- data

def load_set(path: Path) -> list[dict]:
    """Rows from the JSONL prompt set. `#` comments and blank lines allowed."""
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
    if not rows:
        raise SystemExit("no prompts in %s" % path)
    bad = [r["id"] for r in rows if r.get("expect") not in ("call", "no-call")]
    if bad:
        raise SystemExit("rows with no usable `expect`: %s" % ", ".join(bad))
    ids = [r["id"] for r in rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise SystemExit("duplicate row ids: %s" % ", ".join(dupes))
    return rows


def halves(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """``(should_call, should_not_call)``.

    Both must be non-empty: a set with one half is the single-number failure
    this whole tier exists to refuse, so it is an error rather than a warning.
    """
    call = [r for r in rows if r["expect"] == "call"]
    no_call = [r for r in rows if r["expect"] == "no-call"]
    if not call or not no_call:
        raise SystemExit(
            "the prompt set needs BOTH halves — %d should-call, %d should-not-call. "
            "Scoring one direction rewards an assertive surface, which is the "
            "capture this tier exists to detect." % (len(call), len(no_call)))
    return call, no_call


# -------------------------------------------------------------- scoring

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for ``k`` successes in ``n`` trials.

    Wilson rather than the textbook normal approximation because this tier runs
    small N by design (a live host call is seconds and money). At n=3, k=3 the
    normal interval is [1.0, 1.0] — it claims certainty from three samples,
    which would let a wording regression hide behind a lucky run. Wilson gives
    [0.44, 1.0] there and stays inside [0, 1] at the edges.

    ``n == 0`` returns ``(0.0, 1.0)``: no evidence is the widest interval, not
    a score of zero.
    """
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(observations: list[bool]) -> dict:
    """``{k, n, rate, lo, hi}`` for a list of per-run booleans."""
    k, n = sum(1 for o in observations if o), len(observations)
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "rate": (k / n) if n else 0.0, "lo": lo, "hi": hi}


def score_host(rows: list[dict], observed: dict[str, list[bool]]) -> dict:
    """Per-host metrics from ``{row_id: [called?, ...]}``.

    Rows with no observations are reported as ``skipped`` rather than counted
    as failures — a host that could not be reached must not read as a host that
    declined to call.
    """
    call_rows, no_call_rows = halves(rows)

    def seen(rs: list[dict]) -> list[bool]:
        return [o for r in rs for o in observed.get(r["id"], [])]

    skipped = sorted(r["id"] for r in rows if not observed.get(r["id"]))
    return {
        "call_rate": rate(seen(call_rows)),
        "false_call_rate": rate(seen(no_call_rows)),
        "skipped": skipped,
        "per_row": {r["id"]: rate(observed.get(r["id"], [])) for r in rows},
    }


def verdict(metrics: dict, floor_call: float, ceiling_false: float) -> list[str]:
    """Failure reasons, empty when the host passes both directions.

    Judged against the INTERVAL, not the point estimate: the floor must clear
    the lower bound and the ceiling must clear the upper bound. With small N a
    point estimate of 0.67 from two of three runs is indistinguishable from
    noise, and gating on it would make the tier itself flaky.
    """
    out = []
    c, f = metrics["call_rate"], metrics["false_call_rate"]
    if c["n"] == 0:
        out.append("no should-call observations")
    elif c["lo"] < floor_call:
        out.append("call rate %.2f [%.2f-%.2f] under floor %.2f (%d/%d)"
                   % (c["rate"], c["lo"], c["hi"], floor_call, c["k"], c["n"]))
    if f["n"] and f["hi"] > ceiling_false:
        out.append("false-call rate %.2f [%.2f-%.2f] over ceiling %.2f (%d/%d)"
                   % (f["rate"], f["lo"], f["hi"], ceiling_false, f["k"], f["n"]))
    return out


# ----------------------------------------------------------------- probe

def iter_events(events: str):
    """Yield the parsed NDJSON objects in a host's stream, skipping junk.

    A stream carries non-JSON lines (warnings, a truncated tail on timeout), and
    a context note must never fail the run it annotates, so bad lines are
    skipped rather than raised.
    """
    for line in (events or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            yield json.loads(line)
        except ValueError:
            continue


def tool_calls(events: str) -> list[str]:
    """Every tool this run actually invoked, in order.

    A *call* is a `tool_use` block inside an `assistant` event. Nothing else
    counts, and that distinction is the whole measurement.
    """
    names = []
    for ev in iter_events(events):
        if ev.get("type") != "assistant":
            continue
        content = (ev.get("message") or {}).get("content") or []
        names.extend(b.get("name") or "" for b in content
                     if isinstance(b, dict) and b.get("type") == "tool_use")
    return names


def called_boost(events: str) -> bool:
    """Did this run actually invoke a boost CONSULT tool?

    Reads the host's own stream rather than the model's prose: an agent that
    says "let me check boost" and does not is a miss, and one that calls
    without narrating is a hit.

    **It must not substring-match the raw stream, and the first version did.**
    `claude -p --output-format stream-json --verbose` opens with a
    `system`/`init` event enumerating every tool available to the session — on
    a machine where boost is registered that list contains
    `mcp__boost__boost_search` and the other three CONSULT names, in every run,
    including runs with no tool call at all. So the old check returned True
    unconditionally: `Say OK and nothing else.` scored as a boost consult, and
    the no-call ceiling could never be met on any machine boost was installed
    on. `make eval-tools` was guaranteed red, and the one finding this tier had
    produced was an artifact of its own probe.

    A tool being *offered* is not a tool being *called*, so the parse looks for
    the call. Matching stays on the bare suffix, which covers every host's
    namespacing (`mcp__boost__boost_search`, `mcp_boost_…`, `boost/…`).
    """
    return any(any(t in name for t in CONSULT_TOOLS)
               for name in tool_calls(events))


def session_surface(events: str) -> tuple[int, int]:
    """`(tools, mcp_servers)` the host offered this run, from its init event.

    The confound the old probe hid rather than reported: call rate depends far
    more on how crowded the tool surface is than on any wording edit, and the
    init event has carried both counts all along.
    """
    for ev in iter_events(events):
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            return len(ev.get("tools") or []), len(ev.get("mcp_servers") or [])
    return 0, 0


def claude_available() -> bool:
    return shutil.which("claude") is not None


def strict_mcp_config(launcher: str) -> dict:
    """The boost-only `--mcp-config` payload for a `claude -p` run.

    Claude Code's own `mcpServers` shape (`{"mcpServers": {name: {"command",
    "args", "env"}}}` — confirmed against a real `claude mcp add-json` write,
    not guessed) with exactly one entry: boost, launched the same way
    `core.mcphost.register_argv` registers it (`<launcher> mcp --stdio`, plus
    `LAUNCH_ENV` — the fork-safety env a real registration always carries, and
    whose absence is a macOS SIGABRT, not a cosmetic gap). Kept a plain
    function, not a file write, so a test can assert the shape without
    touching disk.
    """
    return {"mcpServers": {mcphost.SERVER_NAME: {
        "command": launcher, "args": ["mcp", "--stdio"],
        "env": dict(mcphost.LAUNCH_ENV)}}}


def run_claude(prompt: str, timeout: int,
                mcp_config: Path | None = None) -> str | None:
    """One `claude -p` run, returning its raw event stream (or None).

    `--output-format stream-json` is what makes the probe honest: it emits a
    `tool_use` block per call, so the observation is the host's record of what
    happened rather than the model's account of it.

    `mcp_config`, when given, adds `--strict-mcp-config --mcp-config <path>` —
    the card's own fix for the confound `_report_surface` can only report, not
    prevent: a machine with several MCP servers registered offers every one of
    their tools to every prompt, which moves the call rate far more than any
    wording edit and costs real tokens describing tools this eval never asked
    about. `--strict-mcp-config` replaces the host's merged configuration with
    only what this file names, so the run sees boost and nothing else.
    """
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json",
           "--verbose", "--max-turns", "2"]
    if mcp_config is not None:
        cmd += ["--strict-mcp-config", "--mcp-config", str(mcp_config)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    # A non-zero exit with output still carries the events we care about; only
    # a silent failure is unusable.
    return proc.stdout or None


# ------------------------------------------------------------------ cli

def _print_context() -> None:
    """Name the installed RULES, because they are part of what is being scored.

    A rule is standing instructions in the agent's own context file, and
    boost's own `boost-first` rule tells the agent to call these tools. A rate
    measured with it installed is a rate for rule + descriptions; reading it as
    a verdict on the descriptions alone is the mistake this line exists to
    prevent. Printed, never subtracted — the honest move is to say what was in
    scope, not to guess at its share.
    """
    try:
        from boost_cli.core import lockfile
        rules = sorted(lockfile.all_installed().get("rule") or {})
    except Exception:      # a context note must never fail the run it annotates
        print("context: could not read the lock file")
        return
    print("context: %d rule(s) installed and in scope for every prompt%s"
          % (len(rules), (" — " + ", ".join(rules)) if rules else ""))
    if rules:
        print("         these are standing instructions; the rates below are "
              "for rule + descriptions, not descriptions alone.")


def _report_surface(tools: int, servers: int) -> None:
    """How crowded the tool surface was — the other half of the context.

    A call rate depends far more on how many tools competed for the slot than
    on any wording edit, and the host's init event has carried both counts all
    along. Printed, never subtracted: the honest move is to say what was in
    scope, the same rule `_print_context` follows for rules.
    """
    if tools:
        print("         host offered %d tool(s) across %d MCP server(s) this "
              "run; a rate is for that surface, not for boost alone."
              % (tools, servers))


def _report(host: str, rows: list[dict], metrics: dict,
            reasons: list[str]) -> None:
    c, f = metrics["call_rate"], metrics["false_call_rate"]
    print("\n== %s ==" % host)
    print("  should-call      %d/%d = %.2f  [%.2f-%.2f]"
          % (c["k"], c["n"], c["rate"], c["lo"], c["hi"]))
    print("  should-NOT-call  %d/%d = %.2f  [%.2f-%.2f]   (lower is better)"
          % (f["k"], f["n"], f["rate"], f["lo"], f["hi"]))
    if metrics["skipped"]:
        print("  skipped (no observations): %s" % ", ".join(metrics["skipped"]))
    for r in rows:
        m = metrics["per_row"][r["id"]]
        if not m["n"]:
            continue
        want = "call" if r["expect"] == "call" else "no-call"
        ok = (m["k"] == m["n"]) if r["expect"] == "call" else (m["k"] == 0)
        print("    %-24s want %-8s got %d/%d %s"
              % (r["id"], want, m["k"], m["n"], "" if ok else "<-"))
    for reason in reasons:
        print("  FAIL: %s" % reason)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="eval_tools.py",
        description="Tier 3: tool-call behaviour, floored in both directions")
    p.add_argument("--set", type=Path, default=DEFAULT_SET)
    p.add_argument("--runs", type=int, default=1,
                   help="runs per prompt; more narrows the interval")
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--floor-call", type=float, default=0.60,
                   help="lower bound of the should-call rate must clear this")
    p.add_argument("--ceiling-false-call", type=float, default=0.20,
                   help="upper bound of the should-NOT-call rate must stay under")
    p.add_argument("--dry-run", action="store_true",
                   help="print the plan and the halves; call no host")
    p.add_argument("--json", action="store_true")
    p.add_argument("--report-context", action="store_true", default=True,
                   help="name the installed rules in scope (default on); a "
                        "rate read without them is not attributable to wording")
    p.add_argument("--strict-mcp-config", action="store_true",
                   help="run with only boost on the MCP surface (--strict-mcp-config "
                        "--mcp-config), so a crowded machine's other servers don't "
                        "move the call rate or the token bill")
    args = p.parse_args(argv)

    rows = load_set(args.set)
    call_rows, no_call_rows = halves(rows)
    if args.dry_run:
        print("%d prompts: %d should-call, %d should-NOT-call, %d run(s) each"
              % (len(rows), len(call_rows), len(no_call_rows), args.runs))
        print("floor(call) >= %.2f   ceiling(false-call) <= %.2f"
              % (args.floor_call, args.ceiling_false_call))
        for r in rows:
            print("  %-24s %-8s %s" % (r["id"], r["expect"], r["prompt"][:56]))
        return 0

    if not claude_available():
        # Degrade the way every other opt-in eval does: say what is missing and
        # exit 0, so a contributor without a host is not handed a red build for
        # a tier that is deliberately outside `check`.
        print("no host available — this tier drives the `claude` CLI and it is "
              "not on PATH. Install it, or run with --dry-run.")
        return 0
    if os.environ.get("BOOST_NO_AI"):
        print("BOOST_NO_AI is set — refusing to spend tokens.")
        return 0

    if args.report_context:
        _print_context()

    mcp_config_path = None
    if args.strict_mcp_config:
        from boost_cli.core import paths
        config = strict_mcp_config(str(paths.launcher()))
        fd, name = tempfile.mkstemp(suffix=".json", prefix="boost-eval-mcp-")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(config, fh)
        mcp_config_path = Path(name)
        print("context: --strict-mcp-config on — this run sees only boost's "
              "own MCP server, not whatever else is registered on this machine.")

    observed: dict[str, list[bool]] = {}
    surface = (0, 0)
    try:
        for r in rows:
            for _ in range(max(1, args.runs)):
                events = run_claude(r["prompt"], args.timeout, mcp_config_path)
                if events is None:
                    continue
                if surface == (0, 0):
                    surface = session_surface(events)
                observed.setdefault(r["id"], []).append(called_boost(events))
    finally:
        if mcp_config_path is not None:
            mcp_config_path.unlink(missing_ok=True)
    if args.report_context:
        _report_surface(*surface)

    metrics = score_host(rows, observed)
    reasons = verdict(metrics, args.floor_call, args.ceiling_false_call)
    if args.json:
        print(json.dumps({"host": "claude-code", "metrics": metrics,
                          "failures": reasons}, indent=2))
    else:
        _report("claude-code", rows, metrics, reasons)
    return 1 if reasons else 0


if __name__ == "__main__":
    sys.exit(main())
