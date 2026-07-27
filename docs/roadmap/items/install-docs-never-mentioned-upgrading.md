---
id: install-docs-never-mentioned-upgrading
board: code
section: docsite
status: shipped
category: Docs
complexity: S
impact: Med
wow: 3
note: reported by a real user stuck 24 releases behind
order: 57
owner: loop/docs-upgrade-command
pr:
title: No install doc ever said how to <em>upgrade</em>, so users guessed <code>install --upgrade</code> — which no-ops
---
A user on the README-recommended <code>pipx</code> install ran
<code>pipx install boost-skill-cli --upgrade</code> and stayed on 1.0.203 while PyPI was at
1.0.226 — 23 releases behind. Nothing was broken. pipx's <code>install --upgrade</code> only
acts when the installed version does not satisfy the <b>supplied spec</b>, and the spec was
the bare name <code>boost-skill-cli</code>, which every version satisfies. It printed
<code>boost-skill-cli 1.0.203 already satisfies boost-skill-cli</code> and did nothing.

Confirmed at the source (pipx 1.16.2): <code>package_spec_satisfied()</code> returns True for
a bare name at any installed version, so the upgrade branch is never reached;
a pinned spec returns False. <code>pipx upgrade boost-skill-cli</code> is the correct verb,
verified end to end (1.0.203 → 1.0.227).

The root cause is documentation, not pipx. Every install surface — README,
<code>docs/index.html</code>, the site root — stopped at the install command; the word
"upgrade" appeared nowhere in any of them. With no correct command to copy, guessing
<code>install --upgrade</code> is the reasonable move.

Fixed by adding the upgrade line <em>inside</em> the code block users already copy from
(<code>docs/index.html</code>'s Copy button takes the whole block, so the right command
travels with the paste). The deeper bug — <code>boost self-update</code> hard-failing on
pip/pipx installs and telling a PyPI user to clone the repo — is separate and still open at
<code>self-update-broken-for-pip-pipx-installs</code>.
