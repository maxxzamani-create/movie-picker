#!/bin/bash
# AdShark flip toolkit - Phase 1
d=org.gnome.Mutter.DisplayConfig
p=/org/gnome/Mutter/DisplayConfig
case "$1" in
game)
busctl --user set-property $d $p $d PowerSaveMode i 3
;;
ads)
busctl --user set-property $d $p $d PowerSaveMode i 0
;;
test)
echo "Cutting to game feed in 3 seconds..."
sleep 3
busctl --user set-property $d $p $d PowerSaveMode i 3
sleep 5
busctl --user set-property $d $p $d PowerSaveMode i 0
echo "SOFTWARE WAKE WORKS - if you can read this, we won"
;;
demo)
echo "AdShark Phase 1 demo: ad loop starts, then 3 hands-free flip cycles"
mpv --fs --really-quiet --loop-playlist=inf ~/ads/*.mp4 &
sleep 8
for i in 1 2 3
do
echo "cycle $i: flip to GAME"
busctl --user set-property $d $p $d PowerSaveMode i 3
sleep 8
echo "cycle $i: flip to ADS"
busctl --user set-property $d $p $d PowerSaveMode i 0
sleep 8
done
echo "PHASE 1 COMPLETE - the shark flips on command"
;;
*)
echo "usage: bash flip.sh game - or - ads - or - test - or - demo"
;;
esac
