Feature: boost mcp
  Register boost as an MCP server for Claude Code. Never shells out to a real
  `claude` CLI in these scenarios — shutil.which/subprocess.run are mocked.

  Background:
    Given a fresh boost environment

  Scenario: registering without the claude CLI prints the manual command
    Given the "claude" CLI is not on PATH
    When I run "boost mcp register"
    Then the exit code should be 0
    And the output should contain "`claude` CLI not found — run this yourself:"
    And the output should contain "claude mcp add boost --scope user"

  Scenario: registering with the claude CLI present succeeds
    Given the "claude" CLI is on PATH and succeeds
    When I run "boost mcp register"
    Then the exit code should be 0
    And the output should contain "registered boost as an MCP server (scope: user)"

  Scenario: a claude mcp add failure surfaces the error
    Given the "claude" CLI is on PATH but fails with "no auth"
    When I run "boost mcp register"
    Then the exit code should be 1
    And the output should contain "claude mcp register failed: no auth"

  Scenario: unregistering without the claude CLI prints the manual command
    Given the "claude" CLI is not on PATH
    When I run "boost mcp unregister"
    Then the exit code should be 0
    And the output should contain "claude mcp remove boost"
