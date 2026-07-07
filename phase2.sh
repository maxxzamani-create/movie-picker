#!/bin/bash
# AdShark Phase 2 toolkit - eyes on the feed
# usage: bash phase2.sh setup | eyes | record [minutes] | detect <file>
case "$1" in
setup)
sudo apt update
sudo apt install -y openssh-server python3-opencv python3-numpy ffmpeg v4l-utils alsa-utils
sudo systemctl enable --now ssh
mkdir -p ~/adshark/recordings
wget -q -O ~/adshark/detector_v1.py https://adshark.tv/detector_v1.py
echo "----------------------------------------"
echo "G10 address(es) for SSH (user: maxxzamani):"
hostname -I
echo "SETUP DONE"
;;
eyes)
echo "--- video devices ---"
v4l2-ctl --list-devices
echo "--- capture card formats (/dev/video0) ---"
v4l2-ctl -d /dev/video0 --list-formats-ext 2>/dev/null | head -25
echo "--- audio capture devices ---"
arecord -l
echo "--- 3-second live view test (close window or wait) ---"
timeout 10 ffplay -hide_banner -loglevel error -f v4l2 -video_size 1280x720 -i /dev/video0 -autoexit -t 3 2>/dev/null || echo "ffplay preview skipped (no display from ssh) - that is OK"
;;
record)
mins=${2:-30}
f=~/adshark/recordings/game_$(date +%Y%m%d_%H%M).mkv
echo "Recording $mins minutes of the feed to $f"
echo "(video only if audio device differs; tune -i default later)"
ffmpeg -hide_banner -f v4l2 -framerate 30 -video_size 1280x720 -i /dev/video0 -f alsa -i default -t $((mins*60)) -c:v libx264 -preset veryfast -crf 23 -c:a aac "$f" || \
ffmpeg -hide_banner -f v4l2 -framerate 30 -video_size 1280x720 -i /dev/video0 -t $((mins*60)) -c:v libx264 -preset veryfast -crf 23 "$f"
echo "DONE: $f"
;;
detect)
python3 ~/adshark/detector_v1.py "$2"
;;
*)
echo "usage: bash phase2.sh setup - or - eyes - or - record [minutes] - or - detect <recording>"
;;
esac
