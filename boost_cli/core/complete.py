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

import argparse
import contextlib
import importlib
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ..errors import BoostError
from . import catalog, config, lockfile, output, paths, policy, registry, store, util

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


#: Whether this process already said it could not save the names cache.
_WARNED_UNSAVED = False


def refresh_names() -> int:
    """Rebuild the names cache from the tap caches. Returns the name count.

    Called after anything that changes the catalogue (tap, untap, update,
    heal), and lazily by :func:`_cached_names` when the file is missing or
    unreadable, so a user who never runs those still gets completion on their
    first TAB.
    """
    global _WARNED_UNSAVED
    names = sorted({str(e.get("name", "")) for e in catalog.all_entries()
                    if e.get("name")})
    text = "\n".join(names)
    path = names_file()
    # Replaced, not rewritten in place, for the reason catalog.rebuild_tap is:
    # a copy one `sudo boost` run left read-only made heal, update, untap and
    # a repeat tap exit 70 here while doctor said healthy. A replace needs the
    # directory writable, so a read-only dir holding a writable file falls
    # back to the in-place write. If neither lands, the completion list is a
    # convenience, and failing to keep one never fails the command asking.
    try:
        # Only the one directory this file lives in: paths.ensure_dirs()
        # here made a single TAB in a HOME boost never ran create the whole
        # ~/.boost tree and ~/.agents/skills, the store Gemini CLI discovers.
        path.parent.mkdir(parents=True, exist_ok=True)
        util.atomic_write_text(path, text)
    except OSError:
        try:
            path.write_text(text, encoding="utf-8")
        except OSError as e:
            # Once per process, like rebuild_tap: the fix is the same each time.
            # A cache dir that could not be created is fixed in its parent.
            if not _WARNED_UNSAVED:
                _WARNED_UNSAVED = True
                where = paths.nearest_existing(path.parent)
                output.warn("could not save the completion list (%s) — tab "
                            "completion may offer stale names; make %s "
                            "writable" % (e.strerror or e, paths.tilde(where)),
                            stream=sys.stderr, wrap=True)
    return len(names)


def _cached_names() -> list[str]:
    path = names_file()
    # errors="replace" rather than a raise: a cache corrupted by a half-written
    # file must degrade to whatever is readable, not break the prompt.
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        if not path.parent.is_dir():
            # No cache dir means nothing was ever tapped here, so there is
            # nothing to offer — and a keystroke must not be what creates
            # boost's state on a machine where boost never ran.
            return []
        # Missing, or unreadable: the root-owned 0600 copy a `sudo boost` run
        # leaves emptied TAB silently while doctor said healthy. Rebuilding
        # replaces it whenever the dir is writable; when it is not, TAB offers
        # nothing, as it would for a missing file.
        refresh_names()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
    return [line for line in text.split("\n") if line]


def _installed_names() -> list[str]:
    # store.installed() is the skills lock section only; the commands this
    # feeds (uninstall, pin, verify, ...) govern rules and workflows too, so
    # TAB must offer those names as well.
    #
    # Every row, including a `--local` one for another checkout and one whose
    # checkout has been deleted (`scopes.stranded`). Filtering by "is it this
    # repo's" would be wrong for both: `uninstall`, `info` and `verify` take
    # either from anywhere, and `boost uninstall <name>` is the one remedy
    # doctor names for a stranded row, so hiding it there hides the fix.
    names = set(store.installed())
    names.update(lockfile.installed_rules())
    names.update(lockfile.installed_workflows())
    return sorted(names)


def _tap_names() -> list[str]:
    return sorted(t.name for t in registry.list_taps())


class _Captured(BaseException):
    """Carries a command's parser out of its ``cmd_*`` function.

    A ``BaseException`` rather than an ``Exception`` so a command body's own
    ``except Exception`` cannot swallow it on the way out.
    """

    def __init__(self, parser: argparse.ArgumentParser) -> None:
        super().__init__()
        self.parser = parser


_PARSE_METHODS = ("parse_args", "parse_known_args", "parse_intermixed_args",
                  "parse_known_intermixed_args")


def _capture(_self: argparse.ArgumentParser, *_a: object, **_k: object):
    raise _Captured(_self)


def _parser_for(command: str,
                commands: Registry) -> argparse.ArgumentParser | None:
    """The parser ``command`` really parses with, or None if unavailable.

    Every command builds its parser inside its ``cmd_*`` function, so there is
    no object to ask without running it. This runs it with argparse's parse
    methods swapped for a raise that hands back the parser — the very object
    that decides what the command accepts, shared helpers like
    :func:`cliparse.add_scope_flags` included. It replaced a regex over the
    function's source, which never saw a helper's flags (`install --s<TAB>`
    offered nothing, although `--scope` is valid) and picked up `--x` strings
    from git argv lists the parser rejects (`onboard --fill`).

    Nothing runs past parser construction: every ``cmd_*`` parses first, and
    ``tests/unit/test_complete.py`` pins, per command, that building the
    parser this way writes nothing into ``$HOME``.
    """
    row = next((r for r in commands if r[0] == command), None)
    if row is None:
        return None
    module = importlib.import_module("boost_cli.commands." + row[2])
    func = getattr(module, "cmd_" + command.replace("-", "_"), None)
    if func is None:
        return None
    saved = {n: getattr(argparse.ArgumentParser, n) for n in _PARSE_METHODS}
    try:
        for name in _PARSE_METHODS:
            setattr(argparse.ArgumentParser, name, _capture)
        with open(os.devnull, "w", encoding="utf-8") as sink, \
                contextlib.redirect_stdout(sink), \
                contextlib.redirect_stderr(sink):
            func([])
    except _Captured as c:
        return c.parser
    except (Exception, SystemExit):
        return None
    finally:
        for name, method in saved.items():
            setattr(argparse.ArgumentParser, name, method)
    return None


def _long_flags(parser: argparse.ArgumentParser) -> list[str]:
    # Long spellings only: `-k` and friends mean different things across
    # commands, and the long form is what docs and muscle memory use. A
    # `help=SUPPRESS` option is accepted but deliberately undocumented (a
    # compatibility alias), so TAB keeps it as quiet as --help does.
    return sorted({o for a in parser._actions for o in a.option_strings
                   if o.startswith("--") and a.help != argparse.SUPPRESS})


def _flags_for(command: str, commands: Registry) -> list[str]:
    """The long options ``command``'s top-level parser accepts."""
    parser = _parser_for(command, commands)
    return _long_flags(parser) if parser is not None else []


def _subparsers(parser: argparse.ArgumentParser
                ) -> argparse._SubParsersAction | None:
    return next((a for a in parser._actions
                 if isinstance(a, argparse._SubParsersAction)), None)


def _values_taken(action: argparse.Action) -> int:
    """How many following words an option consumes: 0 for a switch, -1 for
    "every word up to the next flag" (``nargs='*'``/``'+'``)."""
    nargs = action.nargs
    if isinstance(nargs, int):                  # 0 for store_true and kin
        return nargs
    if nargs in ("*", "+", argparse.REMAINDER):
        return -1
    return 1                                    # None or "?"


@dataclass
class _Walk:
    """Where a command line stands once its typed words are read."""
    parser: argparse.ArgumentParser
    positionals: list[str]                      # in the active (sub)parser
    pending: argparse.Action | None             # option awaiting a value


def _walk(parser: argparse.ArgumentParser, words: Sequence[str]) -> _Walk:
    """Read ``words`` (the command's own, before the one being typed) the way
    argparse would, as far as completion needs: options and their values are
    not positionals, and a subcommand word switches to its own parser.

    Counting flags as positionals put every later position off by one per
    flag: `completions --eval <TAB>` offered nothing and `install --scope
    <TAB>` offered skill names where only user/project is valid.
    """
    state = _Walk(parser, [], None)
    owed = 0                  # values still owed to state.pending; -1 = open
    only_positionals = False
    for word in words:
        if not only_positionals and word.startswith("-") and word != "-":
            if word == "--":
                only_positionals, state.pending, owed = True, None, 0
                continue
            flag, eq, _value = word.partition("=")
            action = state.parser._option_string_actions.get(flag)
            owed = _values_taken(action) if action is not None and not eq else 0
            state.pending = action if owed else None
            continue
        if owed:
            if owed > 0:
                owed -= 1
            if not owed:
                state.pending = None
            continue
        sub = _subparsers(state.parser)
        if sub is not None and word in sub.choices and \
                len(state.positionals) == _positional_index(state.parser, sub):
            state = _Walk(sub.choices[word], [], None)
            continue
        state.positionals.append(word)
    return state


def _positional_actions(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    return [a for a in parser._actions if not a.option_strings]


def _positional_index(parser: argparse.ArgumentParser,
                      target: argparse.Action) -> int:
    return _positional_actions(parser).index(target)


def _positional_at(parser: argparse.ArgumentParser,
                   position: int) -> argparse.Action | None:
    """The positional action that takes the word at ``position``, letting a
    variadic one (``nargs='*'``/``'+'``) absorb every word after it."""
    actions = _positional_actions(parser)
    for i, action in enumerate(actions):
        if i == position:
            return action
        if _values_taken(action) == -1:
            return action
    return None


def _choices(action: argparse.Action | None) -> list[str] | None:
    if action is None or not action.choices:
        return None
    return [str(c) for c in action.choices]


def _dotted_keys(node: object, prefix: str = "") -> list[str]:
    """Every dotted leaf key a nested defaults dict declares, e.g.
    ``"ai.enabled"`` out of ``config.DEFAULTS["ai"]["enabled"]``. A non-dict
    leaf (including an empty dict) ends the walk, so ``"serve.port"`` is a
    key but ``"serve"`` alone is not — matching what `config.set_value`
    actually accepts."""
    if isinstance(node, dict) and node:
        keys: list[str] = []
        for k, v in node.items():
            keys.extend(_dotted_keys(v, "%s.%s" % (prefix, k) if prefix else k))
        return keys
    return [prefix] if prefix else []


def _config_keys() -> list[str]:
    return sorted(_dotted_keys(config.DEFAULTS))


def _policy_keys() -> list[str]:
    return sorted(policy.DEFAULTS)


# A positional whose candidates come from `policy.DEFAULTS` / `config.DEFAULTS`
# rather than from `choices=` in the parser — `policy set KEY` and
# `config {get,set,unset} KEY` validate the key against that dict in the
# command body, not through argparse, so the parser has no choices to read.
# Keyed by command; the value names which already-typed action word (position
# 0) unlocks it, and the source itself. Only position 1 (the word right after
# the action) is covered — a value in position 2 is never a static choice.
_ACTION_KEY_SOURCE: dict[str, tuple[frozenset[str], Callable[[], list[str]]]] = {
    "policy": (frozenset({"set", "unset"}), _policy_keys),
    "config": (frozenset({"get", "set", "unset"}), _config_keys),
}

# What `cli._route` answers before any command is named, besides the global
# flags `cli.main` peels (passed in as `global_flags`): `boost --help` and
# `boost --version`. Literal here because core cannot import cli.
_TOP_LEVEL_OPTIONS = frozenset({"--help", "-h", "--version", "-V"})


def _source_for(command: str, position: int, prior: tuple[str, ...],
                 parser: argparse.ArgumentParser | None
                 ) -> Callable[[], list[str]] | None:
    """What TAB offers for the positional at ``position`` (0-indexed among a
    command's own arguments) after ``prior`` — the positional words already
    typed for this command, oldest first.
    """
    table: dict[str, Callable[[], list[str]]] = {}
    for name in _CATALOG_ARG:
        table[name] = _cached_names
    for name in _INSTALLED_ARG:
        table[name] = _installed_names
    for name in _TAP_ARG:
        table[name] = _tap_names
    if command in table:
        # Position-independent on purpose: `install`/`uninstall`/`untap` take
        # a variadic list of names, so word 2 and word 5 offer the same thing.
        return table[command]

    if position == 1 and command in _ACTION_KEY_SOURCE:
        actions, source = _ACTION_KEY_SOURCE[command]
        if prior and prior[0] in actions:
            return source
        return None

    if parser is None:
        return None
    values = _choices(_positional_at(parser, position))
    if values:
        return lambda: values
    return None


def candidates(words: list[str], commands: Registry,
               global_flags: frozenset[str] = frozenset()) -> list[str]:
    """Completions for ``words``, where the last element is the partial word.

    ``words`` is the command line as the shell split it, including ``boost``
    itself — so ``["boost", "install", "code"]`` is a user who has typed
    ``boost install code<TAB>``.

    ``commands`` is ``cli.COMMANDS``, passed in rather than imported: ``core``
    is the bottom layer and must not reach up into ``cli`` (the import-linter
    contract enforces it), so the registry arrives as data. ``global_flags``
    is ``cli._GLOBAL_FLAGS`` for the same reason: ``cli.main`` peels those off
    before the command name, so ``boost --debug install <TAB>`` is a real line
    and completion has to peel them the same way.
    """
    try:
        if len(words) < 2:
            return []
        # Only leading flags, and never the word being typed: `--debug<TAB>`
        # is a partial word, not a flag already given.
        lead = 1
        while lead < len(words) - 1 and words[lead] in global_flags:
            lead += 1
        words = [words[0], *words[lead:]]
        current = words[-1]
        if len(words) == 2:                     # completing the command itself
            if current.startswith("-"):
                # `boost --deb<TAB>`: what cli.main accepts before a command.
                return sorted(f for f in global_flags | _TOP_LEVEL_OPTIONS
                              if f.startswith(current))
            return [c for c in _command_names(commands) if c.startswith(current)]
        command = words[1]
        if command in ("help", "-h", "--help"):
            # The help pseudo-command is not a COMMANDS row, so no source
            # knows it, yet the top-level usage line advertises it — and
            # `cli._route` sends `--help <cmd>` / `-h <cmd>` the same way.
            if len(words) != 3:
                return []
            return [c for c in _command_names(commands) if c.startswith(current)]
        parser = _parser_for(command, commands)
        if parser is None:
            walk = None
            prior = tuple(w for w in words[2:-1] if not w.startswith("-"))
        else:
            walk = _walk(parser, words[2:-1])
            prior = tuple(walk.positionals)
        if current.startswith("-"):
            if walk is None:
                return []
            return [f for f in _long_flags(walk.parser) if f.startswith(current)]
        if walk is not None and walk.pending is not None:
            # The word is an option's value: its choices, or nothing — never
            # the command's positional source (skill names after `--scope`).
            return [c for c in _choices(walk.pending) or []
                    if c.startswith(current)]
        source = _source_for(command, len(prior), prior,
                             walk.parser if walk is not None else None)
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
  # The slice is copied into an array *before* IFS changes: on bash 3.2
  # (macOS's /bin/bash) a quoted "${COMP_WORDS[@]:0:N}" under IFS=$'\\n'
  # expands to ONE word, so `boost __complete` got 'boost install br' as a
  # single argument and every TAB completed nothing.
  local -a words=( "${COMP_WORDS[@]:0:$((COMP_CWORD+1))}" )
  local IFS=$'\\n'
  COMPREPLY=( $(boost __complete "${words[@]}" 2>/dev/null) )
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

# `compdef` exists only once compinit has run, and stock macOS zsh never runs
# it: without this guard every shell start printed `command not found:
# compdef` and TAB stayed dead. Loading the completion system is what
# `compdef` needs, so load it rather than skip registering.
_ZSH_EVAL = """%s
(( $+functions[compdef] )) || { autoload -Uz compinit && compinit -i; }
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


# Fish auto-loads this path, but only once the directory exists, and fish
# creates it on first launch — so a fresh HOME has none, and the redirect
# alone fails with "No such file or directory".
_FISH_FILE = "~/.config/fish/completions/boost.fish"
_FISH_WRITE = "boost completions fish > " + _FISH_FILE

INSTALL_HINT = {
    "bash": "boost completions --install   (or by hand: boost completions bash >> ~/.bashrc)",
    "zsh": "boost completions --install   (or by hand: boost completions zsh > ~/.zfunc/_boost, "
           "with fpath+=~/.zfunc before compinit)",
    "fish": "mkdir -p ~/.config/fish/completions && " + _FISH_WRITE,
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
            # Backtick spans, so the hint wraps around each command rather
            # than through it: split at the `>`, the first line is a redirect
            # with no target. One hint answers --install and --uninstall,
            # which both land here.
            hint="fish needs none — install: `%s`, remove: `rm %s`"
                 % (INSTALL_HINT["fish"], _FISH_FILE)
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
    keeps its mtime (and its place in the user's backups) on a repeat run.

    ``newline="\\n"`` because the reader here is **bash**, which does not
    fold. The damage is worse than a stray character: measured on bash 3.2
    and zsh, a CRLF rc file does not merely mangle tokens, it stops parsing
    — ``fi\\r`` gives ``syntax error: unexpected end of file``, so nothing
    after the user's first ``if`` or ``for`` runs at all.

    This rewrites the user's **whole** ``~/.bashrc`` or ``~/.zshrc``, not
    only the lines boost added, so an unpinned write on Windows re-endings a
    file boost does not own — ``tests (windows-latest, 3.14)`` measured
    ``b'export A=1\\r\\neval "$(boost _complete)"\\r\\n'`` from a one-line
    rc. Pinning cuts the same way: it normalizes the whole file to LF,
    including lines boost never wrote, which is what bash wants and is still
    a change beyond boost's own three. The one shell that might forgive CRLF
    is MSYS2/Cygwin bash with ``shopt igncr``, which is off by default.

    Idempotence is unaffected either way: :func:`_read_rc` reads through
    universal newlines, so the next run compares LF to LF and reports no
    change — which is also why boost would never repair a file it had
    mangled, and would keep saying "already wired" over it.
    """
    if plan.changes:
        plan.path.write_text(plan.after, encoding="utf-8", newline="\n")
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
