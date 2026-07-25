---
id: self-update-broken-for-pip-pipx-installs
board: code
section: compat
status: planned
category: Bug
complexity: M
impact: High
wow: 3
note:
order: 10
owner:
pr:
title: <code>self-update</code> is non-functional for pip/pipx installs
---
<code>boost self-update</code> only works when boost runs from a git checkout: <code>paths.repo_root()</code>
resolves inside <code>site-packages</code> for a pip/pipx install, <code>gitutil.is_repo()</code> is
False, and <code>cmd_self_update</code> raises "boost is not running from a git checkout" with a hint
to clone the repo — telling a normal PyPI user to abandon their install method. Detect the install
method and shell out to <code>pip install --upgrade boost-skill-cli</code> /
<code>pipx upgrade boost-skill-cli</code>, falling back to the git-pull path only for source
checkouts.
