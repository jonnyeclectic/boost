---
id: audit-export-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 1
note: -o x.zip writes a gzip tarball; the repair hint drops the skill from the lock instead
order: 268
owner:
pr:
title: "<code>boost export</code>: CLI audit findings (2026-08)"
---
<b>export picks the archive format from <code>--zip</code> alone, so <code>-o x.zip</code> writes a
gzip tarball named .zip.</b> <code>export brainstorming -o byname.zip</code> produces
<em>&ldquo;gzip compressed data&rdquo;</em> per file(1); <code>--zip -o byflag.tar.gz</code>
produces <em>&ldquo;Zip archive data&rdquo;</em> &mdash; both report <em>&ldquo;&#10003; exported 1
skill&rdquo;</em> with no hint, and the mislabelled archive fails downstream tools with an opaque
error. <code>pkg.py:1649</code> computes the extension but uses it only for the default filename;
<code>pkg.py:1654</code> branches the writer on <code>args.zip</code> alone. Infer the format from
<code>dest.suffix</code> when <code>-o</code> is given and <code>--zip</code> absent, warn when they
contradict, and add a functional test asserting <code>zipfile.is_zipfile</code> on a
<code>-o x.zip</code> export; regenerate <code>docs/commands.html</code>.

<br><br><b>export's &ldquo;repair with <code>boost sync</code>&rdquo; hint drops a local skill from
the lock instead of repairing it.</b> With a <code>tap=local</code> skill's store dir missing but
its recorded <code>source_dir</code> still on disk, export says <em>&ldquo;hint: repair with `boost
sync`&rdquo;</em> &mdash; and sync then prints <em>&ldquo;&#10003; dropped ab-testing from lock
(store dir missing, source gone)&rdquo;</em>, a message that is itself false while the source
exists. <code>store.sync_apply</code> gates repair on <code>tap_name != "local"</code>
(<code>store.py:1639</code>), yet <code>boost reinstall</code> in the same state already performs
the exact repair (<code>pkg.py:1153-1168</code>) &mdash; the hint names the one command that
destroys instead of the one that fixes. Teach <code>sync_apply</code>'s missing-store branch to call
<code>install_from_path</code> when <code>tap=='local'</code> and <code>source_dir</code> has a
SKILL.md, and branch <code>cmd_export</code>'s hint (<code>pkg.py:1644-1646</code>) to name
<code>boost reinstall &lt;name&gt;</code> for local skills.

<br><br><b>The hand-built Boostfile member carries inconsistent metadata in both archive
formats.</b> <code>tar tzvf</code> shows <code>-rw-r--r-- 0 0 0 &hellip; Boostfile</code> beside
<code>drwxr-xr-x 0 jonny wheel &hellip; brainstorming/</code> &mdash; extracting as root yields a
root-owned Boostfile next to user-owned files &mdash; and the zip branch gives the Boostfile mode
0o600 against the skill files' 0o644. Verification prefers the opposite normalisation to the
auditor's: pass a filter to <code>tf.add</code> (<code>pkg.py:1654-1670</code>) that zeroes
uid/gid and blanks uname/gname on <em>every</em> member to match the Boostfile &mdash;
deterministic archives that stop leaking the local username &mdash; and in the zip branch write the
Boostfile via a <code>ZipInfo</code> with <code>external_attr = (0o644|S_IFREG)&lt;&lt;16</code>.

<br><br>Found by the 2026-08 CLI audit (clusters export-archive-format, sync-local-source-repair,
export-tar-ownership); repro in the audit log.
