"""Configuration: ~/.boost/config.json with deep-merged defaults."""
from __future__ import annotations

import json
from copy import deepcopy

from . import paths

DEFAULTS = {
    "agents": {
        "claude-code": {"dir": "~/.claude/skills", "enabled": True},
        "windsurf": {"dir": "~/.windsurf/skills", "enabled": True},
        "cursor": {"dir": "~/.cursor/skills", "enabled": True},
    },
    "taps": [],  # [{"name": "owner/repo", "url": "...", "curated": bool}]
    "ai": {
        "enabled": True,
        "model": "claude-haiku-4-5-20251001",        # ranking / quick summaries
        "author_model": "claude-sonnet-5",           # authoring (infer/distill/evolve)
    },
    "serve": {"port": 8787},
    "policy_enforce": True,
    "telemetry": False,
}

# Recommended public registries, added via `boost tap --defaults`.
DEFAULT_TAPS = [
    {"name": "anthropics/skills", "url": "https://github.com/anthropics/skills",
     "curated": True,
     "focus": "Official Anthropic skills — docs, artifacts, MCP, agent workflows"},
    {"name": "obra/superpowers", "url": "https://github.com/obra/superpowers",
     "curated": True,
     "focus": "Community powerhouse — TDD, debugging, planning, subagents"},
]


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict
mutants_x__merge__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x__merge__mutmut)
def _merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def x__merge__mutmut_orig(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def x__merge__mutmut_1(base: dict, override: dict) -> dict:
    out = None
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def x__merge__mutmut_2(base: dict, override: dict) -> dict:
    out = deepcopy(None)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def x__merge__mutmut_3(base: dict, override: dict) -> dict:
    out = copy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def x__merge__mutmut_4(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in (override and {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def x__merge__mutmut_5(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) or isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def x__merge__mutmut_6(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = None
        else:
            out[k] = v
    return out


def x__merge__mutmut_7(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(None, v)
        else:
            out[k] = v
    return out


def x__merge__mutmut_8(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], None)
        else:
            out[k] = v
    return out


def x__merge__mutmut_9(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(v)
        else:
            out[k] = v
    return out


def x__merge__mutmut_10(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], )
        else:
            out[k] = v
    return out


def x__merge__mutmut_11(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = None
    return out

mutants_x__merge__mutmut['_mutmut_orig'] = x__merge__mutmut_orig # type: ignore # mutmut generated
mutants_x__merge__mutmut['x__merge__mutmut_1'] = x__merge__mutmut_1 # type: ignore # mutmut generated
mutants_x__merge__mutmut['x__merge__mutmut_2'] = x__merge__mutmut_2 # type: ignore # mutmut generated
mutants_x__merge__mutmut['x__merge__mutmut_3'] = x__merge__mutmut_3 # type: ignore # mutmut generated
mutants_x__merge__mutmut['x__merge__mutmut_4'] = x__merge__mutmut_4 # type: ignore # mutmut generated
mutants_x__merge__mutmut['x__merge__mutmut_5'] = x__merge__mutmut_5 # type: ignore # mutmut generated
mutants_x__merge__mutmut['x__merge__mutmut_6'] = x__merge__mutmut_6 # type: ignore # mutmut generated
mutants_x__merge__mutmut['x__merge__mutmut_7'] = x__merge__mutmut_7 # type: ignore # mutmut generated
mutants_x__merge__mutmut['x__merge__mutmut_8'] = x__merge__mutmut_8 # type: ignore # mutmut generated
mutants_x__merge__mutmut['x__merge__mutmut_9'] = x__merge__mutmut_9 # type: ignore # mutmut generated
mutants_x__merge__mutmut['x__merge__mutmut_10'] = x__merge__mutmut_10 # type: ignore # mutmut generated
mutants_x__merge__mutmut['x__merge__mutmut_11'] = x__merge__mutmut_11 # type: ignore # mutmut generated
mutants_x_load__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_load__mutmut)
def load() -> dict:
    p = paths.config_path()
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(DEFAULTS, user)


def x_load__mutmut_orig() -> dict:
    p = paths.config_path()
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(DEFAULTS, user)


def x_load__mutmut_1() -> dict:
    p = None
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(DEFAULTS, user)


def x_load__mutmut_2() -> dict:
    p = paths.config_path()
    if p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(DEFAULTS, user)


def x_load__mutmut_3() -> dict:
    p = paths.config_path()
    if not p.exists():
        return deepcopy(None)
    try:
        user = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(DEFAULTS, user)


def x_load__mutmut_4() -> dict:
    p = paths.config_path()
    if not p.exists():
        return copy(DEFAULTS)
    try:
        user = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(DEFAULTS, user)


def x_load__mutmut_5() -> dict:
    p = paths.config_path()
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = None
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(DEFAULTS, user)


def x_load__mutmut_6() -> dict:
    p = paths.config_path()
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = json.loads(None)
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(DEFAULTS, user)


def x_load__mutmut_7() -> dict:
    p = paths.config_path()
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return deepcopy(None)
    return _merge(DEFAULTS, user)


def x_load__mutmut_8() -> dict:
    p = paths.config_path()
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return copy(DEFAULTS)
    return _merge(DEFAULTS, user)


def x_load__mutmut_9() -> dict:
    p = paths.config_path()
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(None, user)


def x_load__mutmut_10() -> dict:
    p = paths.config_path()
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(DEFAULTS, None)


def x_load__mutmut_11() -> dict:
    p = paths.config_path()
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(user)


def x_load__mutmut_12() -> dict:
    p = paths.config_path()
    if not p.exists():
        return deepcopy(DEFAULTS)
    try:
        user = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULTS)
    return _merge(DEFAULTS, )

mutants_x_load__mutmut['_mutmut_orig'] = x_load__mutmut_orig # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_1'] = x_load__mutmut_1 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_2'] = x_load__mutmut_2 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_3'] = x_load__mutmut_3 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_4'] = x_load__mutmut_4 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_5'] = x_load__mutmut_5 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_6'] = x_load__mutmut_6 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_7'] = x_load__mutmut_7 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_8'] = x_load__mutmut_8 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_9'] = x_load__mutmut_9 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_10'] = x_load__mutmut_10 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_11'] = x_load__mutmut_11 # type: ignore # mutmut generated
mutants_x_load__mutmut['x_load__mutmut_12'] = x_load__mutmut_12 # type: ignore # mutmut generated
mutants_x_save__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_save__mutmut)
def save(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(json.dumps(cfg, indent=2, sort_keys=False) + "\n")


def x_save__mutmut_orig(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(json.dumps(cfg, indent=2, sort_keys=False) + "\n")


def x_save__mutmut_1(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(None)


def x_save__mutmut_2(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(json.dumps(cfg, indent=2, sort_keys=False) - "\n")


def x_save__mutmut_3(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(json.dumps(None, indent=2, sort_keys=False) + "\n")


def x_save__mutmut_4(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(json.dumps(cfg, indent=None, sort_keys=False) + "\n")


def x_save__mutmut_5(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(json.dumps(cfg, indent=2, sort_keys=None) + "\n")


def x_save__mutmut_6(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(json.dumps(indent=2, sort_keys=False) + "\n")


def x_save__mutmut_7(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(json.dumps(cfg, sort_keys=False) + "\n")


def x_save__mutmut_8(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(json.dumps(cfg, indent=2, ) + "\n")


def x_save__mutmut_9(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(json.dumps(cfg, indent=3, sort_keys=False) + "\n")


def x_save__mutmut_10(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n")


def x_save__mutmut_11(cfg: dict) -> None:
    paths.ensure_dirs()
    paths.config_path().write_text(json.dumps(cfg, indent=2, sort_keys=False) + "XX\nXX")

mutants_x_save__mutmut['_mutmut_orig'] = x_save__mutmut_orig # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_1'] = x_save__mutmut_1 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_2'] = x_save__mutmut_2 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_3'] = x_save__mutmut_3 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_4'] = x_save__mutmut_4 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_5'] = x_save__mutmut_5 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_6'] = x_save__mutmut_6 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_7'] = x_save__mutmut_7 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_8'] = x_save__mutmut_8 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_9'] = x_save__mutmut_9 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_10'] = x_save__mutmut_10 # type: ignore # mutmut generated
mutants_x_save__mutmut['x_save__mutmut_11'] = x_save__mutmut_11 # type: ignore # mutmut generated
mutants_x_get__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_get__mutmut)
def get(dotted: str, default=None):
    node = load()
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def x_get__mutmut_orig(dotted: str, default=None):
    node = load()
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def x_get__mutmut_1(dotted: str, default=None):
    node = None
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def x_get__mutmut_2(dotted: str, default=None):
    node = load()
    for part in dotted.split(None):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def x_get__mutmut_3(dotted: str, default=None):
    node = load()
    for part in dotted.split("XX.XX"):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def x_get__mutmut_4(dotted: str, default=None):
    node = load()
    for part in dotted.split("."):
        if not isinstance(node, dict) and part not in node:
            return default
        node = node[part]
    return node


def x_get__mutmut_5(dotted: str, default=None):
    node = load()
    for part in dotted.split("."):
        if isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def x_get__mutmut_6(dotted: str, default=None):
    node = load()
    for part in dotted.split("."):
        if not isinstance(node, dict) or part in node:
            return default
        node = node[part]
    return node


def x_get__mutmut_7(dotted: str, default=None):
    node = load()
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = None
    return node

mutants_x_get__mutmut['_mutmut_orig'] = x_get__mutmut_orig # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_1'] = x_get__mutmut_1 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_2'] = x_get__mutmut_2 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_3'] = x_get__mutmut_3 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_4'] = x_get__mutmut_4 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_5'] = x_get__mutmut_5 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_6'] = x_get__mutmut_6 # type: ignore # mutmut generated
mutants_x_get__mutmut['x_get__mutmut_7'] = x_get__mutmut_7 # type: ignore # mutmut generated
mutants_x_set_value__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_set_value__mutmut)
def set_value(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_orig(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_1(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = None
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_2(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(None)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_3(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = None
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_4(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = None
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_5(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = None
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_6(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = None
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_7(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(None)
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_8(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split("XX.XX")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_9(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:+1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_10(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-2]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_11(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = None
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_12(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(None, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_13(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, None)
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_14(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault({})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_15(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, )
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_16(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_17(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError(None)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_18(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" / part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_19(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("XXconfig key %r is not a sectionXX" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_20(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("CONFIG KEY %R IS NOT A SECTION" % part)
    node[parts[-1]] = value
    save(cfg)


def x_set_value__mutmut_21(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = None
    save(cfg)


def x_set_value__mutmut_22(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[+1]] = value
    save(cfg)


def x_set_value__mutmut_23(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-2]] = value
    save(cfg)


def x_set_value__mutmut_24(dotted: str, raw: str) -> None:
    """Set a dotted key. Values parse as JSON when possible, else string."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = raw
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise TypeError("config key %r is not a section" % part)
    node[parts[-1]] = value
    save(None)

mutants_x_set_value__mutmut['_mutmut_orig'] = x_set_value__mutmut_orig # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_1'] = x_set_value__mutmut_1 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_2'] = x_set_value__mutmut_2 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_3'] = x_set_value__mutmut_3 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_4'] = x_set_value__mutmut_4 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_5'] = x_set_value__mutmut_5 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_6'] = x_set_value__mutmut_6 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_7'] = x_set_value__mutmut_7 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_8'] = x_set_value__mutmut_8 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_9'] = x_set_value__mutmut_9 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_10'] = x_set_value__mutmut_10 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_11'] = x_set_value__mutmut_11 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_12'] = x_set_value__mutmut_12 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_13'] = x_set_value__mutmut_13 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_14'] = x_set_value__mutmut_14 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_15'] = x_set_value__mutmut_15 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_16'] = x_set_value__mutmut_16 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_17'] = x_set_value__mutmut_17 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_18'] = x_set_value__mutmut_18 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_19'] = x_set_value__mutmut_19 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_20'] = x_set_value__mutmut_20 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_21'] = x_set_value__mutmut_21 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_22'] = x_set_value__mutmut_22 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_23'] = x_set_value__mutmut_23 # type: ignore # mutmut generated
mutants_x_set_value__mutmut['x_set_value__mutmut_24'] = x_set_value__mutmut_24 # type: ignore # mutmut generated
mutants_x_unset__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_unset__mutmut)
def unset(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_orig(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_1(dotted: str) -> bool:
    cfg = None
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_2(dotted: str) -> bool:
    cfg = load()
    node = None
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_3(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = None
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_4(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(None)
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_5(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split("XX.XX")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_6(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:+1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_7(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-2]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_8(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = None
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_9(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(None)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_10(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_11(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return True
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_12(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[+1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_13(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-2] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_14(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] not in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_15(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[+1]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_16(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-2]]
        save(cfg)
        return True
    return False


def x_unset__mutmut_17(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(None)
        return True
    return False


def x_unset__mutmut_18(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return False
    return False


def x_unset__mutmut_19(dotted: str) -> bool:
    cfg = load()
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return False
    if parts[-1] in node:
        del node[parts[-1]]
        save(cfg)
        return True
    return True

mutants_x_unset__mutmut['_mutmut_orig'] = x_unset__mutmut_orig # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_1'] = x_unset__mutmut_1 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_2'] = x_unset__mutmut_2 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_3'] = x_unset__mutmut_3 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_4'] = x_unset__mutmut_4 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_5'] = x_unset__mutmut_5 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_6'] = x_unset__mutmut_6 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_7'] = x_unset__mutmut_7 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_8'] = x_unset__mutmut_8 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_9'] = x_unset__mutmut_9 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_10'] = x_unset__mutmut_10 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_11'] = x_unset__mutmut_11 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_12'] = x_unset__mutmut_12 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_13'] = x_unset__mutmut_13 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_14'] = x_unset__mutmut_14 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_15'] = x_unset__mutmut_15 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_16'] = x_unset__mutmut_16 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_17'] = x_unset__mutmut_17 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_18'] = x_unset__mutmut_18 # type: ignore # mutmut generated
mutants_x_unset__mutmut['x_unset__mutmut_19'] = x_unset__mutmut_19 # type: ignore # mutmut generated
