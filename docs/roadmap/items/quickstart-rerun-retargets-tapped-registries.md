---
id: quickstart-rerun-retargets-tapped-registries
board: code
section: dx
status: planned
category: CLI · UX
complexity: M
impact: Med
wow: 2
note: a rerun leaves an already-tapped registry where it is, even when the manifest names another commit
order: 332
owner:
pr:
title: "boost quickstart: a rerun could move already-tapped registries to their vectors"
---
<b>A rerun of quickstart still leaves an already-tapped registry at the commit it was tapped at.</b> <code>registry.add_many</code> skips a configured tap (<code>already tapped</code>), so a registry first tapped before quickstart pinned anything, or overtaken by a weekly republish, stays where it is, and <code>shards.sync</code> then refuses its shard (<code>tap is at X, shard is for Y</code>). The <code>audit-quickstart-findings</code> fix flags that refusal and names <code>boost update --shards</code>, which already moves such taps through <code>shards.ingest</code> (download and verify first, then move the tap). That was the smaller half of the card; its other half was to have quickstart do the move itself. Fix: on a rerun, hand the configured taps the manifest publishes to <code>shards.ingest</code> instead of <code>shards.sync</code>, so the vectors land in one command. Decide first whether quickstart may move a tap the user tapped on purpose at another commit: <code>boost update</code> treats a pin as a promise, and a tap pinned with <code>boost tap --at</code> should keep it. Pin that choice in <code>tests/functional/test_cli_quickstart.py</code> beside the <code>commit_moved</code> tests.
