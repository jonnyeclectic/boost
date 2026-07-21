"""behave hooks — mirrors tests/conftest.py's sandboxing for BDD scenarios.

Every scenario runs against a throwaway $HOME (never the real one) and shares
one fixture tap built once per run via tests/make_fixture.py.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_SANDBOX_ENV = ("BOOST_HOME", "BOOST_AGENTS_STORE", "BOOST_DEBUG",
                "BOOST_LOG_LEVEL", "BOOST_NO_LOG", "VOYAGE_API_KEY",
                "OPENAI_API_KEY", "BOOST_NO_EMBED")


def before_all(context):
    context._run_dir = Path(tempfile.mkdtemp(prefix="boost-bdd-"))
    dest = context._run_dir / "fixture-tap"
    subprocess.run(
        [sys.executable, str(ROOT / "tests" / "make_fixture.py"), str(dest)],
        check=True, capture_output=True)
    context.fixture_tap_src = dest


_scenario_counter = [0]


def before_scenario(context, scenario):
    context._saved_env = dict(os.environ)
    _scenario_counter[0] += 1
    home = context._run_dir / ("home-%d" % _scenario_counter[0])
    home.mkdir(parents=True, exist_ok=True)
    os.environ["HOME"] = str(home)
    for var in _SANDBOX_ENV:
        os.environ.pop(var, None)
    os.environ["BOOST_NO_AI"] = "1"       # deterministic: no AI calls
    os.environ["NO_COLOR"] = "1"          # plain output for assertions
    os.environ["BOOST_ASSUME_YES"] = "1"  # never block on confirm()
    context._home = home
    context._tapped = False
    context._patchers = []

    from boost_cli.core import logs
    logs.reset()


def after_scenario(context, scenario):
    for patcher in reversed(context._patchers):
        patcher.stop()
    context._patchers = []
    from boost_cli.core import logs
    logs.reset()
    os.environ.clear()
    os.environ.update(context._saved_env)


def after_all(context):
    shutil.rmtree(context._run_dir, ignore_errors=True)
