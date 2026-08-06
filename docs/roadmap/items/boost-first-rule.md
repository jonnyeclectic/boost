---
id: boost-first-rule
board: code
section: dx
status: inflight
category: Interop · Adoption
complexity: M
impact: High
wow: 4
note: the tool descriptions only help on hosts that deliver them — this is the surface that survives when none do
order: 76
owner: loop/boost-first-rule
pr:
title: <code>boost-first</code> — the one rule boost authors, offered opt-in at <code>boost mcp register</code>
---
The companion to <code>mcp-already-covered-defeater</code>, and the half of it that survives a
host which never delivers boost's text at all.

<b>The delivery problem, measured.</b> Gemini CLI never delivers MCP server
<code>instructions</code> in interactive mode: <code>Config.initialize()</code> does not await
<code>mcpInitializationPromise</code>, so <code>getMcpInstructions()</code> returns <code>""</code>;
<code>startChat</code> stamps the env-context entry once with a stable id and short-circuits; the
later <code>refreshMcpContext()</code> re-renders Tier 1 only. Worse,
<code>startConfiguredMcpServers()</code> returns early in an <b>untrusted folder</b> — and a
brand-new project directory is untrusted by default — so in exactly the situation the trigger
exists for, boost has <b>no tools at all</b>, not merely no instructions.
<code>~/.gemini/GEMINI.md</code> is loaded unconditionally and is not trust-gated. It is the only
boost surface that survives both failures.

<b>So boost ships one rule of its own.</b> It carries the same defeater as the tool descriptions —
an already-matching skill was installed before this request existed, matched on its own
description, and is one kind of three — plus the shell fallback (<code>boost search "…"</code>)
for the untrusted-folder case where no MCP tools exist, and the skip list in plain sight.

<b>It is an ordinary catalog item, and that is the point.</b> boost's whole product is asking
users to accept standing text written by strangers under <code>boost install</code>, reversible
with <code>boost uninstall</code>. Its OWN standing text has to be the same kind of thing, subject
to the same commands — a privileged block that <code>boost list</code> cannot see and
<code>boost uninstall</code> cannot remove is precisely the asymmetry a user is entitled to
resent. So <code>boost-first</code> lives in a real tap, in a real <code>.mdc</code>, and installs
through the same <code>_install_rule</code> path as anything else.

<b>Consent, deliberately expensive.</b> This is the most invasive thing boost can propose — text
in a file the user reads every session, in every project. The body is printed <i>in full</i>
before the question, the target paths are named, the answer <b>defaults to No</b>, and the
reversal command is shown whether they accept or decline. <code>BOOST_NO_RULE</code> is the escape
hatch, checked <i>before</i> <code>out.confirm</code> — which is load-bearing, because confirm
returns True under <code>BOOST_ASSUME_YES</code> or a bare <code>--yes</code> anywhere in argv, and
the test fixtures set exactly that. Without the guard every existing register test, and every
provisioning script, would silently write a standing block into a real CLAUDE.md. The offer is
scoped to hosts where boost actually registered a server, so it never reaches Cursor or Windsurf,
where a block naming <code>boost_search</code> would advertise tools that agent does not have.

<b>The bug this design exists to avoid.</b> An earlier proposal made
<code>registry.get("boost/builtin")</code> return a <code>Tap</code> whose <code>path</code>
pointed <i>inside the installed wheel</i>. That sits one <code>boost untap</code> away from
<code>registry.remove()</code>, which ends in <code>util.rmtree(tap.path)</code> — deleting part
of the user's own package. Here the shipped <code>.mdc</code> is <b>copied out</b> of the wheel
into <code>~/.boost/repos/boost__builtin/</code> on first use; the worst case is a recreatable
directory going away. <code>test_the_tap_path_is_never_inside_the_wheel</code> is what catches a
refactor that reintroduces it.

<b>And it must not answer a question it was not asked.</b> <code>mcp.no_results</code> and
<code>boost_doctor</code> both decide "has this user configured anything yet" by counting taps and
print the one-command setup path when the answer is zero. boost's own tap is excluded from that
count via <code>configured_tap_count()</code>: a machine holding nothing but
<code>boost-first</code> has an effectively empty catalog, and suppressing the setup message there
would strand a new user with a search that can never match.

<b>Known cost, stated rather than solved.</b> At register time there is usually no repo yet, so
the install is user-scope — the rule then stands in every project, including ones where boost has
nothing to offer. <code>store.install(scope="project")</code> exists and would bound it; wiring
that to a per-repo offer is a separate card.
