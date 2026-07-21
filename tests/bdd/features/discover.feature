Feature: boost discover
  Browse and filter the GitHub-wide discovery index built by `boost index`.

  Background:
    Given a fresh boost environment

  Scenario: without an index and without gh, hints to install gh
    Given the GitHub CLI is not installed
    When I run "boost discover"
    Then the exit code should be 0
    And the output should contain "the discovery index has not been built yet"
    And the output should contain "install the GitHub CLI first"

  Scenario: without an index but with gh, hints to run boost index
    Given the GitHub CLI is installed and code search returns 2 sample skill files
    When I run "boost discover"
    Then the exit code should be 0
    And the output should contain "build it with `boost index` (GitHub Code Search)"

  Scenario: a query filters indexed entries
    Given the discovery index is seeded with sample items
    When I run "boost discover acme"
    Then the exit code should be 0
    And the output should contain "skills/web/SKILL.md"
    And the output should not contain "octo/skills"
    And the output should contain "2 of 3 indexed skills · GitHub reports ~42 total"

  Scenario: a query with no matches reports the index size
    Given the discovery index is seeded with sample items
    When I run "boost discover zzz"
    Then the exit code should be 0
    And the output should contain "no indexed skills match 'zzz'"
    And the output should contain "the index holds 3 entries — rebuild with `boost index`"

  Scenario: a corrupt index fails cleanly
    Given the discovery index is corrupt
    When I run "boost discover"
    Then the exit code should be 1
    And the output should contain "the discovery index is corrupt"
