# boost demo — regenerate with:  brew install vhs && make demo
# (runs from the repo root; uses a throwaway $HOME so your setup is untouched)

Output docs/demo.gif

Set FontSize 15
Set Width 940
Set Height 540
Set Padding 12
Set TypingSpeed 35ms
Set Theme "Dracula"

Hide
Type "export HOME=$(mktemp -d) COLORTERM=truecolor PATH=$PWD:$PATH; python3 tests/make_fixture.py /tmp/boost-demo-tap >/dev/null 2>&1; clear"
Enter
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
