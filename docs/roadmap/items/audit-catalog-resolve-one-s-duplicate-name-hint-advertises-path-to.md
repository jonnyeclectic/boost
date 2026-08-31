---
id: audit-catalog-resolve-one-s-duplicate-name-hint-advertises-path-to
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: High
wow: 1
note: Following the CLI's own hint earns `unrecognized arguments: --path`, exit 2
order: 215
owner:
pr:
title: "<code>catalog.resolve_one</code>'s duplicate-name hint advertises <code>--path</code> to commands that reject it"
---
When a name matches two skills inside one tap, every <code>catalog.resolve_one</code> caller prints
the same hint: <em>&ldquo;that registry ships one name twice &mdash; pick one with
<code>--path &lt;one of the above&gt;</code>&rdquo;</em>. Only <code>install</code>,
<code>recommend</code> and <code>infer</code> actually take <code>--path</code>. Verified live:
<code>boost adapt ultrawork --to agents-sdk</code> prints the hint, and
<code>adapt ultrawork --to crewai --path .agents/workflows</code> answers
<em>&ldquo;Error: unrecognized arguments: --path .agents/workflows&rdquo;</em>, exit 2 &mdash; same for
<code>run --print</code>, <code>log</code>, <code>home</code> and <code>explain</code>, while
<code>install ultrawork --path .agents/workflows --dry-run</code> works. A bonus wrinkle:
<code>csharp-reviewer</code> is a <em>workflow</em>, and the message calls the matches
&ldquo;skills&rdquo;.

Why it matters: this is the CLI contradicting itself &mdash; the error's one actionable line produces a
usage error when followed, so a duplicate-name skill in an uninstalled tap cannot be adapted, run or
read at all through those commands. The shipped <em>install-path-disambiguation</em> item added
<code>--path</code> to <code>install</code> only; the shared hint at
<code>boost_cli/core/catalog.py:555-556</code> was never parametrised by caller, so this is residual
scope of that work, not a duplicate.

Fix (verified recommendation): let <code>catalog.resolve_one</code> take the calling command's
disambiguation option (or <code>None</code>) &mdash; callers without <code>--path</code> get a hint
that works for them, e.g. <em>read one copy with <code>boost cat</code></em> or
<em>install with <code>boost install NAME --path &hellip;</code></em>; alternatively add
<code>--path</code> passthrough to <code>adapt</code>/<code>run</code>/<code>log</code>/<code>home</code>/<code>explain</code>/<code>cat</code>
(mirroring <code>cmd_install</code>, see <code>boost_cli/commands/pkg.py:1711-1723</code>). Use the
entry's <code>kind</code> in the message so a workflow is called one. Docs: regenerate
<code>docs/commands.html</code> if <code>--path</code> is added to any command; update
<code>docs/adapters.html</code>. Found by the 2026-08 CLI audit (cluster
<code>path-hint-unactionable</code>); repro in the audit log.
