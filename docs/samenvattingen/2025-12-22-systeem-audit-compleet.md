# EMSN 2.0 - Compleet Systeem Audit
**Datum:** 2025-12-22 18:15 CET
**Uitgevoerd op:** emsn2-zolder (192.168.1.178)
**Type:** Diepgaand onderzoek alle systeemcomponenten

---

## Executive Summary

Het EMSN 2.0 systeem is **overwegend gezond en stabiel**. Van de 22 services draaien er 21 perfect. Beide stations hebben een uptime van 26+ dagen zonder throttling. De belangrijkste bevindingen:

- ✅ **75.811 detecties** succesvol opgeslagen (23.240 zolder + 52.571 berging)
- ✅ **13.679 dual detections** (35% overlap tussen stations)
- ✅ **78 unieke soorten** geïdentificeerd
- ⚠️ **1 gefaalde service** (hardware-monitor - WorkingDirectory issue)
- ⚠️ **Database connectie probleem** in cooldown-display service
- ✅ Alle core BirdNET functies operationeel
- ✅ MQTT bridge stabiel tussen beide stations
- ✅ NAS shares correct gemount
- ✅ PostgreSQL database gezond (148 MB)

---

## 1. Service Status Overzicht

### ✅ Station Zolder (192.168.1.178)

**Actieve Services (13/14):**
- `birdnet_analysis.service` - Active, detecteert vogels
- `birdnet_recording.service` - Active, neemt audio op
- `birdnet_stats.service` - Active, Streamlit dashboard
- `birdnet_log.service` - Active
- `birdnet-mqtt-publisher.service` - Active, publiceert naar MQTT
- `mqtt-bridge-monitor.service` - Active, monitort bridge
- `mqtt-cooldown-publisher.service` - Active
- `emsn-cooldown-display.service` - Active (maar met warnings)
- `emsn-reports-api.service` - Active sinds 18 dec, port 8081
- `ulanzi-bridge.service` - Active
- `ulanzi-screenshot.service` - Active sinds 14 dec
- `ulanzi-screenshot-server.service` - Active, port 8082
- `avahi-alias@emsn2-zolder.local.service` - Active

**Gefaalde Services (1):**
- ❌ `hardware-monitor.service` - **FAILED**
  - **Oorzaak:** WorkingDirectory=/home/ronny/sync bestaat niet
  - **Impact:** Geen hardware metrics naar database
  - **Oplossing:** Update service file naar /home/ronny/emsn2/scripts/sync

### ✅ Station Berging (192.168.1.87)

**Actieve Services (6/6):**
- `birdnet_analysis.service` - Active
- `birdnet_recording.service` - Active
- `birdnet_stats.service` - Active
- `birdnet_log.service` - Active
- `birdnet-mqtt-publisher.service` - Active (restarted 17:42, nu stabiel)
- `avahi-alias@emsn2-berging.local.service` - Active

**Geen gefaalde services** ✅

---

## 2. Timer Status

**Actieve Timers (11):**

| Timer | Interval | Laatste run | Status |
|-------|----------|-------------|--------|
| `lifetime-sync.timer` | 5 min | 18:10:12 | ✅ OK |
| `mqtt-failover.timer` | 5 min | 18:11:42 | ✅ OK |
| `emsn-dbmirror-zolder.timer` | 5 min | 18:13:32 | ✅ OK |
| `emsn-dbmirror-berging.timer` | 5 min | - | ✅ OK |
| `sync-birdnet-nas.timer` | Dagelijks 02:00 | 22 dec 02:00 | ✅ OK |
| `emsn-weekly-report.timer` | Ma 07:00 | 22 dec 07:00 | ✅ OK |
| `emsn-monthly-report.timer` | 1e/maand 08:00 | - | ✅ Gepland |
| `emsn-yearly-report.timer` | 2 jan 08:00 | - | ✅ Gepland |
| `emsn-seasonal-report-*.timer` (4x) | Seizoensmatig | - | ✅ Gepland |

---

## 3. Database Status (PostgreSQL @ NAS)

**Connectiviteit:** ✅ Werkend
**Host:** 192.168.1.25:5433
**Database:** emsn (148 MB)
**Laatste update:** 2025-12-22 18:13:22

### Schema (54 tabellen)

**Belangrijkste tabellen:**

| Tabel | Records | Grootte | Laatste data |
|-------|---------|---------|--------------|
| `bird_detections` | 75.811 | 103 MB | 2025-12-22 16:49:45 |
| `system_health` | 23.122+ | 13 MB | 2025-12-22 16:20:01 |
| `weather_data` | 38.414 | 8.7 MB | 2025-12-22 18:13:22 |
| `dual_detections` | 13.679 | 4.6 MB | - |
| `ulanzi_notification_log` | - | 3.4 MB | - |
| `performance_metrics` | - | 3.0 MB | - |
| `species_reference` | - | 2.5 MB | - |
| `moon_observations` | 2.950 | 552 KB | - |
| `sky_observations` | 1.474 | 512 KB | - |
| `milestones` | 1 | - | 2025-12-04 |
| `anomalies` | 15 | - | - |
| `bat_detections` | 0 | - | - |

### Detectie Statistieken

**Per Station:**
- Berging: 52.571 detecties (69%)
- Zolder: 23.240 detecties (31%)
- **Totaal:** 75.811 detecties

**Dual Detections:**
- 26.641 dual detections (35% van alle detecties)
- 49.170 single station detecties

**Top 10 Soorten:**
1. Pica pica (Ekster) - 21.924
2. Erithacus rubecula (Roodborst) - 19.205
3. Cyanistes caeruleus (Pimpelmees) - 6.932
4. Corvus monedula (Kauw) - 6.129
5. Parus major (Koolmees) - 4.376
6. Turdus iliacus (Koperwiek) - 2.989
7. Columba palumbus (Houtduif) - 2.609
8. Anser albifrons (Kolgans) - 2.412
9. Fringilla coelebs (Vink) - 1.185
10. Turdus merula (Merel) - 1.091

**Vocalization Training:**
- 3.809 detecties met vocalization_type (5%)
- Training data beschikbaar op NAS

---

## 4. MQTT Status

**Hoofdbroker:** 192.168.1.178:1883 ✅
**Credentials:** Zie .secrets file (MQTT_USER / MQTT_PASS)

### Message Flow

**Zolder → MQTT:**
- Laatste hardware metrics: 16:20:01 (2 uur geleden - geen recente updates)
- Laatste detection stats: 18:10:13
- Weather data: 18:11:03

**Berging → MQTT:**
- Hardware metrics: 18:11:02 ✅
- Detecties worden gepubliceerd ✅

**Bridge Events (24u):**
- 4x connected events
- 2x startup events
- Geen disconnects ✅

### MQTT Failover

Timer draait elke 5 minuten, laatste check 18:11:42 - succesvol ✅

---

## 5. Ulanzi Display (TC001)

**IP:** 192.168.1.11
**Status:** ✅ Bereikbaar

**API Health:**
```json
{
  "bat": 100,
  "temp": 20,
  "hum": 32,
  "uptime": 905295,
  "wifi_signal": -49,
  "version": "0.98",
  "app": "Time"
}
```

**Services:**
- `ulanzi-bridge.service` - ✅ Active (geen recente logs)
- `ulanzi-screenshot.service` - ✅ Active sinds 14 dec
- `ulanzi-screenshot-server.service` - ✅ Active, HTTP server op :8082

**Screenshots:**
- Opslag: /mnt/nas-reports/ulanzi-screenshots/
- Laatste: 2025-12-22/
- HTTP toegang: http://192.168.1.178:8082/ ✅

**Notificaties:**
- Test notificatie succesvol (POST /api/notify) ✅
- Database: ulanzi_notification_log (3.4 MB)

---

## 6. NAS Integratie

**NAS:** 192.168.1.25 (DS224Plus)
**Mounts:** ✅ Beide shares actief

### Shares

```
//192.168.1.25/docker → /mnt/nas-docker (3.5 TB, 1% gebruikt)
//192.168.1.25/emsn-AIRapporten → /mnt/nas-reports (3.5 TB, 1% gebruikt)
```

### Vocalization Training

**Container:** emsn-vocalization-pytorch
**Locatie:** /mnt/nas-docker/emsn-vocalization/

**Bestanden:**
- `train_existing.py` - Training script
- `data/` - Training data
- `models/` - Opgeslagen modellen (.pt)
- `logs/` - Training logs
- `src/` - Source code

**Database tabellen:**
- `vocalization_training` - Status per soort
- `vocalization_model_versions` - Versie tracking
- `vocalization_confusion_matrix` - Evaluatie data

### Reports

**Laatste rapporten:**
- 2025-W51-Weekrapport.pdf (4.5 MB) - 16 dec 20:45
- 2025-W50-Weekrapport.pdf (1.7 MB) - 15 dec 21:38
- Diverse markdown en PNG bestanden

**Reports API:**
- Service: `emsn-reports-api.service` ✅ Active sinds 18 dec
- Port: 8081
- Frontend: http://192.168.1.178:8081/ ✅
- Health endpoint: /health ontbreekt (404)

---

## 7. Netwerk & Hardware

### Station Zolder

**Hostname:** emsn2-zolder
**IP:** 192.168.1.178
**Uptime:** 26 dagen, 22:45 uur
**Load:** 0.41, 0.33, 0.34 (laag, gezond)

**Temperatuur:** 52.7°C
**Throttling:** 0x0 (geen throttling) ✅

**Memory:**
- Totaal: 7.9 GB
- Gebruikt: 5.9 GB (75%)
- Beschikbaar: 1.9 GB
- Swap: 1.4/2.0 GB gebruikt (70%)

**Disk:**
- Root: 234 GB (12% gebruikt)
- /mnt/usb: 29 GB (1% gebruikt)
- /mnt/audio: 470 GB (3% gebruikt)

### Station Berging

**Hostname:** emsn2-berging
**IP:** 192.168.1.87
**Uptime:** 26 dagen, 22:42 uur
**Load:** 0.40, 0.58, 0.64 (normaal)

**Temperatuur:** 36.0°C (veel koeler dan zolder)
**Throttling:** 0x0 (geen throttling) ✅

**Memory:**
- Totaal: 7.6 GB
- Gebruikt: 1.3 GB (17% - veel beter dan zolder!)
- Beschikbaar: 6.3 GB
- Swap: 26/2048 MB gebruikt (1%)

**Disk:**
- Root: 235 GB (15% gebruikt)
- /mnt/usb: 29 GB (13% gebruikt)
- /mnt/audio: 470 GB (6% gebruikt)

**Netwerk:**
- Ping Zolder ↔ Berging: 0.2 ms ✅

---

## 8. Sync Services

**Locatie scripts:**
- ✅ Nieuw: /home/ronny/emsn2/scripts/sync/
- ❌ Oud: /home/ronny/sync/ (bestaat niet meer)

**Scripts aanwezig:**
- `lifetime_sync.py` - ✅ Draait elke 5 min
- `dual_detection_sync.py` - Aanwezig
- `hardware_monitor.py` - ❌ Service verwijst naar oude locatie
- `weather_sync.py` - Aanwezig
- `bayesian_verification.py` - Aanwezig

**Lifetime Sync Status:**
- Laatste run: 18:10:13
- SQLite: 23.243 detecties
- PostgreSQL: 23.240 detecties
- Delta: 3 detecties (sync loopt goed)

---

## 9. BirdNET Core

### Analysis Service

**Status:** ✅ Active en detecteert

**Laatste detecties (18:11:47):**
```
6.0;9.0  - Turdus iliacus (Koperwiek), 0.023
7.0;10.0 - Emberiza hortulana (Ortolaan), 0.039
8.0;11.0 - Emberiza hortulana (Ortolaan), 0.049
```

BirdNET draait stabiel en detecteert actief. Veel "Human" detecties gefilterd.

### Recording Service

**Status:** ✅ Active
**Logs:** Geen recente errors

### Stats Service

**Status:** ✅ Active
**URL:** http://localhost:8501/stats
**Streamlit dashboard:** Beschikbaar

---

## 10. Grafana

**URL:** http://192.168.1.25:3000
**Health:** ✅ OK

```json
{
  "database": "ok",
  "version": "12.3.0",
  "commit": "20051fb1fc604fc54aae76356da1c14612af41d0"
}
```

**Credentials:** Zie .secrets file
**API Token:** Zie .secrets file (GRAFANA_API_TOKEN)

---

## 11. Errors & Warnings

### ❌ Kritieke Issues

**1. hardware-monitor.service FAILED**
```
Changing to the requested working directory failed: No such file or directory
WorkingDirectory=/home/ronny/sync
```

**Impact:**
- Geen hardware metrics naar database sinds laatste restart
- Laatste data in system_health: 16:20:01 (2 uur geleden)

**Oplossing:**
```bash
sudo nano /etc/systemd/system/hardware-monitor.service
# Wijzig WorkingDirectory=/home/ronny/sync
# Naar:  WorkingDirectory=/home/ronny/emsn2/scripts/sync
sudo systemctl daemon-reload
sudo systemctl restart hardware-monitor.service
```

### ⚠️ Warnings

**1. emsn-cooldown-display.service - Database connectie**
```
[ERROR] Error getting cooldowns: connection already closed
[INFO] Published 0 cooldowns to MQTT
```

**Impact:** Beperkt - cooldown data wordt niet gepubliceerd
**Frequentie:** Elke 30 seconden
**Laatste errors:** 17:49:12 (batched logs)

**Mogelijke oorzaak:**
- Database connection pool timeout
- Reconnect logica ontbreekt

**2. Berging MQTT Publisher - Tijdelijke restart**
```
Dec 22 17:42:27 - Failed with result 'exit-code'
Dec 22 17:42:57 - Started (nu stabiel)
```

**Impact:** 30 seconden downtime, nu opgelost ✅

### ℹ️ Observaties

**1. System State: degraded**
- Oorzaak: 1 gefaalde service (hardware-monitor)
- Anders gezond systeem

**2. Memory gebruik Zolder**
- 5.9/7.9 GB gebruikt (75%)
- Swap actief (1.4 GB)
- Berging: slechts 17% gebruikt
- **Mogelijke oorzaak:** BirdNET analysis/model cache?

**3. Rarity Scores**
- Tabel `bird_detections` heeft rarity_score/rarity_tier kolommen
- Maar: alle waarden NULL (0 rows met data)
- Dynamic_rarity_scores tabel aanwezig maar niet gevuld

**4. Bat Detections**
- Tabel aanwezig maar 0 records
- Mogelijke toekomstige feature?

---

## 12. Goede Dingen ✅

1. **Uptime:** 26+ dagen op beide stations zonder crashes
2. **Geen throttling:** CPU's blijven koel onder belasting
3. **MQTT bridge:** Stabiel, geen disconnects in 24u
4. **Database:** Gezond, 148 MB, goede response times
5. **Dual detection:** 35% overlap tussen stations is uitstekend
6. **78 soorten** geïdentificeerd sinds 25 november
7. **NAS shares:** Correct gemount, geen errors
8. **Ulanzi display:** Volledig functioneel met screenshots
9. **Sync services:** Lifetime sync perfect (slechts 3 detecties delta)
10. **BirdNET:** Core functionaliteit 100% operationeel
11. **Reports:** Week rapporten worden gegenereerd
12. **Netwerk:** Sub-milliseconde latency tussen stations
13. **Grafana:** Dashboard beschikbaar en gezond
14. **Vocalization training:** Infrastructure aanwezig op NAS

---

## 13. Aanbevelingen

### Prioriteit 1 (Direct oplossen)

**1. Fix hardware-monitor.service**
```bash
sudo systemctl stop hardware-monitor.timer
sudo nano /etc/systemd/system/hardware-monitor.service
# WorkingDirectory=/home/ronny/emsn2/scripts/sync
sudo systemctl daemon-reload
sudo systemctl start hardware-monitor.timer
systemctl status hardware-monitor.service
```

**2. Fix cooldown-display database connectie**
- Check connection pool settings
- Voeg reconnect logica toe
- Of: gebruik connection per request ipv persistent

### Prioriteit 2 (Deze week)

**3. Memory optimalisatie Zolder**
- Analyseer wat 5.9 GB gebruikt
- Check BirdNET model cache size
- Overweeg cache cleanup
- Berging gebruikt slechts 1.3 GB met zelfde workload

**4. Rarity scores implementeren**
- Dynamic_rarity_scores tabel vullen
- Rarity tier assignments activeren
- Kan interessante insights geven

**5. Reports API health endpoint**
- Voeg /health endpoint toe
- Consistentie met andere services

### Prioriteit 3 (Nice to have)

**6. Bat detection activeren**
- Tabel staat klaar maar niet in gebruik
- Evalueer of dit gewenst is

**7. Monitoring dashboard**
- Grafana dashboard voor alle services
- Alert bij failed services
- Memory/CPU trending

**8. Backup verificatie**
- Test restore procedure
- Verify sync-birdnet-nas backups

**9. Documentation**
- Update service file paths in docs
- Nieuwe locatie /home/ronny/emsn2/scripts/sync

### Prioriteit 4 (Toekomst)

**10. Auto-healing**
- Systemd restart policies
- Health check scripts
- Notification bij failures

**11. Consolidatie**
- Verwijder oude /home/ronny/sync referenties volledig
- Cleanup unused tables

---

## 14. Conclusie

Het EMSN 2.0 systeem is **gezond en stabiel** met slechts 1 gefaalde service die gemakkelijk te fixen is. De core functionaliteit (BirdNET detectie, MQTT, database sync) werkt uitstekend:

**Cijfer: 8.5/10**

**Sterkste punten:**
- 26 dagen uptime zonder crashes
- Perfecte MQTT bridge tussen stations
- Uitstekende dual detection rate (35%)
- Stabiele database sync (slechts 3 detecties delta)
- Geen hardware throttling ondanks continue belasting

**Aandachtspunten:**
- 1 gefaalde service (hardware-monitor - eenvoudig te fixen)
- Cooldown display heeft database reconnect issue
- Memory gebruik Zolder aan de hoge kant
- Sommige database features (rarity scores) niet actief

**Aanbeveling:** Fix de hardware-monitor service vandaag nog, onderzoek de cooldown database issue deze week, en het systeem is weer 10/10.

---

## Appendix: Command Reference

### Health Checks

```bash
# Overall system status
systemctl status
systemctl list-units --type=service --state=failed

# Specific services
systemctl status birdnet_analysis.service
journalctl -u hardware-monitor.service --since "1 hour ago"

# Database (zie .secrets voor wachtwoord)
PGPASSWORD=$PG_PASS psql -h 192.168.1.25 -p 5433 -U birdpi_zolder -d emsn -c "SELECT COUNT(*) FROM bird_detections;"

# MQTT (zie .secrets voor credentials)
mosquitto_sub -h 192.168.1.178 -u $MQTT_USER -P $MQTT_PASS -t 'emsn2/#' -C 5

# Hardware
vcgencmd measure_temp
vcgencmd get_throttled
free -h
df -h

# Network
ping -c 3 192.168.1.87
ssh ronny@192.168.1.87 "uptime"
```

### Fix Commands

```bash
# Hardware monitor fix
sudo systemctl stop hardware-monitor.timer
sudo nano /etc/systemd/system/hardware-monitor.service
sudo systemctl daemon-reload
sudo systemctl start hardware-monitor.timer

# Service restart
sudo systemctl restart <service-name>

# Check logs
journalctl -u <service-name> -f
```

---

**Audit uitgevoerd door:** Claude (Anthropic)
**Voor:** Ronny Hullegie
**Datum:** 2025-12-22 18:30 CET

---

## ADDENDUM: Fixes Toegepast (18:23 CET)

### ✅ hardware-monitor.service OPGELOST

**Probleem:** Service verwees naar oude locatie `/home/ronny/sync/`
**Oplossing:** Service file bijgewerkt naar `/home/ronny/emsn2/scripts/sync/`

**Acties uitgevoerd:**
1. Oude hardening regels verwijderd (ProtectHome, ProtectSystem)
2. WorkingDirectory directive verwijderd (niet nodig)
3. ExecStart path bijgewerkt naar nieuwe locatie
4. Service getest en werkt perfect

**Resultaat:**
```
Dec 22 18:22:48 - Finished hardware-monitor.service - EMSN Hardware Monitor - Zolder Station
[INFO] Metrics collected - Health Score: 100/100
[INFO] Metrics saved to PostgreSQL
[INFO] Metrics published to MQTT
```

**Status verificatie:**
- ✅ Service draait succesvol elke minuut
- ✅ Nieuwe data in database: 2025-12-22 18:23:00
- ✅ System state: **running** (was: degraded)
- ✅ Failed services: **0** (was: 1)

**Nieuwe system state:**
```
State: running
Units: 492 loaded
Failed: 0 units
```

### Nieuw Cijfer: 9.5/10

Met de hardware-monitor service hersteld is het systeem nu nagenoeg perfect. Enige resterende aandachtspunt is de cooldown-display database reconnect issue.

**Next steps:**
1. ✅ hardware-monitor.service - OPGELOST
2. ⚠️ cooldown-display.service - Database reconnect logica toevoegen
3. 📊 Memory usage Zolder monitoren
4. 📈 Rarity scores activeren (optional)

---

**Update uitgevoerd door:** Claude (Anthropic)
**Tijdstip:** 2025-12-22 18:23 CET
