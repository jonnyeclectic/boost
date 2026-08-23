---
id: marketing-crm-domain-had-no-category
board: code
section: internals
status: inflight
category: Catalog · Curation
complexity: M
impact: High
wow: 3
note: the four marketing registries already carried were filed under writing and general, so the category returned nothing
order: 124
owner: loop/marketing-crm-registries
pr:
title: <code>--category marketing</code> matched nothing, while four marketing registries sat in the catalog under other names
---
<b>The catalog carried marketing registries and could not hand you one.</b>
<code>boost tap --catalog --category marketing</code> returned zero rows, because no row was filed
that way. Four already existed: <code>coreyhaines31/marketingskills</code> (45,374 stars) under
<code>writing</code>, and <code>minhnv0807/ai-business-skills</code>,
<code>AgriciDaniel/claude-ads</code> and <code>AgriciDaniel/claude-seo</code> under
<code>general</code>. Their items are named <code>cold-email</code>, <code>email-sequence</code>,
<code>market-emails</code>, <code>ads-attribution</code>, <code>seo-backlinks</code>. Nothing about
that is writing, and nothing about it is general.

<b>The misfiling has one cause, and it is the counterpart of the <code>ui</code> trap.</b>
<code>ui</code> is pinned because a scorer keyed on the <em>repo name</em> files
<code>ai-design-skills</code> as design. This domain fails one step earlier: every repo in it
describes itself in agent vocabulary before it says what the skills do — &ldquo;345 skills for
Claude Code, Codex, Gemini CLI, Cursor and 8 more coding agents&rdquo; — so a scorer keyed on the
<em>README</em> lands on <code>general</code> every time and never reaches the word
<code>hubspot</code>. Reading item names is what separates them, which is the rule
<code>CLAUDE.md</code> already states and which this batch is a second proof of.

<b>Twenty registries, 2,388 measured items, seventh curated domain.</b> Sixteen new rows plus the
four recategorised. Every count is <code>scripts/measure_registry.py</code> against a fresh
<code>--filter=blob:none --depth=1</code> clone, never the repo's advertised figure — and the two
recategorised counts moved a long way when re-measured: <code>marketingskills</code> from 10 to
<b>50</b> items and <code>ai-business-skills</code> from 62 to <b>169</b>. Both old numbers were
that repo's own README total from an earlier release. Moving a row's category is not a reason to
trust the number attached to it, so <code>MARKETING_MEASURED</code> pins both.

<b>The cut that nearly shipped a CRM category with no CRM in it.</b> Thirty candidates were cloned
and measured; ten were dropped — <code>mikiarlo3/awesome-growth-hacking-skills</code> scans to
<b>0</b> items, <code>CosmoBlk/email-marketing-bible</code> to 1,
<code>mysticaltech/marketingskills</code> is a stale fork of a repo already in the batch, and
<code>gtm-skills/gtm</code> ships 5 items under names (<code>rep</code>, <code>scout</code>,
<code>closer</code>) that say nothing. Ranking the survivors by adoption then produced a top 20 in
which <b>the CRM half of the domain's own name had no coverage at all</b>: the CRM registries are
the least-starred rows in the batch — <code>LeadMagic/gtm-skills</code> at 42 stars for 206 items
covering Salesforce, HubSpot and Attio setup, <code>NEON-Rutger/B2B-revops-skills</code> at 45 for
CRM migration and lead routing — against 45,374 for the top content-marketing pack. Popularity and
coverage disagree here, and coverage wins:
<code>TestMarketingDomain::test_every_advertised_subdomain_has_a_registry</code> names the registry
carrying each of the four advertised sub-domains (CRM, RevOps, cold outreach, campaigns) and fails
if one is dropped or flagged <code>list_only</code>.

<b>Discovery was <code>boost_search</code> first, and it earned its ten seconds by narrowing the
question.</b> The corpus already tapped on this machine returned <code>cold-email</code>,
<code>deal-outreach</code>, <code>ai-cold-outreach</code> and <code>emails</code> — real hits, from
repos mostly already in the catalog. That is what said the gap was not <em>items</em> but a
<em>category</em>: the skills existed and were unreachable by domain. GitHub code search over
<code>filename:SKILL.md</code> with CRM vocabulary (<code>hubspot</code>,
<code>salesforce</code>, <code>pipeline</code>) is what surfaced the two CRM registries; repo search
alone never returned either, because neither repo's description mentions a CRM by name.

<b>What is deliberately not here.</b> Six live candidates were measured and left out for being
mixed rather than bad: <code>Varnan-Tech/opendirectory</code> (64 items, but
<code>dependency-update-bot</code> and <code>explain-this-pr</code> sit beside the marketing ones),
<code>TheCraigHewitt/skills</code> (65 items, roughly a quarter marketing, the rest founder ops),
<code>citedy/adclaw</code>, <code>manojbajaj95/claude-gtm-plugin</code>,
<code>markster-public/markster-os</code> and <code>hyperfx-ai/marketing-skills</code>. They are
recorded here rather than merely dropped, so the next sweep does not re-derive them from the same
search and re-litigate the same call.
