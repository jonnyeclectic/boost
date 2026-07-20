"""Tests for the fork-safe HTTP opener (``core/nethttp``).

The whole point of the module is to keep proxy resolution on the pure-env
``getproxies_environment()`` path and off the macOS ``_scproxy`` Obj-C path
(``getproxies()`` / ``getproxies_macosx_sysconf()``), which aborts on the child
side of a ``fork()``. These tests pin that contract.
"""
import os
import urllib.request

import pytest

from boost_cli.core import nethttp


def _proxy_handler(opener):
    for h in opener.handlers:
        if isinstance(h, urllib.request.ProxyHandler):
            return h
    return None


class TestBuildOpener:
    def test_seeds_proxyhandler_from_environment(self, monkeypatch):
        monkeypatch.setattr(urllib.request, "getproxies_environment",
                            lambda: {"https": "http://proxy.example:8080"})
        opener = nethttp.build_opener()
        handler = _proxy_handler(opener)
        assert handler is not None
        assert handler.proxies == {"https": "http://proxy.example:8080"}

    def test_no_env_proxies_installs_no_proxy_handler(self, monkeypatch):
        # No *_proxy vars -> empty map -> stdlib build_opener registers no proxy
        # handler at all. So at request time nothing consults proxy_bypass /
        # the macOS sysconf Obj-C path: the fork-safe outcome.
        monkeypatch.setattr(urllib.request, "getproxies_environment", dict)
        assert _proxy_handler(nethttp.build_opener()) is None

    def test_never_calls_getproxies_sysconf_fallback(self, monkeypatch):
        # getproxies() is the fork-unsafe entry point (its macOS branch hits
        # _scproxy). If build_opener ever routed through it, this blows up.
        def _forbidden():
            raise AssertionError("build_opener used getproxies() (fork-unsafe)")

        monkeypatch.setattr(urllib.request, "getproxies", _forbidden)
        monkeypatch.setattr(urllib.request, "getproxies_environment", dict)
        opener = nethttp.build_opener()
        assert isinstance(opener, urllib.request.OpenerDirector)

    def test_returns_opener_director(self, monkeypatch):
        monkeypatch.setattr(urllib.request, "getproxies_environment", dict)
        assert isinstance(nethttp.build_opener(),
                          urllib.request.OpenerDirector)


class TestUrlopen:
    def test_delegates_to_opener_open_with_timeout(self, monkeypatch):
        calls = {}

        class FakeOpener:
            def open(self, req, timeout):
                calls["req"] = req
                calls["timeout"] = timeout
                return "RESP"

        monkeypatch.setattr(nethttp, "build_opener", FakeOpener)
        out = nethttp.urlopen("http://x.invalid", timeout=17)
        assert out == "RESP"
        assert calls == {"req": "http://x.invalid", "timeout": 17}

    def test_forwards_the_request_object_unchanged(self, monkeypatch):
        seen = {}

        class FakeOpener:
            def open(self, req, timeout):
                seen["req"] = req
                return None

        req = urllib.request.Request("http://x.invalid")
        monkeypatch.setattr(nethttp, "build_opener", FakeOpener)
        nethttp.urlopen(req, timeout=1)
        assert seen["req"] is req

    def test_timeout_is_required(self):
        with pytest.raises(TypeError):
            nethttp.urlopen("http://x.invalid")  # type: ignore[call-arg]


class TestHardenForkSafety:
    def test_seeds_no_proxy_when_no_env_proxy(self, monkeypatch):
        # No *_proxy vars configured -> the default getproxies() would fall
        # through to the fork-unsafe macOS sysconf path. harden seeds no_proxy
        # so getproxies_environment() wins instead.
        monkeypatch.setattr(urllib.request, "getproxies_environment", dict)
        monkeypatch.delenv("no_proxy", raising=False)
        assert nethttp.harden_fork_safety() is True
        assert os.environ["no_proxy"] == "*"

    def test_respects_existing_proxy_config(self, monkeypatch):
        # A real proxy is set -> getproxies_environment() already wins and the
        # sysconf branch is unreachable, so harden must not touch the env.
        monkeypatch.setattr(urllib.request, "getproxies_environment",
                            lambda: {"https": "http://proxy.example:8080"})
        monkeypatch.delenv("no_proxy", raising=False)
        assert nethttp.harden_fork_safety() is False
        assert "no_proxy" not in os.environ

    def test_does_not_clobber_existing_no_proxy(self, monkeypatch):
        # setdefault semantics: a user's own no_proxy value survives untouched.
        monkeypatch.setattr(urllib.request, "getproxies_environment", dict)
        monkeypatch.setenv("no_proxy", "example.com")
        assert nethttp.harden_fork_safety() is True
        assert os.environ["no_proxy"] == "example.com"

    def test_idempotent(self, monkeypatch):
        monkeypatch.setattr(urllib.request, "getproxies_environment", dict)
        monkeypatch.delenv("no_proxy", raising=False)
        assert nethttp.harden_fork_safety() is True
        assert nethttp.harden_fork_safety() is True
        assert os.environ["no_proxy"] == "*"
