#!/bin/bash
# Install FlySafe Radar Scraper Timers
# Runs every 4 hours during day, every 2 hours at night

set -e

echo "=== Installing FlySafe Radar Scraper Timers ==="

# Copy service and timers
sudo cp /home/ronny/emsn2/systemd/flysafe-radar.service /etc/systemd/system/
sudo cp /home/ronny/emsn2/systemd/flysafe-radar-day.timer /etc/systemd/system/
sudo cp /home/ronny/emsn2/systemd/flysafe-radar-night.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start timers
sudo systemctl enable flysafe-radar-day.timer
sudo systemctl enable flysafe-radar-night.timer
sudo systemctl start flysafe-radar-day.timer
sudo systemctl start flysafe-radar-night.timer

echo ""
echo "✅ Timers installed and started"
echo ""
echo "Schedule:"
echo "  Day:   Every 4 hours (06:00, 10:00, 14:00, 18:00)"
echo "  Night: Every 2 hours (22:00, 00:00, 02:00, 04:00)"
echo ""
echo "Check status:"
echo "  systemctl list-timers flysafe-radar*"
echo "  systemctl status flysafe-radar-day.timer"
echo "  systemctl status flysafe-radar-night.timer"
echo ""
echo "View logs:"
echo "  tail -f /mnt/usb/logs/flysafe-radar.log"
echo ""
