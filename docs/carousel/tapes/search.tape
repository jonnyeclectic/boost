# boost carousel — Discovery & Search flagship: search
# regenerate (from repo root): vhs docs/carousel/tapes/search.tape

Output docs/carousel/gifs/search.gif
Set FontSize 15
Set Width 940
Set Height 540
Set Padding 12
Set TypingSpeed 35ms
Set Theme "Dracula"

Hide
Type "export HOME=$(mktemp -d) COLORTERM=truecolor PATH=$PWD:$PATH; export BOOST_NO_AI=1 BOOST_ASSUME_YES=1; python3 tests/make_fixture.py /tmp/boost-carousel-find >/dev/null 2>&1; boost tap /tmp/boost-carousel-find >/dev/null 2>&1; clear"
Enter
Show

Type "boost search 'never write production code without a failing test'"
Enter
Sleep 3.5s

Type "boost search jira"
Enter
Sleep 3s
