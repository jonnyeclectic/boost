---
id: fix-frontmatter-parsing
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Medium
wow: 2
note: a nested author map renamed a skill, and a byte-order mark hid a file's whole frontmatter
order: 375
owner:
pr:
title: Nested frontmatter maps and byte-order marks no longer corrupt a skill's metadata
---
<b>A nested map overrode top-level fields.</b> <code>frontmatter.parse_block</code> read every
<code>k: v</code> line as a top-level key, whatever its indent. A SKILL.md with
<code>author:</code> and an indented <code>name: Jane Doe</code> under it was catalogued as
<code>jane-doe</code>, so <code>boost install author-skill</code> said no such skill existed.
A nested <code>metadata: {version: "2.0"}</code>, the map the Agent Skills spec defines, became
the skill's version. Now only keys at the block's own top-level indent count as top-level. One
level of nested map is kept as a dict under its parent key (<code>meta["author"] ==
{"name": "Jane Doe", ...}</code>), and anything deeper is skipped. <code>frontmatter.dump</code>
writes the map back out. The <code>requires: {mcp: [rube]}</code> shape that shipped skills use
used to work only because the parser hoisted <code>mcp</code> to the top level by accident.
<code>mcpdecl.declared_names</code> now reads it from the dict. The list readers for
<code>requires:</code>/<code>conflicts:</code> treat a dict as naming nothing, and catalog
reads a dict where it expects a name, description or version as absent, never as its repr.

<b>A UTF-8 byte-order mark hid the frontmatter.</b> Windows editors write a BOM at the start of a
file. The <code>---</code> check then failed, so a valid SKILL.md came out with
<code>meta == {}</code>, description <code>﻿---</code> and version 0.0.0. A Boostfile with a
BOM failed its first line as "unrecognised", and the message did not show the BOM.
<code>frontmatter.split</code> and <code>unclosed</code> now strip the BOM. Catalog and
<code>rag.read_body</code> both go through <code>split</code>, so the content digest stays in
parity. <code>bundle install</code> strips the BOM for a file and for stdin.
<code>catalog.CACHE_FORMAT</code> is now 3, so existing tap caches are rescanned and pick up
the corrected metadata.
