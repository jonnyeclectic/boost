# boost carousel — Registry (Taps) flagship: tap
# regenerate (from repo root): vhs docs/carousel/tapes/tap.tape

Output docs/carousel/gifs/tap.gif
Set FontSize 15
Set Width 940
Set Height 540
Set Padding 12
Set TypingSpeed 35ms
Set Theme "Dracula"

Hide
Type "export HOME=$(mktemp -d) COLORTERM=truecolor PATH=$PWD:$PATH; export BOOST_NO_AI=1 BOOST_ASSUME_YES=1; python3 tests/make_fixture.py /tmp/boost-carousel-tap >/dev/null 2>&1; clear"
Enter
Show

Type "boost tap --catalog --category rag --dry-run"
Enter
Sleep 3.5s

Type "boost tap /tmp/boost-carousel-tap"
Enter
Sleep 2s

Type "boost taps"
Enter
Sleep 2.5s
