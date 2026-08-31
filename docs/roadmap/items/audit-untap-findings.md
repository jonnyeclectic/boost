---
id: audit-untap-findings
board: code
section: dx
status: planned
category: CLI · UX
complexity: S
impact: Low
wow: 1
note: tap takes several SPECs in parallel; untap still errors on a second name
order: 300
owner:
pr:
title: "<code>boost untap</code>: CLI audit findings (2026-08)"
---
<b>untap accepts only one NAME while tap accepts several SPECs.</b> <code>untap minio/skills anthropics/skills</code> answers <em>&ldquo;Error: unrecognized arguments: anthropics/skills&rdquo;</em> (exit 2, usage <code>boost untap [-h] [-f] name</code>), while <code>tap a b c</code> clones three in parallel &mdash; the reverse operation needs one invocation per tap. Verified: <code>cmd_tap</code> declares <code>spec</code> with <code>nargs='*'</code> (<code>taps.py:110-112</code>) and <code>cmd_untap</code> declares a bare single positional (<code>taps.py:178</code>); the per-tap dependent-item warning at <code>taps.py:187-200</code> already operates per tap, so looping is mechanical, not a redesign. Fix: make <code>name</code> <code>nargs='+'</code>, loop the existing dependent/confirm/remove body over each name, and return non-zero if any iteration failed. Regenerate <code>docs/commands.html</code> for the usage line. Found by the 2026-08 CLI audit (cluster <code>untap-single-name</code>); repro in the audit log.
