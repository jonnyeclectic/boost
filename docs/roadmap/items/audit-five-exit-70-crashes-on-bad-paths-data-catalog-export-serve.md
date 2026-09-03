---
id: audit-five-exit-70-crashes-on-bad-paths-data-catalog-export-serve
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: M
impact: High
wow: 1
note: five user-reachable bad paths/values end in exit 70 + a crash report instead of one line
order: 204
owner: loop/exit70-hardening
pr: 721
title: "Five exit-70 crashes on bad paths/data: <code>catalog --export</code>, <code>serve --port</code>, <code>count</code>, <code>replay</code>, <code>infer -o</code>"
---
Five user-reachable conditions escape their guards and become <em>&ldquo;Error: boost hit an unexpected error: &hellip;&rdquo;</em> + <em>&ldquo;a crash report was written to &hellip;&rdquo;</em>, exit 70, where a framed BoostError belongs &mdash; the same class as the shipped two-crashes-that-should-have-been-messages item, five new sites, all verified. <code>catalog --export /nonexistent-dir-zz/b.tgz</code> &rarr; PermissionError (the <code>mkdir</code> at <code>boost_cli/core/catalogbundle.py:119</code> sits <em>before</em> the <code>except OSError</code> at <code>:127</code>). <code>serve --port 99999</code> (or <code>-1</code>) &rarr; <em>&ldquo;OverflowError: bind(): port must be 0-65535.&rdquo;</em> (<code>serve.py:931</code> catches OSError, and OverflowError is not one). <code>count</code> with a list-shaped <code>cache/discovery.json</code> &rarr; <em>&ldquo;AttributeError: 'list' object has no attribute 'get'&rdquo;</em> (<code>commands/discovery.py:1839-1841</code> guards JSONDecodeError/OSError only &mdash; and the verifier's probe <code>{"items": 3}</code> also crashes with a TypeError, so both container levels need validating). <code>replay show</code>/<code>rollback</code> on an unparseable snapshot &rarr; JSONDecodeError from <code>lockfile.py:254</code>, while <code>replay list</code> silently skips the file (<code>:226-233</code>) so the user cannot see why an id vanished. <code>infer -o /dev/null/nope/SKILL.md</code> &rarr; NotADirectoryError from the unguarded mkdir/write in <code>commands/intelligence.py:128-136</code>.

Why it matters: each is an expected condition &mdash; a typo'd path, an out-of-range flag, one stale derived cache file &mdash; and each currently costs a crash log and exit 70. <code>count</code> is the quick always-safe summary and must not crash on one derived cache; a corrupt <code>discovery.json</code> that is invalid JSON already degrades correctly to <code>discovery: null</code>, so valid-JSON-wrong-shape crashing is pure guard-shape accident.

Fix as one hardening sweep, per the verified recommendation: move the mkdir inside catalogbundle's OSError guard; validate <code>--port</code> in argparse (an ArgumentTypeError converter, exit 2) or catch OverflowError beside OSError in <code>serve_http</code>; in <code>cmd_count</code> check <code>isinstance(data, dict)</code> and <code>isinstance(items, list)</code> &rarr; discovery None; wrap <code>history_read</code>'s <code>json.loads</code> in a BoostError (<em>&ldquo;lock history entry &hellip; is unreadable&rdquo;</em>) and have <code>replay list</code> print one dim <em>&ldquo;N unreadable snapshot(s) skipped&rdquo;</em> line; wrap <code>_write_generated</code>'s mkdir/write_text in <code>except OSError</code> &rarr; BoostError. Unit-test each site. Docs: regenerate <code>docs/commands.html</code> (no flag/summary change).

Found by the 2026-08 CLI audit (cluster <code>crashes-should-be-messages</code>); repro in the audit log. Verified 2026-08-31: all five reproduced with exit 70 and a crash report.
