---
id: build-provenance-slsa-attestations
board: code
section: pipeline
status: inflight
category: Security · Supply chain
complexity: S
impact: Med
wow: 4
note: SLSA build L2
order: 3
owner: loop/slsa
pr:
title: Build provenance — SLSA attestations
---
<code>actions/attest-build-provenance</code> emits a cryptographically
           signed, verifiable record of <em>which workflow built which wheel from
           which commit</em>, layered on top of the existing PyPI Trusted
           Publishing. Consumers can <code>gh attestation verify</code> the
           artifact they install — provenance without a paid signing service.
