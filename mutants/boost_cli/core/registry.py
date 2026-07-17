"""Tap registries: GitHub repos (or local paths) full of SKILL.md files."""
from __future__ import annotations

import difflib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..errors import BoostError
from . import config, gitutil, paths


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict


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
mutants_x_parse_spec__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_parse_spec__mutmut)
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


def x_parse_spec__mutmut_orig(spec: str):
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


def x_parse_spec__mutmut_1(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = None
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


def x_parse_spec__mutmut_2(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip(None)
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


def x_parse_spec__mutmut_3(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().lstrip("/")
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


def x_parse_spec__mutmut_4(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("XX/XX")
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


def x_parse_spec__mutmut_5(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = None
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


def x_parse_spec__mutmut_6(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(None).expanduser()
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


def x_parse_spec__mutmut_7(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() or p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_8(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(None))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_9(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(None):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_10(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("XXhttp://XX", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_11(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("HTTP://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_12(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "XXhttps://XX", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_13(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "HTTPS://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_14(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "XXgit@XX", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_15(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "GIT@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_16(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "XXssh://XX")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_17(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "SSH://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_18(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = None
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_19(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(None)[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_20(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split("XX:XX")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_21(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[+1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_22(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-2] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_23(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith(None) else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_24(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("XXgit@XX") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_25(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("GIT@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_26(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = None
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_27(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split(None) if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_28(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(None, "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_29(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", None).split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_30(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace("").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_31(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", ).split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_32(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace("XX.gitXX", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_33(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".GIT", "").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_34(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "XXXX").split("/") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_35(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("XX/XX") if x][-2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_36(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][+2:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_37(spec: str):
    """Resolve a tap spec -> (name, url).

    Accepts: owner/repo | full git URL | existing local path.
    """
    spec = spec.strip().rstrip("/")
    p = Path(spec).expanduser()
    if p.exists() and p.is_dir():
        return (p.resolve().name, str(p.resolve()))
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        tail = spec.split(":")[-1] if spec.startswith("git@") else spec
        parts = [x for x in tail.replace(".git", "").split("/") if x][-3:]
        return ("/".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_38(spec: str):
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
        return ("/".join(None), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_39(spec: str):
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
        return ("XX/XX".join(parts), spec)
    if "/" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_40(spec: str):
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
    if "/" in spec or " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_41(spec: str):
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
    if "XX/XX" in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_42(spec: str):
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
    if "/" not in spec and " " not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_43(spec: str):
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
    if "/" in spec and "XX XX" not in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_44(spec: str):
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
    if "/" in spec and " " in spec:
        return (spec, "https://github.com/%s" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_45(spec: str):
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
        return (spec, "https://github.com/%s" / spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_46(spec: str):
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
        return (spec, "XXhttps://github.com/%sXX" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_47(spec: str):
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
        return (spec, "HTTPS://GITHUB.COM/%S" % spec)
    raise BoostError("cannot parse tap spec %r" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_48(spec: str):
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
    raise BoostError(None,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_49(spec: str):
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
                    hint=None)


def x_parse_spec__mutmut_50(spec: str):
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
    raise BoostError(hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_51(spec: str):
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
                    )


def x_parse_spec__mutmut_52(spec: str):
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
    raise BoostError("cannot parse tap spec %r" / spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_53(spec: str):
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
    raise BoostError("XXcannot parse tap spec %rXX" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_54(spec: str):
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
    raise BoostError("CANNOT PARSE TAP SPEC %R" % spec,
                    hint="use owner/repo, a git URL, or a local directory")


def x_parse_spec__mutmut_55(spec: str):
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
                    hint="XXuse owner/repo, a git URL, or a local directoryXX")


def x_parse_spec__mutmut_56(spec: str):
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
                    hint="use owner/repo, a git url, or a local directory")


def x_parse_spec__mutmut_57(spec: str):
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
                    hint="USE OWNER/REPO, A GIT URL, OR A LOCAL DIRECTORY")

mutants_x_parse_spec__mutmut['_mutmut_orig'] = x_parse_spec__mutmut_orig # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_1'] = x_parse_spec__mutmut_1 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_2'] = x_parse_spec__mutmut_2 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_3'] = x_parse_spec__mutmut_3 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_4'] = x_parse_spec__mutmut_4 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_5'] = x_parse_spec__mutmut_5 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_6'] = x_parse_spec__mutmut_6 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_7'] = x_parse_spec__mutmut_7 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_8'] = x_parse_spec__mutmut_8 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_9'] = x_parse_spec__mutmut_9 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_10'] = x_parse_spec__mutmut_10 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_11'] = x_parse_spec__mutmut_11 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_12'] = x_parse_spec__mutmut_12 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_13'] = x_parse_spec__mutmut_13 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_14'] = x_parse_spec__mutmut_14 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_15'] = x_parse_spec__mutmut_15 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_16'] = x_parse_spec__mutmut_16 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_17'] = x_parse_spec__mutmut_17 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_18'] = x_parse_spec__mutmut_18 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_19'] = x_parse_spec__mutmut_19 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_20'] = x_parse_spec__mutmut_20 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_21'] = x_parse_spec__mutmut_21 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_22'] = x_parse_spec__mutmut_22 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_23'] = x_parse_spec__mutmut_23 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_24'] = x_parse_spec__mutmut_24 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_25'] = x_parse_spec__mutmut_25 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_26'] = x_parse_spec__mutmut_26 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_27'] = x_parse_spec__mutmut_27 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_28'] = x_parse_spec__mutmut_28 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_29'] = x_parse_spec__mutmut_29 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_30'] = x_parse_spec__mutmut_30 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_31'] = x_parse_spec__mutmut_31 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_32'] = x_parse_spec__mutmut_32 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_33'] = x_parse_spec__mutmut_33 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_34'] = x_parse_spec__mutmut_34 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_35'] = x_parse_spec__mutmut_35 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_36'] = x_parse_spec__mutmut_36 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_37'] = x_parse_spec__mutmut_37 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_38'] = x_parse_spec__mutmut_38 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_39'] = x_parse_spec__mutmut_39 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_40'] = x_parse_spec__mutmut_40 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_41'] = x_parse_spec__mutmut_41 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_42'] = x_parse_spec__mutmut_42 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_43'] = x_parse_spec__mutmut_43 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_44'] = x_parse_spec__mutmut_44 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_45'] = x_parse_spec__mutmut_45 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_46'] = x_parse_spec__mutmut_46 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_47'] = x_parse_spec__mutmut_47 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_48'] = x_parse_spec__mutmut_48 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_49'] = x_parse_spec__mutmut_49 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_50'] = x_parse_spec__mutmut_50 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_51'] = x_parse_spec__mutmut_51 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_52'] = x_parse_spec__mutmut_52 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_53'] = x_parse_spec__mutmut_53 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_54'] = x_parse_spec__mutmut_54 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_55'] = x_parse_spec__mutmut_55 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_56'] = x_parse_spec__mutmut_56 # type: ignore # mutmut generated
mutants_x_parse_spec__mutmut['x_parse_spec__mutmut_57'] = x_parse_spec__mutmut_57 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_list_taps__mutmut)
def list_taps() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_orig() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_1() -> List[Tap]:
    return [Tap(name=None, url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_2() -> List[Tap]:
    return [Tap(name=t["name"], url=None, curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_3() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), curated=None)
            for t in config.get("taps", [])]


def x_list_taps__mutmut_4() -> List[Tap]:
    return [Tap(url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_5() -> List[Tap]:
    return [Tap(name=t["name"], curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_6() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), )
            for t in config.get("taps", [])]


def x_list_taps__mutmut_7() -> List[Tap]:
    return [Tap(name=t["XXnameXX"], url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_8() -> List[Tap]:
    return [Tap(name=t["NAME"], url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_9() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get(None, ""), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_10() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", None), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_11() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get(""), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_12() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_13() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("XXurlXX", ""), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_14() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("URL", ""), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_15() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", "XXXX"), curated=bool(t.get("curated")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_16() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(None))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_17() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get(None)))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_18() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get("XXcuratedXX")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_19() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get("CURATED")))
            for t in config.get("taps", [])]


def x_list_taps__mutmut_20() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in config.get(None, [])]


def x_list_taps__mutmut_21() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in config.get("taps", None)]


def x_list_taps__mutmut_22() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in config.get([])]


def x_list_taps__mutmut_23() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in config.get("taps", )]


def x_list_taps__mutmut_24() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in config.get("XXtapsXX", [])]


def x_list_taps__mutmut_25() -> List[Tap]:
    return [Tap(name=t["name"], url=t.get("url", ""), curated=bool(t.get("curated")))
            for t in config.get("TAPS", [])]

mutants_x_list_taps__mutmut['_mutmut_orig'] = x_list_taps__mutmut_orig # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_1'] = x_list_taps__mutmut_1 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_2'] = x_list_taps__mutmut_2 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_3'] = x_list_taps__mutmut_3 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_4'] = x_list_taps__mutmut_4 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_5'] = x_list_taps__mutmut_5 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_6'] = x_list_taps__mutmut_6 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_7'] = x_list_taps__mutmut_7 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_8'] = x_list_taps__mutmut_8 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_9'] = x_list_taps__mutmut_9 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_10'] = x_list_taps__mutmut_10 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_11'] = x_list_taps__mutmut_11 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_12'] = x_list_taps__mutmut_12 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_13'] = x_list_taps__mutmut_13 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_14'] = x_list_taps__mutmut_14 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_15'] = x_list_taps__mutmut_15 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_16'] = x_list_taps__mutmut_16 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_17'] = x_list_taps__mutmut_17 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_18'] = x_list_taps__mutmut_18 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_19'] = x_list_taps__mutmut_19 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_20'] = x_list_taps__mutmut_20 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_21'] = x_list_taps__mutmut_21 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_22'] = x_list_taps__mutmut_22 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_23'] = x_list_taps__mutmut_23 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_24'] = x_list_taps__mutmut_24 # type: ignore # mutmut generated
mutants_x_list_taps__mutmut['x_list_taps__mutmut_25'] = x_list_taps__mutmut_25 # type: ignore # mutmut generated
mutants_x_get__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_get__mutmut)
def get(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_orig(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_1(name: str) -> Tap:
    taps = None
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_2(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name and t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_3(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name and t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_4(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name != name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_5(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name != name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_6(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split(None)[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_7(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("XX/XX")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_8(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[+1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_9(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-2] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_10(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] != name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_11(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = None
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_12(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(None, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_13(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, None, n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_14(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=None)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_15(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches([t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_16(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_17(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], )
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_18(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=2)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_19(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError(None,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_20(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=None)


def x_get__mutmut_21(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError(hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_22(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    )


def x_get__mutmut_23(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" / name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_24(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("XXno such tap: %sXX" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_25(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("NO SUCH TAP: %S" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_26(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" / close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_27(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("XXdid you mean %s?XX" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_28(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("DID YOU MEAN %S?" % close[0]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_29(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[1]) if close
                    else "list taps with `boost taps`")


def x_get__mutmut_30(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "XXlist taps with `boost taps`XX")


def x_get__mutmut_31(name: str) -> Tap:
    taps = list_taps()
    for t in taps:
        if t.name == name or t.safe_name == name or t.name.split("/")[-1] == name:
            return t
    close = difflib.get_close_matches(name, [t.name for t in taps], n=1)
    raise BoostError("no such tap: %s" % name,
                    hint=("did you mean %s?" % close[0]) if close
                    else "LIST TAPS WITH `BOOST TAPS`")

mutants_x_get__mutmut['_mutmut_orig'] = x_get__mutmut_orig # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_1'] = x_get__mutmut_1 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_2'] = x_get__mutmut_2 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_3'] = x_get__mutmut_3 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_4'] = x_get__mutmut_4 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_5'] = x_get__mutmut_5 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_6'] = x_get__mutmut_6 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_7'] = x_get__mutmut_7 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_8'] = x_get__mutmut_8 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_9'] = x_get__mutmut_9 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_10'] = x_get__mutmut_10 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_11'] = x_get__mutmut_11 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_12'] = x_get__mutmut_12 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_13'] = x_get__mutmut_13 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_14'] = x_get__mutmut_14 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_15'] = x_get__mutmut_15 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_16'] = x_get__mutmut_16 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_17'] = x_get__mutmut_17 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_18'] = x_get__mutmut_18 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_19'] = x_get__mutmut_19 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_20'] = x_get__mutmut_20 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_21'] = x_get__mutmut_21 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_22'] = x_get__mutmut_22 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_23'] = x_get__mutmut_23 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_24'] = x_get__mutmut_24 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_25'] = x_get__mutmut_25 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_26'] = x_get__mutmut_26 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_27'] = x_get__mutmut_27 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_28'] = x_get__mutmut_28 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_29'] = x_get__mutmut_29 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_30'] = x_get__mutmut_30 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_31'] = x_get__mutmut_31 # type: ignore # mutmut generated
mutants_x_add__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_add__mutmut)
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


def x_add__mutmut_orig(spec: str, curated: bool = False) -> Tap:
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


def x_add__mutmut_1(spec: str, curated: bool = True) -> Tap:
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


def x_add__mutmut_2(spec: str, curated: bool = False) -> Tap:
    name, url = None
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


def x_add__mutmut_3(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(None)
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


def x_add__mutmut_4(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name != name:
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


def x_add__mutmut_5(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError(None,
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


def x_add__mutmut_6(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint=None)
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


def x_add__mutmut_7(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError(hint="`boost update %s` to refresh it" % name)
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


def x_add__mutmut_8(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            )
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


def x_add__mutmut_9(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" / name,
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


def x_add__mutmut_10(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("XXtap %s is already configuredXX" % name,
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


def x_add__mutmut_11(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("TAP %S IS ALREADY CONFIGURED" % name,
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


def x_add__mutmut_12(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" / name)
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


def x_add__mutmut_13(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="XX`boost update %s` to refresh itXX" % name)
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


def x_add__mutmut_14(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`BOOST UPDATE %S` TO REFRESH IT" % name)
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


def x_add__mutmut_15(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = None
    paths.ensure_dirs()
    if tap.path.exists():
        shutil.rmtree(tap.path)
    gitutil.clone_shallow(url, tap.path)
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_16(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=None, url=url, curated=curated)
    paths.ensure_dirs()
    if tap.path.exists():
        shutil.rmtree(tap.path)
    gitutil.clone_shallow(url, tap.path)
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_17(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=name, url=None, curated=curated)
    paths.ensure_dirs()
    if tap.path.exists():
        shutil.rmtree(tap.path)
    gitutil.clone_shallow(url, tap.path)
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_18(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=name, url=url, curated=None)
    paths.ensure_dirs()
    if tap.path.exists():
        shutil.rmtree(tap.path)
    gitutil.clone_shallow(url, tap.path)
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_19(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(url=url, curated=curated)
    paths.ensure_dirs()
    if tap.path.exists():
        shutil.rmtree(tap.path)
    gitutil.clone_shallow(url, tap.path)
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_20(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=name, curated=curated)
    paths.ensure_dirs()
    if tap.path.exists():
        shutil.rmtree(tap.path)
    gitutil.clone_shallow(url, tap.path)
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_21(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=name, url=url, )
    paths.ensure_dirs()
    if tap.path.exists():
        shutil.rmtree(tap.path)
    gitutil.clone_shallow(url, tap.path)
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_22(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=name, url=url, curated=curated)
    paths.ensure_dirs()
    if tap.path.exists():
        shutil.rmtree(None)
    gitutil.clone_shallow(url, tap.path)
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_23(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=name, url=url, curated=curated)
    paths.ensure_dirs()
    if tap.path.exists():
        shutil.rmtree(tap.path)
    gitutil.clone_shallow(None, tap.path)
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_24(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=name, url=url, curated=curated)
    paths.ensure_dirs()
    if tap.path.exists():
        shutil.rmtree(tap.path)
    gitutil.clone_shallow(url, None)
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_25(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=name, url=url, curated=curated)
    paths.ensure_dirs()
    if tap.path.exists():
        shutil.rmtree(tap.path)
    gitutil.clone_shallow(tap.path)
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_26(spec: str, curated: bool = False) -> Tap:
    name, url = parse_spec(spec)
    for existing in list_taps():
        if existing.name == name:
            raise BoostError("tap %s is already configured" % name,
                            hint="`boost update %s` to refresh it" % name)
    tap = Tap(name=name, url=url, curated=curated)
    paths.ensure_dirs()
    if tap.path.exists():
        shutil.rmtree(tap.path)
    gitutil.clone_shallow(url, )
    cfg = config.load()
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_27(spec: str, curated: bool = False) -> Tap:
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
    cfg = None
    cfg.setdefault("taps", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_28(spec: str, curated: bool = False) -> Tap:
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
        None)
    config.save(cfg)
    return tap


def x_add__mutmut_29(spec: str, curated: bool = False) -> Tap:
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
    cfg.setdefault(None, []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_30(spec: str, curated: bool = False) -> Tap:
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
    cfg.setdefault("taps", None).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_31(spec: str, curated: bool = False) -> Tap:
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
    cfg.setdefault([]).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_32(spec: str, curated: bool = False) -> Tap:
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
    cfg.setdefault("taps", ).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_33(spec: str, curated: bool = False) -> Tap:
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
    cfg.setdefault("XXtapsXX", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_34(spec: str, curated: bool = False) -> Tap:
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
    cfg.setdefault("TAPS", []).append(
        {"name": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_35(spec: str, curated: bool = False) -> Tap:
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
        {"XXnameXX": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_36(spec: str, curated: bool = False) -> Tap:
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
        {"NAME": name, "url": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_37(spec: str, curated: bool = False) -> Tap:
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
        {"name": name, "XXurlXX": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_38(spec: str, curated: bool = False) -> Tap:
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
        {"name": name, "URL": url, "curated": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_39(spec: str, curated: bool = False) -> Tap:
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
        {"name": name, "url": url, "XXcuratedXX": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_40(spec: str, curated: bool = False) -> Tap:
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
        {"name": name, "url": url, "CURATED": curated})
    config.save(cfg)
    return tap


def x_add__mutmut_41(spec: str, curated: bool = False) -> Tap:
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
    config.save(None)
    return tap

mutants_x_add__mutmut['_mutmut_orig'] = x_add__mutmut_orig # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_1'] = x_add__mutmut_1 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_2'] = x_add__mutmut_2 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_3'] = x_add__mutmut_3 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_4'] = x_add__mutmut_4 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_5'] = x_add__mutmut_5 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_6'] = x_add__mutmut_6 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_7'] = x_add__mutmut_7 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_8'] = x_add__mutmut_8 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_9'] = x_add__mutmut_9 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_10'] = x_add__mutmut_10 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_11'] = x_add__mutmut_11 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_12'] = x_add__mutmut_12 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_13'] = x_add__mutmut_13 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_14'] = x_add__mutmut_14 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_15'] = x_add__mutmut_15 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_16'] = x_add__mutmut_16 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_17'] = x_add__mutmut_17 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_18'] = x_add__mutmut_18 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_19'] = x_add__mutmut_19 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_20'] = x_add__mutmut_20 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_21'] = x_add__mutmut_21 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_22'] = x_add__mutmut_22 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_23'] = x_add__mutmut_23 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_24'] = x_add__mutmut_24 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_25'] = x_add__mutmut_25 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_26'] = x_add__mutmut_26 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_27'] = x_add__mutmut_27 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_28'] = x_add__mutmut_28 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_29'] = x_add__mutmut_29 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_30'] = x_add__mutmut_30 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_31'] = x_add__mutmut_31 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_32'] = x_add__mutmut_32 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_33'] = x_add__mutmut_33 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_34'] = x_add__mutmut_34 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_35'] = x_add__mutmut_35 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_36'] = x_add__mutmut_36 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_37'] = x_add__mutmut_37 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_38'] = x_add__mutmut_38 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_39'] = x_add__mutmut_39 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_40'] = x_add__mutmut_40 # type: ignore # mutmut generated
mutants_x_add__mutmut['x_add__mutmut_41'] = x_add__mutmut_41 # type: ignore # mutmut generated
mutants_x_remove__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_remove__mutmut)
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


def x_remove__mutmut_orig(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("taps", []) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_1(name: str) -> Tap:
    tap = None
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("taps", []) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_2(name: str) -> Tap:
    tap = get(None)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("taps", []) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_3(name: str) -> Tap:
    tap = get(name)
    cfg = None
    cfg["taps"] = [t for t in cfg.get("taps", []) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_4(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = None
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_5(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["XXtapsXX"] = [t for t in cfg.get("taps", []) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_6(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["TAPS"] = [t for t in cfg.get("taps", []) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_7(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get(None, []) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_8(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("taps", None) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_9(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get([]) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_10(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("taps", ) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_11(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("XXtapsXX", []) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_12(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("TAPS", []) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_13(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("taps", []) if t["XXnameXX"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_14(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("taps", []) if t["NAME"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_15(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("taps", []) if t["name"] == tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_16(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("taps", []) if t["name"] != tap.name]
    config.save(None)
    if tap.path.exists():
        shutil.rmtree(tap.path)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap


def x_remove__mutmut_17(name: str) -> Tap:
    tap = get(name)
    cfg = config.load()
    cfg["taps"] = [t for t in cfg.get("taps", []) if t["name"] != tap.name]
    config.save(cfg)
    if tap.path.exists():
        shutil.rmtree(None)
    if tap.cache_file.exists():
        tap.cache_file.unlink()
    return tap

mutants_x_remove__mutmut['_mutmut_orig'] = x_remove__mutmut_orig # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_1'] = x_remove__mutmut_1 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_2'] = x_remove__mutmut_2 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_3'] = x_remove__mutmut_3 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_4'] = x_remove__mutmut_4 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_5'] = x_remove__mutmut_5 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_6'] = x_remove__mutmut_6 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_7'] = x_remove__mutmut_7 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_8'] = x_remove__mutmut_8 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_9'] = x_remove__mutmut_9 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_10'] = x_remove__mutmut_10 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_11'] = x_remove__mutmut_11 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_12'] = x_remove__mutmut_12 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_13'] = x_remove__mutmut_13 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_14'] = x_remove__mutmut_14 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_15'] = x_remove__mutmut_15 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_16'] = x_remove__mutmut_16 # type: ignore # mutmut generated
mutants_x_remove__mutmut['x_remove__mutmut_17'] = x_remove__mutmut_17 # type: ignore # mutmut generated
mutants_x_update__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_update__mutmut)
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


def x_update__mutmut_orig(name: Optional[str] = None) -> dict:
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


def x_update__mutmut_1(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = None
    results = {}
    for tap in targets:
        if not tap.is_cloned:
            gitutil.clone_shallow(tap.url, tap.path)
            results[tap.name] = "cloned"
        else:
            results[tap.name] = gitutil.pull(tap.path)
    return results


def x_update__mutmut_2(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = [get(None)] if name else list_taps()
    results = {}
    for tap in targets:
        if not tap.is_cloned:
            gitutil.clone_shallow(tap.url, tap.path)
            results[tap.name] = "cloned"
        else:
            results[tap.name] = gitutil.pull(tap.path)
    return results


def x_update__mutmut_3(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = [get(name)] if name else list_taps()
    results = None
    for tap in targets:
        if not tap.is_cloned:
            gitutil.clone_shallow(tap.url, tap.path)
            results[tap.name] = "cloned"
        else:
            results[tap.name] = gitutil.pull(tap.path)
    return results


def x_update__mutmut_4(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = [get(name)] if name else list_taps()
    results = {}
    for tap in targets:
        if tap.is_cloned:
            gitutil.clone_shallow(tap.url, tap.path)
            results[tap.name] = "cloned"
        else:
            results[tap.name] = gitutil.pull(tap.path)
    return results


def x_update__mutmut_5(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = [get(name)] if name else list_taps()
    results = {}
    for tap in targets:
        if not tap.is_cloned:
            gitutil.clone_shallow(None, tap.path)
            results[tap.name] = "cloned"
        else:
            results[tap.name] = gitutil.pull(tap.path)
    return results


def x_update__mutmut_6(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = [get(name)] if name else list_taps()
    results = {}
    for tap in targets:
        if not tap.is_cloned:
            gitutil.clone_shallow(tap.url, None)
            results[tap.name] = "cloned"
        else:
            results[tap.name] = gitutil.pull(tap.path)
    return results


def x_update__mutmut_7(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = [get(name)] if name else list_taps()
    results = {}
    for tap in targets:
        if not tap.is_cloned:
            gitutil.clone_shallow(tap.path)
            results[tap.name] = "cloned"
        else:
            results[tap.name] = gitutil.pull(tap.path)
    return results


def x_update__mutmut_8(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = [get(name)] if name else list_taps()
    results = {}
    for tap in targets:
        if not tap.is_cloned:
            gitutil.clone_shallow(tap.url, )
            results[tap.name] = "cloned"
        else:
            results[tap.name] = gitutil.pull(tap.path)
    return results


def x_update__mutmut_9(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = [get(name)] if name else list_taps()
    results = {}
    for tap in targets:
        if not tap.is_cloned:
            gitutil.clone_shallow(tap.url, tap.path)
            results[tap.name] = None
        else:
            results[tap.name] = gitutil.pull(tap.path)
    return results


def x_update__mutmut_10(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = [get(name)] if name else list_taps()
    results = {}
    for tap in targets:
        if not tap.is_cloned:
            gitutil.clone_shallow(tap.url, tap.path)
            results[tap.name] = "XXclonedXX"
        else:
            results[tap.name] = gitutil.pull(tap.path)
    return results


def x_update__mutmut_11(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = [get(name)] if name else list_taps()
    results = {}
    for tap in targets:
        if not tap.is_cloned:
            gitutil.clone_shallow(tap.url, tap.path)
            results[tap.name] = "CLONED"
        else:
            results[tap.name] = gitutil.pull(tap.path)
    return results


def x_update__mutmut_12(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = [get(name)] if name else list_taps()
    results = {}
    for tap in targets:
        if not tap.is_cloned:
            gitutil.clone_shallow(tap.url, tap.path)
            results[tap.name] = "cloned"
        else:
            results[tap.name] = None
    return results


def x_update__mutmut_13(name: Optional[str] = None) -> dict:
    """git-pull one tap (or all). Returns {tap_name: summary}."""
    targets = [get(name)] if name else list_taps()
    results = {}
    for tap in targets:
        if not tap.is_cloned:
            gitutil.clone_shallow(tap.url, tap.path)
            results[tap.name] = "cloned"
        else:
            results[tap.name] = gitutil.pull(None)
    return results

mutants_x_update__mutmut['_mutmut_orig'] = x_update__mutmut_orig # type: ignore # mutmut generated
mutants_x_update__mutmut['x_update__mutmut_1'] = x_update__mutmut_1 # type: ignore # mutmut generated
mutants_x_update__mutmut['x_update__mutmut_2'] = x_update__mutmut_2 # type: ignore # mutmut generated
mutants_x_update__mutmut['x_update__mutmut_3'] = x_update__mutmut_3 # type: ignore # mutmut generated
mutants_x_update__mutmut['x_update__mutmut_4'] = x_update__mutmut_4 # type: ignore # mutmut generated
mutants_x_update__mutmut['x_update__mutmut_5'] = x_update__mutmut_5 # type: ignore # mutmut generated
mutants_x_update__mutmut['x_update__mutmut_6'] = x_update__mutmut_6 # type: ignore # mutmut generated
mutants_x_update__mutmut['x_update__mutmut_7'] = x_update__mutmut_7 # type: ignore # mutmut generated
mutants_x_update__mutmut['x_update__mutmut_8'] = x_update__mutmut_8 # type: ignore # mutmut generated
mutants_x_update__mutmut['x_update__mutmut_9'] = x_update__mutmut_9 # type: ignore # mutmut generated
mutants_x_update__mutmut['x_update__mutmut_10'] = x_update__mutmut_10 # type: ignore # mutmut generated
mutants_x_update__mutmut['x_update__mutmut_11'] = x_update__mutmut_11 # type: ignore # mutmut generated
mutants_x_update__mutmut['x_update__mutmut_12'] = x_update__mutmut_12 # type: ignore # mutmut generated
mutants_x_update__mutmut['x_update__mutmut_13'] = x_update__mutmut_13 # type: ignore # mutmut generated
