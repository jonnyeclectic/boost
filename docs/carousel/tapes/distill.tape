# boost carousel — Intelligence flagship: distill
# regenerate (from repo root): vhs docs/carousel/tapes/distill.tape

Output docs/carousel/gifs/distill.gif
Set FontSize 15
Set Width 940
Set Height 540
Set Padding 12
Set TypingSpeed 35ms
Set Theme "Dracula"

Hide
Type "export HOME=$(mktemp -d) COLORTERM=truecolor PATH=$PWD:$PATH; export BOOST_NO_AI=1 BOOST_ASSUME_YES=1; python3 tests/make_fixture.py /tmp/boost-carousel-ai >/dev/null 2>&1; boost tap /tmp/boost-carousel-ai >/dev/null 2>&1; mkdir -p /tmp/boost-carousel-ai-work; cd /tmp/boost-carousel-ai-work; clear"
Enter
Show

Type "boost distill tdd-workflow commit-messages -o safe-tdd"
Enter
Sleep 3s

Type "cat safe-tdd/SKILL.md"
Enter
Sleep 3.5s
