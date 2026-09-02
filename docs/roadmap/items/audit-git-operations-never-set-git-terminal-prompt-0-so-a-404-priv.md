---
id: audit-git-operations-never-set-git-terminal-prompt-0-so-a-404-priv
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: a typo'd tap makes git ask "Username for 'https://github.com':"
order: 227
owner: loop/git-terminal-prompt
pr: 705
title: "git ops never set <code>GIT_TERMINAL_PROMPT=0</code>, so a 404/private repo prompts for credentials"
---
<code>gitutil.run</code> (<code>boost_cli/core/gitutil.py:19-41</code>) passes
<code>os.environ | {"GIT_LFS_SKIP_SMUDGE": "1"}</code> and nothing else &mdash;
<code>grep -rn GIT_TERMINAL_PROMPT boost_cli</code> has zero hits. So when a clone or fetch hits a repo
that does not exist or is private, git falls back to an interactive credential prompt. Verified across
all three surfaces: <code>tap nosuchowner-zz/nosuchrepo-zz-404</code> &rarr; <em>&ldquo;Error: git clone
failed: fatal: could not read Username for 'https://github.com': Device not configured&rdquo;</em> (exit 1);
same text from <code>import https://github.com/nosuch-owner-xyz-123/&hellip;</code> and, after a tap's
origin was rewritten to a 404 repo, from <code>update minio/skills</code> (&ldquo;git fetch failed&rdquo;).
&ldquo;Device not configured&rdquo; means git tried to open <code>/dev/tty</code> and the sandbox had none
&mdash; on a real terminal, a typo'd tap <em>blocks</em> <code>boost tap</code>, <code>import</code>,
<code>bundle install</code> and <code>update</code> on <code>Username for 'https://github.com':</code>. A
deleted-or-private upstream is exactly the case <code>registry.update</code>'s failures branch exists for,
and it never gets reached interactively.

Fix per the verified recommendation: add <code>GIT_TERMINAL_PROMPT="0"</code> (optionally
<code>GIT_ASKPASS=""</code>) to the env dict in <code>gitutil.run</code> &mdash; one line that fixes tap,
import, bundle install and update at once; in <code>clone_shallow</code>/fetch, map stderr containing
<em>could not read Username</em> / <em>Repository not found</em> / <em>Authentication failed</em> to a
<code>BoostError</code> naming the spec (&ldquo;repository not found or private&rdquo;); pin the env with a
unit test. With the flag set, git's own text becomes <em>&ldquo;&hellip;: terminal prompts disabled&rdquo;</em>
&mdash; already verified as the failure mode to translate. Docs:
<code>docs/roadmap/items/one-dead-tap-broke-every-update.md</code> gains a line (it never mentions the
credential-prompt failure mode). Found by the 2026-08 CLI audit (cluster git-credential-prompt); repro
in the audit log.
