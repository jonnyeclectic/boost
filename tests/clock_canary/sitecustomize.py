# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Move this interpreter's calendar forward: the clock canary's shim.

``scripts/clock_canary.py`` puts this directory first on ``PYTHONPATH`` and
sets ``BOOST_CLOCK_CANARY_DAYS``. ``site`` imports the first ``sitecustomize``
on ``sys.path`` while the interpreter starts, before any test or boost module,
so every later ``from datetime import datetime`` binds the stand-in below, in
pytest, in its xdist workers and in each Python subprocess that inherits
``PYTHONPATH`` (one started with ``PYTHONPATH`` replaced runs on the real
clock; ``scripts/clock_canary.py`` says which tests do that).
Nothing else puts this directory on the path: a plain run never loads it, and
with the variable unset it changes nothing even when it is loaded.

**What moves:** ``datetime.datetime.now/today/utcnow`` and
``datetime.date.today``.

**What does not, by measurement:** ``time.time()``, ``time.time_ns()`` and the
no-argument ``time.gmtime/localtime/strftime/ctime``. File modification times
and git's commit dates come from the kernel and could never move, so a moved
``time.time()`` puts every file a test has just written 14 days in the past for
each ``time.time() - st_mtime`` boost computes (``util.py``, ``registry.py``,
``shards.py``, ``safety.py``). Measured over the whole suite at +14 days
(2026-11-23, macOS, Python 3.15, one process), against a plain run: moving the
calendar alone failed 3 more tests, and moving ``time.time()`` as well failed
24. One in each was this file shadowing Homebrew's ``sitecustomize`` (chained
since, below) and one in each compared against git's commit dates. Beyond
those, the calendar-only run failed one test that compared two clocks (fixed
in that test), and the ``time.time()`` run failed 22, all of the kind above --
a lock just taken read as stale, a refresh marker just stamped read as 14 days
old -- and not one a fixed date going stale. (Those 22 were judged from their
assertion messages; that run was not repeated after the chaining fix.) Moving
it would bury a bomb under artifacts and find none, so it stays put, and a
test that reads the calendar through ``time.time()`` is outside what this can
see.

**Only the classes are stand-ins.** Their metaclass makes every constructor
and classmethod return a real ``date``/``datetime``, so ``repr`` and
``pickle`` behave as they do without the shim, and ``isinstance`` accepts
real instances. A subclass a test builds on top (as ``test_util.py``'s
``_FrozenDatetime`` does) is an ordinary subclass again. **The limit is exact
class identity:** ``type(x) is datetime.datetime`` is False for every
instance, and so is any lookup keyed on the class object taken after startup
-- a ``functools.singledispatch`` or PyYAML representer registered on
``datetime.datetime``, sqlite3's default adapters. Nothing in the suite does
that today (the canary ran clean at +14, +30 and +45 days); a test that fails
here for this shim's reason, not the calendar's, belongs in
``scripts/clock_canary.py``'s ``ARTIFACTS`` saying so.

**The sitecustomize this one shadows still runs.** ``site`` imports only the
first module of that name, and an interpreter may ship its own: Homebrew's
rewrites ``sys.base_prefix`` to its stable ``opt/`` path, and shadowing it
changed what ``test_selfupdate_python.py`` saw on the moved and the unmoved
clock alike. :func:`chain` finds the next one on ``sys.path`` and runs it.
"""
from __future__ import annotations

import copyreg
import datetime as _dt
import importlib.machinery
import importlib.util
import os
import sys

ENV = "BOOST_CLOCK_CANARY_DAYS"


def install(days: float) -> None:
    """Replace ``datetime.date`` and ``datetime.datetime`` with stand-ins ``days`` ahead.

    Called once, at interpreter start, and never undone: the shim lives for
    the whole process it was started in.
    """
    real_date, real_datetime = _dt.date, _dt.datetime
    delta = _dt.timedelta(days=days)

    def moved_utc():
        return real_datetime.now(_dt.UTC) + delta

    class _StandIn(type):
        """The stand-ins' metaclass. Only a class holding ``_real`` itself is special."""

        def __call__(cls, *args, **kwargs):
            real = cls.__dict__.get("_real")
            return real(*args, **kwargs) if real else super().__call__(*args, **kwargs)

        def __instancecheck__(cls, obj):
            real = cls.__dict__.get("_real")
            return isinstance(obj, real) if real else super().__instancecheck__(obj)

        def __subclasscheck__(cls, sub):
            real = cls.__dict__.get("_real")
            return issubclass(sub, real) if real else super().__subclasscheck__(sub)

    class date(real_date, metaclass=_StandIn):
        _real = real_date

        @classmethod
        def today(cls):
            return moved_utc().astimezone().date()

    class datetime(real_datetime, metaclass=_StandIn):
        _real = real_datetime

        @classmethod
        def now(cls, tz=None):
            # Through UTC, so an aware ``now`` carries the offset in force at
            # the moved instant and a naive one the local wall time then.
            moved = moved_utc()
            return moved.astimezone(tz) if tz is not None else (
                moved.astimezone().replace(tzinfo=None))

        @classmethod
        def today(cls):
            return cls.now()

        @classmethod
        def utcnow(cls):
            return moved_utc().replace(tzinfo=None)

    for real, stand_in in ((real_date, date), (real_datetime, datetime)):
        # pickle finds a class by module + qualname and refuses a real
        # instance whose name now leads to the stand-in, so reduce real
        # instances to the stand-in, which rebuilds a real one.
        stand_in.__module__, stand_in.__qualname__ = "datetime", stand_in.__name__
        copyreg.dispatch_table[real] = (
            lambda obj, stand_in=stand_in: (stand_in, obj.__reduce__()[1]))
    _dt.date, _dt.datetime = date, datetime


def chain() -> None:
    """Run the ``sitecustomize`` that this one hides, if there is one.

    Run whether or not the clock moves: the canary's re-runs on today's clock
    keep this directory on the path for its pytest plugin, and must see the
    interpreter exactly as a plain run does.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    rest = [p for p in sys.path if os.path.abspath(p or os.curdir) != here]
    spec = importlib.machinery.PathFinder.find_spec("sitecustomize", rest)
    if spec is not None and spec.loader is not None:
        spec.loader.exec_module(importlib.util.module_from_spec(spec))


_days = os.environ.get(ENV)
if _days:
    install(float(_days))
chain()
