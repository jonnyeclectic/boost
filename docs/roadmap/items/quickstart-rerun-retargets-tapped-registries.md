---
id: quickstart-rerun-retargets-tapped-registries
board: code
section: dx
status: shipped
category: CLI · UX
complexity: M
impact: Med
wow: 2
note: a rerun leaves an already-tapped registry where it is, even when the manifest names another commit
order: 332
owner: loop/quickstart-retarget
pr:
title: "boost quickstart: a rerun could move already-tapped registries to their vectors"
---
<b>A rerun of quickstart still leaves an already-tapped registry at the commit it was tapped at.</b> <code>registry.add_many</code> skips a configured tap (<code>already tapped</code>), so a registry first tapped before quickstart pinned anything, or overtaken by a weekly republish, stays where it is, and <code>shards.sync</code> then refuses its shard (<code>tap is at X, shard is for Y</code>). The <code>audit-quickstart-findings</code> fix flags that refusal and names <code>boost update --shards</code>, which already moves such taps through <code>shards.ingest</code> (download and verify first, then move the tap). That was the smaller half of the card; its other half was to have quickstart do the move itself. Fix: on a rerun, hand the configured taps the manifest publishes to <code>shards.ingest</code> instead of <code>shards.sync</code>, so the vectors land in one command. Decide first whether quickstart may move a tap the user tapped on purpose at another commit: <code>boost update</code> treats a pin as a promise, and a tap pinned with <code>boost tap --at</code> should keep it. Pin that choice in <code>tests/functional/test_cli_quickstart.py</code> beside the <code>commit_moved</code> tests.

<b>Shipped.</b> Reproduced on <code>origin/main</code> (<code>11dbbc77</code>) over a real two-commit clone: tapped unpinned at <code>da3158c</code>, manifest row at <code>961fda8</code>, and the rerun printed <code>reg: shard refused (tap is at da3158c, shard is for 961fda8)</code> and left the clone where it was. The decision follows the one thing config.json does record, the pin. An <b>unpinned</b> tap tracks HEAD, and every <code>boost update</code> already moves it, so the rerun now moves it: <code>shards.plan</code> takes <code>movable</code> (default empty, so <code>sync</code> and <code>pkg._resync_vectors</code> plan exactly as before) and marks such a tap <code>"move"</code>, which quickstart hands to <code>shards.ingest</code>. That downloads and verifies the shard first, then moves the tap and pins it to the row, as a first run would have done. Each move is announced (<code>moving reg to 961fda8</code>), the dry run previews it (<code>would move 1 tap(s) … and pin them there</code>) and counts its download in the size, and the moved tap's catalog cache and the keyword index are rebuilt. A <b>pinned</b> tap is left alone. A pin quickstart set and a pin <code>boost tap --at</code> set look the same in config.json, so the rerun keeps both, and it names <code>boost update --shards</code> as the deliberate way to move them. So the weekly-republish half of the card (a tap quickstart itself pinned, then overtaken) still goes through <code>update --shards</code>. Pinned both ways in <code>tests/functional/test_cli_quickstart.py</code> (<code>TestARerunMovesAnUnpinnedTapToItsVectors</code>, over real git: moved and pinned, re-indexed, pinned tap left in place, a failed download moves nothing, the dry run moves nothing) and in <code>tests/unit/test_shards.py</code> (<code>movable</code> in both directions). Every new test fails on the old source.
