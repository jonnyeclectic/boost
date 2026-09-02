---
id: audit-create-distill-infer-absorb-install-silently-replace-an-inst
board: code
section: dx
status: inflight
category: Safety · Bug
complexity: S
impact: High
wow: 2
note: a tap skill becomes the TODO scaffold, lock flips to local — and the message says installed
order: 206
owner: loop/generated-install-overwrite
pr: 716
title: "create/distill/infer/absorb <code>--install</code> silently replace an installed (unpinned) skill and flip its lock provenance to local"
---
The generated-skill install path never checks whether the name is already taken. Verified: after
<code>install brainstorming</code> (sickn33 tap), <code>create brainstorming --install</code>
printed <em>"&#10003; installed brainstorming &rarr; ~/.agents/skills/brainstorming"</em> and the
store SKILL.md became the TODO scaffold (<code>description: "TODO: describe when this skill should
trigger"</code>), lock now <code>tap=local v0.1.0</code>. <code>distill --install -o
brainstorming &hellip;</code> likewise: lock <code>tap=local v1.0.0</code> with
<code>source_dir</code> pointing at a deleted <code>/tmp/&hellip;/boost-gen-&hellip;</code>
tempdir. Exit 0, no warning either time, and repeating any <code>--install</code> run re-copies
over the store with no notice. Only a <b>pinned</b> skill is protected — the unpinned default is
silently destroyed, with provenance flipped so the loss is invisible to <code>list</code>.

The gate belongs in the callers, not the store: <code>store.install_from_path</code>'s docstring
(<code>store.py:1175-1177</code>) deliberately omits the already-installed refusal because it
serves re-import/reinstall. Neither <code>_install_generated</code>
(<code>intelligence.py:103-123</code>) nor <code>cmd_create</code>
(<code>configuration.py:370-371</code>) checks <code>lockfile.get_skill</code>.

Fix: in <code>_install_generated</code> and <code>cmd_create</code>, check
<code>lockfile.get_skill(name)</code> before <code>store.install_from_path</code>: refuse with a
hint ("already installed from &lt;tap&gt;; <code>boost uninstall</code> first, pass
<code>--force</code>, or pick another name") or <code>out.confirm</code>; print "replaced" rather
than "installed" when overwriting is confirmed. Keep <code>install_from_path</code> itself
unchanged. Regenerate <code>docs/commands.html</code> if a <code>--force</code> flag is added to
create/distill/infer/absorb.

Found by the 2026-08 CLI audit (cluster <code>generated-install-overwrites</code>); repro in the
audit log.

<br><br><b>Fixed, per the verified recommendation.</b> Added <code>store.existing_skill_owner(name)</code>
(a thin <code>lockfile.get_skill</code> lookup returning the owning tap, core-level so both callers
and any future one share it) and used it in <code>_install_generated</code>
(<code>intelligence.py</code>, shared by distill/infer/absorb) and <code>cmd_create</code>
(<code>configuration.py</code>): when a name is already installed, ask with <code>out.confirm</code>
before replacing (mirrors the existing <code>_write_generated</code> overwrite-confirm for the
non-<code>--install</code> path) rather than adding a new <code>--force</code> flag, print
&ldquo;replaced&rdquo; instead of &ldquo;installed&rdquo; when confirmed, and on refusal save the
generated skill to cwd exactly as the existing policy-refusal branch already did (factored into one
<code>_save_generated_fallback</code> helper). <code>install_from_path</code> itself is unchanged, as
specified. No CLI surface changed, so <code>docs/commands.html</code> needed no regeneration
(confirmed via <code>build_command_reference.py --check</code>). New unit tests cover
<code>existing_skill_owner</code> directly; new functional tests cover the confirmed-replace and
declined-decline paths for both <code>create --install</code> and
<code>distill/infer/absorb --install</code>, verified manually end-to-end against a disposable
<code>BOOST_HOME</code> in both the declined and <code>BOOST_ASSUME_YES</code> branches.

<b>Gate status: implementation verified locally short of the full <code>make check</code>.</b> This
session's sandbox has no PyPI network access (pip/uv both get 403 from the index), so the
hash-pinned toolchain in <code>requirements/*.txt</code> could not be installed and
<code>mutmut</code>/<code>vulture</code>/<code>xenon</code>/<code>interrogate</code>/<code>refurb</code>/<code>codespell</code>/<code>actionlint</code>/<code>zizmor</code>/<code>import-linter</code>
are unavailable here. Verified instead with what the image does carry: <code>ruff check</code>,
<code>mypy</code> and <code>pyright</code> clean on every changed file (mypy's two pre-existing
<code>pkg.py</code> errors are untouched by this change); the full <code>tests/unit</code> +
<code>tests/functional</code> suite passes under Python 3.12 (three failures are pre-existing and
unrelated — two <code>test_catalog.py</code> permission tests and one <code>doctor</code> log-write
test all rely on a non-root <code>chmod</code> denial, which does not hold running as root here).
CI carries real network access and should run the full gate on the PR; left <code>inflight</code>
rather than <code>shipped</code> until that's confirmed green.
