---
id: refresh-the-marketing-surface
board: code
section: planned
status: shipped
category: Docs · Marketing
complexity: M
impact: Med
wow: 4
note: 
order: 4
owner: loop/marketing
pr: 245
title: Refresh the marketing surface
---
The front page had drifted from the product: the README claimed <b>72</b> commands
           in one place and 78 in another (78 is correct), and <b>~2,600</b> mutants against a
           real ~9,900. A number a reader can check in ten seconds costs more credibility
           when wrong than the feature it describes earned. All three corrected — and pinned,
           so they cannot rot again: a unit test derives the command and group counts from
           <code>cli.COMMANDS</code> and fails if the README, the landing page, or the two
           disagree with each other. The README hero now leads with the one-line pitch and a
           four-command block that shows the whole flow before any prose. And
           <code>demo.gif</code> — a generated artifact whose regeneration needed
           <code>brew install vhs</code> on someone's laptop, so in practice it drifted (a
           merged PR had to fix it for showing <code>./boost</code> long after that changed)
           — is now re-recorded by CI whenever the surfaces it demonstrates change, proposed
           as a PR because a GIF re-encode always differs byte-for-byte and its correctness
           is visual, not comparable.
