---
id: lockfile-enforcement-and-commit-pinning
board: code
section: trust
status: shipped
category: Security · Integrity
complexity: S
impact: Med
wow: 3
note: digest binding at load, opt-in
order: 7
owner: loop/integrity
pr: 215
title: Lockfile enforcement &amp; commit pinning
---
Promoted the recorded <code>sha256</code> from a note to a rule. The check
           moved into <code>core/integrity.py</code> (where the mutation gate
           covers it), and every command that serves a skill's content routes
           through one resolver that now refuses a tree whose bytes have drifted
           from the lock — a tamper tripwire at the point of use, since boost
           can't police what the <em>agent</em> loads but can refuse to hand you
           a skill that no longer matches what you reviewed. Opt-in
           (<code>config security.enforce_digest</code>, default off) so it never
           surprises an existing setup; <code>verify</code> reports drift either
           way. Commit pinning rides alongside: <code>boost pin &lt;skill&gt;
           --commit</code> freezes the exact source commit, and
           <code>verify</code> flags it if the recorded commit ever moves off the
           pin.
