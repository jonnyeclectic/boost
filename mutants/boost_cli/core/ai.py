"""Optional AI bridge for the Intelligence commands and --smart ranking.

Strategy: prefer the `claude` CLI if on PATH, else the Anthropic API via
urllib when ANTHROPIC_API_KEY is set, else return None so every caller
degrades to its non-AI fallback.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Optional

from . import config

API_URL = "https://api.anthropic.com/v1/messages"


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict
mutants_x_enabled__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_enabled__mutmut)
def enabled() -> bool:
    return bool(config.get("ai.enabled", True)) and not os.environ.get("BOOST_NO_AI")


def x_enabled__mutmut_orig() -> bool:
    return bool(config.get("ai.enabled", True)) and not os.environ.get("BOOST_NO_AI")


def x_enabled__mutmut_1() -> bool:
    return bool(config.get("ai.enabled", True)) or not os.environ.get("BOOST_NO_AI")


def x_enabled__mutmut_2() -> bool:
    return bool(None) and not os.environ.get("BOOST_NO_AI")


def x_enabled__mutmut_3() -> bool:
    return bool(config.get(None, True)) and not os.environ.get("BOOST_NO_AI")


def x_enabled__mutmut_4() -> bool:
    return bool(config.get("ai.enabled", None)) and not os.environ.get("BOOST_NO_AI")


def x_enabled__mutmut_5() -> bool:
    return bool(config.get(True)) and not os.environ.get("BOOST_NO_AI")


def x_enabled__mutmut_6() -> bool:
    return bool(config.get("ai.enabled", )) and not os.environ.get("BOOST_NO_AI")


def x_enabled__mutmut_7() -> bool:
    return bool(config.get("XXai.enabledXX", True)) and not os.environ.get("BOOST_NO_AI")


def x_enabled__mutmut_8() -> bool:
    return bool(config.get("AI.ENABLED", True)) and not os.environ.get("BOOST_NO_AI")


def x_enabled__mutmut_9() -> bool:
    return bool(config.get("ai.enabled", False)) and not os.environ.get("BOOST_NO_AI")


def x_enabled__mutmut_10() -> bool:
    return bool(config.get("ai.enabled", True)) and os.environ.get("BOOST_NO_AI")


def x_enabled__mutmut_11() -> bool:
    return bool(config.get("ai.enabled", True)) and not os.environ.get(None)


def x_enabled__mutmut_12() -> bool:
    return bool(config.get("ai.enabled", True)) and not os.environ.get("XXBOOST_NO_AIXX")


def x_enabled__mutmut_13() -> bool:
    return bool(config.get("ai.enabled", True)) and not os.environ.get("boost_no_ai")

mutants_x_enabled__mutmut['_mutmut_orig'] = x_enabled__mutmut_orig # type: ignore # mutmut generated
mutants_x_enabled__mutmut['x_enabled__mutmut_1'] = x_enabled__mutmut_1 # type: ignore # mutmut generated
mutants_x_enabled__mutmut['x_enabled__mutmut_2'] = x_enabled__mutmut_2 # type: ignore # mutmut generated
mutants_x_enabled__mutmut['x_enabled__mutmut_3'] = x_enabled__mutmut_3 # type: ignore # mutmut generated
mutants_x_enabled__mutmut['x_enabled__mutmut_4'] = x_enabled__mutmut_4 # type: ignore # mutmut generated
mutants_x_enabled__mutmut['x_enabled__mutmut_5'] = x_enabled__mutmut_5 # type: ignore # mutmut generated
mutants_x_enabled__mutmut['x_enabled__mutmut_6'] = x_enabled__mutmut_6 # type: ignore # mutmut generated
mutants_x_enabled__mutmut['x_enabled__mutmut_7'] = x_enabled__mutmut_7 # type: ignore # mutmut generated
mutants_x_enabled__mutmut['x_enabled__mutmut_8'] = x_enabled__mutmut_8 # type: ignore # mutmut generated
mutants_x_enabled__mutmut['x_enabled__mutmut_9'] = x_enabled__mutmut_9 # type: ignore # mutmut generated
mutants_x_enabled__mutmut['x_enabled__mutmut_10'] = x_enabled__mutmut_10 # type: ignore # mutmut generated
mutants_x_enabled__mutmut['x_enabled__mutmut_11'] = x_enabled__mutmut_11 # type: ignore # mutmut generated
mutants_x_enabled__mutmut['x_enabled__mutmut_12'] = x_enabled__mutmut_12 # type: ignore # mutmut generated
mutants_x_enabled__mutmut['x_enabled__mutmut_13'] = x_enabled__mutmut_13 # type: ignore # mutmut generated
mutants_x_available__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_available__mutmut)
def available() -> bool:
    return enabled() and (has_cli() or bool(os.environ.get("ANTHROPIC_API_KEY")))


def x_available__mutmut_orig() -> bool:
    return enabled() and (has_cli() or bool(os.environ.get("ANTHROPIC_API_KEY")))


def x_available__mutmut_1() -> bool:
    return enabled() or (has_cli() or bool(os.environ.get("ANTHROPIC_API_KEY")))


def x_available__mutmut_2() -> bool:
    return enabled() and (has_cli() and bool(os.environ.get("ANTHROPIC_API_KEY")))


def x_available__mutmut_3() -> bool:
    return enabled() and (has_cli() or bool(None))


def x_available__mutmut_4() -> bool:
    return enabled() and (has_cli() or bool(os.environ.get(None)))


def x_available__mutmut_5() -> bool:
    return enabled() and (has_cli() or bool(os.environ.get("XXANTHROPIC_API_KEYXX")))


def x_available__mutmut_6() -> bool:
    return enabled() and (has_cli() or bool(os.environ.get("anthropic_api_key")))

mutants_x_available__mutmut['_mutmut_orig'] = x_available__mutmut_orig # type: ignore # mutmut generated
mutants_x_available__mutmut['x_available__mutmut_1'] = x_available__mutmut_1 # type: ignore # mutmut generated
mutants_x_available__mutmut['x_available__mutmut_2'] = x_available__mutmut_2 # type: ignore # mutmut generated
mutants_x_available__mutmut['x_available__mutmut_3'] = x_available__mutmut_3 # type: ignore # mutmut generated
mutants_x_available__mutmut['x_available__mutmut_4'] = x_available__mutmut_4 # type: ignore # mutmut generated
mutants_x_available__mutmut['x_available__mutmut_5'] = x_available__mutmut_5 # type: ignore # mutmut generated
mutants_x_available__mutmut['x_available__mutmut_6'] = x_available__mutmut_6 # type: ignore # mutmut generated
mutants_x_has_cli__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_has_cli__mutmut)
def has_cli() -> bool:
    return shutil.which("claude") is not None


def x_has_cli__mutmut_orig() -> bool:
    return shutil.which("claude") is not None


def x_has_cli__mutmut_1() -> bool:
    return shutil.which(None) is not None


def x_has_cli__mutmut_2() -> bool:
    return shutil.which("XXclaudeXX") is not None


def x_has_cli__mutmut_3() -> bool:
    return shutil.which("CLAUDE") is not None


def x_has_cli__mutmut_4() -> bool:
    return shutil.which("claude") is None

mutants_x_has_cli__mutmut['_mutmut_orig'] = x_has_cli__mutmut_orig # type: ignore # mutmut generated
mutants_x_has_cli__mutmut['x_has_cli__mutmut_1'] = x_has_cli__mutmut_1 # type: ignore # mutmut generated
mutants_x_has_cli__mutmut['x_has_cli__mutmut_2'] = x_has_cli__mutmut_2 # type: ignore # mutmut generated
mutants_x_has_cli__mutmut['x_has_cli__mutmut_3'] = x_has_cli__mutmut_3 # type: ignore # mutmut generated
mutants_x_has_cli__mutmut['x_has_cli__mutmut_4'] = x_has_cli__mutmut_4 # type: ignore # mutmut generated
mutants_x_fallback_note__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_fallback_note__mutmut)
def fallback_note() -> str:
    return ("AI features need the `claude` CLI on PATH or ANTHROPIC_API_KEY set "
            "— using the heuristic fallback")


def x_fallback_note__mutmut_orig() -> str:
    return ("AI features need the `claude` CLI on PATH or ANTHROPIC_API_KEY set "
            "— using the heuristic fallback")


def x_fallback_note__mutmut_1() -> str:
    return ("XXAI features need the `claude` CLI on PATH or ANTHROPIC_API_KEY set XX"
            "— using the heuristic fallback")


def x_fallback_note__mutmut_2() -> str:
    return ("ai features need the `claude` cli on path or anthropic_api_key set "
            "— using the heuristic fallback")


def x_fallback_note__mutmut_3() -> str:
    return ("AI FEATURES NEED THE `CLAUDE` CLI ON PATH OR ANTHROPIC_API_KEY SET "
            "— using the heuristic fallback")


def x_fallback_note__mutmut_4() -> str:
    return ("AI features need the `claude` CLI on PATH or ANTHROPIC_API_KEY set "
            "XX— using the heuristic fallbackXX")


def x_fallback_note__mutmut_5() -> str:
    return ("AI features need the `claude` CLI on PATH or ANTHROPIC_API_KEY set "
            "— USING THE HEURISTIC FALLBACK")

mutants_x_fallback_note__mutmut['_mutmut_orig'] = x_fallback_note__mutmut_orig # type: ignore # mutmut generated
mutants_x_fallback_note__mutmut['x_fallback_note__mutmut_1'] = x_fallback_note__mutmut_1 # type: ignore # mutmut generated
mutants_x_fallback_note__mutmut['x_fallback_note__mutmut_2'] = x_fallback_note__mutmut_2 # type: ignore # mutmut generated
mutants_x_fallback_note__mutmut['x_fallback_note__mutmut_3'] = x_fallback_note__mutmut_3 # type: ignore # mutmut generated
mutants_x_fallback_note__mutmut['x_fallback_note__mutmut_4'] = x_fallback_note__mutmut_4 # type: ignore # mutmut generated
mutants_x_fallback_note__mutmut['x_fallback_note__mutmut_5'] = x_fallback_note__mutmut_5 # type: ignore # mutmut generated
mutants_x_ask__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_ask__mutmut)
def ask(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_orig(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_1(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1501, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_2(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 121) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_3(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_4(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = None
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_5(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model and str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_6(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(None)
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_7(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get(None))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_8(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("XXai.modelXX"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_9(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("AI.MODEL"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_10(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = None
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_11(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(None, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_12(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, None, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_13(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, None, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_14(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, None)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_15(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_16(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_17(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_18(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, )
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_19(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get(None):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_20(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("XXANTHROPIC_API_KEYXX"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_21(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("anthropic_api_key"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_22(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(None, system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_23(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, None, model, max_tokens, timeout)
    return None


def x_ask__mutmut_24(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, None, max_tokens, timeout)
    return None


def x_ask__mutmut_25(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, None, timeout)
    return None


def x_ask__mutmut_26(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, None)
    return None


def x_ask__mutmut_27(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(system, model, max_tokens, timeout)
    return None


def x_ask__mutmut_28(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, model, max_tokens, timeout)
    return None


def x_ask__mutmut_29(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, max_tokens, timeout)
    return None


def x_ask__mutmut_30(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, timeout)
    return None


def x_ask__mutmut_31(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, )
    return None

mutants_x_ask__mutmut['_mutmut_orig'] = x_ask__mutmut_orig # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_1'] = x_ask__mutmut_1 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_2'] = x_ask__mutmut_2 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_3'] = x_ask__mutmut_3 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_4'] = x_ask__mutmut_4 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_5'] = x_ask__mutmut_5 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_6'] = x_ask__mutmut_6 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_7'] = x_ask__mutmut_7 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_8'] = x_ask__mutmut_8 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_9'] = x_ask__mutmut_9 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_10'] = x_ask__mutmut_10 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_11'] = x_ask__mutmut_11 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_12'] = x_ask__mutmut_12 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_13'] = x_ask__mutmut_13 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_14'] = x_ask__mutmut_14 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_15'] = x_ask__mutmut_15 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_16'] = x_ask__mutmut_16 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_17'] = x_ask__mutmut_17 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_18'] = x_ask__mutmut_18 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_19'] = x_ask__mutmut_19 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_20'] = x_ask__mutmut_20 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_21'] = x_ask__mutmut_21 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_22'] = x_ask__mutmut_22 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_23'] = x_ask__mutmut_23 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_24'] = x_ask__mutmut_24 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_25'] = x_ask__mutmut_25 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_26'] = x_ask__mutmut_26 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_27'] = x_ask__mutmut_27 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_28'] = x_ask__mutmut_28 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_29'] = x_ask__mutmut_29 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_30'] = x_ask__mutmut_30 # type: ignore # mutmut generated
mutants_x_ask__mutmut['x_ask__mutmut_31'] = x_ask__mutmut_31 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_ask_author__mutmut)
def ask_author(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(config.get("ai.author_model")),
               max_tokens=max_tokens, timeout=240)


def x_ask_author__mutmut_orig(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(config.get("ai.author_model")),
               max_tokens=max_tokens, timeout=240)


def x_ask_author__mutmut_1(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4001) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(config.get("ai.author_model")),
               max_tokens=max_tokens, timeout=240)


def x_ask_author__mutmut_2(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(None, system=system, model=str(config.get("ai.author_model")),
               max_tokens=max_tokens, timeout=240)


def x_ask_author__mutmut_3(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=None, model=str(config.get("ai.author_model")),
               max_tokens=max_tokens, timeout=240)


def x_ask_author__mutmut_4(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=None,
               max_tokens=max_tokens, timeout=240)


def x_ask_author__mutmut_5(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(config.get("ai.author_model")),
               max_tokens=None, timeout=240)


def x_ask_author__mutmut_6(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(config.get("ai.author_model")),
               max_tokens=max_tokens, timeout=None)


def x_ask_author__mutmut_7(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(system=system, model=str(config.get("ai.author_model")),
               max_tokens=max_tokens, timeout=240)


def x_ask_author__mutmut_8(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, model=str(config.get("ai.author_model")),
               max_tokens=max_tokens, timeout=240)


def x_ask_author__mutmut_9(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, max_tokens=max_tokens, timeout=240)


def x_ask_author__mutmut_10(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(config.get("ai.author_model")),
               timeout=240)


def x_ask_author__mutmut_11(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(config.get("ai.author_model")),
               max_tokens=max_tokens, )


def x_ask_author__mutmut_12(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(None),
               max_tokens=max_tokens, timeout=240)


def x_ask_author__mutmut_13(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(config.get(None)),
               max_tokens=max_tokens, timeout=240)


def x_ask_author__mutmut_14(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(config.get("XXai.author_modelXX")),
               max_tokens=max_tokens, timeout=240)


def x_ask_author__mutmut_15(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(config.get("AI.AUTHOR_MODEL")),
               max_tokens=max_tokens, timeout=240)


def x_ask_author__mutmut_16(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(config.get("ai.author_model")),
               max_tokens=max_tokens, timeout=241)

mutants_x_ask_author__mutmut['_mutmut_orig'] = x_ask_author__mutmut_orig # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_1'] = x_ask_author__mutmut_1 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_2'] = x_ask_author__mutmut_2 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_3'] = x_ask_author__mutmut_3 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_4'] = x_ask_author__mutmut_4 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_5'] = x_ask_author__mutmut_5 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_6'] = x_ask_author__mutmut_6 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_7'] = x_ask_author__mutmut_7 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_8'] = x_ask_author__mutmut_8 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_9'] = x_ask_author__mutmut_9 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_10'] = x_ask_author__mutmut_10 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_11'] = x_ask_author__mutmut_11 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_12'] = x_ask_author__mutmut_12 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_13'] = x_ask_author__mutmut_13 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_14'] = x_ask_author__mutmut_14 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_15'] = x_ask_author__mutmut_15 # type: ignore # mutmut generated
mutants_x_ask_author__mutmut['x_ask_author__mutmut_16'] = x_ask_author__mutmut_16 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x__ask_cli__mutmut)
def _ask_cli(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_orig(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_1(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = None
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_2(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["XXclaudeXX", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_3(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["CLAUDE", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_4(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "XX-pXX", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_5(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-P", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_6(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "XX--modelXX", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_7(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--MODEL", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_8(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "XX--output-formatXX", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_9(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--OUTPUT-FORMAT", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_10(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "XXtextXX"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_11(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "TEXT"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_12(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd = ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_13(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd -= ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_14(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["XX--append-system-promptXX", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_15(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--APPEND-SYSTEM-PROMPT", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_16(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = None
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_17(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(None, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_18(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=None, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_19(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=None,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_20(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=None, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_21(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=None)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_22(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_23(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_24(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_25(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_26(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_27(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=False,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_28(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=False, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_29(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode == 0:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_30(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 1:
        return None
    return proc.stdout.strip() or None


def x__ask_cli__mutmut_31(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() and None

mutants_x__ask_cli__mutmut['_mutmut_orig'] = x__ask_cli__mutmut_orig # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_1'] = x__ask_cli__mutmut_1 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_2'] = x__ask_cli__mutmut_2 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_3'] = x__ask_cli__mutmut_3 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_4'] = x__ask_cli__mutmut_4 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_5'] = x__ask_cli__mutmut_5 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_6'] = x__ask_cli__mutmut_6 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_7'] = x__ask_cli__mutmut_7 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_8'] = x__ask_cli__mutmut_8 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_9'] = x__ask_cli__mutmut_9 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_10'] = x__ask_cli__mutmut_10 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_11'] = x__ask_cli__mutmut_11 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_12'] = x__ask_cli__mutmut_12 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_13'] = x__ask_cli__mutmut_13 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_14'] = x__ask_cli__mutmut_14 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_15'] = x__ask_cli__mutmut_15 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_16'] = x__ask_cli__mutmut_16 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_17'] = x__ask_cli__mutmut_17 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_18'] = x__ask_cli__mutmut_18 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_19'] = x__ask_cli__mutmut_19 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_20'] = x__ask_cli__mutmut_20 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_21'] = x__ask_cli__mutmut_21 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_22'] = x__ask_cli__mutmut_22 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_23'] = x__ask_cli__mutmut_23 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_24'] = x__ask_cli__mutmut_24 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_25'] = x__ask_cli__mutmut_25 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_26'] = x__ask_cli__mutmut_26 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_27'] = x__ask_cli__mutmut_27 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_28'] = x__ask_cli__mutmut_28 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_29'] = x__ask_cli__mutmut_29 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_30'] = x__ask_cli__mutmut_30 # type: ignore # mutmut generated
mutants_x__ask_cli__mutmut['x__ask_cli__mutmut_31'] = x__ask_cli__mutmut_31 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x__ask_api__mutmut)
def _ask_api(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_orig(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_1(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = None
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_2(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "XXmodelXX": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_3(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "MODEL": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_4(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "XXmax_tokensXX": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_5(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "MAX_TOKENS": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_6(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "XXmessagesXX": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_7(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "MESSAGES": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_8(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"XXroleXX": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_9(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"ROLE": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_10(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "XXuserXX", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_11(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "USER", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_12(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "XXcontentXX": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_13(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "CONTENT": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_14(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = None
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_15(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["XXsystemXX"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_16(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["SYSTEM"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_17(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_18(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        None,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_19(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=None,
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_20(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers=None,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_21(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method=None,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_22(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_23(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_24(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_25(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_26(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(None).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_27(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "XXcontent-typeXX": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_28(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "CONTENT-TYPE": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_29(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "XXapplication/jsonXX",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_30(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "APPLICATION/JSON",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_31(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "XXx-api-keyXX": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_32(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "X-API-KEY": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_33(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["XXANTHROPIC_API_KEYXX"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_34(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["anthropic_api_key"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_35(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "XXanthropic-versionXX": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_36(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "ANTHROPIC-VERSION": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_37(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "XX2023-06-01XX",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_38(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="XXPOSTXX",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_39(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="post",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_40(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(None, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_41(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=None) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_42(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_43(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, ) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_44(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_45(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(None)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_46(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = None
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_47(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get(None, "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_48(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", None) for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_49(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_50(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", ) for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_51(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("XXtextXX", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_52(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("TEXT", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_53(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "XXXX") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_54(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get(None, [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_55(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", None)
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_56(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get([])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_57(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", )
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_58(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("XXcontentXX", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_59(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("CONTENT", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_60(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get(None) == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_61(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("XXtypeXX") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_62(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("TYPE") == "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_63(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") != "text"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_64(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "XXtextXX"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_65(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "TEXT"]
    return "\n".join(parts).strip() or None


def x__ask_api__mutmut_66(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() and None


def x__ask_api__mutmut_67(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(None).strip() or None


def x__ask_api__mutmut_68(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "XX\nXX".join(parts).strip() or None

mutants_x__ask_api__mutmut['_mutmut_orig'] = x__ask_api__mutmut_orig # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_1'] = x__ask_api__mutmut_1 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_2'] = x__ask_api__mutmut_2 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_3'] = x__ask_api__mutmut_3 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_4'] = x__ask_api__mutmut_4 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_5'] = x__ask_api__mutmut_5 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_6'] = x__ask_api__mutmut_6 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_7'] = x__ask_api__mutmut_7 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_8'] = x__ask_api__mutmut_8 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_9'] = x__ask_api__mutmut_9 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_10'] = x__ask_api__mutmut_10 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_11'] = x__ask_api__mutmut_11 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_12'] = x__ask_api__mutmut_12 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_13'] = x__ask_api__mutmut_13 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_14'] = x__ask_api__mutmut_14 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_15'] = x__ask_api__mutmut_15 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_16'] = x__ask_api__mutmut_16 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_17'] = x__ask_api__mutmut_17 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_18'] = x__ask_api__mutmut_18 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_19'] = x__ask_api__mutmut_19 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_20'] = x__ask_api__mutmut_20 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_21'] = x__ask_api__mutmut_21 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_22'] = x__ask_api__mutmut_22 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_23'] = x__ask_api__mutmut_23 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_24'] = x__ask_api__mutmut_24 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_25'] = x__ask_api__mutmut_25 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_26'] = x__ask_api__mutmut_26 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_27'] = x__ask_api__mutmut_27 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_28'] = x__ask_api__mutmut_28 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_29'] = x__ask_api__mutmut_29 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_30'] = x__ask_api__mutmut_30 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_31'] = x__ask_api__mutmut_31 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_32'] = x__ask_api__mutmut_32 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_33'] = x__ask_api__mutmut_33 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_34'] = x__ask_api__mutmut_34 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_35'] = x__ask_api__mutmut_35 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_36'] = x__ask_api__mutmut_36 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_37'] = x__ask_api__mutmut_37 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_38'] = x__ask_api__mutmut_38 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_39'] = x__ask_api__mutmut_39 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_40'] = x__ask_api__mutmut_40 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_41'] = x__ask_api__mutmut_41 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_42'] = x__ask_api__mutmut_42 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_43'] = x__ask_api__mutmut_43 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_44'] = x__ask_api__mutmut_44 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_45'] = x__ask_api__mutmut_45 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_46'] = x__ask_api__mutmut_46 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_47'] = x__ask_api__mutmut_47 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_48'] = x__ask_api__mutmut_48 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_49'] = x__ask_api__mutmut_49 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_50'] = x__ask_api__mutmut_50 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_51'] = x__ask_api__mutmut_51 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_52'] = x__ask_api__mutmut_52 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_53'] = x__ask_api__mutmut_53 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_54'] = x__ask_api__mutmut_54 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_55'] = x__ask_api__mutmut_55 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_56'] = x__ask_api__mutmut_56 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_57'] = x__ask_api__mutmut_57 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_58'] = x__ask_api__mutmut_58 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_59'] = x__ask_api__mutmut_59 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_60'] = x__ask_api__mutmut_60 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_61'] = x__ask_api__mutmut_61 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_62'] = x__ask_api__mutmut_62 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_63'] = x__ask_api__mutmut_63 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_64'] = x__ask_api__mutmut_64 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_65'] = x__ask_api__mutmut_65 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_66'] = x__ask_api__mutmut_66 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_67'] = x__ask_api__mutmut_67 # type: ignore # mutmut generated
mutants_x__ask_api__mutmut['x__ask_api__mutmut_68'] = x__ask_api__mutmut_68 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_extract_markdown__mutmut)
def extract_markdown(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_orig(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_1(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = None
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_2(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text and "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_3(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "XXXX").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_4(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith(None):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_5(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("XX```XX"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_6(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = None
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_7(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith(None):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_8(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[1].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_9(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("XX```XX"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_10(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = None
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_11(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[2:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_12(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines or lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_13(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[+1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_14(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-2].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_15(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() != "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_16(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "XX```XX":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_17(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = None
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_18(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:+1]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_19(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-2]
        return "\n".join(lines).strip()
    return t


def x_extract_markdown__mutmut_20(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(None).strip()
    return t


def x_extract_markdown__mutmut_21(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "XX\nXX".join(lines).strip()
    return t

mutants_x_extract_markdown__mutmut['_mutmut_orig'] = x_extract_markdown__mutmut_orig # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_1'] = x_extract_markdown__mutmut_1 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_2'] = x_extract_markdown__mutmut_2 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_3'] = x_extract_markdown__mutmut_3 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_4'] = x_extract_markdown__mutmut_4 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_5'] = x_extract_markdown__mutmut_5 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_6'] = x_extract_markdown__mutmut_6 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_7'] = x_extract_markdown__mutmut_7 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_8'] = x_extract_markdown__mutmut_8 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_9'] = x_extract_markdown__mutmut_9 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_10'] = x_extract_markdown__mutmut_10 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_11'] = x_extract_markdown__mutmut_11 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_12'] = x_extract_markdown__mutmut_12 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_13'] = x_extract_markdown__mutmut_13 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_14'] = x_extract_markdown__mutmut_14 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_15'] = x_extract_markdown__mutmut_15 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_16'] = x_extract_markdown__mutmut_16 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_17'] = x_extract_markdown__mutmut_17 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_18'] = x_extract_markdown__mutmut_18 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_19'] = x_extract_markdown__mutmut_19 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_20'] = x_extract_markdown__mutmut_20 # type: ignore # mutmut generated
mutants_x_extract_markdown__mutmut['x_extract_markdown__mutmut_21'] = x_extract_markdown__mutmut_21 # type: ignore # mutmut generated
