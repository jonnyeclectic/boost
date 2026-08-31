---
id: audit-config-policy-set-store-type-unchecked-values-consumers-cras
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: High
wow: 2
note: '`policy set pin_only no` stores the truthy string "no" — pin-only ON, installs frozen'
order: 202
owner:
pr:
title: "<code>config</code>/<code>policy set</code> store type-unchecked values; consumers crash exit 70 and <code>pin_only no</code> freezes installs"
---
Both setters accept any value for any known key and the damage lands later, elsewhere. <code>policy set max_skills abc</code> &rarr; <em>&ldquo;&#10003; set max_skills = &quot;abc&quot;&rdquo;</em> exit 0; the next <code>install brainstorming</code> &rarr; <em>&ldquo;Error: boost hit an unexpected error: ValueError: invalid literal for int() with base 10: 'abc'&rdquo;</em> exit 70 plus a crash report. <code>config set serve.port abc</code> then crashes even <code>serve --help</code> with the same ValueError &mdash; before argparse runs. <code>policy set blocked_skills 42</code> &rarr; <em>&ldquo;TypeError: argument of type 'int' is not iterable&rdquo;</em> from <code>policy check</code> and <code>install</code>.

The nastiest shape is silent inversion, not a crash: <code>policy set pin_only no</code> stores the <em>string</em> <code>"no"</code>, which is truthy &mdash; <code>policy check</code> reports <em>&ldquo;pin-only mode is on &mdash; installs/updates are frozen&rdquo;</em> and <code>install</code> refuses with <em>&ldquo;environment is pin-only (frozen)&rdquo;</em>. Same for <code>yes</code>, <code>off</code>, <code>0</code>, and every boolean policy key (<code>require_version</code>, <code>require_signed_taps</code>, &hellip;). Verification narrowed the claim honestly: key <em>names</em> are validated (<code>policy set nonsense_key x</code> exits 1 with the key list) &mdash; the gap is value types only, and <code>DEFAULTS</code> tables already exist in both modules to derive them from.

Fix per the verified recommendation: in <code>_parse_policy_value</code> (<code>boost_cli/commands/configuration.py:382-390</code>) and <code>config.set_value</code> (<code>boost_cli/core/config.py:246-258</code>), derive a per-key type from <code>policy.DEFAULTS</code> (<code>boost_cli/core/policy.py:15-34</code>) / <code>config.DEFAULTS</code>: map bools from {true,yes,on,1}/{false,no,off,0} case-insensitively, ints via <code>int()</code>, lists via <code>json.loads</code>, treat <code>max_skills</code> as int|None, and reject mismatches with a BoostError naming the expected type. Wrap the consumers (<code>cmd_serve</code>'s port read, <code>policy.load</code>) so a hand-edited bad value is a framed error with a hint, never a traceback. Regenerate <code>docs/commands.html</code> if the help epilogs gain the valid-value lists.

Found by the 2026-08 CLI audit (cluster <code>config-policy-set-validation</code>); repro in the audit log. Verified 2026-08-31: reproduced end to end, including the pin_only inversion and the exit-70 consumers.
