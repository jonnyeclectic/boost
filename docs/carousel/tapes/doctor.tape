# boost carousel — Quality & Health flagship: doctor
# regenerate (from repo root): vhs docs/carousel/tapes/doctor.tape

Output docs/carousel/gifs/doctor.gif
Set FontSize 15
Set Width 940
Set Height 540
Set Padding 12
Set TypingSpeed 35ms
Set Theme "Dracula"

Hide
Type "export HOME=$(mktemp -d) COLORTERM=truecolor PATH=$PWD:$PATH; export BOOST_NO_AI=1 BOOST_ASSUME_YES=1; python3 tests/make_fixture.py /tmp/boost-carousel-chk >/dev/null 2>&1; boost tap /tmp/boost-carousel-chk >/dev/null 2>&1; boost install brainstorming >/dev/null 2>&1; rm -rf $HOME/.agents/skills/brainstorming; clear"
Enter
Show

Type "boost doctor"
Enter
Sleep 3.5s

Type "boost heal"
Enter
Sleep 2.5s

Type "boost doctor"
Enter
Sleep 3s
