Feature: boost search
  Search skills across tap registries, ranked by full-content BM25.

  Background:
    Given a fresh boost environment

  Scenario: no taps configured fails with a hint
    When I run "boost search anything"
    Then the exit code should be 1
    And the output should contain "no taps configured — nothing to search"
    And the output should contain "boost tap --defaults"

  Scenario: multi-word query ranks the exact match first
    Given the fixture tap is added
    When I run "boost search commit messages"
    Then the exit code should be 0
    And the output should contain "commit-messages"
    And the output should contain "ranked by full-content BM25"

  Scenario: no matches hints at discover
    Given the fixture tap is added
    When I run "boost search zzzznothing"
    Then the exit code should be 0
    And the output should contain "no matches for 'zzzznothing'"
    And the output should contain "try `boost discover zzzznothing`"

  Scenario: --json emits a single-line JSON document
    Given the fixture tap is added
    When I run "boost search brainstorming --json"
    Then the exit code should be 0
    And the output should match "\"name\": \"brainstorming\""

  Scenario: --limit rejects a non-positive value
    Given the fixture tap is added
    When I run "boost search x --limit 0"
    Then the exit code should be 2
    And the output should contain "must be >= 1"
