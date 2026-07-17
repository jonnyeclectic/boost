"""AI agent targets: where installed skills get symlinked."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from . import config, paths

DISPLAY = {"claude-code": "Claude Code", "windsurf": "Windsurf", "cursor": "Cursor"}


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict
mutants_x_known_agents__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_known_agents__mutmut)
def known_agents() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_orig() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_1() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = None
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_2() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") and {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_3() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get(None) or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_4() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("XXagentsXX") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_5() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("AGENTS") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_6() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = None
    return out


def x_known_agents__mutmut_7() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "XXdirXX": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_8() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "DIR": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_9() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(None),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_10() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(None)),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_11() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get(None, ""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_12() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", None))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_13() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get(""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_14() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_15() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("XXdirXX", ""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_16() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("DIR", ""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_17() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", "XXXX"))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_18() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "XXenabledXX": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_19() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "ENABLED": bool(spec.get("enabled", True)),
        }
    return out


def x_known_agents__mutmut_20() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(None),
        }
    return out


def x_known_agents__mutmut_21() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get(None, True)),
        }
    return out


def x_known_agents__mutmut_22() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", None)),
        }
    return out


def x_known_agents__mutmut_23() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get(True)),
        }
    return out


def x_known_agents__mutmut_24() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", )),
        }
    return out


def x_known_agents__mutmut_25() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("XXenabledXX", True)),
        }
    return out


def x_known_agents__mutmut_26() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("ENABLED", True)),
        }
    return out


def x_known_agents__mutmut_27() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", False)),
        }
    return out

mutants_x_known_agents__mutmut['_mutmut_orig'] = x_known_agents__mutmut_orig # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_1'] = x_known_agents__mutmut_1 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_2'] = x_known_agents__mutmut_2 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_3'] = x_known_agents__mutmut_3 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_4'] = x_known_agents__mutmut_4 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_5'] = x_known_agents__mutmut_5 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_6'] = x_known_agents__mutmut_6 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_7'] = x_known_agents__mutmut_7 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_8'] = x_known_agents__mutmut_8 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_9'] = x_known_agents__mutmut_9 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_10'] = x_known_agents__mutmut_10 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_11'] = x_known_agents__mutmut_11 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_12'] = x_known_agents__mutmut_12 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_13'] = x_known_agents__mutmut_13 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_14'] = x_known_agents__mutmut_14 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_15'] = x_known_agents__mutmut_15 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_16'] = x_known_agents__mutmut_16 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_17'] = x_known_agents__mutmut_17 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_18'] = x_known_agents__mutmut_18 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_19'] = x_known_agents__mutmut_19 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_20'] = x_known_agents__mutmut_20 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_21'] = x_known_agents__mutmut_21 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_22'] = x_known_agents__mutmut_22 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_23'] = x_known_agents__mutmut_23 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_24'] = x_known_agents__mutmut_24 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_25'] = x_known_agents__mutmut_25 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_26'] = x_known_agents__mutmut_26 # type: ignore # mutmut generated
mutants_x_known_agents__mutmut['x_known_agents__mutmut_27'] = x_known_agents__mutmut_27 # type: ignore # mutmut generated
mutants_x_enabled_agents__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_enabled_agents__mutmut)
def enabled_agents() -> Dict[str, Path]:
    return {n: s["dir"] for n, s in known_agents().items() if s["enabled"]}


def x_enabled_agents__mutmut_orig() -> Dict[str, Path]:
    return {n: s["dir"] for n, s in known_agents().items() if s["enabled"]}


def x_enabled_agents__mutmut_1() -> Dict[str, Path]:
    return {n: s["XXdirXX"] for n, s in known_agents().items() if s["enabled"]}


def x_enabled_agents__mutmut_2() -> Dict[str, Path]:
    return {n: s["DIR"] for n, s in known_agents().items() if s["enabled"]}


def x_enabled_agents__mutmut_3() -> Dict[str, Path]:
    return {n: s["dir"] for n, s in known_agents().items() if s["XXenabledXX"]}


def x_enabled_agents__mutmut_4() -> Dict[str, Path]:
    return {n: s["dir"] for n, s in known_agents().items() if s["ENABLED"]}

mutants_x_enabled_agents__mutmut['_mutmut_orig'] = x_enabled_agents__mutmut_orig # type: ignore # mutmut generated
mutants_x_enabled_agents__mutmut['x_enabled_agents__mutmut_1'] = x_enabled_agents__mutmut_1 # type: ignore # mutmut generated
mutants_x_enabled_agents__mutmut['x_enabled_agents__mutmut_2'] = x_enabled_agents__mutmut_2 # type: ignore # mutmut generated
mutants_x_enabled_agents__mutmut['x_enabled_agents__mutmut_3'] = x_enabled_agents__mutmut_3 # type: ignore # mutmut generated
mutants_x_enabled_agents__mutmut['x_enabled_agents__mutmut_4'] = x_enabled_agents__mutmut_4 # type: ignore # mutmut generated
mutants_x_display_name__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_display_name__mutmut)
def display_name(agent: str) -> str:
    return DISPLAY.get(agent, agent)


def x_display_name__mutmut_orig(agent: str) -> str:
    return DISPLAY.get(agent, agent)


def x_display_name__mutmut_1(agent: str) -> str:
    return DISPLAY.get(None, agent)


def x_display_name__mutmut_2(agent: str) -> str:
    return DISPLAY.get(agent, None)


def x_display_name__mutmut_3(agent: str) -> str:
    return DISPLAY.get(agent)


def x_display_name__mutmut_4(agent: str) -> str:
    return DISPLAY.get(agent, )

mutants_x_display_name__mutmut['_mutmut_orig'] = x_display_name__mutmut_orig # type: ignore # mutmut generated
mutants_x_display_name__mutmut['x_display_name__mutmut_1'] = x_display_name__mutmut_1 # type: ignore # mutmut generated
mutants_x_display_name__mutmut['x_display_name__mutmut_2'] = x_display_name__mutmut_2 # type: ignore # mutmut generated
mutants_x_display_name__mutmut['x_display_name__mutmut_3'] = x_display_name__mutmut_3 # type: ignore # mutmut generated
mutants_x_display_name__mutmut['x_display_name__mutmut_4'] = x_display_name__mutmut_4 # type: ignore # mutmut generated
mutants_x_ensure_agent_dirs__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_ensure_agent_dirs__mutmut)
def ensure_agent_dirs() -> None:
    for d in enabled_agents().values():
        d.mkdir(parents=True, exist_ok=True)


def x_ensure_agent_dirs__mutmut_orig() -> None:
    for d in enabled_agents().values():
        d.mkdir(parents=True, exist_ok=True)


def x_ensure_agent_dirs__mutmut_1() -> None:
    for d in enabled_agents().values():
        d.mkdir(parents=None, exist_ok=True)


def x_ensure_agent_dirs__mutmut_2() -> None:
    for d in enabled_agents().values():
        d.mkdir(parents=True, exist_ok=None)


def x_ensure_agent_dirs__mutmut_3() -> None:
    for d in enabled_agents().values():
        d.mkdir(exist_ok=True)


def x_ensure_agent_dirs__mutmut_4() -> None:
    for d in enabled_agents().values():
        d.mkdir(parents=True, )


def x_ensure_agent_dirs__mutmut_5() -> None:
    for d in enabled_agents().values():
        d.mkdir(parents=False, exist_ok=True)


def x_ensure_agent_dirs__mutmut_6() -> None:
    for d in enabled_agents().values():
        d.mkdir(parents=True, exist_ok=False)

mutants_x_ensure_agent_dirs__mutmut['_mutmut_orig'] = x_ensure_agent_dirs__mutmut_orig # type: ignore # mutmut generated
mutants_x_ensure_agent_dirs__mutmut['x_ensure_agent_dirs__mutmut_1'] = x_ensure_agent_dirs__mutmut_1 # type: ignore # mutmut generated
mutants_x_ensure_agent_dirs__mutmut['x_ensure_agent_dirs__mutmut_2'] = x_ensure_agent_dirs__mutmut_2 # type: ignore # mutmut generated
mutants_x_ensure_agent_dirs__mutmut['x_ensure_agent_dirs__mutmut_3'] = x_ensure_agent_dirs__mutmut_3 # type: ignore # mutmut generated
mutants_x_ensure_agent_dirs__mutmut['x_ensure_agent_dirs__mutmut_4'] = x_ensure_agent_dirs__mutmut_4 # type: ignore # mutmut generated
mutants_x_ensure_agent_dirs__mutmut['x_ensure_agent_dirs__mutmut_5'] = x_ensure_agent_dirs__mutmut_5 # type: ignore # mutmut generated
mutants_x_ensure_agent_dirs__mutmut['x_ensure_agent_dirs__mutmut_6'] = x_ensure_agent_dirs__mutmut_6 # type: ignore # mutmut generated
