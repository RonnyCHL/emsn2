# EMSN 2.0 - Systeem Inventarisatie

**Gegenereerd:** 2025-12-28 06:00:10
**Script versie:** 1.2.0
**Gegenereerd op:** emsn2-zolder

---

## Samenvatting

| Systeem | Status | Uptime | IP Adres |
|---------|--------|--------|----------|
| Zolder Pi | ✅ Online | up 4 weeks, 4 days, 10 hours, 32 minutes | 192.168.1.178 |
| Berging Pi | ✅ Online | up 4 weeks, 4 days, 10 hours, 29 minutes | 192.168.1.87 |
| NAS Database | ❌ Offline | - | 192.168.1.25 |

### ⚠️ Gevonden Problemen

- ❌ **Zolder:** Service `●` is FAILED
- ❌ **Zolder:** Service `●` is FAILED
- ❌ **Zolder:** Service `●` is FAILED
- ❌ **Zolder:** Service `●` is FAILED
- ❌ **Zolder:** Service `●` is FAILED
- ❌ **Zolder:** Service `●` is FAILED
- ❌ **Zolder:** Service `●` is FAILED
- ❌ **Zolder:** Service `●` is FAILED
- ❌ **Zolder:** Service `●` is FAILED
- ❌ **Zolder:** Service `●` is FAILED
- ❌ **Berging:** Service `●` is FAILED
- ❌ **Berging:** Service `●` is FAILED
- ❌ **Berging:** Service `●` is FAILED
- ❌ **Database:** connection to server at "192.168.1.25", port 5433 failed: FATAL:  remaining connection slots are reserved for roles with the SUPERUSER attribute


### 🆕 Nieuwe Componenten Sinds Vorige Run

*Vergeleken met inventarisatie van: 2025-12-21T06:00:24.576358*

**Zolder - Nieuwe Services:**
- `nestbox-screenshot.service`
- `sd-backup-cleanup.service`
- `sd-backup-database.service`

**Zolder - Nieuwe Timers:**
- `birdnet-archive-sync.timer`
- `database-backup.timer`
- `nestbox-screenshot.timer`
- `sd-backup-cleanup.timer`
- `sd-backup-daily.timer`
- `sd-backup-database.timer`
- `sd-backup-weekly.timer`

**Zolder - Nieuwe Scripts:**
- `/home/ronny/emsn2/scripts/archive/birdnet_archive_sync.py`
- `/home/ronny/emsn2/scripts/archive/fast_berging_sync.py`
- `/home/ronny/emsn2/scripts/atmosbird/atmosbird_archive_sync.py`
- `/home/ronny/emsn2/scripts/backup/backup_config.py`
- `/home/ronny/emsn2/scripts/backup/sd_backup_cleanup.py`
- `/home/ronny/emsn2/scripts/backup/sd_backup_daily.py`
- `/home/ronny/emsn2/scripts/backup/sd_backup_database.py`
- `/home/ronny/emsn2/scripts/backup/sd_backup_weekly.py`
- `/home/ronny/emsn2/scripts/homer_stats_update.py`
- `/home/ronny/emsn2/scripts/maintenance/database_backup.py`
- `/home/ronny/emsn2/scripts/maintenance/database_cleanup.py`
- `/home/ronny/emsn2/scripts/maintenance/system_health_check.py`
- `/home/ronny/emsn2/scripts/monitoring/network_monitor.py`
- `/home/ronny/emsn2/scripts/nas_metrics_collector.py`
- `/home/ronny/emsn2/scripts/nestbox/nestbox_occupancy_detector.py`
- `/home/ronny/emsn2/scripts/vocalization/vocalization_classifier.py`
- `/home/ronny/emsn2/scripts/vocalization/vocalization_enricher.py`

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
| Uptime | up 4 weeks, 4 days, 10 hours, 32 minutes |
| Online sinds | 2025-11-25 19:28:01 |
| Load Average | 1.62 1.63 1.63 |

### Disk Usage

| Mount | Grootte | Gebruikt | Beschikbaar | Gebruik |
|-------|---------|----------|-------------|---------|
| / | 235G | 35G | 191G | 16% |
| /mnt/usb | 29G | 191M | 27G | 1% |
| /mnt/nas-reports | 3.5T | 24G | 3.5T | 1% |
| /mnt/nas-docker | 3.5T | 24G | 3.5T | 1% |

### Systemd Services

| Service | Status | Staat | Beschrijving |
|---------|--------|-------|--------------|
| avahi-alias@emsn2-zolder.local.service | ✅ active | running | Publish emsn2/zolder.local as alias for emsn2-zold... |
| backup-cleanup.service | ⚪ inactive | dead | EMSN Backup Cleanup Service... |
| birdnet-mqtt-publisher.service | ✅ active | running | EMSN BirdNET MQTT Publisher... |
| birdnet_analysis.service | ✅ active | running | BirdNET Analysis... |
| birdnet_log.service | ✅ active | running | BirdNET Analysis Log... |
| birdnet_recording.service | ✅ active | running | BirdNET Recording... |
| birdnet_stats.service | ✅ active | running | BirdNET Stats... |
| dpkg-db-backup.service | ⚪ inactive | dead | Daily dpkg database backup service... |
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
| mqtt-bridge-monitor.service | ✅ active | running | EMSN MQTT Bridge Monitor... |
| mqtt-failover.service | ⚪ inactive | dead | EMSN MQTT Failover Check... |
| nestbox-screenshot.service | ⚪ inactive | dead | Nestkast Screenshot Capture... |
| screenshot-cleanup.service | ⚪ inactive | dead | EMSN Screenshot Cleanup Service... |
| sd-backup-cleanup.service | ⚪ inactive | dead | EMSN Backup Cleanup (verwijder oude backups)... |
| sd-backup-database.service | ⚪ inactive | dead | EMSN Database Uurlijkse Backup... |
| sync-birdnet-nas.service | ⚪ inactive | dead | Sync BirdNET database naar NAS voor vocalisatie tr... |
| ulanzi-bridge.service | ✅ active | running | EMSN Ulanzi Bridge Service... |
| ulanzi-screenshot-server.service | ✅ active | running | EMSN Ulanzi Screenshot HTTP Server... |
| ulanzi-screenshot.service | ✅ active | running | EMSN Ulanzi Screenshot Service... |

### Systemd Timers

| Timer | Details |
|-------|---------|
| lifetime-sync.timer | Sun 2025-12-28 06:00:06 CET                1s Sun 2025-12-28 05:55:26 CET 4min 3... |
| nestbox-screenshot.timer | Sun 2025-12-28 06:00:38 CET               33s Sun 2025-12-28 05:00:47 CET    59m... |
| hardware-monitor.timer | Sun 2025-12-28 06:01:00 CET               55s Sun 2025-12-28 06:00:00 CET       ... |
| mqtt-failover.timer | Sun 2025-12-28 06:03:15 CET          3min 10s Sun 2025-12-28 05:58:15 CET 1min 4... |
| dual-detection.timer | Sun 2025-12-28 06:03:25 CET          3min 20s Sun 2025-12-28 05:58:25 CET 1min 3... |
| emsn-dbmirror-zolder.timer | Sun 2025-12-28 06:04:35 CET          4min 30s Sun 2025-12-28 05:59:35 CET      2... |
| sd-backup-database.timer | Sun 2025-12-28 06:15:00 CET             14min Sun 2025-12-28 05:15:00 CET    45m... |
| birdnet-archive-sync.timer | Sun 2025-12-28 06:15:05 CET             15min Sun 2025-12-28 05:19:59 CET    40m... |
| flysafe-radar-day.timer | Sun 2025-12-28 10:00:00 CET          3h 59min Sun 2025-12-28 06:00:00 CET       ... |
| flysafe-radar-night.timer | Sun 2025-12-28 22:00:00 CET               15h Sun 2025-12-28 04:00:00 CET  2h 0m... |
| dpkg-db-backup.timer | Mon 2025-12-29 00:00:00 CET               17h Sun 2025-12-28 00:00:00 CET       ... |
| sync-birdnet-nas.timer | Mon 2025-12-29 02:00:00 CET               19h Sun 2025-12-28 02:00:00 CET  4h 0m... |
| database-backup.timer | Mon 2025-12-29 02:02:39 CET               20h Sun 2025-12-28 02:02:30 CET 3h 57m... |
| sd-backup-daily.timer | Mon 2025-12-29 02:03:44 CET               20h Sun 2025-12-28 02:01:20 CET 3h 58m... |
| sd-backup-cleanup.timer | Mon 2025-12-29 02:30:00 CET               20h Sun 2025-12-28 02:30:00 CET 3h 30m... |
| screenshot-cleanup.timer | Mon 2025-12-29 03:00:00 CET               20h Sun 2025-12-28 03:00:00 CET  3h 0m... |
| rarity-cache.timer | Mon 2025-12-29 04:04:22 CET               22h Sun 2025-12-28 04:01:10 CET 1h 58m... |
| emsn-weekly-report.timer | Mon 2025-12-29 07:00:00 CET               24h Mon 2025-12-22 07:00:00 CET   5 da... |
| emsn-monthly-report.timer | Thu 2026-01-01 08:00:00 CET            4 days -                                 ... |
| emsn-yearly-report.timer | Fri 2026-01-02 08:00:00 CET            5 days -                                 ... |
| anomaly-baseline-learn.timer | Sun 2026-01-04 03:00:00 CET            6 days Sun 2025-12-28 03:00:00 CET  3h 0m... |
| sd-backup-weekly.timer | Sun 2026-01-04 03:07:02 CET            6 days Sun 2025-12-28 03:03:02 CET 2h 57m... |
| backup-cleanup.timer | Sun 2026-01-04 04:02:39 CET            6 days Sun 2025-12-28 04:01:41 CET 1h 58m... |
| emsn-seasonal-report-winter.timer | Sun 2026-03-01 07:00:00 CET   2 months 2 days -                                 ... |
| emsn-seasonal-report-spring.timer | Mon 2026-06-01 07:00:00 CEST  5 months 2 days -                                 ... |
| emsn-seasonal-report-summer.timer | Tue 2026-09-01 07:00:00 CEST  8 months 3 days -                                 ... |
| emsn-seasonal-report-autumn.timer | Tue 2026-12-01 07:00:00 CET  11 months 3 days -                                 ... |
| anomaly-datagap-check.timer | -                                           - Sat 2025-12-27 23:28:13 CET       ... |
| anomaly-hardware-check.timer | -                                           - Sat 2025-12-27 23:28:13 CET       ... |

### MQTT Broker (Mosquitto)

- **Status:** active
- **Actief sinds:** Sun 2025-12-28 05:43:18 CET


### Git Repository

- **Branch:** main
- **Laatste commit:** 0dc04fd feat: AtmosBird foto archivering naar NAS 8TB
- **Uncommitted changes:** 1 bestanden


### Python Scripts

| Script | Pad | Beschrijving |
|--------|-----|--------------|
| baseline_learner.py | `/home/ronny/emsn2/scripts/anomaly/baseline_learner.py` | ... |
| data_gap_checker.py | `/home/ronny/emsn2/scripts/anomaly/data_gap_checker.py` | ... |
| hardware_checker.py | `/home/ronny/emsn2/scripts/anomaly/hardware_checker.py` | ... |
| birdnet_archive_sync.py | `/home/ronny/emsn2/scripts/archive/birdnet_archive_sync.py` | ... |
| fast_berging_sync.py | `/home/ronny/emsn2/scripts/archive/fast_berging_sync.py` | Fast Berging Sync - Bulk rsync per direc... |
| atmosbird_analysis.py | `/home/ronny/emsn2/scripts/atmosbird/atmosbird_analysis.py` | AtmosBird Advanced Analysis Script... |
| atmosbird_archive_sync.py | `/home/ronny/emsn2/scripts/atmosbird/atmosbird_archive_sync.py` | ... |
| atmosbird_capture.py | `/home/ronny/emsn2/scripts/atmosbird/atmosbird_capture.py` | AtmosBird Sky Capture Script... |
| atmosbird_timelapse.py | `/home/ronny/emsn2/scripts/atmosbird/atmosbird_timelapse.py` | AtmosBird Timelapse Generator... |
| backup_config.py | `/home/ronny/emsn2/scripts/backup/backup_config.py` | EMSN 2.0 - SD Kaart Backup Configuratie... |
| sd_backup_cleanup.py | `/home/ronny/emsn2/scripts/backup/sd_backup_cleanup.py` | EMSN 2.0 - Backup Cleanup Script... |
| sd_backup_daily.py | `/home/ronny/emsn2/scripts/backup/sd_backup_daily.py` | EMSN 2.0 - Dagelijkse SD Kaart Backup... |
| sd_backup_database.py | `/home/ronny/emsn2/scripts/backup/sd_backup_database.py` | EMSN 2.0 - Uurlijkse Database Backup... |
| sd_backup_weekly.py | `/home/ronny/emsn2/scripts/backup/sd_backup_weekly.py` | ... |
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
| homer_stats_update.py | `/home/ronny/emsn2/scripts/homer_stats_update.py` | Homer Dashboard Stats Updater... |
| database_backup.py | `/home/ronny/emsn2/scripts/maintenance/database_backup.py` | ... |
| database_cleanup.py | `/home/ronny/emsn2/scripts/maintenance/database_cleanup.py` | ... |
| system_health_check.py | `/home/ronny/emsn2/scripts/maintenance/system_health_check.py` | ... |
| network_monitor.py | `/home/ronny/emsn2/scripts/monitoring/network_monitor.py` | EMSN Network Monitor - Bewaakt alle netw... |

---

## 🏚️ Berging Pi (192.168.1.87)

### Systeem Informatie

| Eigenschap | Waarde |
|------------|--------|
| Hostname | emsn2-berging |
| IP Adres | 192.168.1.87 fd64:5d33:8fcf:e2ec:c541:a2d7:2db5:8c37 |
| OS | N/A |
| Kernel | 6.12.47+rpt-rpi-v8 |
| Uptime | up 4 weeks, 4 days, 10 hours, 29 minutes |
| Online sinds | 2025-11-25 19:30:45 |

### Disk Usage

| Mount | Grootte | Gebruikt | Beschikbaar | Gebruik |
|-------|---------|----------|-------------|---------|
| / | 235G | 37G | 189G | 17% |
| /mnt/usb | 29G | 3.4G | 24G | 13% |
| /mnt/nas-docker | 3.5T | 24G | 3.5T | 1% |

### Systemd Services

| Service | Status | Staat | Beschrijving |
|---------|--------|-------|--------------|

### Systemd Timers

| Timer | Details |
|-------|---------|

### Git Repository

- **Branch:** main
- **Laatste commit:** 03eff2f feat: SD kaart backup & disaster recovery systeem
- **Uncommitted changes:** 1 bestanden


---

## 🗄️ NAS PostgreSQL Database (192.168.1.25)

**❌ Fout:** connection to server at "192.168.1.25", port 5433 failed: FATAL:  remaining connection slots are reserved for roles with the SUPERUSER attribute



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
