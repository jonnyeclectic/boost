# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What a shell offers at TAB, decided in Python rather than in shell.

WHY THIS EXISTS. `boost completions` used to emit a static list of command names
per shell and nothing else, so `boost install <TAB>` — the single most useful
completion a package manager has — re-offered command names in bash, offered
local *filenames* in zsh, and offered nothing in fish. Each failed structurally:
a bash `-W` wordlist is position-independent by definition, zsh guarded on
`(( CURRENT == 2 ))` and fell through to `_files`, and fish registered every
completion under `__fish_use_subcommand`.

The fix is one completer here and three thin shims that call it, so the context
rules are written once, in a language that can test them, instead of three times
in three shell dialects that cannot share a test.

TWO CONSTRAINTS SHAPE EVERYTHING BELOW.

*It runs on a keystroke.* `catalog.all_entries()` measured **423 ms** for 71,655
entries on a real install — four times over any reasonable TAB budget, before
interpreter start. So names come from a flat cache rebuilt from the tap caches:
the same question answered in **1.9 ms**, a 220x difference, which is what makes
argument completion affordable at all.

*It must never fail loudly.* A traceback printed into a live prompt is worse than
no completion, so every public entry point swallows exceptions and returns
nothing. Silence degrades; a stack trace corrupts the line the user is typing.
"""
from __future__ import annotations

import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ..errors import BoostError
from . import catalog, lockfile, paths, registry, store

# cli.COMMANDS rows: (name, group, module, summary). Typed here rather than
# imported so `core` stays the bottom layer.
Registry = Sequence[tuple[str, str, str, str]]

# Commands whose first argument is a catalogue item, an installed item, or a tap.
# Anything absent completes nothing rather than guessing: a wrong candidate list
# actively teaches the wrong thing, which is worse than an empty one.
_CATALOG_ARG = ("install", "info", "cat", "preview", "explain", "why",
                "distill", "adapt", "absorb")
_INSTALLED_ARG = ("uninstall", "reinstall", "pin", "unpin", "edit", "verify")
_TAP_ARG = ("untap",)

def names_file() -> Path:
    """Flat newline-delimited catalogue names, one per line."""
    return paths.cache_dir() / "_names.txt"


def _command_names(commands: Registry) -> list[str]:
    # No hidden-name filter here: `__complete` is dispatched in cli.main()
    # without a COMMANDS row precisely so it stays out of --help, the generated
    # docs, the counts *and* this list. One mechanism, not two.
    return [n for n, _g, _m, _s in commands]


def refresh_names() -> int:
    """Rebuild the names cache from the tap caches. Returns the count written.

    Called after anything that changes the catalogue (tap, untap, update), and
    lazily by :func:`_cached_names` when the file is missing, so a user who
    never runs those still gets completion on their first TAB.
    """
    names = sorted({str(e.get("name", "")) for e in catalog.all_entries()
                    if e.get("name")})
    paths.ensure_dirs()
    names_file().write_text("\n".join(names), encoding="utf-8")
    return len(names)


def _cached_names() -> list[str]:
    path = names_file()
    if not path.exists():
        refresh_names()
    # errors="replace" rather than a raise: a cache corrupted by a half-written
    # file must degrade to whatever is readable, not break the prompt.
    text = path.read_text(encoding="utf-8", errors="replace")
    return [line for line in text.split("\n") if line]


def _installed_names() -> list[str]:
    # store.installed() is the skills lock section only; the commands this
    # feeds (uninstall, pin, verify, ...) govern rules and workflows too, so
    # TAB must offer those names as well.
    names = set(store.installed())
    names.update(lockfile.installed_rules())
    names.update(lockfile.installed_workflows())
    return sorted(names)


def _tap_names() -> list[str]:
    return sorted(t.name for t in registry.list_taps())


# Long flags a command documents, read from its own parser rather than a shared
# list — a global flag list would offer flags the command rejects.
def _flags_for(command: str, commands: Registry) -> list[str]:
    row = next((r for r in commands if r[0] == command), None)
    if row is None:
        return []
    module = __import__("boost_cli.commands." + row[2], fromlist=["x"])
    func = getattr(module, "cmd_" + command.replace("-", "_"), None)
    if func is None:
        return []
    # The parser is built inside the command function, so there is no object to
    # interrogate without running it. The docstring/source is the cheap,
    # dependency-free source of truth for what it accepts.
    import inspect
    try:
        src = inspect.getsource(func)
    except (OSError, TypeError):
        return []
    return sorted(set(re.findall(r'"(--[a-z][a-z0-9-]*)"', src)))


def _source_for(command: str) -> Callable[[], list[str]] | None:
    table: dict[str, Callable[[], list[str]]] = {}
    for name in _CATALOG_ARG:
        table[name] = _cached_names
    for name in _INSTALLED_ARG:
        table[name] = _installed_names
    for name in _TAP_ARG:
        table[name] = _tap_names
    return table.get(command)


def candidates(words: list[str], commands: Registry) -> list[str]:
    """Completions for ``words``, where the last element is the partial word.

    ``words`` is the command line as the shell split it, including ``boost``
    itself — so ``["boost", "install", "code"]`` is a user who has typed
    ``boost install code<TAB>``.

    ``commands`` is ``cli.COMMANDS``, passed in rather than imported: ``core``
    is the bottom layer and must not reach up into ``cli`` (the import-linter
    contract enforces it), so the registry arrives as data.
    """
    try:
        if len(words) < 2:
            return []
        current = words[-1]
        if len(words) == 2:                     # completing the command itself
            return [c for c in _command_names(commands) if c.startswith(current)]
        command = words[1]
        if current.startswith("-"):
            return [f for f in _flags_for(command, commands) if f.startswith(current)]
        source = _source_for(command)
        if source is None:
            return []
        return [c for c in source() if c.startswith(current)]
    except Exception:
        # Deliberately broad. Anything raised here would otherwise land in the
        # middle of the line the user is typing.
        return []


_BASH = """# boost bash completion — delegates to `boost __complete`, so the
# candidate rules live in Python and cannot drift from the CLI.
_boost_complete() {
  local IFS=$'\\n'
  COMPREPLY=( $(boost __complete "${COMP_WORDS[@]:0:$((COMP_CWORD+1))}" 2>/dev/null) )
}
complete -F _boost_complete boost
"""

# The function body is shared between two different trailers (see
# `eval_script` for why): one that self-invokes for zsh's fpath/autoload
# machinery, one that self-registers for a direct `eval` into a running shell.
_ZSH_FUNC = """_boost() {
  local -a reply
  # "${(@)...}" preserves the EMPTY current word. Unquoted, zsh drops it,
  # so `boost install <TAB>` arrives as two words and completes command
  # names instead of skills — the exact bug this rewrite is fixing.
  reply=( ${(f)"$(boost __complete "${(@)words[1,$CURRENT]}" 2>/dev/null)"} )
  compadd -- $reply
}"""

_ZSH = """#compdef boost
# Delegates to `boost __complete` rather than embedding a static list, so
# arguments complete too — the previous version fell through to _files, which
# offered local filenames where a skill name belongs.
%s
_boost "$@"
""" % _ZSH_FUNC

_ZSH_EVAL = """%s
compdef _boost boost
""" % _ZSH_FUNC

_FISH = """# boost fish completion — delegates to `boost __complete`.
# `-f` disables fish's filename fallback, which is what it offered previously
# once the subcommand was typed.
function __boost_complete
  boost __complete (commandline -opc) (commandline -ct) 2>/dev/null
end
complete -c boost -f -a '(__boost_complete)'
"""

_SCRIPTS = {"bash": _BASH, "zsh": _ZSH, "fish": _FISH}


def script(shell: str) -> str:
    """The completion script for ``shell``. Unknown shells get bash's."""
    return _SCRIPTS.get(shell, _BASH)


def eval_script(shell: str) -> str:
    """The variant safe to ``eval`` directly into a *running* shell, e.g. from
    an rc file — what ``boost completions --install`` wires up.

    Bash's script is unconditional registration (``complete -F ... boost``),
    so it behaves identically whether sourced from a file or eval'd inline —
    the same script serves both, so this just returns :func:`script`.

    zsh's shipped script instead *self-invokes* (``_boost "$@"``), which is
    correct only when zsh's own fpath/autoload machinery is what calls it:
    the first real TAB press is what swaps the autoload stub for this body,
    so that trailing call answers *that* press. Eval'd inline at shell
    startup there is no press to answer yet — it would fire once, uselessly,
    against the shell's own startup arguments, and register nothing for
    later. ``compdef _boost boost`` instead registers the function for zsh's
    completion system to call on every subsequent TAB press.
    """
    return _ZSH_EVAL if shell == "zsh" else script(shell)


INSTALL_HINT = {
    "bash": "boost completions --install   (or by hand: boost completions bash >> ~/.bashrc)",
    "zsh": "boost completions --install   (or by hand: boost completions zsh > ~/.zfunc/_boost, "
           "with fpath+=~/.zfunc before compinit)",
    "fish": "boost completions fish > ~/.config/fish/completions/boost.fish",
}

# Shells `--install`/`--uninstall` know how to wire up, and the rc file each
# writes to. Fish needs neither: `~/.config/fish/completions/*.fish` is
# auto-discovered, so `boost completions fish > that path` is already one
# shell command with nothing left to automate.
RC_FILE = {"bash": ".bashrc", "zsh": ".zshrc"}

# Shell-comment markers, not core.rules's HTML-comment ones: an rc file
# executes as shell code, so `<!-- ... -->` there is a syntax error, not a
# comment.
_RC_START = "# >>> boost completions >>>"
_RC_END = "# <<< boost completions <<<"


def _rc_block(shell: str) -> str:
    # Calls back into `boost completions <shell> --eval` at every shell
    # startup, rather than embedding a frozen copy of the script, so an
    # installed hook never drifts from whatever boost version is on PATH.
    return ("%s\ncommand -v boost >/dev/null 2>&1 && "
            "eval \"$(boost completions %s --eval)\"\n%s"
            % (_RC_START, shell, _RC_END))


def _spans(text: str, rc: Path | None = None) -> list[tuple[int, int]]:
    """Half-open (start, end) index pairs of every managed block in ``text``.

    Raises :class:`BoostError` for a start marker with no matching end, because
    an rc file in that state cannot be edited safely by index. Both writers used
    to pair the *first* start with the *next* end found anywhere after it, so an
    orphan start marker sitting above real config made the next edit delete
    every line in between — reported as ``✓ wired boost completions``. Refusing
    costs the user one hand-edit; guessing cost them their shell config.

    An orphan *end* is not an error: nothing pairs to it, it is skipped, and the
    file keeps working. Only an unclosed block is ambiguous.
    """
    spans: list[tuple[int, int]] = []
    i = 0
    while (s := text.find(_RC_START, i)) != -1:
        after = s + len(_RC_START)
        e = text.find(_RC_END, after)
        nxt = text.find(_RC_START, after)
        # A block must close before the next one opens. Testing only `e == -1`
        # is the original bug in a new place: an orphan start sitting above a
        # real block finds *that* block's end and swallows every line between.
        if e == -1 or (nxt != -1 and nxt < e):
            where = " in %s" % paths.tilde(rc) if rc is not None else ""
            raise BoostError(
                "boost completions block%s starts but never ends" % where,
                hint="%s has no matching %s — delete the stray start line (or "
                     "close the block), then re-run"
                     % (_RC_START, _RC_END))
        e += len(_RC_END)
        spans.append((s, e))
        i = e
    return spans


def _outside(text: str, spans: list[tuple[int, int]]) -> list[str]:
    """The stretches of ``text`` that sit outside every managed block."""
    parts, prev = [], 0
    for s, e in spans:
        parts.append(text[prev:s])
        prev = e
    parts.append(text[prev:])
    return parts


def _merge_rc(text: str, block: str, rc: Path | None = None) -> str:
    """Idempotently set ``block`` in ``text``: replace a prior boost block in
    place, or append one after a single blank line. Mirrors
    :func:`core.rules.merge_block`'s shape with rc-file-safe markers.

    Collapses to exactly one block. Replacing only the first left a second one
    live, so `--install` was idempotent in content but not in count.
    """
    spans = _spans(text, rc)
    if not spans:
        base = text.rstrip("\n")
        return (base + "\n\n" + block + "\n") if base else block + "\n"
    parts = _outside(text, spans)
    return (parts[0] + block + "".join(parts[1:])).rstrip("\n") + "\n"


def _strip_rc(text: str, rc: Path | None = None) -> str:
    """Inverse of :func:`_merge_rc`: remove every managed block, if present.

    Every, not the first: `--uninstall` on a doubled block used to report
    "removed" while the shell went on sourcing the survivor.
    """
    spans = _spans(text, rc)
    if not spans:
        return text
    parts = [p.strip("\n") for p in _outside(text, spans)]
    parts = [p for p in parts if p]
    return "\n\n".join(parts) + "\n" if parts else ""


def _rc_path(shell: str) -> Path:
    if shell not in RC_FILE:
        raise BoostError(
            "no one-shot install for %s yet" % shell,
            hint="fish needs none: boost completions fish > "
                 "~/.config/fish/completions/boost.fish"
            if shell == "fish" else "supported: %s" % ", ".join(RC_FILE))
    return paths.expand("~/" + RC_FILE[shell])


@dataclass(frozen=True)
class RcPlan:
    """What an install/uninstall would do to one rc file, before it does it.

    ``--dry-run`` prints this; ``install``/``uninstall`` apply it. One code path
    computes both, so the preview cannot disagree with the write.
    """
    path: Path
    action: str        # create | add | replace | remove | none
    before: str
    after: str

    @property
    def changes(self) -> bool:
        """True when applying this would alter the file."""
        return self.before != self.after


def _read_rc(shell: str) -> tuple[Path, str, bool]:
    rc = _rc_path(shell)
    exists = rc.exists()
    return rc, (rc.read_text(encoding="utf-8") if exists else ""), exists


def plan_install(shell: str) -> RcPlan:
    """Describe wiring ``shell``'s rc file, writing nothing.

    Raises :class:`BoostError` for a shell with no rc-file install path, and for
    an rc file holding an unclosed block — so a dry run answers the dangerous
    question too, rather than only the safe one.
    """
    rc, text, exists = _read_rc(shell)
    after = _merge_rc(text, _rc_block(shell), rc)
    if not exists:
        action = "create"
    elif after == text:
        action = "none"
    elif _spans(text, rc):
        action = "replace"
    else:
        action = "add"
    return RcPlan(path=rc, action=action, before=text, after=after)


def plan_uninstall(shell: str) -> RcPlan:
    """Describe removing what :func:`install` wired up, writing nothing."""
    rc, text, _ = _read_rc(shell)
    after = _strip_rc(text, rc)
    return RcPlan(path=rc, action=("remove" if after != text else "none"),
                  before=text, after=after)


def apply(plan: RcPlan) -> Path:
    """Write ``plan``'s result. A no-op when it changes nothing, so an rc file
    keeps its mtime (and its place in the user's backups) on a repeat run."""
    if plan.changes:
        plan.path.write_text(plan.after, encoding="utf-8")
    return plan.path


def install(shell: str) -> Path:
    """Idempotently wire ``shell``'s rc file to eval boost's completions on
    every startup. Returns the rc file path. Raises :class:`BoostError` for
    a shell with no rc-file install path (currently anything but bash/zsh)."""
    return apply(plan_install(shell))


def uninstall(shell: str) -> Path:
    """Remove what :func:`install` wired up. A no-op if never installed."""
    return apply(plan_uninstall(shell))


def detect_shell() -> str:
    """The caller's shell from ``$SHELL``, basename only (e.g. "zsh")."""
    return Path(os.environ.get("SHELL", "")).name
