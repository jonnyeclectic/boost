---
id: prompt-injection-scanning-of-skill-markdown
board: code
section: trust
status: shipped
category: Security · Content
complexity: M
impact: High
wow: 5
note: the core risk
order: 1
owner: loop/inject-scan
pr: 131
title: Prompt-injection scanning of skill Markdown
---
The highest-signal gap: boost installs Markdown an agent then <em>executes</em>,
           and nothing inspects that content. Scan skills for injection patterns —
           <em>"ignore previous instructions"</em>, data-exfiltration prompts,
           embedded <code>curl … | sh</code> — with free rule engines
           (<code>semgrep</code> custom rules, <code>garak</code>/<code>llm-guard</code>
           patterns) at tap and install time.
