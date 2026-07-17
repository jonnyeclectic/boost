"""Tap registries: GitHub repos (or local paths) full of SKILL.md files."""
from __future__ import annotations

import difflib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..errors import BoostError
from . import config, gitutil, paths


@dataclass
class Tap:
    name: str          # "anthropics/skills" or a short alias
    url: str           # https URL or local path
    curated: bool = False

    @property
    def safe_name(self) -> str:
        return self.name.replace("/", "__")

    @property
    def path(self) -> Path:
        return paths.repos_dir() / self.safe_name

    @property
    def cache_file(self) -> Path:
        return paths.cache_dir() / (self.safe_name + ".json")

    @property
    def is_cloned(self) -> bool:
        return self.path.is_dir()


def parse_spec(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
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
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def get(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def add(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=name, url=url, curated=curated)
    paths.ensure_dirs()
    if tap.path.exists():
        shutil.rmtree(tap.path)
    gitutil.clone_shallow(url, tap.path)
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def remove(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("taps", []) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
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
