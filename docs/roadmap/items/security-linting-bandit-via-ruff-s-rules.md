---
id: security-linting-bandit-via-ruff-s-rules
board: code
section: health
status: planned
category: Security · Vuln
complexity: S
impact: High
wow: 3
note: 0 new deps
order: 1
owner:
pr:
title: Security linting — <code>bandit</code> via ruff <code>S</code> rules
---
Turn on the <em>flake8-bandit</em> (<code>S</code>) rule family already
           bundled in ruff — one line in <code>pyproject.toml</code>, zero new
           tools. It catches the Python SAST smells the linter is blind to today:
           <code>subprocess(shell=True)</code>, <code>assert</code> as a runtime
           check, <code>tempfile.mktemp</code>, unsafe <code>yaml.load</code>,
           hardcoded secrets and weak hashing. Semgrep Community rules are the
           heavier alternative when a finding needs real dataflow.
