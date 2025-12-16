# EMSN 2.0 - Systeem Inventarisatie

**Gegenereerd:** 2025-12-16 19:18:13
**Script versie:** 1.2.0
**Gegenereerd op:** emsn2-zolder

---

## Samenvatting

| Systeem | Status | Uptime | IP Adres |
|---------|--------|--------|----------|
| Zolder Pi | ✅ Online | up 2 weeks, 6 days, 23 hours, 50 minutes | 192.168.1.178 |
| Berging Pi | ✅ Online | up 2 weeks, 6 days, 23 hours, 47 minutes | 192.168.1.87 |
| NAS Database | ✅ Online | - | 192.168.1.25 |

### ✅ Geen Kritieke Problemen Gevonden

### 🆕 Nieuwe Componenten Sinds Vorige Run

*Vergeleken met inventarisatie van: 2025-12-16T19:17:43.647716*

**Zolder - Nieuwe Services:**
- `ulanzi-bridge.service`

**Zolder - Nieuwe Timers:**
- `mqtt-failover.timer`

> **Let op:** Deze nieuwe componenten zijn nog niet gedocumenteerd in het handboek.
> Overweeg om de documentatie bij te werken!

---

## 🏠 Zolder Pi (192.168.1.178)

### Systeem Informatie

| Eigenschap | Waarde |
|------------|--------|
| Hostname | emsn2-zolder |
| IP Adres | 192.168.1.178 |
| OS | Debian GNU/Linux 13 (trixie) |
| Kernel | 6.12.47+rpt-rpi-2712 |
| Uptime | up 2 weeks, 6 days, 23 hours, 50 minutes |
| Online sinds | 2025-11-25 19:28:01 |
| Load Average | 0.34 0.33 0.35 |

### Disk Usage

| Mount | Grootte | Gebruikt | Beschikbaar | Gebruik |
|-------|---------|----------|-------------|---------|
| / | 235G | 17G | 209G | 8% |
| /mnt/usb | 29G | 113M | 27G | 1% |
| /mnt/nas-reports | 3.5T | 3.8G | 3.5T | 1% |
| /mnt/nas-docker | 3.5T | 3.8G | 3.5T | 1% |

### Systemd Services

| Service | Status | Staat | Beschrijving |
|---------|--------|-------|--------------|
| anomaly-baseline-learn.service | ⚪ inactive | dead | EMSN Species Baseline Learning... |
| anomaly-datagap-check.service | ⚪ inactive | dead | EMSN Data Gap Anomaly Check... |
| anomaly-hardware-check.service | ⚪ inactive | dead | EMSN Hardware Anomaly Check... |
| avahi-alias@emsn2-zolder.local.service | ✅ active | running | Publish emsn2/zolder.local as alias for emsn2-zold... |
| backup-cleanup.service | ⚪ inactive | dead | EMSN Backup Cleanup Service... |
| birdnet-mqtt-publisher.service | ✅ active | running | EMSN BirdNET MQTT Publisher... |
| birdnet_analysis.service | ✅ active | running | BirdNET Analysis... |
| birdnet_log.service | ✅ active | running | BirdNET Analysis Log... |
| birdnet_recording.service | ✅ active | running | BirdNET Recording... |
| birdnet_stats.service | ✅ active | running | BirdNET Stats... |
| dpkg-db-backup.service | ⚪ inactive | dead | Daily dpkg database backup service... |
| dual-detection.service | ⚪ inactive | dead | EMSN Dual Detection Sync Service... |
| emsn-cooldown-display.service | ✅ active | running | EMSN Cooldown MQTT Publisher for Home Assistant... |
| emsn-dbmirror-zolder.service | ⚪ inactive | dead | EMSN 2.0 - Database Mirror Sync (Zolder)... |
| emsn-monthly-report.service | ⚪ inactive | dead | EMSN Monthly Bird Activity Report Generator... |
| emsn-reports-api.service | ✅ active | running | EMSN Reports Web API... |
| emsn-seasonal-report.service | ⚪ inactive | dead | EMSN Seasonal Bird Report Generator... |
| emsn-weekly-report.service | ⚪ inactive | dead | EMSN Weekly Bird Activity Report Generator... |
| emsn-yearly-report.service | ⚪ inactive | dead | EMSN Yearly Bird Report Generator... |
| flysafe-radar.service | ⚪ inactive | dead | FlySafe Radar Scraper - Bird Migration Monitoring... |
| hardware-metrics.service | ✅ active | running | EMSN Hardware Metrics Collector... |
| hardware-monitor.service | ⚪ inactive | dead | EMSN Hardware Monitor - Zolder Station... |
| lifetime-sync.service | ⚪ inactive | dead | EMSN Lifetime Sync - Zolder Station... |
| mqtt-bridge-monitor.service | ✅ active | running | EMSN MQTT Bridge Monitor... |
| mqtt-cooldown-publisher.service | ✅ active | running | EMSN MQTT Cooldown Publisher... |
| mqtt-failover.service | ⚪ inactive | dead | EMSN MQTT Failover Check... |
| rarity-cache.service | ⚪ inactive | dead | EMSN Rarity Cache Refresh... |
| screenshot-cleanup.service | ⚪ inactive | dead | EMSN Screenshot Cleanup Service... |
| ulanzi-bridge.service | ✅ active | running | EMSN Ulanzi Bridge Service... |
| ulanzi-screenshot-server.service | ✅ active | running | EMSN Ulanzi Screenshot HTTP Server... |
| ulanzi-screenshot.service | ✅ active | running | EMSN Ulanzi Screenshot Service... |

### Systemd Timers

| Timer | Details |
|-------|---------|
| dual-detection.timer | Tue 2025-12-16 19:18:39 CET                31s Tue 2025-12-16 19:13:39 CET  4min... |
| hardware-monitor.timer | Tue 2025-12-16 19:19:00 CET                51s Tue 2025-12-16 19:18:00 CET      ... |
| lifetime-sync.timer | Tue 2025-12-16 19:20:18 CET           2min 10s Tue 2025-12-16 19:15:29 CET  2min... |
| emsn-dbmirror-zolder.timer | Tue 2025-12-16 19:22:39 CET           4min 31s Tue 2025-12-16 19:17:39 CET      ... |
| mqtt-failover.timer | Tue 2025-12-16 19:22:49 CET           4min 41s Tue 2025-12-16 19:17:49 CET      ... |
| anomaly-datagap-check.timer | Tue 2025-12-16 19:22:59 CET           4min 51s Tue 2025-12-16 19:07:59 CET     1... |
| anomaly-hardware-check.timer | Tue 2025-12-16 19:22:59 CET           4min 51s Tue 2025-12-16 19:07:59 CET     1... |
| flysafe-radar-night.timer | Tue 2025-12-16 22:00:00 CET           2h 41min Tue 2025-12-16 04:00:00 CET      ... |
| dpkg-db-backup.timer | Wed 2025-12-17 00:00:00 CET           4h 41min Tue 2025-12-16 00:00:00 CET      ... |
| screenshot-cleanup.timer | Wed 2025-12-17 03:00:00 CET                 7h Tue 2025-12-16 03:00:00 CET      ... |
| rarity-cache.timer | Wed 2025-12-17 04:02:55 CET                 8h Tue 2025-12-16 04:04:00 CET      ... |
| flysafe-radar-day.timer | Wed 2025-12-17 06:00:00 CET                10h Tue 2025-12-16 18:00:00 CET  1h 1... |
| anomaly-baseline-learn.timer | Sun 2025-12-21 03:00:00 CET             4 days Sun 2025-12-14 03:00:00 CET    2 ... |
| backup-cleanup.timer | Sun 2025-12-21 04:04:22 CET             4 days Sun 2025-12-14 04:00:56 CET    2 ... |
| emsn-weekly-report.timer | Mon 2025-12-22 07:00:00 CET             5 days Mon 2025-12-15 07:00:00 CET 1 day... |
| emsn-monthly-report.timer | Thu 2026-01-01 08:00:00 CET      2 weeks 1 day -                                ... |
| emsn-yearly-report.timer | Fri 2026-01-02 08:00:00 CET     2 weeks 2 days -                                ... |
| emsn-seasonal-report-winter.timer | Sun 2026-03-01 07:00:00 CET   2 months 13 days -                                ... |
| emsn-seasonal-report-spring.timer | Mon 2026-06-01 07:00:00 CEST  5 months 14 days -                                ... |
| emsn-seasonal-report-summer.timer | Tue 2026-09-01 07:00:00 CEST  8 months 14 days -                                ... |
| emsn-seasonal-report-autumn.timer | Tue 2026-12-01 07:00:00 CET  11 months 14 days -                                ... |

### MQTT Broker (Mosquitto)

- **Status:** active
- **Actief sinds:** Sun 2025-12-14 16:05:02 CET


### Git Repository

- **Branch:** main
- **Laatste commit:** d2126ee feat: add weekly system inventory with handbook auto-update
- **Uncommitted changes:** 7 bestanden


### Python Scripts

| Script | Pad | Beschrijving |
|--------|-----|--------------|
| baseline_learner.py | `/home/ronny/emsn2/scripts/anomaly/baseline_learner.py` | ... |
| data_gap_checker.py | `/home/ronny/emsn2/scripts/anomaly/data_gap_checker.py` | ... |
| hardware_checker.py | `/home/ronny/emsn2/scripts/anomaly/hardware_checker.py` | ... |
| atmosbird_analysis.py | `/home/ronny/emsn2/scripts/atmosbird/atmosbird_analysis.py` | AtmosBird Advanced Analysis Script... |
| atmosbird_capture.py | `/home/ronny/emsn2/scripts/atmosbird/atmosbird_capture.py` | AtmosBird Sky Capture Script... |
| atmosbird_timelapse.py | `/home/ronny/emsn2/scripts/atmosbird/atmosbird_timelapse.py` | AtmosBird Timelapse Generator... |
| backup_cleanup.py | `/home/ronny/emsn2/scripts/backup_cleanup.py` | EMSN 2.0 - Backup Cleanup Script... |
| database_mirror_sync.py | `/home/ronny/emsn2/scripts/database_mirror_sync.py` | EMSN 2.0 - Database Mirror Sync... |
| color_analyzer.py | `/home/ronny/emsn2/scripts/flysafe/color_analyzer.py` | ... |
| flysafe_scraper.py | `/home/ronny/emsn2/scripts/flysafe/flysafe_scraper.py` | ... |
| migration_alerts.py | `/home/ronny/emsn2/scripts/flysafe/migration_alerts.py` | FlySafe Migration Alerts... |
| migration_forecast.py | `/home/ronny/emsn2/scripts/flysafe/migration_forecast.py` | ... |
| radar_correlation.py | `/home/ronny/emsn2/scripts/flysafe/radar_correlation.py` | ... |
| seasonal_analysis.py | `/home/ronny/emsn2/scripts/flysafe/seasonal_analysis.py` | ... |
| species_correlation.py | `/home/ronny/emsn2/scripts/flysafe/species_correlation.py` | ... |
| timelapse_generator.py | `/home/ronny/emsn2/scripts/flysafe/timelapse_generator.py` | ... |
| hardware_metrics.py | `/home/ronny/emsn2/scripts/hardware_metrics.py` | EMSN 2.0 - Hardware Metrics Collector... |
| birdnet_mqtt_publisher.py | `/home/ronny/emsn2/scripts/mqtt/birdnet_mqtt_publisher.py` | EMSN BirdNET MQTT Publisher... |
| bridge_monitor.py | `/home/ronny/emsn2/scripts/mqtt/bridge_monitor.py` | EMSN MQTT Bridge Monitor... |
| mqtt_failover.py | `/home/ronny/emsn2/scripts/mqtt/mqtt_failover.py` | EMSN MQTT Failover Monitor... |
| comparison_report.py | `/home/ronny/emsn2/scripts/reports/comparison_report.py` | EMSN Comparison Report Generator... |
| monthly_report.py | `/home/ronny/emsn2/scripts/reports/monthly_report.py` | EMSN Monthly Bird Activity Report Genera... |
| report_base.py | `/home/ronny/emsn2/scripts/reports/report_base.py` | EMSN Report Base Class... |
| report_charts.py | `/home/ronny/emsn2/scripts/reports/report_charts.py` | EMSN Report Charts Module... |
| report_highlights.py | `/home/ronny/emsn2/scripts/reports/report_highlights.py` | EMSN Report Highlights Module... |
| report_spectrograms.py | `/home/ronny/emsn2/scripts/reports/report_spectrograms.py` | EMSN Report Spectrograms Module... |
| seasonal_report.py | `/home/ronny/emsn2/scripts/reports/seasonal_report.py` | ... |
| species_report.py | `/home/ronny/emsn2/scripts/reports/species_report.py` | EMSN Species-Specific Report Generator... |
| weekly_report.py | `/home/ronny/emsn2/scripts/reports/weekly_report.py` | EMSN Weekly Bird Activity Report Generat... |
| yearly_report.py | `/home/ronny/emsn2/scripts/reports/yearly_report.py` | EMSN Yearly Bird Activity Report Generat... |

---

## 🏚️ Berging Pi (192.168.1.87)

### Systeem Informatie

| Eigenschap | Waarde |
|------------|--------|
| Hostname | emsn2-berging |
| IP Adres | 192.168.1.87 fd64:5d33:8fcf:e2ec:c541:a2d7:2db5:8c37 |
| OS | N/A |
| Kernel | 6.12.47+rpt-rpi-v8 |
| Uptime | up 2 weeks, 6 days, 23 hours, 47 minutes |
| Online sinds | 2025-11-25 19:30:45 |

### Disk Usage

| Mount | Grootte | Gebruikt | Beschikbaar | Gebruik |
|-------|---------|----------|-------------|---------|
| / | 235G | 27G | 199G | 12% |
| /mnt/usb | 29G | 1.5G | 26G | 6% |

### Systemd Services

| Service | Status | Staat | Beschrijving |
|---------|--------|-------|--------------|

### Systemd Timers

| Timer | Details |
|-------|---------|

### Git Repository

- **Branch:** main
- **Laatste commit:** 6d937c0 feat: Add bi-directional sync for deletions and species changes
- **Uncommitted changes:** 7 bestanden


---

## 🗄️ NAS PostgreSQL Database (192.168.1.25)

### Database Overzicht

- **Database:** emsn
- **Grootte:** 137 MB
- **Laatste vogeldetectie:** 2025-12-16 19:00:37
- **Laatste health check:** 2025-12-16 19:18:03.558744

### Tabellen

| Tabel | Grootte | Kolommen | Rijen |
|-------|---------|----------|-------|
| bird_detections | 103 MB | 22 | 53,294 |
| system_health | 8072 kB | 18 | 37,775 |
| weather_data | 6880 kB | 24 | 30,006 |
| dual_detections | 2704 kB | 14 | 7,473 |
| species_reference | 2456 kB | 15 | 148 |
| ulanzi_notification_log | 1576 kB | 9 | 9,513 |
| performance_metrics | 1400 kB | 9 | 10,325 |
| moon_observations | 280 kB | 10 | 1,234 |
| sky_observations | 264 kB | 12 | 616 |
| anomaly_check_log | 232 kB | 6 | 963 |
| ulanzi_screenshots | 208 kB | 8 | 565 |
| atmosbird_health | 160 kB | 12 | 616 |
| species_baselines | 136 kB | 13 | 47 |
| system_events | 128 kB | 11 | 2 |
| ulanzi_cooldown_status | 104 kB | 7 | 72 |
| anomalies | 104 kB | 12 | 7 |
| radar_observations | 96 kB | 10 | 36 |
| species_rarity_cache | 88 kB | 5 | 138 |
| timelapses | 64 kB | 14 | 23 |
| milestones | 64 kB | 8 | 1 |
| meteor_detections | 32 kB | 13 | 0 |
| iss_passes | 24 kB | 9 | 0 |
| daily_summary | 24 kB | 16 | 0 |
| sky_bird_correlations | 24 kB | 9 | 0 |
| species_behavior_patterns | 16 kB | 10 | 0 |
| flock_detections | 16 kB | 10 | 0 |
| moon_phases | 16 kB | 5 | 0 |
| correlation_cache | 16 kB | 11 | 0 |
| nestbox_events | 16 kB | 13 | 0 |
| user_annotations | 16 kB | 9 | 0 |
| dynamic_rarity_scores | 16 kB | 10 | 0 |
| migration_events | 16 kB | 11 | 0 |
| territory_analysis | 16 kB | 10 | 0 |
| star_brightness | 16 kB | 9 | 0 |
| astronomical_events | 8192 bytes | 10 | 0 |
| bat_detections | 8192 bytes | 14 | 0 |
| daily_statistics | 0 bytes | 7 | 22 |
| bird_weather_correlation | 0 bytes | 14 | 53,294 |
| anomaly_summary_24h | 0 bytes | 6 | 0 |
| station_comparison | 0 bytes | 5 | 2 |
| active_anomalies | 0 bytes | 11 | 7 |
| recent_activity | 0 bytes | 7 | 100 |

---

## 📋 Appendix

### Netwerk Overzicht

| Systeem | IP | Functie |
|---------|-----|---------|
| Pi Zolder | 192.168.1.178 | BirdNET-Pi, MQTT broker, API server |
| Pi Berging | 192.168.1.87 | BirdNET-Pi, AtmosBird, MQTT bridge |
| NAS | 192.168.1.25 | PostgreSQL, Grafana, Opslag |
| Ulanzi | 192.168.1.11 | LED Matrix Display |
| Homer | http://192.168.1.25:8181 | Dashboard |

### Belangrijke URLs

- **Reports API:** http://192.168.1.178:8081
- **Grafana:** http://192.168.1.25:3000
- **Homer Dashboard:** http://192.168.1.25:8181

### MQTT Topics

- `emsn2/{station}/#` - Systeem data
- `birdnet/{station}/detection` - Live detecties
- `birdnet/{station}/stats` - Statistieken
- `emsn2/bridge/status` - Bridge status

---

*Dit rapport is automatisch gegenereerd door system_inventory.py*
