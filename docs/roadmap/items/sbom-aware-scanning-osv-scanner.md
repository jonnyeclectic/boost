---
id: sbom-aware-scanning-osv-scanner
board: code
section: pipeline
status: inflight
category: Security · Vuln
complexity: S
impact: Med
wow: 2
note: OSV-backed
order: 5
owner: loop/osv
pr:
title: SBOM-aware scanning — <code>osv-scanner</code>
---
Google's <code>osv-scanner</code> cross-checks a lockfile or the SBOM
           above against the OSV database, with broader ecosystem coverage than a
           single-language audit. The SBOM-driven complement to <code>pip-audit</code>:
           one scans the resolved env, the other scans the published manifest.
