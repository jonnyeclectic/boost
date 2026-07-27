"""Tap registries: GitHub repos (or local paths) full of SKILL.md files."""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..errors import BoostError
from . import config, gitutil, paths, policy, util


@dataclass
class Tap:
    """One configured tap: name, source URL, and derived on-disk paths."""
    name: str          # "anthropics/skills" or a short alias
    url: str           # https URL or local path
    curated: bool = False

    @property
    def safe_name(self) -> str:
        """Filesystem-safe name: `/` replaced with `__`."""
        return self.name.replace("/", "__")

    @property
    def path(self) -> Path:
        """Local clone directory under `~/.boost/repos/`."""
        return paths.repos_dir() / self.safe_name

    @property
    def cache_file(self) -> Path:
        """Catalog JSON path under `~/.boost/cache/`."""
        return paths.cache_dir() / (self.safe_name + ".json")

    @property
    def is_cloned(self) -> bool:
        """True if the tap's clone directory exists on disk."""
        return self.path.is_dir()


def parse_spec(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    # paths.expand(), not Path.expanduser(): expanduser() consults the OS's
    # own home-dir lookup (USERPROFILE on Windows), which ignores the $HOME
    # override the whole test suite (and BOOST_HOME sandboxing) relies on.
    p = paths.expand(spec)
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def list_taps() -> List[Tap]:
    """Configured taps from config.json.

    Malformed config or entries read as no taps, never raise.
    """
    # `or []`, not just the get() default: config.get returns the default only
    # when the key is ABSENT, so a config.json carrying `"taps": null` (or any
    # non-list scalar) would otherwise reach the comprehension and raise
    # TypeError. A malformed config should read as "no taps", never crash every
    # command that lists them.
    taps = config.get("taps", []) or []
    if not isinstance(taps, list):
        return []
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in taps if isinstance(t, dict) and t.get("name")]


def get(name: str) -> Tap:
    """Look up a tap by name, safe_name, or bare repo name.

    Tiered so a qualified name always beats a short one: exact ``owner/repo``
    first, then ``safe_name``, then the bare repo tail. Within a tier a name
    that matches more than one tap is an error rather than a guess — with
    ``angular/skills`` and ``microsoft/skills`` both tapped, ``boost untap
    skills`` used to act on whichever came first in config.json, which for a
    destructive command is the wrong answer half the time.

    Raises BoostError (with a did-you-mean hint) if none match.
    """
    taps = list_taps()
    for key in (lambda t: t.name, lambda t: t.safe_name,
                lambda t: t.name.split("/")[-1]):
        hits = [t for t in taps if key(t) == name]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise BoostError(
                "%r is ambiguous — it matches %d taps: %s"
                % (name, len(hits), ", ".join(sorted(t.name for t in hits))),
                hint="use the full owner/repo name")
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def add(spec: str, curated: bool = False) -> Tap:
    """Parse `spec`, shallow-clone it, and record the tap in config.

    Raises BoostError if a tap with that name is already configured.
    """
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=name, url=url, curated=curated)
    paths.ensure_dirs()
    if tap.path.exists():
        util.rmtree(tap.path)
    gitutil.clone_shallow(url, tap.path)
    problems = policy.check_tap_signing(tap.path)
    if problems:
        util.rmtree(tap.path)  # leave no half-added tap behind
        raise BoostError(
            "tap %s failed provenance policy: %s" % (name, "; ".join(problems)),
            hint="add its key with `boost trust add <name> <key>`, "
                 "or relax `boost policy set require_signed_taps false`")
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def remove(name: str) -> Tap:
    """Deregister a tap and delete its clone and cache file.

    Returns the removed Tap; raises BoostError if it does not exist.
    """
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("taps", []) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        util.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def update(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = [get(name)] if name else list_taps()
    results = {}
    for tap in targets:
        if not tap.is_cloned:
            gitutil.clone_shallow(tap.url, tap.path)
            results[tap.name] = "cloned"
        else:
            results[tap.name] = gitutil.pull(tap.path)
    return results
