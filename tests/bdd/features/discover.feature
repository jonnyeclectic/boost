Feature: boost discover
  Search GitHub for skill repositories you have not tapped yet, falling back to
  the local index built by `boost index` when GitHub cannot be reached.

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

  Scenario: a query searches GitHub itself, one row per repository
    Given the GitHub CLI is installed and code search returns 2 sample skill files
    When I run "boost discover pack"
    Then the exit code should be 0
    And the output should contain "acme/pack"
    And the output should contain "live GitHub Code Search"

  # Every scenario below drives the LOCAL index, so each one pins gh as absent
  # rather than relying on the runner not having it. A bare `boost discover
  # <query>` now reaches for the network, and CI runners ship gh — without this
  # these scenarios would shell out to real GitHub and flake on someone else's
  # rate limit.
  Scenario: --local filters indexed entries without touching the network
    Given the discovery index is seeded with sample items
    And the GitHub CLI is not installed
    When I run "boost discover acme --local"
    Then the exit code should be 0
    And the output should contain "skills/web/SKILL.md"
    And the output should not contain "octo/skills"
    And the output should contain "1 repo(s) across 2 of 3 indexed skill files"

  Scenario: a query falls back to the index when gh is missing
    Given the discovery index is seeded with sample items
    And the GitHub CLI is not installed
    When I run "boost discover acme"
    Then the exit code should be 0
    And the output should contain "falling back to the local index"
    And the output should contain "skills/web/SKILL.md"

  Scenario: a --local query with no matches says what it searched
    Given the discovery index is seeded with sample items
    And the GitHub CLI is not installed
    When I run "boost discover zzz --local"
    Then the exit code should be 0
    And the output should contain "no locally indexed skills match 'zzz'"
    And the output should contain "drop --local to search GitHub itself"

  Scenario: a fallback with no matches does not tell you to drop a flag you never passed
    Given the discovery index is seeded with sample items
    And the GitHub CLI is not installed
    When I run "boost discover zzz"
    Then the exit code should be 0
    And the output should contain "because the `gh` CLI is not installed"
    And the output should not contain "because GitHub could not be reached"
    And the output should not contain "drop --local"

  Scenario: a corrupt index fails cleanly
    Given the discovery index is corrupt
    When I run "boost discover"
    Then the exit code should be 1
    And the output should contain "the discovery index is corrupt"
