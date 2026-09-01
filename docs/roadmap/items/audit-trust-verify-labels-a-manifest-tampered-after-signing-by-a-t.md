---
id: audit-trust-verify-labels-a-manifest-tampered-after-signing-by-a-t
board: code
section: trust
status: inflight
category: Safety · Bug
complexity: S
impact: High
wow: 2
note: the tampering case the feature exists for reads as "key unknown", and the sweep exits 0
order: 221
owner: loop/trust-verify-tamper
pr: 675
title: "<code>trust verify</code> labels a manifest tampered after signing by a TRUSTED key 'untrusted'; sweep exits 0"
---
Sign a tap's manifest with a trusted key, then edit the manifest &mdash; the exact tampering <code>trust verify</code> exists to catch. The sweep reports <code>iktakahiro/python-fastapi-ddd-sk&hellip;&nbsp; untrusted&nbsp; no trusted key verifies this sig&hellip;</code> and <b>exits 0</b>; <code>--json</code> says <code>{"status": "untrusted", "key_name": null, "fingerprint": "1122334455667788"}</code> &mdash; and that fingerprint is the trusted <code>acme</code> key's own. So a modified manifest is indistinguishable from a merely unknown signer, and a scripted sweep sails past it. One narrowing from verification: the named-tap path (<code>trust verify TAP</code>) does exit 1; the exit-0 hole is the sweep, whose alarm at <code>boost_cli/commands/quality.py:1329</code> fires only on INVALID. The 'untrusted / key unknown' mislabel affects both paths.

The cause is a fall-through: <code>provenance.verify_dir</code> (<code>boost_cli/core/provenance.py:156-163</code>) returns UNTRUSTED whenever no key verifies, even when <code>sig.key_id</code> equals a trusted key's id. <code>minisign.verify</code> already returns False on a key-id mismatch (<code>boost_cli/core/minisign.py:113</code>), so the id comparison is implementable, and nothing in <code>tests/functional/test_tap_signing.py</code> pins the current behaviour as intended &mdash; it covers only the unknown-key case.

Fix, per the verified recommendation: when the loop ends and <code>sig.key_id</code> matches a trusted key's, return <code>Result(INVALID, key_name=&lt;name&gt;, fingerprint=&hellip;, detail='signature by trusted key &lt;name&gt; does not verify &mdash; manifest modified?')</code>; keep UNTRUSTED for key ids not in the store. The sweep then exits 1 unchanged. Add the tamper case to <code>tests/functional/test_tap_signing.py</code>. Docs: <code>docs/security-design.md</code>.

Found by the 2026-08 CLI audit (cluster <code>trust-tampered-manifest</code>); repro in the audit log. Verified against source 2026-08-31.
