#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Build a local fixture tap (a git repo of sample skills) for offline testing.

Usage:  python3 tests/make_fixture.py [dest_dir]
Prints the fixture repo path. Use it like:
  export HOME=/tmp/boost-sandbox        # sandbox everything
  boost tap /path/to/fixture-tap
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

SKILLS = {
    "brainstorming": {
        "frontmatter": """---
name: brainstorming
description: Structured ideation &
  divergent-thinking facilitation
version: 1.4.0
tags: [ideation, thinking]
---""",
        "body": """# Brainstorming

When the user wants to explore ideas, facilitate structured divergent thinking:

1. Diverge — generate widely, defer judgment
2. Cluster — group related concepts
3. Converge — score & select

## Rules

- Never critique during the diverge phase.
- Always produce at least 12 raw ideas before clustering.
- Score candidates on impact and effort.

```text
diverge -> cluster -> converge
```
""",
    },
    "jira-integration": {
        "frontmatter": """---
name: jira-integration
description: Sync commits and PRs to Jira tickets
version: 2.1.0
tags: [jira, workflow]
requires: [commit-messages]
---""",
        "body": """# Jira Integration

Keep Jira in lockstep with the repository.

## Workflow

1. Parse the ticket ID from the branch name (`PROJ-123-fix-thing`).
2. Prefix every commit message with the ticket ID.
3. On PR open, transition the ticket to "In Review".

- Always link the PR URL in a ticket comment.
- Never transition tickets that are flagged.
""",
    },
    "commit-messages": {
        "frontmatter": """---
name: commit-messages
description: Conventional, atomic commit message discipline
version: 1.0.2
tags: [git, hygiene]
---""",
        "body": """# Commit Messages

Write conventional commits.

## Rules

- Always use `type(scope): subject` — feat, fix, chore, docs, refactor, test.
- Subject line max 72 chars, imperative mood.
- Body explains why, not what.

```text
feat(parser): tolerate folded YAML scalars
```
""",
    },
    "tdd-workflow": {
        "frontmatter": """---
name: tdd-workflow
description: Red-green-refactor test-driven development loop
version: 3.0.1
tags: [testing, workflow]
conflicts: [cowboy-coding]
---""",
        "body": """# TDD Workflow

Strict red-green-refactor.

1. Write a failing test first. Watch it fail.
2. Write the minimum code to pass.
3. Refactor with the tests green.

- Never write production code without a failing test.
- Always run the full suite before committing.
""",
    },
    "cowboy-coding": {
        "frontmatter": """---
name: cowboy-coding
description: Ship fast without tests (intentionally contradictory fixture)
version: 0.1.0
tags: [testing]
---""",
        "body": """# Cowboy Coding

Move fast.

- Never write tests first; ship prototypes immediately.
- Always push straight to main.
""",
    },
}


def main() -> int:
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        tempfile.mkdtemp(prefix="boost-fixture-")) / "fixture-tap"
    skills_root = dest / "skills"
    for name, spec in SKILLS.items():
        d = skills_root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(spec["frontmatter"] + "\n\n" + spec["body"],
                                    encoding="utf-8")
    (dest / "README.md").write_text("# fixture-tap\n\nSample skills for boost tests.\n",
                                    encoding="utf-8")
    run = lambda *a: subprocess.run(a, cwd=dest, check=True, capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "fixture@boost.test")
    run("git", "config", "user.name", "Boost Fixture")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "fixture skills")
    print(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
