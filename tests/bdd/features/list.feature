Feature: boost list
  List installed skills, rules, and workflows.

  Background:
    Given a fresh boost environment

  Scenario: no skills installed shows an empty state
    When I run "boost list"
    Then the exit code should be 0
    And the output should contain "no skills installed"
    And the output should contain "boost tap --defaults"

  Scenario: an installed skill is listed with its version and tap
    Given the "brainstorming" skill is installed
    When I run "boost list"
    Then the exit code should be 0
    And the output should contain "installed skills"
    And the output should contain "brainstorming"
    And the output should contain "1.4.0"
    And the output should contain "fixture-tap"
    And the output should contain "1 skill installed"

  Scenario: --json is machine readable
    Given the "brainstorming" skill is installed
    When I run "boost list --json"
    Then the exit code should be 0
    And the output should match "\"brainstorming\""
    And the output should match "\"skills\""

  Scenario: --tag narrows the listing to custom-tagged skills
    Given the "brainstorming" skill is installed
    When I run "boost tag brainstorming +fav"
    And I run "boost list --tag fav"
    Then the exit code should be 0
    And the output should contain "brainstorming"
    And the output should contain "#fav"

  Scenario: --tag with no matching skills shows the tagged empty state
    Given the "brainstorming" skill is installed
    When I run "boost list --tag nope-tag"
    Then the exit code should be 0
    And the output should contain "no skills installed with tag #nope-tag"
