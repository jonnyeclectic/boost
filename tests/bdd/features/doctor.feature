Feature: boost doctor
  Check installation health and report issues.

  Background:
    Given a fresh boost environment

  Scenario: an empty environment is set up, not healthy
    When I run "boost doctor"
    Then the exit code should be 0
    And the output should contain "boost doctor"
    And the output should contain "no registries tapped"
    And the output should contain "boost tap --defaults"
    And the output should contain "ready to set up"
    And the output should contain "0 skills installed · 0 taps synced · 0 broken links"

  Scenario: a healthy environment with installed skills
    Given the "brainstorming" skill is installed
    When I run "boost doctor"
    Then the exit code should be 0
    And the output should contain "git on PATH"
    And the output should contain "1 tap cloned & cached"
    And the output should contain "1 skill installed · 1 tap synced · 0 broken links"
    And the output should contain "● healthy"

  Scenario: a broken symlink is reported and flips the verdict
    Given the "brainstorming" skill is installed
    And a broken skill symlink exists
    When I run "boost doctor"
    Then the exit code should be 1
    And the output should contain "1 broken symlink in agent dirs — run `boost heal`"
    And the output should contain "need attention"

