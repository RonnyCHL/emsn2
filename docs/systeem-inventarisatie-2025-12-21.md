# EMSN 2.0 - Systeem Inventarisatie

**Gegenereerd:** 2025-12-21 06:00:24
**Script versie:** 1.2.0
**Gegenereerd op:** emsn2-zolder

---

## Samenvatting

| Systeem | Status | Uptime | IP Adres |
|---------|--------|--------|----------|
| Zolder Pi | ✅ Online | up 3 weeks, 4 days, 10 hours, 32 minutes | 192.168.1.178 |
| Berging Pi | ✅ Online | up 3 weeks, 4 days, 10 hours, 29 minutes | 192.168.1.87 |
| NAS Database | ✅ Online | - | 192.168.1.25 |

### ⚠️ Gevonden Problemen

- ❌ **Zolder:** Service `●` is FAILED

### 🆕 Nieuwe Componenten Sinds Vorige Run

*Vergeleken met inventarisatie van: 2025-12-16T19:18:13.254689*

**Zolder - Nieuwe Services:**
- `sync-birdnet-nas.service`

**Zolder - Nieuwe Timers:**
- `sync-birdnet-nas.timer`

**Zolder - Nieuwe Scripts:**
- `/home/ronny/emsn2/scripts/reports/species_images.py`
- `/home/ronny/emsn2/scripts/reports/weather_forecast.py`
- `/home/ronny/emsn2/scripts/timer_timeline.py`
- `/home/ronny/emsn2/scripts/train_existing_v2.py`
- `/home/ronny/emsn2/scripts/vocalization/auto_continue.py`
- `/home/ronny/emsn2/scripts/vocalization/dutch_bird_species.py`
- `/home/ronny/emsn2/scripts/vocalization/full_pipeline.py`
- `/home/ronny/emsn2/scripts/vocalization/src/classifiers/cnn_classifier_pytorch.py`
- `/home/ronny/emsn2/scripts/vocalization/src/collectors/xeno_canto.py`
- `/home/ronny/emsn2/scripts/vocalization/src/processors/spectrogram_generator.py`
- `/home/ronny/emsn2/scripts/vocalization/train_existing.py`

**Database - Nieuwe Tabellen:**
- `mqtt_bridge_events`
- `mqtt_bridge_uptime`
- `mqtt_hourly_stats`
- `pending_reports`
- `pending_reports_active`
- `timer_timeline`
- `timer_timeline_current`
- `vocalization_confusion_matrix`
- `vocalization_training`
- `xeno_canto_recordings`

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
| Uptime | up 3 weeks, 4 days, 10 hours, 32 minutes |
| Online sinds | 2025-11-25 19:28:01 |
| Load Average | 0.52 0.36 0.29 |

### Disk Usage

| Mount | Grootte | Gebruikt | Beschikbaar | Gebruik |
|-------|---------|----------|-------------|---------|
| / | 235G | 23G | 203G | 10% |
| /mnt/usb | 29G | 83M | 27G | 1% |
| /mnt/nas-reports | 3.5T | 99G | 3.4T | 3% |
| /mnt/nas-docker | 3.5T | 99G | 3.4T | 3% |

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
| sync-birdnet-nas.service | ⚪ inactive | dead | Sync BirdNET database naar NAS voor vocalisatie tr... |
| ulanzi-bridge.service | ✅ active | running | EMSN Ulanzi Bridge Service... |
| ulanzi-screenshot-server.service | ✅ active | running | EMSN Ulanzi Screenshot HTTP Server... |
| ulanzi-screenshot.service | ✅ active | running | EMSN Ulanzi Screenshot Service... |

### Systemd Timers

| Timer | Details |
|-------|---------|
| lifetime-sync.timer | Sun 2025-12-21 06:00:25 CET                 6s Sun 2025-12-21 05:55:02 CET     5... |
| hardware-monitor.timer | Sun 2025-12-21 06:01:00 CET                40s Sun 2025-12-21 06:00:00 CET      ... |
| emsn-dbmirror-zolder.timer | Sun 2025-12-21 06:03:19 CET           2min 59s Sun 2025-12-21 05:58:19 CET  2min... |
| mqtt-failover.timer | Sun 2025-12-21 06:03:29 CET            3min 9s Sun 2025-12-21 05:58:29 CET 1min ... |
| dual-detection.timer | Sun 2025-12-21 06:04:19 CET           3min 59s Sun 2025-12-21 05:59:19 CET  1min... |
| anomaly-datagap-check.timer | Sun 2025-12-21 06:08:49 CET               8min Sun 2025-12-21 05:53:49 CET     6... |
| anomaly-hardware-check.timer | Sun 2025-12-21 06:08:49 CET               8min Sun 2025-12-21 05:53:49 CET     6... |
| flysafe-radar-day.timer | Sun 2025-12-21 10:00:00 CET           3h 59min Sun 2025-12-21 06:00:00 CET      ... |
| flysafe-radar-night.timer | Sun 2025-12-21 22:00:00 CET                15h Sun 2025-12-21 04:00:00 CET  2h 0... |
| dpkg-db-backup.timer | Mon 2025-12-22 00:00:00 CET                17h Sun 2025-12-21 00:00:00 CET      ... |
| sync-birdnet-nas.timer | Mon 2025-12-22 02:00:00 CET                19h Sun 2025-12-21 02:00:00 CET  4h 0... |
| screenshot-cleanup.timer | Mon 2025-12-22 03:00:00 CET                20h Sun 2025-12-21 03:00:00 CET  3h 0... |
| rarity-cache.timer | Mon 2025-12-22 04:00:24 CET                22h Sun 2025-12-21 04:00:38 CET 1h 59... |
| emsn-weekly-report.timer | Mon 2025-12-22 07:00:00 CET                24h Mon 2025-12-15 07:00:00 CET   5 d... |
| anomaly-baseline-learn.timer | Sun 2025-12-28 03:00:00 CET             6 days Sun 2025-12-21 03:00:00 CET  3h 0... |
| backup-cleanup.timer | Sun 2025-12-28 04:03:49 CET             6 days Sun 2025-12-21 04:02:58 CET 1h 57... |
| emsn-monthly-report.timer | Thu 2026-01-01 08:00:00 CET      1 week 4 days -                                ... |
| emsn-yearly-report.timer | Fri 2026-01-02 08:00:00 CET      1 week 5 days -                                ... |
| emsn-seasonal-report-winter.timer | Sun 2026-03-01 07:00:00 CET    2 months 9 days -                                ... |
| emsn-seasonal-report-spring.timer | Mon 2026-06-01 07:00:00 CEST   5 months 9 days -                                ... |
| emsn-seasonal-report-summer.timer | Tue 2026-09-01 07:00:00 CEST  8 months 10 days -                                ... |
| emsn-seasonal-report-autumn.timer | Tue 2026-12-01 07:00:00 CET  11 months 10 days -                                ... |

### MQTT Broker (Mosquitto)

- **Status:** active
- **Actief sinds:** Sun 2025-12-14 16:05:02 CET


### Git Repository

- **Branch:** main
- **Laatste commit:** 6bc3d73 fix: training completion bug en sessie samenvatting
- **Uncommitted changes:** 0 bestanden


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
| bridge_monitor.py | `/home/ronny/emsn2/scripts/mqtt/bridge_monitor.py` | EMSN MQTT Bridge Monitor v2.0... |
| mqtt_failover.py | `/home/ronny/emsn2/scripts/mqtt/mqtt_failover.py` | EMSN MQTT Failover Monitor... |
| comparison_report.py | `/home/ronny/emsn2/scripts/reports/comparison_report.py` | EMSN Comparison Report Generator... |
| monthly_report.py | `/home/ronny/emsn2/scripts/reports/monthly_report.py` | EMSN Monthly Bird Activity Report Genera... |
| report_base.py | `/home/ronny/emsn2/scripts/reports/report_base.py` | EMSN Report Base Class... |
| report_charts.py | `/home/ronny/emsn2/scripts/reports/report_charts.py` | EMSN Report Charts Module... |
| report_highlights.py | `/home/ronny/emsn2/scripts/reports/report_highlights.py` | EMSN Report Highlights Module... |
| report_spectrograms.py | `/home/ronny/emsn2/scripts/reports/report_spectrograms.py` | EMSN Report Spectrograms Module... |
| seasonal_report.py | `/home/ronny/emsn2/scripts/reports/seasonal_report.py` | ... |
| species_images.py | `/home/ronny/emsn2/scripts/reports/species_images.py` | EMSN Species Images Module... |
| species_report.py | `/home/ronny/emsn2/scripts/reports/species_report.py` | EMSN Species-Specific Report Generator... |
| weather_forecast.py | `/home/ronny/emsn2/scripts/reports/weather_forecast.py` | EMSN Weather Forecast Module... |

---

## 🏚️ Berging Pi (192.168.1.87)

### Systeem Informatie

| Eigenschap | Waarde |
|------------|--------|
| Hostname | emsn2-berging |
| IP Adres | 192.168.1.87 fd64:5d33:8fcf:e2ec:c541:a2d7:2db5:8c37 |
| OS | N/A |
| Kernel | 6.12.47+rpt-rpi-v8 |
| Uptime | up 3 weeks, 4 days, 10 hours, 29 minutes |
| Online sinds | 2025-11-25 19:30:45 |

### Disk Usage

| Mount | Grootte | Gebruikt | Beschikbaar | Gebruik |
|-------|---------|----------|-------------|---------|
| / | 235G | 29G | 197G | 13% |
| /mnt/usb | 29G | 3.0G | 24G | 12% |

### Systemd Services

| Service | Status | Staat | Beschrijving |
|---------|--------|-------|--------------|

### Systemd Timers

| Timer | Details |
|-------|---------|

### Git Repository

- **Branch:** main
- **Laatste commit:** 9bd346c feat: add new component detection to system inventory v1.2.0
- **Uncommitted changes:** 2 bestanden


---

## 🗄️ NAS PostgreSQL Database (192.168.1.25)

### Database Overzicht

- **Database:** emsn
- **Grootte:** 146 MB
- **Laatste vogeldetectie:** 2025-12-21 05:53:19
- **Laatste health check:** 2025-12-21 06:00:02.647717

### Tabellen

| Tabel | Grootte | Kolommen | Rijen |
|-------|---------|----------|-------|
| bird_detections | 103 MB | 22 | 64,758 |
| system_health | 12 MB | 18 | 56,981 |
| weather_data | 8200 kB | 24 | 36,283 |
| dual_detections | 3600 kB | 14 | 10,402 |
| ulanzi_notification_log | 2584 kB | 9 | 16,002 |
| performance_metrics | 2560 kB | 9 | 19,250 |
| species_reference | 2456 kB | 15 | 157 |
| moon_observations | 480 kB | 10 | 2,515 |
| sky_observations | 432 kB | 12 | 1,257 |
| ulanzi_screenshots | 400 kB | 8 | 1,327 |
| anomaly_check_log | 360 kB | 6 | 1,817 |
| atmosbird_health | 272 kB | 12 | 1,257 |
| xeno_canto_recordings | 168 kB | 9 | 600 |
| species_baselines | 136 kB | 13 | 51 |
| system_events | 128 kB | 11 | 2 |
| ulanzi_cooldown_status | 112 kB | 7 | 104 |
| radar_observations | 104 kB | 10 | 73 |
| timer_timeline | 104 kB | 12 | 31 |
| anomalies | 104 kB | 12 | 14 |
| timelapses | 96 kB | 14 | 53 |
| species_rarity_cache | 88 kB | 5 | 126 |
| vocalization_training | 80 kB | 14 | 14 |
| mqtt_bridge_events | 80 kB | 7 | 6 |
| milestones | 64 kB | 8 | 1 |
| vocalization_confusion_matrix | 56 kB | 6 | 9 |
| pending_reports | 40 kB | 17 | 0 |
| meteor_detections | 32 kB | 13 | 0 |
| mqtt_hourly_stats | 24 kB | 11 | 0 |
| iss_passes | 24 kB | 9 | 0 |
| sky_bird_correlations | 24 kB | 9 | 0 |
| daily_summary | 24 kB | 16 | 0 |
| correlation_cache | 16 kB | 11 | 0 |
| user_annotations | 16 kB | 9 | 0 |
| nestbox_events | 16 kB | 13 | 0 |
| dynamic_rarity_scores | 16 kB | 10 | 0 |
| migration_events | 16 kB | 11 | 0 |
| territory_analysis | 16 kB | 10 | 0 |
| species_behavior_patterns | 16 kB | 10 | 0 |
| flock_detections | 16 kB | 10 | 0 |
| star_brightness | 16 kB | 9 | 0 |
| moon_phases | 16 kB | 5 | 0 |
| bat_detections | 8192 bytes | 14 | 0 |
| astronomical_events | 8192 bytes | 10 | 0 |
| pending_reports_active | 0 bytes | 12 | 0 |
| station_comparison | 0 bytes | 5 | 2 |
| daily_statistics | 0 bytes | 7 | 27 |
| mqtt_bridge_uptime | 0 bytes | 5 | 3 |
| bird_weather_correlation | 0 bytes | 14 | 64,758 |
| anomaly_summary_24h | 0 bytes | 6 | 0 |
| active_anomalies | 0 bytes | 11 | 14 |
| recent_activity | 0 bytes | 7 | 100 |
| timer_timeline_current | 0 bytes | 10 | 22 |

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
