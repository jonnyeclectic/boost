# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""pytest plugin: tell scripts/clock_canary.py which tests failed, by node id.

The canary loads it with ``-p clock_canary_report``, which resolves only
because that run puts this directory first on ``PYTHONPATH``; nothing else
loads it, and without ``BOOST_CLOCK_CANARY_REPORT`` set it writes nothing.

Each line is ``<outcome>\\t<node id>``: every failed setup, call or teardown
(an ERROR row is as red as a FAILED one), every module that failed to collect,
and the outcome of the one test named by ``BOOST_CLOCK_CANARY_SENTINEL`` --
the suite's own check that the moved clock reached the process running it,
which reads ``skipped`` when the canary's variables did not.

Node ids come from pytest's reports rather than from its ``FAILED ...``
summary because the canary re-runs each failure by id, and a parametrised id
can hold spaces and ``" - "`` (``test_the_pin_is_there[util.py:fd, "w",
encoding=]`` does), which is where a summary line splits id from message.
Under xdist the controller receives every worker's report and each worker
loads this plugin too, so a line can be written twice; the reader takes a set.
"""
from __future__ import annotations

import os

ENV = "BOOST_CLOCK_CANARY_REPORT"
SENTINEL_ENV = "BOOST_CLOCK_CANARY_SENTINEL"


def _record(outcome: str, nodeid: str) -> None:
    path = os.environ.get(ENV)
    if path:
        with open(path, "a", encoding="utf-8", newline="\n") as out:
            out.write("%s\t%s\n" % (outcome, nodeid))


def pytest_runtest_logreport(report):
    if report.failed:
        _record("failed", report.nodeid)
    elif report.nodeid == os.environ.get(SENTINEL_ENV) and (
            report.when == "call" or report.skipped):
        _record(report.outcome, report.nodeid)


def pytest_collectreport(report):
    if report.failed:
        _record("failed", report.nodeid)
