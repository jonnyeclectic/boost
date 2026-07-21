Feature: boost install
  Install a skill from a tap registry into the local store and link it into
  every enabled agent.

  Background:
    Given a fresh boost environment
    And the fixture tap is added

  Scenario: installing a known skill links it into every agent
    When I run "boost install brainstorming"
    Then the exit code should be 0
    And the output should contain "copied to ~/.agents/skills/brainstorming"
    And the output should contain "linked → claude-code · windsurf · cursor"
    And the output should contain "Installed 1 new skill; quality score 95/100"
    And the output should contain "next: boost info brainstorming"

  Scenario: --dry-run changes nothing on disk
    When I run "boost install brainstorming --dry-run"
    Then the exit code should be 0
    And the output should contain "would install brainstorming v1.4.0 from fixture-tap"
    And the output should contain "dry run — nothing was changed"

  Scenario: --agent restricts linking to a single agent
    When I run "boost install brainstorming --agent claude-code"
    Then the exit code should be 0
    And the output should contain "linked → claude-code"
    And the output should not contain "windsurf"

  Scenario: an unknown agent is rejected
    When I run "boost install brainstorming --agent emacs"
    Then the exit code should be 1
    And the output should contain "unknown agent: emacs"

  Scenario: installing an unknown skill fails with a hint
    When I run "boost install does-not-exist"
    Then the exit code should be 1
    And the output should contain "no skill named 'does-not-exist' in any tap"

  Scenario: a mix of known and unknown skills installs the known ones
    When I run "boost install brainstorming nope"
    Then the exit code should be 1
    And the output should contain "nope: no skill named 'nope' in any tap"
    And the output should contain "Installed 1 new skill; quality score 95/100"
