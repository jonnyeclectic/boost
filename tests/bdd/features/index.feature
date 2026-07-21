Feature: boost index
  Build the discovery registry via GitHub Code Search. `gh` is always
  mocked in these scenarios — no real network call.

  Background:
    Given a fresh boost environment

  Scenario: requires the GitHub CLI
    Given the GitHub CLI is not installed
    When I run "boost index"
    Then the exit code should be 1
    And the output should contain "the GitHub CLI (gh) is required to build the index"
    And the output should contain "brew install gh"

  Scenario: builds the cache from gh's JSON output
    Given the GitHub CLI is installed and code search returns 2 sample skill files
    When I run "boost index --limit 100"
    Then the exit code should be 0
    And the output should contain "indexed 2 skill files across 2 repos (GitHub reports 7 total)"

  Scenario: a gh failure on the first page aborts with an error
    Given the GitHub CLI is installed but code search fails
    When I run "boost index --limit 50"
    Then the exit code should be 1
    And the output should contain "GitHub code search failed"
