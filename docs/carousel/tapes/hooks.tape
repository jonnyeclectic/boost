# boost carousel — Configuration flagship: hooks
# regenerate (from repo root): vhs docs/carousel/tapes/hooks.tape

Output docs/carousel/gifs/hooks.gif
Set FontSize 15
Set Width 940
Set Height 540
Set Padding 12
Set TypingSpeed 35ms
Set Theme "Dracula"

Hide
Type "export HOME=$(mktemp -d) COLORTERM=truecolor PATH=$PWD:$PATH; export BOOST_NO_AI=1 BOOST_ASSUME_YES=1; mkdir -p /tmp/boost-carousel-cfg-work; cd /tmp/boost-carousel-cfg-work; clear"
Enter
Show

Type "boost hooks add SessionStart -c 'boost bmad orient' -n greet --scope project"
Enter
Sleep 3s

Type "boost hooks list"
Enter
Sleep 2.5s
