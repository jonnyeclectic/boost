Feature: boost browse
  Interactive full-screen TUI with fuzzy search. There is no TTY in these
  scenarios, so `browse` takes its documented non-interactive escape hatch
  and prints the full catalog instead of launching curses.

  Background:
    Given a fresh boost environment

  Scenario: no skills available to browse
    When I run "boost browse"
    Then the exit code should be 1
    And the output should contain "no skills available to browse"

  Scenario: without a TTY, prints the full catalog instead of the TUI
    Given the fixture tap is added
    When I run "boost browse"
    Then the exit code should be 0
    And the output should contain "interactive mode needs a TTY — showing the full catalog"
    And the output should contain "brainstorming"
    And the output should contain "commit-messages"
    And the output should contain "5 items: 5 skills · 0 rules · 0 workflows · install with `boost install <name>`"

  Scenario: --help documents the command without touching the catalog
    When I run "boost browse --help"
    Then the exit code should be 0
    And the output should contain "Interactive full-screen TUI with fuzzy search"
