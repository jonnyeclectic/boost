# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""boost's offline LLM evaluation harness (dev/CI only — never imported by the CLI).

Run it with `make evals`, not through a `boost` subcommand: this is a quality
gate in the same family as mutation testing, not user-facing functionality.
See evals/README.md for the metric definitions and how to extend the golden set.
"""
