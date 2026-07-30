Feature: boost mcp
  Register boost as an MCP server with every agent CLI that speaks MCP —
  Claude Code and Gemini CLI. Never shells out to a real CLI in these
  scenarios: shutil.which/subprocess.run are mocked.

  Background:
    Given a fresh boost environment

  Scenario: registering with no agent CLI installed prints both manual commands
    Given no agent CLI is on PATH
    When I run "boost mcp register"
    Then the exit code should be 0
    And the output should contain "no agent CLI found (looked for: claude, gemini)"
    And the output should contain "claude mcp add boost --scope user"
    And the output should contain "gemini mcp add --scope user"

  Scenario: registering with only the claude CLI present succeeds
    Given the "claude" CLI is on PATH and succeeds
    When I run "boost mcp register"
    Then the exit code should be 0
    And the output should contain "registered boost as an MCP server for Claude Code (scope: user)"
    And the output should not contain "Gemini CLI"

  Scenario: registering with only the gemini CLI present succeeds
    Given the "gemini" CLI is on PATH and succeeds
    When I run "boost mcp register"
    Then the exit code should be 0
    And the output should contain "registered boost as an MCP server for Gemini CLI (scope: user)"
    And the output should not contain "Claude Code"

  Scenario: registering with both CLIs present registers both
    Given the "claude" and "gemini" CLIs are on PATH and succeed
    When I run "boost mcp register"
    Then the exit code should be 0
    And the output should contain "registered boost as an MCP server for Claude Code (scope: user)"
    And the output should contain "registered boost as an MCP server for Gemini CLI (scope: user)"

  Scenario: naming a host that is not installed prints its manual command
    Given no agent CLI is on PATH
    When I run "boost mcp register --host gemini"
    Then the exit code should be 0
    And the output should contain "`gemini` CLI not found — run this yourself:"
    And the output should contain "gemini mcp add --scope user"
    And the output should not contain "claude mcp add"

  Scenario: an unknown host fails with the known hosts
    When I run "boost mcp register --host bogus"
    Then the exit code should be 1
    And the output should contain "unknown MCP host 'bogus'"
    And the output should contain "known hosts: claude, gemini"

  Scenario: a claude mcp add failure surfaces the error
    Given the "claude" CLI is on PATH but fails with "no auth"
    When I run "boost mcp register"
    Then the exit code should be 1
    And the output should contain "claude mcp register failed: no auth"

  Scenario: unregistering with no agent CLI prints both manual commands
    Given no agent CLI is on PATH
    When I run "boost mcp unregister"
    Then the exit code should be 0
    And the output should contain "claude mcp remove boost"
    And the output should contain "gemini mcp remove --scope user boost"
