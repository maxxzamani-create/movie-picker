#!/bin/bash
# AdShark Phase 2 toolkit — eyes on the feed + grade the detector
# usage: bash phase2.sh setup | eyes | record [minutes] | detect <file> | score <json> <truth> | harden
set -u
D=~/adshark
case "${1:-}" in
setup)
  sudo apt update
  sudo apt install -y openssh-server python3-opencv python3-numpy ffmpeg v4l-utils alsa-utils sqlite3 mpv
  sudo systemctl enable --now ssh
  mkdir -p "$D/recordings"
  for f in detector_v1.py detector_v2.py score.py; do
    wget -q -O "$D/$f" "https://adshark.tv/$f" && echo "fetched $f" || echo "WARN: could not fetch $f"
  done
  echo "----------------------------------------"
  echo "G10 address(es) for SSH (user: maxxzamani):"
  hostname -I
  echo "SETUP DONE — tell Claude the address above and typing days are over."
  ;;
eyes)
  echo "--- video devices ---";            v4l2-ctl --list-devices
  echo "--- capture formats (/dev/video0) ---"; v4l2-ctl -d /dev/video0 --list-formats-ext 2>/dev/null | head -25
  echo "--- audio capture devices ---";     arecord -l
  echo "--- 3s live-view test (skipped over ssh, that's OK) ---"
  timeout 10 ffplay -hide_banner -loglevel error -f v4l2 -video_size 1280x720 -i /dev/video0 -autoexit -t 3 2>/dev/null \
    || echo "ffplay preview skipped (no display from ssh) — that is OK"
  ;;
record)
  mins=${2:-30}
  f="$D/recordings/game_$(date +%Y%m%d_%H%M).mkv"
  echo "Recording $mins min of the feed to $f"
  ffmpeg -hide_banner -f v4l2 -framerate 30 -video_size 1280x720 -i /dev/video0 -f alsa -i default \
      -t $((mins*60)) -c:v libx264 -preset veryfast -crf 23 -c:a aac "$f" \
    || ffmpeg -hide_banner -f v4l2 -framerate 30 -video_size 1280x720 -i /dev/video0 \
      -t $((mins*60)) -c:v libx264 -preset veryfast -crf 23 "$f"
  echo "DONE: $f"
  ;;
detect)
  rec="${2:?usage: bash phase2.sh detect <recording.mkv>}"
  base="$(basename "$rec" | sed 's/\.[^.]*$//')"
  out="$D/recordings/${base}.json"
  python3 "$D/detector_v2.py" "$rec" --json "$out" --db "$D/events.db"
  echo "shadow log written: $out   (events also appended to $D/events.db)"
  echo "Next: note the REAL break times, put them in ${base}.truth.txt, then:"
  echo "      bash phase2.sh score $out $D/recordings/${base}.truth.txt"
  ;;
score)
  json="${2:?usage: bash phase2.sh score <detector.json> <truth.txt>}"
  truth="${3:?need a ground-truth breaks file}"
  python3 "$D/score.py" "$json" "$truth"
  ;;
harden)
  # Success-gate item: box recovers from a power cycle unattended.
  # Auto-login is on, so a GNOME autostart entry runs inside the Wayland
  # session (where busctl --user + mpv work). Boot = ad loop up, default to GAME.
  mkdir -p "$D" ~/.config/autostart ~/ads
  cat > "$D/boot.sh" << 'BOOT'
#!/bin/bash
# AdShark boot recovery — start the ad loop, default to GAME (fail-safe)
d=org.gnome.Mutter.DisplayConfig; p=/org/gnome/Mutter/DisplayConfig
sleep 5
pgrep -f "mpv.*/ads/" >/dev/null || (mpv --fs --really-quiet --loop-playlist=inf ~/ads/*.mp4 &)
sleep 3
# fail-safe default: show the live game (G10 output dark, priority switch falls to game)
busctl --user set-property $d $p $d PowerSaveMode i 3
BOOT
  chmod +x "$D/boot.sh"
  cat > ~/.config/autostart/adshark.desktop << DESK
[Desktop Entry]
Type=Application
Name=AdShark boot recovery
Exec=bash $D/boot.sh
X-GNOME-Autostart-enabled=true
NoDisplay=true
DESK
  echo "HARDEN installed:"
  echo "  $D/boot.sh  +  ~/.config/autostart/adshark.desktop"
  echo "Put at least one .mp4 house-ad in ~/ads/ , then TEST: pull the G10 power,"
  echo "plug back in, walk away — it must come up playing ads and showing the game."
  ;;
*)
  echo "usage: bash phase2.sh setup | eyes | record [minutes] | detect <file> | score <json> <truth> | harden"
  ;;
esac
