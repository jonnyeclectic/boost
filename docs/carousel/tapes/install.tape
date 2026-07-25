# boost carousel — Package Management flagship: install
# regenerate (from repo root): vhs docs/carousel/tapes/install.tape

Output docs/carousel/gifs/install.gif
Set FontSize 15
Set Width 940
Set Height 540
Set Padding 12
Set TypingSpeed 35ms
Set Theme "Dracula"

Hide
Type "export HOME=$(mktemp -d) COLORTERM=truecolor PATH=$PWD:$PATH; export BOOST_NO_AI=1 BOOST_ASSUME_YES=1; python3 tests/make_fixture.py /tmp/boost-carousel-pkg >/dev/null 2>&1; boost tap /tmp/boost-carousel-pkg >/dev/null 2>&1; clear"
Enter
Show

Type "boost install jira-integration"
Enter
Sleep 3s

Type "boost list"
Enter
Sleep 2.5s
