"""`boost run` — adapt a skill, wire default tools, and run it as a live agent.

The last mile of `boost adapt`: adapt gives an agent a brain (instructions +
model); this bolts on hands (a default read-only toolset) and executes it on
boost's model, streaming the result. Opt-in like the rest of the AI surface —
the OpenAI Agents SDK (`pip install "openai-agents[litellm]"`) and a provider
key are needed to *run*; `--print` emits the runner script offline (zero deps),
so the zero-dependency default holds.

Lives in its own module, not pkg.py, precisely because it does ``import agents``
(the SDK): pkg.py binds the name ``agents`` to boost's own ``core.agents``, and
mixing the two invites a subtle shadowing bug.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .. import cliparse
from ..core import adapters, config, journal, paths, util
from ..core import output as out
from ..errors import BoostError
from .pkg import _resolve_skill_source, _tilde


def cmd_run(argv: list[str]) -> int:
    """boost run NAME [TARGET] [--model M] [--print] [-o FILE]"""
    ap = cliparse.parser(
        prog="boost run",
        description="Adapt a skill, wire default tools & run it as a live agent")
    ap.add_argument("name", help="skill to run")
    ap.add_argument("target", nargs="?",
                    help="file or directory for the agent to work on (default: .)")
    ap.add_argument("--model", metavar="M", default=None,
                    help="LLM to run on (default: boost's ai.model; "
                         "'none' for the SDK's own default)")
    ap.add_argument("--print", dest="print_only", action="store_true",
                    help="print the generated runner script instead of executing it")
    ap.add_argument("-o", "--out", metavar="FILE",
                    help="with --print: write the runner to FILE")
    args = ap.parse_args(argv)

    # Same model resolution as `boost adapt`: default to boost's model, treat
    # none/off/'' as "let the framework pick".
    model = args.model if args.model is not None else str(config.get("ai.model") or "")
    if model.strip().lower() in ("none", "off", ""):
        model = None

    display, description, body = _resolve_skill_source(args.name)
    runner = adapters.render_runner(display, description, body, model, args.target)

    if args.print_only:
        if args.out:
            dest = paths.expand(args.out)
            try:
                util.atomic_write_text(dest, runner)
            except OSError as e:
                raise BoostError("cannot write %s: %s" % (_tilde(dest), e.strerror or e),
                                hint="check the output path exists and is writable") from e
            out.ok("wrote runner for %s → %s" % (display, _tilde(dest.resolve())))
        else:
            sys.stdout.write(runner)
        return 0

    # Execution is opt-in: the SDK (with the litellm extra) must be importable.
    # Importing LitellmModel validates the whole `openai-agents[litellm]` install
    # in one go. This is the top-level `agents` SDK, not boost's core.agents
    # (which is why cmd_run lives in its own module).
    try:
        from agents.extensions.models.litellm_model import (  # type: ignore  # noqa: F401
            LitellmModel,
        )
    except ImportError as e:
        raise BoostError(
            "boost run needs the OpenAI Agents SDK to execute the agent",
            hint='pip install "openai-agents[litellm]"  — or `boost run %s '
                 '--print` to emit the runner without running it' % args.name) from e
    return _execute(runner, display, model, args.target)  # pragma: no cover


def _execute(runner: str, display: str, model, target) -> int:  # pragma: no cover
    """Run the generated runner in a child process (needs the SDK + a key).

    Exercised end-to-end by ``examples/boost-run-prototype.sh``, not the unit
    suite — the framework and a provider key are never present in CI, so this is
    excluded from coverage rather than faked.
    """
    # Check the provider key against how the runner ACTUALLY routes the model
    # (adapters._litellm_model sends a bare id to `anthropic/`), not the raw id —
    # otherwise `--model gpt-4o` would skip the check yet still hit Anthropic.
    routed = adapters._litellm_model(model) if model else ""
    if routed.startswith("anthropic/") and not os.environ.get("ANTHROPIC_API_KEY"):
        raise BoostError(
            "boost run needs ANTHROPIC_API_KEY to call %s" % model,
            hint="export ANTHROPIC_API_KEY=sk-ant-…  — or use `--print`")

    out.info("running %s%s on %s …"
             % (display, " (%s)" % model if model else "", target or "."))
    # Execute the runner in a child process so the SDK never loads into boost's
    # own (stdlib-only) process; sys.executable is the interpreter that just
    # imported the SDK, so it has it too.
    with tempfile.NamedTemporaryFile("w", suffix="_boost_run.py", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(runner)
        runner_path = fh.name
    try:
        proc = subprocess.run([sys.executable, runner_path])
    finally:
        with contextlib.suppress(OSError):
            Path(runner_path).unlink()
    journal.log("run", display)
    return proc.returncode
