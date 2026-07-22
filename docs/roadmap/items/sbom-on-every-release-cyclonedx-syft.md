---
id: sbom-on-every-release-cyclonedx-syft
board: code
section: pipeline
status: inflight
category: Security · Supply chain
complexity: S
impact: Med
wow: 3
note: feeds osv-scanner
order: 4
owner: loop/sbom
pr:
title: SBOM on every release — CycloneDX / Syft
---
Generate a CycloneDX SBOM with the free <code>anchore/sbom-action</code>
           and attach it to each GitHub Release, so downstreams can inventory and
           scan exactly what boost is built from. Modest today (boost is close to
           stdlib-only) but it grows in value as the optional <code>[rag]</code>
           extras pull in real dependencies.
