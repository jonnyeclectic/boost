#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Per-assistant-CLI facts for the AI bridge — a pure table, like `hookhost`.

`core/ai.py` knew exactly one backend: the `claude` CLI, or the Anthropic API
via ANTHROPIC_API_KEY. Every AI-assisted command therefore degraded to its
heuristic fallback for a user running Gemini CLI, even though Gemini exposes
the same headless contract. Skills, MCP, rules, workflows and hooks all fan out
across hosts; this was the last surface that did not, and it is the one a user
notices, because the fallback is visibly worse prose.

Three per-backend facts do the work, and each is a difference that would
otherwise be a bug:

* **The system prompt.** Claude takes `--append-system-prompt`. Gemini has no
  equivalent, so the system text has to be folded into the prompt body. Passing
  an unknown flag would make every call fail with a usage error rather than
  degrade — the one outcome worse than having no AI at all.
* **The model id.** `ai.model` defaults to a Claude model name, and handing
  that to `gemini -m` is an error, not a fallback. A backend only receives a
  model id it owns; otherwise the flag is omitted and the CLI picks its own
  default.
* **Order.** Claude is first, and that is behaviour rather than taste: someone
  with both CLIs installed had Claude answering before this table existed, and
  reordering would silently change every result they get.

The direct-API path in `ai.py` stays Anthropic-only. A user of Gemini CLI has
the `gemini` binary by definition, so the CLI route is the one that matters
here; a second HTTP client is a separate, larger change with its own wire
format and error taxonomy.
"""
from __future__ import annotations

from ..errors import BoostError

CLAUDE = "claude"
GEMINI = "gemini"

#: Ordered: the first installed backend wins. See the module docstring on why
#: Claude must stay at the front.
BACKENDS: dict[str, dict] = {
    CLAUDE: {
        "cli": "claude",
        "label": "Claude Code",
        "prompt_flag": "-p",
        "model_flag": "--model",
        # Model ids this backend accepts. `ai.model` is a Claude id today, so
        # this is what keeps it from being handed to another CLI.
        "model_prefixes": ("claude", "sonnet", "opus", "haiku"),
        "output_flags": ("--output-format", "text"),
        "system_flag": "--append-system-prompt",
        "key_env": "ANTHROPIC_API_KEY",
    },
    GEMINI: {
        "cli": "gemini",
        "label": "Gemini CLI",
        "prompt_flag": "-p",
        "model_flag": "-m",
        "model_prefixes": ("gemini",),
        "output_flags": ("-o", "text"),
        # No equivalent flag. `fold_system` puts the text in the prompt.
        "system_flag": "",
        "key_env": "GEMINI_API_KEY",
    },
}


def backends() -> list[str]:
    """Known backend ids, in preference order."""
    return list(BACKENDS)


def spec(name: str) -> dict:
    """The table row for ``name``, or a BoostError naming the alternatives."""
    try:
        return BACKENDS[name]
    except KeyError:
        raise BoostError(
            "unknown AI backend %r" % name,
            hint="use one of: %s" % ", ".join(backends())) from None


def cli(name: str) -> str:
    """The executable to run for ``name``."""
    return str(spec(name)["cli"])


def label(name: str) -> str:
    """Display name for ``name`` (``gemini`` -> "Gemini CLI")."""
    return str(spec(name)["label"])


def key_env(name: str) -> str:
    """The API-key environment variable ``name`` reads."""
    return str(spec(name)["key_env"])


def takes_system_flag(name: str) -> bool:
    """Whether ``name`` accepts a separate system prompt."""
    return bool(spec(name)["system_flag"])


def owns_model(name: str, model: str | None) -> bool:
    """Whether ``model`` is an id ``name`` clearly owns."""
    if not model:
        return False
    return model.lower().startswith(tuple(spec(name)["model_prefixes"]))


def accepts_model(name: str, model: str | None) -> bool:
    """Whether to hand ``model`` to ``name``.

    The rule is "not another vendor's", not "one of mine". An id that no
    backend claims — a custom alias, a pinned snapshot, anything a user passes
    to `--model` — goes through untouched, because refusing it would silently
    drop an override the user asked for. Only an id another backend plainly
    owns is withheld: `ai.model` defaults to a Claude name, and `gemini -m
    claude-sonnet-4-5` is an error rather than a fallback.
    """
    if not model:
        return False
    if owns_model(name, model):
        return True
    return not any(owns_model(other, model)
                   for other in backends() if other != name)


def fold_system(name: str, system: str | None, prompt: str) -> str:
    """The prompt to send, with ``system`` folded in when there is no flag.

    Returned unchanged for a backend that takes a system flag, so Claude's
    request is byte-for-byte what it has always been.
    """
    if not system or takes_system_flag(name):
        return prompt
    return "%s\n\n%s" % (system, prompt)


def argv(name: str, model: str | None, system: str | None) -> list[str]:
    """The command line for ``name``, minus the prompt (which goes on stdin).

    ``model`` is passed unless another backend plainly owns the id (see
    `accepts_model`), and ``system`` only when this backend has a flag for one
    — `fold_system` handles the other case.
    """
    row = spec(name)
    cmd = [str(row["cli"]), str(row["prompt_flag"])]
    if accepts_model(name, model):
        cmd += [str(row["model_flag"]), str(model)]
    cmd += [str(x) for x in row["output_flags"]]
    if system and row["system_flag"]:
        cmd += [str(row["system_flag"]), system]
    return cmd
