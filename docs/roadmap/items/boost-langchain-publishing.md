---
id: boost-langchain-publishing
board: code
section: planned
status: planned
category: Release
complexity: S
impact: Med
wow: 2
note: the artifacts already build and pass twine check in CI — what is missing is a cadence and a Trusted Publisher
order: 98
title: give <code>boost-langchain</code> a release path to PyPI
---
The <code>boost-langchain</code> distribution shipped under <code>integrations/langchain/</code>
with its whole point being a <b>separate release cadence</b> from <code>boost-skill-cli</code> —
langchain majors move faster than boost does, and the conformance workflow already builds the
sdist/wheel and runs <code>twine check</code> on every touching PR. What does not exist is any way
for those artifacts to reach PyPI: the name 404s there, and nothing publishes on any trigger.

<b>Two pieces, one of which only the repo owner can do.</b> First, create the PyPI project and
configure a <b>Trusted Publisher</b> for it — pending-publisher registration works before the first
upload, and the filename-matching rule that pinned boost's own workflow name applies here too.
Second, a publish workflow with a deliberate trigger: <b>not</b> boost's every-merge cadence
(<code>publish.yml</code> releases <code>boost-skill-cli</code> on every push to main, which is
exactly the coupling the separate distribution exists to avoid) — a tag like
<code>boost-langchain-v0.1.0</code> or a manual dispatch that bumps the static version, builds from
<code>integrations/langchain/</code>, and publishes with the OIDC token. Remember the repo's own
lesson: a <code>release:</code>-triggered workflow can never fire here (GITHUB_TOKEN events do not
chain), so trigger on the tag push or dispatch directly.

<b>The floor is already honest.</b> The package requires <code>boost-skill-cli&gt;=1.0.320</code> —
measured against the actual API it calls, verified by an adversarial install — so the first
published version works against PyPI as it stands today.
