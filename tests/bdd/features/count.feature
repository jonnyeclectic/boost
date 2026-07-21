Feature: boost count
  A one-line inventory summary: installed / available / taps / discovery index.

  Background:
    Given a fresh boost environment

  Scenario: an empty environment
    When I run "boost count"
    Then the exit code should be 0
    And the output should contain "installed 0 · available 0 (across 0 taps) · discovery index not built"

  Scenario: one tap with one installed skill
    Given the "brainstorming" skill is installed
    When I run "boost count"
    Then the exit code should be 0
    And the output should contain "installed 1 · available 5 (across 1 tap) · discovery index not built"
    And the output should contain "╭─ inventory"

  Scenario: --json is machine readable
    Given the "brainstorming" skill is installed
    When I run "boost count --json"
    Then the exit code should be 0
    And the output should match "\"installed\": 1"
    And the output should match "\"taps\": 1"
