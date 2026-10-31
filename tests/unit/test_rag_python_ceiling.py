# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The `[rag]` extra on a Python onnxruntime publishes no wheel for.

Measured 2026-10-28: Homebrew's `python3` became 3.15, onnxruntime 1.31.1
ships cp311-cp314 wheels and no sdist, and `pipx install
"boost-skill-cli[rag]"` failed outright — sqlite-vec and tokenizers too,
though both install on 3.15. pyproject now marks onnxruntime
`python_version < '3.15'`, so the extra installs *without* its model runtime,
and every surface that used to say "reinstall the extra" would be naming a
command that changes nothing. These tests pin the state that replaces it
(`no-local-wheel`), the remedy it names per install method, and that the
marker and `localembed.ONNX_WHEEL_CEILING` cannot drift apart.

`tests/conftest.py` lifts the ceiling out of reach for every other test so the
runner's own interpreter is not an input; each test here puts it back.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import tomllib
from pathlib import Path

import pytest

from boost_cli.core import dense, embed, localembed, selfupdate, shards

#: Read before the conftest fixture lifts it — the shipped value.
CEILING = localembed.ONNX_WHEEL_CEILING
ROOT = Path(__file__).resolve().parents[2]
HERE = "%d.%d" % sys.version_info[:2]
_real_find_spec = importlib.util.find_spec


def _onnx(monkeypatch, present: bool) -> None:
    """Answer `find_spec("onnxruntime")` as `present`; every other name as is."""
    def find_spec(name, *a, **k):
        if name == "onnxruntime":
            return object() if present else None
        return _real_find_spec(name, *a, **k)
    monkeypatch.setattr(importlib.util, "find_spec", find_spec)


@pytest.fixture(autouse=True)
def new_pipx(monkeypatch):
    """A pipx on PATH that takes `--fetch-python=always`.

    The hints name the flag the pipx on PATH accepts, so without this the
    runner's own pipx (or its absence) would be an input to every assertion.
    """
    monkeypatch.setattr(selfupdate.shutil, "which",
                        lambda t: "/opt/bin/" + t)
    monkeypatch.setattr(selfupdate, "pipx_version", lambda *a, **k: (1, 18))


@pytest.fixture
def ceiling(monkeypatch):
    """Put the shipped ceiling back."""
    monkeypatch.setattr(localembed, "ONNX_WHEEL_CEILING", CEILING)


@pytest.fixture
def too_new(monkeypatch):
    """This interpreter is past the ceiling and onnxruntime is not here."""
    monkeypatch.setattr(localembed, "ONNX_WHEEL_CEILING", (3, 0))
    _onnx(monkeypatch, present=False)


@pytest.fixture
def installed_with(monkeypatch):
    def use(method: str) -> None:
        monkeypatch.setattr(selfupdate, "detect", lambda *a, **k: method)
    return use


@pytest.fixture
def no_keys(monkeypatch):
    for env in embed.KEY_ENV.values():
        monkeypatch.delenv(env, raising=False)


@pytest.fixture
def no_provider(monkeypatch):
    """The extra's store is present, no key, no local model — status's input."""
    monkeypatch.setattr(dense, "_load", lambda: object())
    monkeypatch.setattr(embed, "local_available", lambda: False)
    for env in ("VOYAGE_API_KEY", "OPENAI_API_KEY", "BOOST_NO_EMBED"):
        monkeypatch.delenv(env, raising=False)


class TestNoWheelHere:
    def test_below_the_ceiling_it_never_fires(self, ceiling, monkeypatch):
        _onnx(monkeypatch, present=False)
        assert localembed.no_wheel_here((3, 14)) is False

    def test_at_the_ceiling_without_the_runtime_it_fires(self, ceiling,
                                                         monkeypatch):
        _onnx(monkeypatch, present=False)
        assert localembed.no_wheel_here((3, 15)) is True
        assert localembed.no_wheel_here((3, 16)) is True

    def test_a_runtime_that_is_here_wins_over_the_version(self, ceiling,
                                                          monkeypatch):
        # Built from source, or the first cp315 wheel landed before the
        # constant moved: the local model works, so no move is owed.
        _onnx(monkeypatch, present=True)
        assert localembed.no_wheel_here((3, 15)) is False

    def test_the_default_is_the_running_interpreter(self, monkeypatch):
        _onnx(monkeypatch, present=False)
        monkeypatch.setattr(localembed, "ONNX_WHEEL_CEILING",
                            tuple(sys.version_info[:2]))
        assert localembed.no_wheel_here() is True
        monkeypatch.setattr(localembed, "ONNX_WHEEL_CEILING",
                            (sys.version_info[0], sys.version_info[1] + 1))
        assert localembed.no_wheel_here() is False

    @pytest.mark.parametrize("exc", [ValueError("no spec"),
                                     ImportError("parent missing")])
    def test_a_lookup_that_raises_reads_as_absent(self, too_new, monkeypatch,
                                                  exc):
        def broken(name, *a, **k):
            raise exc
        monkeypatch.setattr(importlib.util, "find_spec", broken)
        assert localembed.no_wheel_here() is True


class TestPackaging:
    """pyproject's marker and the runtime constant say the same thing."""

    def _rag(self) -> list[str]:
        with (ROOT / "pyproject.toml").open("rb") as fh:
            meta = tomllib.load(fh)
        return meta["project"]["optional-dependencies"]["rag"]

    def test_onnxruntime_is_marked_at_the_ceiling(self):
        req = [r for r in self._rag() if r.startswith("onnxruntime")]
        assert len(req) == 1
        m = re.search(r"python_version\s*<\s*'(\d+)\.(\d+)'", req[0])
        assert m, req[0]
        assert (int(m.group(1)), int(m.group(2))) == CEILING

    def test_the_rest_of_the_extra_is_unmarked(self):
        # Both install on 3.15 (py3-none and abi3 wheels); marking them too
        # would take dense search through an API key off that interpreter.
        rest = [r for r in self._rag() if not r.startswith("onnxruntime")]
        assert {r.split(">")[0] for r in rest} == {"sqlite-vec", "tokenizers"}
        assert not any(";" in r for r in rest)

    def test_the_classifier_names_the_new_interpreter(self):
        with (ROOT / "pyproject.toml").open("rb") as fh:
            classifiers = tomllib.load(fh)["project"]["classifiers"]
        assert "Programming Language :: Python :: 3.15" in classifiers

    def test_the_recommended_python_is_below_the_ceiling(self):
        major, minor = map(int, localembed.RECOMMENDED_PYTHON.split("."))
        assert (major, minor) < CEILING


class TestStatus:
    def test_the_extra_without_its_runtime_is_named(self, sandbox, too_new,
                                                    no_provider):
        st = dense.status()
        assert st["reason"] == "no-local-wheel"
        assert st["ready"] is False
        # Nothing built, nothing lost: an unfinished setup, not a fault.
        assert st["degraded"] is False

    def test_below_the_ceiling_it_is_still_no_key(self, sandbox, no_provider,
                                                  monkeypatch):
        _onnx(monkeypatch, present=False)
        assert dense.status()["reason"] == "no-key"

    def test_a_key_serves_dense_search_without_the_runtime(self, sandbox,
                                                           too_new,
                                                           no_provider,
                                                           monkeypatch):
        # Voyage and OpenAI embed over HTTP: 3.15 with a key needs no move.
        monkeypatch.setenv("VOYAGE_API_KEY", "vk-test")
        st = dense.status()
        assert st["provider"] == "voyage"
        assert st["reason"] == "no-store"

    def test_a_missing_extra_is_still_no_backend(self, sandbox, too_new,
                                                 no_provider, monkeypatch):
        monkeypatch.setattr(dense, "_load", lambda: None)
        assert dense.status()["reason"] == "no-backend"

    def test_quickstart_refusal_routes_through_the_same_hint(
            self, sandbox, too_new, no_provider, installed_with):
        # Quickstart on 3.15 with the extra: `judge_vectors` refuses the
        # keyless shards (no provider), and its remedy is doctor's answer.
        installed_with(selfupdate.PIPX)
        manifest = {"provider": "local", "model": embed.LOCAL_MODEL,
                    "dim": 384}
        assert shards.incompatible(manifest) == (
            "no embedding backend on this machine")
        assert shards.remedy(manifest) == dense.fix_hint("no-local-wheel")
        assert "`boost self-update --python 3.13`" in shards.remedy(manifest)

    def test_doctor_does_not_call_it_unconfigured(self, sandbox, too_new,
                                                  no_provider, boost):
        r = boost("doctor", expect=None)
        assert "semantic search unavailable on this Python" in r.out
        assert "semantic search not configured" not in r.out

    def test_no_local_wheel_cannot_run_a_build(self):
        # The shard surfaces word "embed on this machine instead" off this.
        assert "no-local-wheel" in shards._CANNOT_RUN
        assert "no-local-wheel" in shards._UNBUILDABLE


class TestHint:
    @pytest.mark.parametrize("method", [selfupdate.PIPX, selfupdate.UV_TOOL])
    def test_a_managed_venv_is_told_to_move_itself(self, installed_with,
                                                   method):
        installed_with(method)
        # Compared as a template rather than %-formatted: "self-update ...
        # set" reads to ruff's S608 as an SQL UPDATE.
        want = ("the local model needs onnxruntime, which has no wheel for "
                "Python {here} yet — `boost self-update --python 3.13` moves "
                "boost there and keeps the extra (or set VOYAGE_API_KEY / "
                "OPENAI_API_KEY, which need no local model)")
        assert dense.fix_hint("no-local-wheel") == want.replace("{here}", HERE)

    @pytest.mark.parametrize("method", [selfupdate.PIP, selfupdate.UV_PIP,
                                        selfupdate.UNKNOWN])
    def test_a_pip_install_is_offered_pipx_with_its_own_python(
            self, installed_with, method):
        installed_with(method)
        hint = dense.fix_hint("no-local-wheel")
        assert ('`pipx install --python 3.13 --fetch-python=always '
                '"boost-skill-cli[rag]"`') in hint
        assert "self-update" not in hint

    def test_a_checkout_is_told_to_rebuild_its_venv(self, installed_with):
        installed_with(selfupdate.GIT)
        hint = dense.fix_hint("no-local-wheel")
        assert "`python3.13 -m venv --clear .venv && " in hint
        assert "self-update" not in hint

    def test_a_store_built_with_a_key_is_told_to_set_it(self, installed_with):
        # Moving to 3.13 would bring the local model back and re-embed every
        # vector into its space; the key is the free way back.
        installed_with(selfupdate.PIPX)
        st = {"reason": "no-local-wheel", "built_provider": "voyage",
              "chunks": 12}
        # On this interpreter no extra reinstall brings the local model back,
        # so the cost named is the move, not the reinstall.
        assert dense.fix_hint("no-local-wheel", st) == (
            "set the key it was built with: `export VOYAGE_API_KEY=...` — "
            "moving boost to a Python with onnxruntime swaps in the local "
            "model and forces all 12 vectors to be re-embedded")
        st["reason"] = "no-key"
        assert dense.fix_hint("no-key", st) == (
            "set the key it was built with: `export VOYAGE_API_KEY=...` — "
            "reinstalling the extra swaps in the local model and forces all "
            "12 vectors to be re-embedded")

    def test_a_store_the_local_model_built_is_not_offered_a_key(
            self, installed_with):
        installed_with(selfupdate.UV_TOOL)
        st = {"reason": "no-local-wheel", "built_provider": "local",
              "chunks": 1}
        assert dense.fix_hint("no-local-wheel", st) == (
            "the local model all 1 vector were built with needs onnxruntime, "
            "which has no wheel for Python %s yet — `boost self-update "
            "--python 3.13` moves boost there and keeps the extra; a key "
            "instead re-embeds them" % HERE)

    def test_an_empty_store_falls_back_to_the_table(self, installed_with):
        installed_with(selfupdate.PIPX)
        st = {"reason": "no-local-wheel", "built_provider": "local",
              "chunks": 0}
        assert (dense.fix_hint("no-local-wheel", st)
                == dense.fix_hint("no-local-wheel"))


class TestExtraHint:
    def test_pipx_past_the_ceiling_reinstalls_on_the_recommended_python(
            self, too_new, no_keys, installed_with):
        # Two steps: `install --force --python` keeps the venv's interpreter,
        # and `reinstall` replays a spec that has no extra.
        installed_with(selfupdate.PIPX)
        want = ('pipx uninstall boost-skill-cli && pipx install --python 3.13 '
                '--fetch-python=always "boost-skill-cli[rag]"')
        assert dense.extra_hint() == want
        # The surfaces that offer the extra for search all carry it.
        assert "`%s`" % want in dense.fix_hint("no-backend")
        assert "`%s`" % want in embed.fallback_note()

    def test_uv_past_the_ceiling_uses_its_own_python(self, too_new, no_keys,
                                                     installed_with):
        installed_with(selfupdate.UV_TOOL)
        assert dense.extra_hint() == (
            'uv tool install --force --managed-python --python 3.13 '
            '"boost-skill-cli[rag]"')

    @pytest.mark.parametrize("method", [selfupdate.PIP, selfupdate.UV_PIP,
                                        selfupdate.UNKNOWN])
    def test_others_past_the_ceiling_are_moved_not_half_installed(
            self, too_new, no_keys, installed_with, method):
        # A plain install here brings the store and no model to fill it.
        installed_with(method)
        assert dense.relocate_extra() is None
        assert dense.extra_hint() == (
            'pipx install --python 3.13 --fetch-python=always '
            '"boost-skill-cli[rag]"')

    def test_a_checkout_past_the_ceiling_rebuilds_its_venv(
            self, too_new, no_keys, installed_with):
        installed_with(selfupdate.GIT)
        assert dense.extra_hint() == (
            "python3.13 -m venv --clear .venv && .venv/bin/pip install -e "
            "'.[rag]'")

    @pytest.mark.parametrize("method", [selfupdate.PIPX, selfupdate.UV_TOOL,
                                        selfupdate.PIP])
    @pytest.mark.parametrize("env", ["VOYAGE_API_KEY", "OPENAI_API_KEY"])
    def test_a_key_needs_only_the_plain_extra(self, too_new, no_keys,
                                              installed_with, monkeypatch,
                                              method, env):
        # The key embeds over HTTP; sqlite-vec is all that is missing, and it
        # installs on this interpreter.
        installed_with(method)
        monkeypatch.setenv(env, "k")
        assert dense.extra_hint() == dense.install_extra()
        assert "--python" not in dense.extra_hint()

    def test_below_the_ceiling_nothing_moves(self, installed_with,
                                             monkeypatch):
        _onnx(monkeypatch, present=False)
        installed_with(selfupdate.PIPX)
        assert dense.extra_hint() == (
            'pipx inject boost-skill-cli "boost-skill-cli[rag]"')

    @pytest.mark.parametrize("method,hint", [
        (selfupdate.PIPX,
         'pipx uninstall boost-skill-cli && pipx install --python 3.13 '
         '--fetch-python=always "boost-skill-cli[rag]"'),
        (selfupdate.PIP,
         'pipx install --python 3.13 --fetch-python=always '
         '"boost-skill-cli[rag]"'),
        (selfupdate.UV_PIP,
         'pipx install --python 3.13 --fetch-python=always '
         '"boost-skill-cli[rag]"'),
        (selfupdate.UNKNOWN,
         'pipx install --python 3.13 --fetch-python=always '
         '"boost-skill-cli[rag]"'),
    ])
    def test_past_the_ceiling_the_hint_never_asks_pipx(
            self, too_new, no_keys, installed_with, monkeypatch, method,
            hint):
        # Every `boost search` on 3.15 renders this hint in a fresh process,
        # so it names the pipx 1.18 flag rather than pay `pipx --version`.
        installed_with(method)

        def no_probe(*a, **k):
            raise AssertionError("pipx --version on the search hint")
        monkeypatch.setattr(selfupdate, "pipx_version", no_probe)
        assert dense.extra_hint() == hint
        dense.fix_hint("no-backend")
        dense.fix_hint("no-local-wheel")

    def test_no_pipx_on_path_names_the_flag_a_fresh_pipx_takes(
            self, too_new, no_keys, installed_with, monkeypatch):
        installed_with(selfupdate.PIP)
        monkeypatch.setattr(selfupdate.shutil, "which", lambda t: None)
        assert dense.extra_hint() == (
            'pipx install --python 3.13 --fetch-python=always '
            '"boost-skill-cli[rag]"')

    def test_below_the_ceiling_pipx_is_never_asked(self, installed_with,
                                                    monkeypatch):
        # The flag costs a subprocess; only an interpreter that needs the
        # move may pay it, never every search.
        _onnx(monkeypatch, present=False)
        installed_with(selfupdate.PIPX)

        def no_probe(*a, **k):
            raise AssertionError("pipx --version on the hot path")
        monkeypatch.setattr(selfupdate, "pipx_version", no_probe)
        dense.extra_hint()
        dense.fix_hint("no-backend")

    def test_unreadable_vectors_still_name_the_plain_extra(self, too_new,
                                                           installed_with):
        # That error is about sqlite-vec, which installs on any interpreter.
        installed_with(selfupdate.PIPX)
        hint = dense._unreadable_vectors("a/b", 3, None).hint
        assert dense.install_extra() in hint
        assert "--python" not in hint
