#!/bin/bash
# EMSN 2.0 - Apply Migration 014 (Anomaly Detection)
#
# This script must be run on the DATABASE SERVER (192.168.1.25) as a user with sudo/postgres access
#
# Usage:
#   scp this script and 014_anomaly_detection.sql to the database server
#   Run: sudo -u postgres psql -d emsn -f migrations/014_anomaly_detection.sql

echo "==========================================="
echo "EMSN 2.0 - Migration 014: Anomaly Detection"
echo "==========================================="
echo ""
echo "This migration creates:"
echo "  - anomalies table"
echo "  - species_baselines table"
echo "  - anomaly_check_log table"
echo "  - Views and functions"
echo ""
echo "Run this on the DATABASE SERVER (192.168.1.25):"
echo ""
echo "  sudo -u postgres psql -d emsn -f /path/to/014_anomaly_detection.sql"
echo ""
echo "==========================================="
