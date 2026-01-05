# EMSN 2.0 - Systeem Inventarisatie

**Gegenereerd:** 2026-01-04 06:01:23
**Script versie:** 1.2.0
**Gegenereerd op:** emsn2-zolder

---

## Samenvatting

| Systeem | Status | Uptime | IP Adres |
|---------|--------|--------|----------|
| Zolder Pi | ✅ Online | up 4 days, 7 hours, 47 minutes | 192.168.1.178 |
| Berging Pi | ✅ Online | up 4 days, 14 hours, 27 minutes | 192.168.1.87 |
| NAS Database | ✅ Online | - | 192.168.1.25 |

### ⚠️ Gevonden Problemen

- ❌ **Zolder:** Service `●` is FAILED
- ❌ **Zolder:** Service `●` is FAILED

### 🆕 Nieuwe Componenten Sinds Vorige Run

*Vergeleken met inventarisatie van: 2025-12-28T06:00:10.084951*

**Zolder - Nieuwe Services:**
- `anomaly-baseline-learn.service`
- `anomaly-datagap-check.service`
- `anomaly-hardware-check.service`
- `birdnet-archive-sync.service`
- `database-backup.service`
- `dual-detection.service`
- `lifetime-sync-zolder.service`
- `lifetime-sync.service`
- `rarity-cache.service`
- `sd-backup-daily.service`
- `sd-backup-weekly.service`

**Zolder - Nieuwe Timers:**
- `lifetime-sync-zolder.timer`

**Zolder - Nieuwe Scripts:**
- `/home/ronny/emsn2/scripts/atmosbird/__init__.py`
- `/home/ronny/emsn2/scripts/atmosbird/climate_control.py`
- `/home/ronny/emsn2/scripts/atmosbird/cloud_classifier_inference.py`
- `/home/ronny/emsn2/scripts/atmosbird/create_timelapse.py`
- `/home/ronny/emsn2/scripts/atmosbird/hardware_test.py`
- `/home/ronny/emsn2/scripts/core/__init__.py`
- `/home/ronny/emsn2/scripts/core/config.py`
- `/home/ronny/emsn2/scripts/core/logging.py`
- `/home/ronny/emsn2/scripts/core/mqtt.py`
- `/home/ronny/emsn2/scripts/core/network.py`
- `/home/ronny/emsn2/scripts/maintenance/log_cleanup.py`
- `/home/ronny/emsn2/scripts/maintenance/weekly_system_report.py`
- `/home/ronny/emsn2/scripts/monitoring/reboot_alert.py`
- `/home/ronny/emsn2/scripts/mqtt/__init__.py`
- `/home/ronny/emsn2/scripts/sync/__init__.py`
- `/home/ronny/emsn2/scripts/vocalization/__init__.py`

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
| Uptime | up 4 days, 7 hours, 47 minutes |
| Online sinds | 2025-12-30 22:13:47 |
| Load Average | 0.75 0.45 0.33 |

### Disk Usage

| Mount | Grootte | Gebruikt | Beschikbaar | Gebruik |
|-------|---------|----------|-------------|---------|
| / | 235G | 39G | 186G | 18% |
| /mnt/usb | 29G | 102M | 27G | 1% |
| /mnt/nas-reports | 3.5T | 24G | 3.5T | 1% |
| /mnt/nas-docker | 3.5T | 24G | 3.5T | 1% |

### Systemd Services

| Service | Status | Staat | Beschrijving |
|---------|--------|-------|--------------|
| anomaly-baseline-learn.service | ⚪ inactive | dead | EMSN Species Baseline Learning... |
| anomaly-datagap-check.service | ⚪ inactive | dead | EMSN Data Gap Anomaly Check... |
| anomaly-hardware-check.service | ⚪ inactive | dead | EMSN Hardware Anomaly Check... |
| avahi-alias@emsn2-zolder.local.service | ✅ active | running | Publish emsn2/zolder.local as alias for emsn2-zold... |
| backup-cleanup.service | ⚪ inactive | dead | EMSN Backup Cleanup Service... |
| birdnet-archive-sync.service | ⚪ inactive | dead | BirdNET Audio/Spectrogram Archive Sync... |
| birdnet-mqtt-publisher.service | ✅ active | running | EMSN BirdNET MQTT Publisher... |
| birdnet_analysis.service | ✅ active | running | BirdNET Analysis... |
| birdnet_log.service | ✅ active | running | BirdNET Analysis Log... |
| birdnet_recording.service | ✅ active | running | BirdNET Recording... |
| birdnet_stats.service | ✅ active | running | BirdNET Stats... |
| database-backup.service | ⚪ inactive | dead | EMSN PostgreSQL Database Backup... |
| dpkg-db-backup.service | ⚪ inactive | dead | Daily dpkg database backup service... |
| dual-detection.service | ⚪ inactive | dead | EMSN Dual Detection Sync Service... |
| emsn-cooldown-display.service | ✅ active | running | EMSN Cooldown MQTT Publisher for Home Assistant... |
| emsn-dbmirror-zolder.service | ⚪ inactive | dead | EMSN 2.0 - Database Mirror Sync (Zolder)... |
| emsn-monthly-report.service | ⚪ inactive | dead | EMSN Monthly Bird Activity Report Generator... |
| emsn-reports-api.service | ✅ active | running | EMSN Reports Web API... |
| emsn-seasonal-report.service | ⚪ inactive | dead | EMSN Seasonal Bird Report Generator... |
| emsn-weekly-report.service | ⚪ inactive | dead | EMSN Weekly Bird Activity Report Generator... |
| flysafe-radar.service | ⚪ inactive | dead | FlySafe Radar Scraper - Bird Migration Monitoring... |
| hardware-metrics.service | ✅ active | running | EMSN Hardware Metrics Collector... |
| hardware-monitor.service | ⚪ inactive | dead | EMSN Hardware Monitor - Zolder Station... |
| lifetime-sync-zolder.service | ⚪ inactive | dead | EMSN Lifetime Sync - Zolder Station... |
| lifetime-sync.service | ⚪ inactive | dead | EMSN Lifetime Sync - Zolder Station... |
| mqtt-bridge-monitor.service | ✅ active | running | EMSN MQTT Bridge Monitor... |
| mqtt-failover.service | ⚪ inactive | dead | EMSN MQTT Failover Check... |
| nestbox-screenshot.service | ⚪ inactive | dead | Nestkast Screenshot Capture... |
| rarity-cache.service | ⚪ inactive | dead | EMSN Rarity Cache Refresh... |
| screenshot-cleanup.service | ⚪ inactive | dead | EMSN Screenshot Cleanup Service... |
| sd-backup-cleanup.service | ⚪ inactive | dead | EMSN Backup Cleanup (verwijder oude backups)... |
| sd-backup-daily.service | ⚪ inactive | dead | EMSN SD Kaart Dagelijkse Backup (rsync)... |
| sd-backup-database.service | ⚪ inactive | dead | EMSN Database Uurlijkse Backup... |
| sd-backup-weekly.service | ⚪ inactive | dead | EMSN SD Kaart Wekelijkse Image Backup... |
| sync-birdnet-nas.service | ⚪ inactive | dead | Sync BirdNET database naar NAS voor vocalisatie tr... |
| ulanzi-bridge.service | ✅ active | running | EMSN Ulanzi Bridge Service... |
| ulanzi-screenshot-server.service | ✅ active | running | EMSN Ulanzi Screenshot HTTP Server... |
| ulanzi-screenshot.service | ✅ active | running | EMSN Ulanzi Screenshot Service... |

### Systemd Timers

| Timer | Details |
|-------|---------|
| emsn-dbmirror-zolder.timer | Sun 2026-01-04 06:01:36 CET                19s Sun 2026-01-04 05:56:36 CET  4min... |
| mqtt-failover.timer | Sun 2026-01-04 06:01:36 CET                19s Sun 2026-01-04 05:56:36 CET  4min... |
| dual-detection.timer | Sun 2026-01-04 06:01:46 CET                29s Sun 2026-01-04 05:56:46 CET  4min... |
| hardware-monitor.timer | Sun 2026-01-04 06:02:00 CET                43s Sun 2026-01-04 06:01:04 CET      ... |
| anomaly-datagap-check.timer | Sun 2026-01-04 06:02:36 CET           1min 19s Sun 2026-01-04 05:47:36 CET     1... |
| anomaly-hardware-check.timer | Sun 2026-01-04 06:04:36 CET           3min 19s Sun 2026-01-04 05:49:36 CET     1... |
| lifetime-sync-zolder.timer | Sun 2026-01-04 06:05:05 CET           3min 48s Sun 2026-01-04 05:05:45 CET     5... |
| lifetime-sync.timer | Sun 2026-01-04 06:05:06 CET           3min 49s Sun 2026-01-04 06:00:26 CET      ... |
| sd-backup-database.timer | Sun 2026-01-04 06:15:00 CET              13min Sun 2026-01-04 05:15:04 CET     4... |
| birdnet-archive-sync.timer | Sun 2026-01-04 06:18:41 CET              17min Sun 2026-01-04 05:15:15 CET     4... |
| nestbox-screenshot.timer | Sun 2026-01-04 07:00:24 CET              59min Sun 2026-01-04 06:00:26 CET      ... |
| flysafe-radar-day.timer | Sun 2026-01-04 10:00:00 CET           3h 58min Sun 2026-01-04 06:00:04 CET  1min... |
| flysafe-radar-night.timer | Sun 2026-01-04 22:00:00 CET                15h Sun 2026-01-04 04:00:04 CET   2h ... |
| dpkg-db-backup.timer | Mon 2026-01-05 00:00:00 CET                17h Sun 2026-01-04 00:00:03 CET      ... |
| sync-birdnet-nas.timer | Mon 2026-01-05 02:00:00 CET                19h Sun 2026-01-04 02:00:04 CET   4h ... |
| database-backup.timer | Mon 2026-01-05 02:01:32 CET                20h Sun 2026-01-04 02:03:44 CET  3h 5... |
| sd-backup-daily.timer | Mon 2026-01-05 02:01:35 CET                20h Sun 2026-01-04 02:04:34 CET  3h 5... |
| sd-backup-cleanup.timer | Mon 2026-01-05 02:30:00 CET                20h Sun 2026-01-04 02:30:00 CET  3h 3... |
| screenshot-cleanup.timer | Mon 2026-01-05 03:00:00 CET                20h Sun 2026-01-04 03:00:04 CET   3h ... |
| rarity-cache.timer | Mon 2026-01-05 04:00:00 CET                21h Sun 2026-01-04 04:02:07 CET  1h 5... |
| emsn-weekly-report.timer | Mon 2026-01-05 07:00:00 CET                24h Mon 2025-12-29 07:00:02 CET      ... |
| anomaly-baseline-learn.timer | Sun 2026-01-11 03:00:00 CET             6 days Sun 2026-01-04 03:00:04 CET   3h ... |
| sd-backup-weekly.timer | Sun 2026-01-11 03:01:12 CET             6 days Sun 2026-01-04 03:01:02 CET   3h ... |
| backup-cleanup.timer | Sun 2026-01-11 04:04:01 CET             6 days Sun 2026-01-04 04:03:17 CET  1h 5... |
| emsn-monthly-report.timer | Sun 2026-02-01 08:00:00 CET     4 weeks 0 days Thu 2026-01-01 08:00:04 CET    2 ... |
| emsn-seasonal-report-winter.timer | Sun 2026-03-01 07:00:00 CET    1 month 25 days Sat 2025-12-13 14:02:57 CET      ... |
| emsn-seasonal-report-spring.timer | Mon 2026-06-01 07:00:00 CEST  4 months 26 days Sat 2025-12-13 14:02:57 CET      ... |
| emsn-seasonal-report-summer.timer | Tue 2026-09-01 07:00:00 CEST  7 months 26 days Sat 2025-12-13 14:02:57 CET      ... |
| emsn-seasonal-report-autumn.timer | Tue 2026-12-01 07:00:00 CET  10 months 26 days Sat 2025-12-13 14:02:57 CET      ... |
| emsn-yearly-report.timer | Sat 2027-01-02 08:00:00 CET  11 months 28 days Fri 2026-01-02 08:00:01 CET 1 day... |

### MQTT Broker (Mosquitto)

- **Status:** active
- **Actief sinds:** Tue 2025-12-30 22:14:23 CET


### Git Repository

- **Branch:** main
- **Laatste commit:** e027865 feat: reboot monitoring met hardware watchdog voor alle Pi's
- **Uncommitted changes:** 2 bestanden


### Python Scripts

| Script | Pad | Beschrijving |
|--------|-----|--------------|
| baseline_learner.py | `/home/ronny/emsn2/scripts/anomaly/baseline_learner.py` | ... |
| data_gap_checker.py | `/home/ronny/emsn2/scripts/anomaly/data_gap_checker.py` | ... |
| hardware_checker.py | `/home/ronny/emsn2/scripts/anomaly/hardware_checker.py` | ... |
| birdnet_archive_sync.py | `/home/ronny/emsn2/scripts/archive/birdnet_archive_sync.py` | ... |
| fast_berging_sync.py | `/home/ronny/emsn2/scripts/archive/fast_berging_sync.py` | Fast Berging Sync - Bulk rsync per direc... |
| __init__.py | `/home/ronny/emsn2/scripts/atmosbird/__init__.py` | EMSN 2.0 - AtmosBird Scripts... |
| atmosbird_analysis.py | `/home/ronny/emsn2/scripts/atmosbird/atmosbird_analysis.py` | AtmosBird Advanced Analysis Script... |
| atmosbird_archive_sync.py | `/home/ronny/emsn2/scripts/atmosbird/atmosbird_archive_sync.py` | ... |
| atmosbird_capture.py | `/home/ronny/emsn2/scripts/atmosbird/atmosbird_capture.py` | AtmosBird Sky Capture Script... |
| atmosbird_timelapse.py | `/home/ronny/emsn2/scripts/atmosbird/atmosbird_timelapse.py` | AtmosBird Timelapse Generator... |
| climate_control.py | `/home/ronny/emsn2/scripts/atmosbird/climate_control.py` | ... |
| cloud_classifier_inference.py | `/home/ronny/emsn2/scripts/atmosbird/cloud_classifier_inference.py` | ... |
| create_timelapse.py | `/home/ronny/emsn2/scripts/atmosbird/create_timelapse.py` | ... |
| hardware_test.py | `/home/ronny/emsn2/scripts/atmosbird/hardware_test.py` | ... |
| backup_config.py | `/home/ronny/emsn2/scripts/backup/backup_config.py` | EMSN 2.0 - SD Kaart Backup Configuratie... |
| sd_backup_cleanup.py | `/home/ronny/emsn2/scripts/backup/sd_backup_cleanup.py` | EMSN 2.0 - Backup Cleanup Script... |
| sd_backup_daily.py | `/home/ronny/emsn2/scripts/backup/sd_backup_daily.py` | EMSN 2.0 - Dagelijkse SD Kaart Backup... |
| sd_backup_database.py | `/home/ronny/emsn2/scripts/backup/sd_backup_database.py` | EMSN 2.0 - Uurlijkse Database Backup... |
| sd_backup_weekly.py | `/home/ronny/emsn2/scripts/backup/sd_backup_weekly.py` | ... |
| backup_cleanup.py | `/home/ronny/emsn2/scripts/backup_cleanup.py` | EMSN 2.0 - Backup Cleanup Script... |
| __init__.py | `/home/ronny/emsn2/scripts/core/__init__.py` | ... |
| config.py | `/home/ronny/emsn2/scripts/core/config.py` | ... |
| logging.py | `/home/ronny/emsn2/scripts/core/logging.py` | ... |
| mqtt.py | `/home/ronny/emsn2/scripts/core/mqtt.py` | ... |
| network.py | `/home/ronny/emsn2/scripts/core/network.py` | ... |
| database_mirror_sync.py | `/home/ronny/emsn2/scripts/database_mirror_sync.py` | EMSN 2.0 - Database Mirror Sync... |
| color_analyzer.py | `/home/ronny/emsn2/scripts/flysafe/color_analyzer.py` | ... |
| flysafe_scraper.py | `/home/ronny/emsn2/scripts/flysafe/flysafe_scraper.py` | ... |
| migration_alerts.py | `/home/ronny/emsn2/scripts/flysafe/migration_alerts.py` | FlySafe Migration Alerts... |
| migration_forecast.py | `/home/ronny/emsn2/scripts/flysafe/migration_forecast.py` | ... |

---

## 🏚️ Berging Pi (192.168.1.87)

### Systeem Informatie

| Eigenschap | Waarde |
|------------|--------|
| Hostname | emsn2-berging |
| IP Adres | 192.168.1.87 fd64:5d33:8fcf:e2ec:c541:a2d7:2db5:8c37 |
| OS | N/A |
| Kernel | 6.12.47+rpt-rpi-v8 |
| Uptime | up 4 days, 14 hours, 27 minutes |
| Online sinds | 2025-12-30 15:34:16 |

### Disk Usage

| Mount | Grootte | Gebruikt | Beschikbaar | Gebruik |
|-------|---------|----------|-------------|---------|
| / | 235G | 43G | 183G | 19% |
| /mnt/usb | 29G | 3.6G | 24G | 14% |
| /mnt/nas-docker | 3.5T | 24G | 3.5T | 1% |

### Systemd Services

| Service | Status | Staat | Beschrijving |
|---------|--------|-------|--------------|

### Systemd Timers

| Timer | Details |
|-------|---------|

### Git Repository

- **Branch:** main
- **Laatste commit:** 6e93d30 fix: weekly backup gebruikt USB schijf als temp (meer ruimte)
- **Uncommitted changes:** 26 bestanden


---

## 🗄️ NAS PostgreSQL Database (192.168.1.25)

### Database Overzicht

- **Database:** emsn
- **Grootte:** 427 MB
- **Laatste vogeldetectie:** 2026-01-04 05:36:10
- **Laatste health check:** 2026-01-04 06:01:04.905501

### Tabellen

| Tabel | Grootte | Kolommen | Rijen |
|-------|---------|----------|-------|
| ulanzi_notification_log | 154 MB | 9 | 282,933 |
| bird_detections | 113 MB | 26 | 111,100 |
| media_archive | 46 MB | 13 | 111,159 |
| system_health | 24 MB | 18 | 115,517 |
| service_status | 20 MB | 9 | 89,172 |
| network_status | 13 MB | 11 | 59,448 |
| weather_data | 12 MB | 24 | 56,059 |
| dual_detections | 7568 kB | 14 | 23,348 |
| atmosbird_climate | 6704 kB | 9 | 31,984 |
| performance_metrics | 6104 kB | 9 | 46,529 |
| species_reference | 2456 kB | 15 | 168 |
| nas_metrics | 2344 kB | 15 | 9,571 |
| timer_timeline | 1840 kB | 12 | 126 |
| sky_observations | 1720 kB | 13 | 3,257 |
| moon_observations | 1448 kB | 10 | 5,705 |
| mqtt_bridge_events | 752 kB | 7 | 2,377 |
| anomaly_check_log | 752 kB | 6 | 4,268 |
| ulanzi_screenshots | 592 kB | 8 | 857 |
| atmosbird_health | 544 kB | 12 | 3,276 |
| nestbox_media | 248 kB | 15 | 683 |
| nestbox_occupancy | 224 kB | 10 | 561 |
| xeno_canto_recordings | 168 kB | 9 | 600 |
| species_baselines | 136 kB | 13 | 61 |
| radar_observations | 128 kB | 10 | 181 |
| system_events | 128 kB | 11 | 2 |
| anomalies | 104 kB | 12 | 49 |
| timelapses | 104 kB | 14 | 102 |
| ulanzi_cooldown_status | 104 kB | 7 | 42 |
| vocalization_training | 80 kB | 14 | 14 |
| pending_reports | 80 kB | 17 | 4 |
| vocalization_model_versions | 80 kB | 10 | 6 |
| nestbox_events | 64 kB | 13 | 5 |
| milestones | 64 kB | 8 | 1 |
| species_rarity_cache | 56 kB | 5 | 119 |
| vocalization_confusion_matrix | 56 kB | 6 | 108 |
| iss_passes | 48 kB | 9 | 16 |
| nestboxes | 48 kB | 9 | 3 |
| atmosbird_climate_settings | 48 kB | 5 | 7 |
| star_brightness | 40 kB | 9 | 8 |
| nestbox_seasons | 32 kB | 19 | 0 |
| meteor_detections | 32 kB | 13 | 0 |
| daily_summary | 24 kB | 16 | 0 |
| mqtt_hourly_stats | 24 kB | 11 | 0 |
| sky_bird_correlations | 24 kB | 9 | 0 |
| correlation_cache | 16 kB | 11 | 0 |
| user_annotations | 16 kB | 9 | 0 |
| moon_phases | 16 kB | 5 | 0 |
| species_behavior_patterns | 16 kB | 10 | 0 |
| flock_detections | 16 kB | 10 | 0 |
| dynamic_rarity_scores | 16 kB | 10 | 0 |
| territory_analysis | 16 kB | 10 | 0 |
| migration_events | 16 kB | 11 | 0 |
| bat_detections | 8192 bytes | 14 | 0 |
| astronomical_events | 8192 bytes | 10 | 0 |
| mqtt_bridge_uptime | 0 bytes | 5 | 23 |
| daily_statistics | 0 bytes | 7 | 41 |
| station_comparison | 0 bytes | 5 | 2 |
| recent_activity | 0 bytes | 7 | 100 |
| timer_timeline_current | 0 bytes | 10 | 31 |
| active_anomalies | 0 bytes | 11 | 49 |
| pending_reports_active | 0 bytes | 12 | 0 |
| bird_weather_correlation | 0 bytes | 14 | 111,100 |
| anomaly_summary_24h | 0 bytes | 6 | 2 |
| v_climate_daily_stats | 0 bytes | 9 | 7 |
| v_climate_current | 0 bytes | 7 | 1 |
| v_nestbox_current_status | 0 bytes | 8 | 2 |
| v_nestbox_media_daily | 0 bytes | 6 | 161 |
| v_nestbox_sleep_analysis | 0 bytes | 7 | 138 |

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
