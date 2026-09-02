# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Read a command-line string at the type its key already declares.

``boost config set`` and ``boost policy set`` both took *any* string for *any*
known key and stored whatever ``json.loads`` made of it. The damage landed
later and elsewhere: ``policy set max_skills abc`` exited 0, and the next
``install`` died with ``ValueError: invalid literal for int()`` and a crash
report. The nastiest shape was not a crash at all — ``policy set pin_only no``
stored the *string* ``"no"``, which is truthy, so boost reported "pin-only mode
is on" and froze every install for a user who had just turned it off.

Both modules already ship a ``DEFAULTS`` table, and a default value names its
own type. This module turns that table into a parser: ``coerce("pin_only",
"no", BOOL)`` is ``False``, and ``coerce("max_skills", "abc", INT_OR_NONE)``
raises :class:`ValueTypeError` at the setter instead of exit 70 at the next
install.

The one deliberate asymmetry is :data:`LIST`, which never raises. A list key's
documented surface is a comma list (``blocked_skills a,b``), so anything that
is not already a JSON array is split on commas rather than refused — which is
also what turns ``blocked_skills 42`` from a stored ``42`` (and a later
``TypeError: argument of type 'int' is not iterable``) into ``["42"]``.
"""
from __future__ import annotations

import json
from typing import Any

#: Spec names. A spec is a plain string so the tables that use it stay readable
#: and JSON-dumpable, and so it can be printed straight into a hint the user
#: retypes (``boost policy set pin_only <bool>``). An unrecognised spec is the
#: lenient :data:`ANY`, never an error — see :func:`describe` for why.
BOOL = "bool"
INT = "int"
INT_OR_NONE = "int-or-null"
LIST = "list"
STR = "str"
DICT = "dict"
ANY = "any"

#: Strings accepted for a true boolean, lower-cased and stripped.
TRUE_WORDS = frozenset({"true", "yes", "on", "1"})
#: Strings accepted for a false boolean. ``no``/``off``/``0`` are the three
#: that used to store a truthy string and invert the setting.
FALSE_WORDS = frozenset({"false", "no", "off", "0"})
#: Strings accepted as "no value" for :data:`INT_OR_NONE`.
NONE_WORDS = frozenset({"", "null", "none"})

_DESCRIPTIONS = {
    BOOL: "a boolean (true/false, yes/no, on/off, 1/0)",
    INT: "a whole number",
    INT_OR_NONE: "a whole number, or null for no limit",
    LIST: "a comma-separated list, or a JSON array",
    STR: "a string",
    DICT: "a JSON object",
    ANY: "any value",
}


class ValueTypeError(ValueError):
    """A raw string that cannot be read at its key's declared type.

    Carries the parts a caller needs to word its own error: which ``key`` was
    being set, the ``raw`` value that failed, and an ``expected`` phrase naming
    the type in the words a user can retype. ``raw`` is a string when the value
    was typed and can be any JSON scalar when it was read back off disk.
    """

    def __init__(self, key: str, raw: Any, spec: str):
        self.key = key
        self.raw = raw
        self.spec = spec
        self.expected = describe(spec)
        super().__init__("%s expects %s, got %r" % (key, self.expected, raw))


def describe(spec: str) -> str:
    """The human phrase for a spec, e.g. ``"a whole number"``.

    An unknown spec describes as :data:`ANY` rather than raising: a wrong hint
    must never be the thing that turns a working setter into a crash.
    """
    return _DESCRIPTIONS.get(spec, _DESCRIPTIONS[ANY])


def spec_for(default: Any) -> str:
    """Derive a spec from a key's default value.

    ``bool`` is tested before ``int`` on purpose — ``bool`` is a subclass of
    ``int``, so the natural order would type every boolean key as a number and
    happily store ``pin_only = 2``. ``None`` carries no type and yields
    :data:`ANY`; a key defaulting to ``None`` that *does* have a type (policy's
    ``max_skills``) declares it explicitly in its own table.
    """
    if isinstance(default, bool):
        return BOOL
    if isinstance(default, int):
        return INT
    if isinstance(default, list):
        return LIST
    if isinstance(default, dict):
        return DICT
    if isinstance(default, str):
        return STR
    return ANY


def _as_bool(key: str, raw: str) -> bool:
    word = raw.strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    raise ValueTypeError(key, raw, BOOL)


def _as_int(key: str, raw: str, spec: str) -> int:
    try:
        return int(raw.strip())
    except (TypeError, ValueError) as e:
        raise ValueTypeError(key, raw, spec) from e


def _as_list(raw: str) -> list:
    """A JSON array as written, else the comma split. Never raises."""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = None
    if isinstance(parsed, list):
        return parsed
    return [s.strip() for s in raw.split(",") if s.strip()]


def _as_dict(key: str, raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueTypeError(key, raw, DICT) from e
    if not isinstance(parsed, dict):
        raise ValueTypeError(key, raw, DICT)
    return parsed


def _as_any(raw: str) -> Any:
    """The old lenient behaviour: JSON when it parses, the string otherwise.

    Kept for keys no ``DEFAULTS`` table describes — ``boost config set`` accepts
    keys boost has never heard of, and inventing a type for those would refuse
    values that work today.
    """
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def coerce(key: str, raw: str, spec: str) -> Any:
    """Read ``raw`` at ``spec``, or raise :class:`ValueTypeError`.

    ``raw`` is what argv handed over, so it is always a string here; the
    already-typed sibling for values read back off disk is :func:`adapt`.
    """
    if spec == BOOL:
        return _as_bool(key, raw)
    if spec == INT:
        return _as_int(key, raw, INT)
    if spec == INT_OR_NONE:
        return None if raw.strip().lower() in NONE_WORDS else _as_int(key, raw, INT_OR_NONE)
    if spec == LIST:
        return _as_list(raw)
    if spec == STR:
        return raw
    if spec == DICT:
        return _as_dict(key, raw)
    return _as_any(raw)


def matches(value: Any, spec: str) -> bool:
    """True when an already-typed ``value`` is acceptable for ``spec``.

    Deliberately stricter than :func:`coerce`: this judges a value that is
    already sitting in a JSON file, where ``"no"`` is a string and not a
    keystroke. ``bool`` is rejected for the numeric specs for the same reason
    :func:`spec_for` tests it first.
    """
    if spec == BOOL:
        return isinstance(value, bool)
    if spec == INT:
        return isinstance(value, int) and not isinstance(value, bool)
    if spec == INT_OR_NONE:
        return value is None or (isinstance(value, int) and not isinstance(value, bool))
    if spec == LIST:
        return isinstance(value, list)
    if spec == STR:
        return isinstance(value, str)
    if spec == DICT:
        return isinstance(value, dict)
    return True


def adapt(key: str, value: Any, spec: str) -> Any:
    """Return ``value`` at ``spec``, or raise :class:`ValueTypeError`.

    The entry point for values read back from a file rather than typed: a
    value that already matches is returned untouched, and a *string* gets one
    chance to be re-read through :func:`coerce`, which is what rescues a
    ``"pin_only": "no"`` written by an older boost or by hand. Anything else
    (a list where a number belongs) is refused — guessing there would be
    inventing data, not reading it.
    """
    if matches(value, spec):
        return value
    if isinstance(value, str):
        return coerce(key, value, spec)
    raise ValueTypeError(key, value, spec)
