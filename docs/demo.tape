# boost demo — regenerate with:  brew install vhs && pipx install . && make demo
# (runs from the repo root; uses a throwaway $HOME so your setup is untouched)
#
# `boost` here is whatever is on PATH, and the GIF shows its output, so record
# with a pipx install like the README's rather than the checkout's ./boost
# shim: from a checkout, `boost doctor` prints the source-checkout hint, with
# the recording machine's interpreter and checkout paths in it.

Output docs/demo.gif

Set FontSize 15
Set Width 940
Set Height 540
Set Padding 12
Set TypingSpeed 35ms
Set Theme "Dracula"

# The Sleep lets `clear` finish while hidden; without it the first frame
# showed this whole setup line.
Hide
Type "export HOME=$(mktemp -d) COLORTERM=truecolor; python3 tests/make_fixture.py /tmp/boost-demo-tap >/dev/null 2>&1; clear"
Enter
Sleep 1s
Show

Type "boost tap /tmp/boost-demo-tap"
Enter
Sleep 2s

Type "boost search tdd"
Enter
Sleep 2s

Type "boost install brainstorming"
Enter
Sleep 2.5s

Type "boost list"
Enter
Sleep 2s

Type "boost doctor"
Enter
Sleep 4s
