---
id: writers-whose-bytes-are-compared-do-not-pin-their-newline
board: code
section: compat
status: shipped
category: Portability · Windows
complexity: M
impact: Med
wow: 2
note: 934 text writes take the platform line ending; five are bugs, and the walker was blind to the worst one
order: 363
owner: loop/pin-compared-newlines
pr: 1035
title: "934 text writes leave the line ending to the platform, and five of them are bugs"
---
Text mode decides two things, and naming the encoding fixes one of them. It also translates
<code>\n</code> to the platform separator <em>on write</em>, so a file written with
<code>encoding="utf-8"</code> on a GitHub <b>Windows</b> runner still holds CRLF. The sibling card
<code>text-io-leaves-its-encoding-to-the-locale</code> closed the encoding half across 414 files; this
is the other half, and it is deliberately not the same kind of sweep.

<b>#1012 hit both, one after the other, and the first fix hid the second.</b> Naming the encoding
turned the three <code>tests (windows-latest, 3.1x)</code> jobs green on the assertion that had failed
&mdash; and the next run put them straight back to red on the line endings of the same line. Two
platform defects in one call, and no way to see the second until the first was gone.

<b>The instrument was broken before the inventory was worth taking.</b> Both walkers in
<code>tests/unit/test_text_io_names_its_encoding.py</code> were blind to <code>os.fdopen</code>, and
blind three separate ways at once: by name (not in <code>_TEXT_IO</code>), by receiver
(<code>os</code> sits in <code>_NOT_FILE_OPENS</code> for <code>os.open</code>, which has no
encoding), and by argument position (<code>_mode</code> reads an attribute call's mode from
<code>args[0]</code>, which for <code>fdopen</code> is the descriptor). Fixing any one alone changes
nothing. What it hid is <code>util.atomic_write_text</code> &mdash; the repo's canonical durable
writer, behind <b>19 call sites</b>: the user lock, the project lock, <code>config.json</code>, every
tap cache, the BM25 index, every rule materialized into a user's <code>CLAUDE.md</code>. None of
those was in the original count. The <em>encoding</em> gate had the identical hole and was already
red underneath it: <code>core/util.py</code>'s PID lock wrote through <code>os.fdopen</code> naming
no encoding at all, under a gate whose docstring claimed it covered "every <code>.py</code> the repo
tracks, exactly".

<b>The count is 934, and a blanket pass would still be wrong.</b> 874 in <code>tests</code>, 32 in
<code>boost_cli</code>, 22 in <code>scripts</code>, 6 in <code>evals</code>. Pinning all of them is
934 edits of which 929 are churn, and churn in a diff is what makes the five real ones unreviewable.
Readers need nothing at all: universal newlines already fold CRLF to LF on the way in, which is why
the guard walks <em>writers only</em>.

<b>Two triage rules did the scoping, and both killed candidates.</b>

<b>R1 &mdash; no literal newline, no translation.</b> If the written string contains zero
<code>\n</code> characters, text mode has nothing to translate. That retires
<code>scripts/publish_shards.py</code> (<code>json.dumps</code> without <code>indent=</code> emits
none) and the PID lock in <code>core/util.py</code>, which writes a bare
<code>str(os.getpid())</code>. The lock is the useful case to state out loud: it sits one function
above <code>atomic_write_text</code> and looks identical, and pinning it for symmetry would be
ceremony in the same commit that argues against ceremony.

<b>R2 &mdash; both sides from the same write is self-consistent.</b> A hash recomputed over the same
local file the hash was recorded from agrees with itself whatever the line endings. A real finding
needs the two sides to come from different producers, cross a machine boundary, or be read by a
non-Python parser.

<b>Five writers are pinned, and the table says why for each.</b>
<code>TestEveryPinnedWriterIsStillPinned</code> anchors each row on the <em>source text</em> of its
call rather than a line number, so a rewritten writer fails loudly instead of being guarded by a
stale line.

<code>core/util.py</code> &middot; <code>atomic_write_text</code> &middot; <b>1-live</b>
&mdash; 19 call sites, 17 after R1 (<code>rag.py</code>'s BM25 index and rerank cache pass bare
<code>json.dumps</code> and emit no literal newline, so the pin is inert for them). The non-folding
reader is <b>git</b>, through exactly one of the seventeen: <code>projectlock.write</code> stamps
<code>&lt;repo&gt;/.boost/skill-lock.json</code>, which that module's own docstring says "is meant to
be <b>committed</b> &hellip; git is its history". It is <em>not</em> <code>sha256_dir</code> &mdash;
all eighteen of those call sites hash a <code>copytree</code>-populated skill dir or a tap clone,
never a file this function wrote, and an earlier draft of this card said otherwise.

<code>core/complete.py</code> &middot; <code>apply</code> &middot; <b>1-live</b> &mdash; rewrites the
user's whole <code>~/.bashrc</code> or <code>~/.zshrc</code>, and bash does not fold. The damage is
worse than stray characters: measured on bash 3.2 and zsh, a CRLF rc <em>stops parsing</em> at the
first compound statement (<code>fi\r</code> gives <code>syntax error: unexpected end of file</code>),
so nothing after the user's first <code>if</code> runs at all. The pin cuts both ways and that is
said out loud in the test: it normalizes the whole file to LF, including lines boost never wrote.

<code>commands/team.py</code> &middot; the <code>boost protocol register</code> handler &middot;
<b>1-live</b> &mdash; a bash script, and bash is a non-Python parser reading it byte for byte. The
write sits <em>above</em> the Darwin/Linux branch, so it is the one part of that command that runs on
Windows. Which CR failure bites is shell-specific and deliberately not claimed: "bad interpreter:
<code>bash\r</code>" is kernel <code>binfmt_script</code> behaviour and Windows has no kernel shebang
support, and the URL-corruption route is ruled out because <code>urlparse</code> strips CR. The
artifact is simply wrong, which is reason enough for one keyword.

<code>commands/intelligence.py</code> &times;2 &middot; the generated skill and
<code>evolve --apply</code> &middot; <b>2-latent</b> &mdash; both stamp a <code>sha256_dir</code>
over bytes they just wrote; every comparison is local today (R2), so nothing breaks &mdash; but a
digest should not record which OS produced the skill.

<b>What was refused, and why that is the result rather than a gap.</b> The eight generated-file
<code>--check</code> gates are <em>not</em> pinned: every one of them compares
<code>read_text()</code> against a freshly built string, and a text read folds &mdash; so CRLF cannot
fail them. They also run only in the <code>lint</code> job on <code>ubuntu-latest</code>. For the
same reason <code>.gitattributes</code> gains no <code>eol=lf</code> rows for
<code>roadmap.html</code> and friends: nothing digests their bytes (the two <code>sha256</code>
mentions near them are historical comments, not live hashes), and the one place where a byte digest
<em>is</em> the identity &mdash; <code>tests/eval/*.jsonl</code>, keyed by <code>golden_key</code>
&mdash; already carries the line.

<b>The Windows runner is the instrument, and it was used that way.</b> A round trip on Linux passes
whether the newline is pinned or not, and <code>os.linesep</code> cannot be monkeypatched to
simulate it &mdash; the C <code>TextIOWrapper</code> hardcodes <code>"\r\n"</code> under
<code>MS_WINDOWS</code> and never consults it, so a local "simulation" would pass against an
unpinned writer and prove the opposite of what it claims. So the byte-equality tests landed in their
own commit <em>before</em> the pins, and <code>tests (windows-latest, 3.14)</code> reported exactly
two failures: <code>assert b'\r' not in b'a\r\nb\r\n'</code> and
<code>assert b'\r' not in b'export A=1\r\neval "$(boost _complete)"\r\n'</code>. That red is the
only evidence the assertions are not ceremony.

<b>Three of the five reasons were overstated on the first pass, and an adversarial re-read caught
them.</b> Worth recording because the corrections are all the same shape &mdash; a plausible
mechanism nobody had traced to a line. The <code>sha256_dir</code> claim above was simply false.
<code>team.py</code>'s "dies with bad interpreter" is Linux/XNU kernel behaviour asserted about
Windows, which has no kernel shebang support at all, and its <code>chmod</code> is a documented
no-op there. And the byte-equality tests, cited at first as co-equal readers, were written by this
same change &mdash; they corroborate a pin, they cannot motivate one, or any writer could be
upgraded that way. The surviving justifications are a committed lock file, a shell that will not
parse, and an artifact that is wrong on its face.

<b>Two blind spots remain, and they are named rather than left to be rediscovered.</b>
<code>tempfile.NamedTemporaryFile</code> is a context manager rather than an <code>open</code>, and
its default mode is binary &mdash; so folding it into <code>_TEXT_IO</code> means teaching
<code>_mode</code> that a missing mode means one thing there and another everywhere else.
<code>logging.FileHandler</code> takes <code>encoding=</code> but has no <code>newline=</code> at
all, so it can only ever join the encoding walker. Both live sites are correct today, and
<code>TestTheWalkersCannotSeeTheseButTheyAreStillPinned</code> asserts that against the source, so
deleting one fails a test rather than a Windows runner.
