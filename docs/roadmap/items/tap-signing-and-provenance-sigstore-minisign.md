---
id: tap-signing-and-provenance-sigstore-minisign
board: code
section: trust
status: shipped
category: Security · Provenance
complexity: M
impact: Med
wow: 4
note: keyless OIDC
order: 3
owner: loop/tapsig
pr: 220
title: Tap signing &amp; provenance — Sigstore / minisign
---
A tap records its <code>commit</code> today but offers no cryptographic
           proof the content came from its claimed publisher, so a hijacked mirror
           can serve altered skills undetected. Verify a signature (Sigstore
           keyless or <code>minisign</code>) before trusting a tap — free, and the
           standard the wider ecosystem is converging on.
