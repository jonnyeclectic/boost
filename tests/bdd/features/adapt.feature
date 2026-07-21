Feature: boost adapt
  Render a skill as another agent framework's native source (CrewAI, Agents SDK).

  Background:
    Given a fresh boost environment
    And the fixture tap is added

  Scenario: adapting an installed skill to CrewAI
    Given the "brainstorming" skill is installed
    When I run "boost adapt brainstorming --to crewai"
    Then the exit code should be 0
    And the output should contain "from crewai import Agent"
    And the output should contain "brainstorming = Agent("

  Scenario: adapting an installed skill to the Agents SDK
    Given the "brainstorming" skill is installed
    When I run "boost adapt brainstorming --to agents-sdk"
    Then the exit code should be 0
    And the output should contain "from agents import Agent"
    And the output should match "name=\"brainstorming\""

  Scenario: adapting a tapped-but-not-installed skill still resolves
    When I run "boost adapt brainstorming --to crewai"
    Then the exit code should be 0
    And the output should contain "brainstorming = Agent("

  Scenario: --model none opts out of pinning an LLM
    Given the "brainstorming" skill is installed
    When I run "boost adapt brainstorming --to crewai --model none"
    Then the exit code should be 0
    And the output should not contain "llm="

  Scenario: an unknown framework is rejected
    Given the "brainstorming" skill is installed
    When I run "boost adapt brainstorming --to langchain"
    Then the exit code should be 1
    And the output should contain "unknown framework"

  Scenario: --to is required
    Given the "brainstorming" skill is installed
    When I run "boost adapt brainstorming"
    Then the exit code should be 2

  Scenario: adapting an unknown skill fails
    When I run "boost adapt does-not-exist --to crewai"
    Then the exit code should be 1
