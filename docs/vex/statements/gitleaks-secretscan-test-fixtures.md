---
id: gitleaks-secretscan-test-fixtures
vulnerability: "gitleaks:leaked-secret-detection"
status: not_affected
justification: vulnerable_code_not_present
source: .gitleaks.toml, tests/unit/test_secretscan.py
---
`tests/unit/test_secretscan.py` exists to prove `boost_cli/core/secretscan.py`
flags private keys and API tokens, so it ships synthetic examples of both by
design — strings shaped exactly like the credentials gitleaks' own ruleset
looks for. gitleaks correctly matches the shape; none of the matched strings
is a real, working credential, was ever live, or grants access to anything.
`.gitleaks.toml` allowlists only this one file, by exact path, and the
allowlist's own comment states why: nothing else in the repository is
excluded from the scan.
