---
id: quality-trust-fingerprint-not-sensitive
vulnerability: "codeql:py/clear-text-logging-sensitive-data"
status: not_affected
justification: vulnerable_code_not_present
source: boost_cli/commands/quality.py:1248
---
CodeQL's `py/clear-text-logging-sensitive-data` query flags
`boost trust add`'s success line, which prints the trusted key's name and
minisign fingerprint, because the argument is user-supplied and `fingerprint`
reads like a credential name. It is not one: the value is a minisign
**public** key fingerprint, which is meant to be published, and printing it is
the entire point of the command — it is how a user checks by eye that the key
they just trusted matches the one the publisher advertises. The class of data
the query exists to catch (a secret, token, or password) is not present in
what is logged, so the pattern the rule looks for does not apply here. An
earlier automated fix that replaced this line with a constant string removed
the only verification `trust add` offers; the line was restored, the
suppression carries this reasoning inline
(`# codeql[py/clear-text-logging-sensitive-data]`), and
`tests/functional/test_tap_signing.py` pins the output so it cannot be quietly
dropped a second time.
