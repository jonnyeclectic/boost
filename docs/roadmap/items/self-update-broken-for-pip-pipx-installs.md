---
id: self-update-broken-for-pip-pipx-installs
board: code
section: compat
status: shipped
category: Bug
complexity: M
impact: High
wow: 3
note:
order: 10
owner: loop/self-update
pr: 272
title: <code>self-update</code> is non-functional for pip/pipx installs
---
<code>boost self-update</code> only works when boost runs from a git checkout: <code>paths.repo_root()</code>
resolves inside <code>site-packages</code> for a pip/pipx install, <code>gitutil.is_repo()</code> is
False, and <code>cmd_self_update</code> raises "boost is not running from a git checkout" with a hint
to clone the repo — telling a normal PyPI user to abandon their install method. Detect the install
method and shell out to <code>pip install --upgrade boost-skill-cli</code> /
<code>pipx upgrade boost-skill-cli</code>, falling back to the git-pull path only for source
checkouts. Shipped as <code>core/selfupdate.py</code>: detection reads evidence on disk —
<code>.git</code>, then <code>pipx_metadata.json</code> or <code>uv-receipt.toml</code> in
<code>sys.prefix</code>, then installed package metadata — and a <code>--dry-run</code> flag
prints the exact command without running it. Two details carry the weight: the pip branch
invokes <code>sys.executable -m pip</code>, never a bare <code>pip</code>, because the pip
first on PATH can belong to another interpreter and would upgrade a different copy while
reporting success; and an install nothing has a record of reports that plainly instead of
guessing pip. The new version is read from a freshly spawned <code>boost --version</code>,
since the running process imported its own version before the upgrade — if that probe says
nothing, neither does boost.
