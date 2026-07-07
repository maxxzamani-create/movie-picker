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
*)
echo "usage: bash flip.sh game - or - ads - or - test"
;;
esac
