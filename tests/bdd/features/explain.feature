Feature: boost explain
  Explain what a skill does in plain English (falls back to a heuristic
  summary when AI is unavailable — the sandbox always sets BOOST_NO_AI=1).

  Background:
    Given a fresh boost environment
    And the fixture tap is added

  Scenario: explaining an installed skill without AI uses the heuristic fallback
    Given the "brainstorming" skill is installed
    When I run "boost explain brainstorming"
    Then the exit code should be 0
    And the output should contain wrapped "using the heuristic fallback"
    And the output should contain "Outline:"
    And the output should contain "Key rules:"

  Scenario: explaining a skill that is only in a tap (not installed)
    When I run "boost explain jira-integration"
    Then the exit code should be 0
    And the output should contain wrapped "using the heuristic fallback"

  Scenario: explaining an unknown skill fails
    When I run "boost explain does-not-exist"
    Then the exit code should be 1
    And the output should contain "no skill named 'does-not-exist' in any tap"
