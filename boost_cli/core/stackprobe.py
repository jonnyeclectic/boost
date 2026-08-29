# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Tech-stack probing: read a project tree and name its languages/frameworks.

``detect_stack`` used to live in ``commands/discovery.py`` even though the
Intelligence and Quality command modules both imported it — engine logic
stranded in a command module, reached across the command layer. It belongs in
``core``: a pure, filesystem-only prober with no command dependencies, so every
consumer shares one implementation instead of a copy plus a fallback table.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# Directories that never describe the project's own stack — skip them so a
# vendored dependency can't masquerade as a first-party language.
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
              "dist", "build", "target", "vendor"}

# A file extension seen ``>= 2`` times is treated as a language signal even
# without a manifest — enough to catch a script-only repo.
_EXT_LANGS = {".py": "python", ".ts": "typescript", ".tsx": "typescript",
              ".js": "javascript", ".jsx": "javascript", ".go": "go",
              ".rs": "rust", ".java": "java", ".rb": "ruby", ".kt": "kotlin",
              ".swift": "swift", ".php": "php", ".cs": "csharp"}


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def detect_stack(path) -> dict[str, list]:
    """Detect a project's tech stack from files on disk.

    Walks at most two directory levels (skipping .git/node_modules etc.) and
    returns ``{"languages": [...], "frameworks": [...], "keywords": [...]}``.
    """
    root = Path(path)
    langs, frameworks, extras = set(), set(), set()
    markers: dict = {}
    ext_counts: dict = {}
    for dirpath, dirnames, filenames in os.walk(str(root)):
        rel = os.path.relpath(dirpath, str(root))
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        dirnames[:] = [] if depth >= 2 else [d for d in dirnames
                                             if d not in _SKIP_DIRS]
        for fn in filenames:
            markers.setdefault(fn.lower(), Path(dirpath) / fn)
            ext = os.path.splitext(fn)[1].lower()
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

    def read(*names) -> str:
        return "\n".join(_read_text(markers[n]) for n in names
                         if n in markers).lower()

    if "package.json" in markers:
        langs.add("javascript")
        try:
            pkg = json.loads(_read_text(markers["package.json"]))
        except json.JSONDecodeError:
            pkg = {}
        if not isinstance(pkg, dict):
            pkg = {}
        deps: set = set()
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            deps.update(pkg.get(section) or {})
        for dep in ("react", "vue", "next", "express"):
            if any(d == dep or d.startswith((dep + "/", "@" + dep + "/"))
                   for d in deps):
                frameworks.add(dep)
        if "typescript" in deps:
            langs.add("typescript")
    if "pyproject.toml" in markers or "requirements.txt" in markers:
        langs.add("python")
        blob = read("pyproject.toml", "requirements.txt")
        for fw in ("django", "flask", "fastapi", "pytest"):
            if fw in blob:
                frameworks.add(fw)
    if "go.mod" in markers:
        langs.add("go")
    if "cargo.toml" in markers:
        langs.add("rust")
    if any(n in markers for n in ("pom.xml", "build.gradle", "build.gradle.kts")):
        langs.add("java")
        if "spring" in read("pom.xml", "build.gradle", "build.gradle.kts"):
            frameworks.add("spring")
    if "gemfile" in markers:
        langs.add("ruby")
        if "rails" in read("gemfile"):
            frameworks.add("rails")
    if "tsconfig.json" in markers:
        langs.add("typescript")
    if "dockerfile" in markers:
        extras.add("docker")
    if (root / ".github" / "workflows").is_dir():
        extras.add("ci")
    if ext_counts.get(".tf"):
        extras.add("terraform")
    for ext, n in ext_counts.items():
        if n >= 2 and ext in _EXT_LANGS:
            langs.add(_EXT_LANGS[ext])
    return {"languages": sorted(langs), "frameworks": sorted(frameworks),
            "keywords": sorted(langs | frameworks | extras)}
