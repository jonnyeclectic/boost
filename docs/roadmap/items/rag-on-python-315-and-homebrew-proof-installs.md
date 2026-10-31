---
id: rag-on-python-315-and-homebrew-proof-installs
board: code
section: compat
status: shipped
category: Compat · Install
complexity: M
impact: High
wow: 3
note: Homebrew removed python@3.14 and stranded the pipx venv; on 3.15 the [rag] extra would not install at all. The extra now installs there, doctor names the gap, and self-update and quickstart offer to move a pipx or uv install to 3.13
order: 379
owner: fix/py315-rag
pr:
title: "Python 3.15 broke the <code>[rag]</code> extra, and a Homebrew upgrade broke the install"
---
<b>What happened, 2026-10-28.</b> Homebrew's <code>python3</code> became 3.15.2 and the
<code>python@3.14</code> formula was removed. The pipx venv boost lived in was built on that
formula, so its <code>bin/python</code> pointed into a deleted directory and <code>boost</code>
failed before it started. Reinstalling on the new default did not help, because
onnxruntime 1.31.1 ships wheels for cp311–cp314 and <b>no sdist</b>. The
<code>[rag]</code> extra was unresolvable on 3.15, and that included sqlite-vec and tokenizers,
which both install there.

<b>What changed.</b>

- <code>pyproject.toml</code> marks onnxruntime <code>python_version &lt; '3.15'</code>, so on
  3.15 the extra installs without its runtime: the store and the tokenizer still install, and an
  API key still gives semantic search. <code>localembed.ONNX_WHEEL_CEILING</code> holds the same
  bound, and <code>tests/unit/test_rag_python_ceiling.py</code> fails if the marker and the
  constant disagree.
- <code>dense.status()</code> reports a new <code>no-local-wheel</code> reason in place of
  <code>no-key</code> on that interpreter. The no-key remedy was to reinstall the extra, which on
  3.15 reinstalls the same partial set of packages. Doctor and search now give the working step:
  <code>boost self-update --python 3.13</code> under pipx or uv tool, a pipx install with its own
  Python under pip, or a venv rebuild in a checkout. A store built with a key is still told to
  set that key, because moving to 3.13 would re-embed it.
- Quickstart and the reindex fallback ask <code>dense.extra_hint()</code>. On 3.15 under pipx or
  uv, that answers with a reinstall on 3.13 with the extra rather than <code>pipx inject</code>
  (for pipx, an uninstall then install: <code>install --force --python</code> keeps the old
  venv's interpreter). Any other install is pointed at a pipx install with its own Python,
  since a plain install there brings the store and no model. With a key set, the plain
  install is still the answer: the key embeds over HTTP.
- <code>boost self-update --python VERSION</code> runs <code>pipx reinstall --python V
  --fetch-python=always</code> (<code>--fetch-missing-python</code> on a pipx older than 1.18,
  which binds to Homebrew's <code>python3.13</code> when there is one, so boost then warns) or
  <code>uv tool install --force --managed-python --python V</code> with the requirement read
  back from <code>uv-receipt.toml</code> (install, not upgrade: only install rewrites the
  receipt's <code>python</code>). The extra survives either way. pip, uv-pip and checkout
  installs are refused with what to run instead.
- A plain <code>pipx install "boost-skill-cli[rag]"</code> (or <code>uv tool install</code>)
  on 3.15 no longer waits for the user to read a hint. A wheel cannot run code at install
  time, so the first commands that can act do: <code>boost self-update</code> and
  <code>boost quickstart</code> ask <code>selfupdate.relocation_reason()</code>, which fires
  only for a pipx or uv tool install, past the ONNX ceiling, with sqlite-vec present (the
  record that <code>[rag]</code> was asked for) and no API key. After a confirmation,
  self-update runs the 3.13 reinstall in place of its upgrade (one manager call, which also
  lands on the latest release), and quickstart runs it and then re-execs itself on the rebuilt
  venv, with <code>BOOST_RELOCATED=1</code> set so a move that did not take cannot loop.
  <code>--keep-python</code> on either command skips the offer, and <code>--dry-run</code>
  prints the command without running it. A working Homebrew interpreter is never moved; that
  stays a warning. The printed pipx hints now name the fetch flag the pipx on PATH accepts,
  the same rule the reinstall itself follows.
- The README recommends installing on a pinned, fetched interpreter, and
  <code>docs/DEBUGGING.md</code> has the one-line recovery for a stranded venv. CI's test matrix
  gains a 3.15 leg, which is advisory: not a required check, and
  <code>continue-on-error</code> so a red cell cannot hold back a release.

<b>When to undo it.</b> Drop the marker and raise the ceiling when onnxruntime publishes cp315
wheels.
