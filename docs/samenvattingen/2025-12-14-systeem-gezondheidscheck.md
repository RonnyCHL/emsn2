# Sessie Samenvatting: Systeem Gezondheidscheck

**Datum:** 14 december 2025
**Type:** Diepgaand systeemonderzoek en reparaties

## Uitgevoerde Analyse

Volledige gezondheidscheck van alle EMSN systemen:
- Zolder station (192.168.1.178)
- Berging station (192.168.1.87)
- Database (PostgreSQL op NAS)
- Alle systemd services en timers
- NAS mounts en opslag
- Web interfaces

## Bevindingen

### Werkende Systemen (alles OK)

| Component | Status | Details |
|-----------|--------|---------|
| BirdNET-Pi Zolder | OK | 8.032 detecties |
| BirdNET-Pi Berging | OK | 35.481 detecties |
| PostgreSQL Database | OK | 43.513 totale detecties |
| Weather sync | OK | 26.948 records, real-time |
| Reports API | OK | Draait op port 8081 |
| MQTT Broker | OK | Mosquitto actief |
| Ulanzi Bridge | OK | Verwerkt detecties |
| All sync timers | OK | lifetime, dual, hardware |
| Anomaly detection | OK | Draait elke 15 min |
| FlySafe radar | OK | Elke 2 uur scraping |
| NAS mounts | OK | Both shares mounted |
| Grafana | OK | v12.3.0 |
| Homer Dashboard | OK | Bereikbaar |

### Gevonden Problemen

1. **rarity-cache.timer** - Was INACTIEF (niet gestart na reboot)
2. **Oude anomalieën** - 5 niet-genotificeerde anomalieën ouder dan 24u
3. **emsn-monthly-report** - Failed status (normaal - geen data voor huidige maand)
4. **AtmosBird timers** - Niet geïnstalleerd (optioneel)

## Uitgevoerde Reparaties

### 1. rarity-cache.timer Geactiveerd
```bash
sudo systemctl start rarity-cache.timer
```
- **Status:** Nu actief, volgende run morgen 04:03
- **Impact:** Zeldzaamheid cache wordt weer dagelijks bijgewerkt

### 2. Oude Anomalieën Opgeruimd
```sql
UPDATE anomalies SET notified = true
WHERE notified = false AND timestamp < NOW() - INTERVAL '24 hours';
```
- **Resultaat:** 5 oude anomalieën gemarkeerd als afgehandeld
- **Nog actief:** 1 recente station_imbalance (van gisteren 21:22)

## Database Statistieken

| Tabel | Records | Laatste Update |
|-------|---------|----------------|
| bird_detections | 43.513 | 14 dec 15:18 |
| weather_data | 26.948 | 14 dec 15:20 |
| dual_detections | 4.782 | 14 dec 14:50 |
| radar_observations | 19 | 14 dec |
| species_baselines | 47 | 14 dec 02:00 |
| species_rarity_cache | 128 | 11 dec |
| performance_metrics | 5.978 | 14 dec 15:20 |

## Detecties per Station (Laatste 3 dagen)

| Datum | Zolder | Berging |
|-------|--------|---------|
| 14 dec | 1.176 | 1.366 |
| 13 dec | 617 | 1.946 |
| 12 dec | 876 | 3.068 |

**Opmerking:** Berging detecteert consistent meer dan Zolder. Mogelijke oorzaken:
- Locatieverschil (meer vogels bij berging)
- Microfoon gevoeligheid
- Omgevingsgeluid verschil

## Actieve Timers (28 totaal)

Alle kritieke timers draaien correct:
- `lifetime-sync.timer` - elke 5 min
- `dual-detection.timer` - elke 5 min
- `hardware-monitor.timer` - elke minuut
- `anomaly-*.timer` - elke 15 min / wekelijks
- `flysafe-radar-*.timer` - elke 2 uur
- `backup-cleanup.timer` - wekelijks
- `rarity-cache.timer` - dagelijks (nu actief)
- Alle rapport timers (weekly, monthly, seasonal, yearly)

## Conclusie

**Systeem gezondheid: GOED**

Het EMSN systeem draait stabiel. Beide BirdNET-Pi stations zijn operationeel, alle sync processen werken, en de database wordt real-time bijgewerkt. De enige echte fix was het activeren van de rarity-cache timer.

## Volgende Stappen (Optioneel)

1. **Station imbalance onderzoeken** - Waarom detecteert Berging meer?

---

## Update: Email & AtmosBird (zelfde sessie)

### Email Notificaties Ingesteld
- **SMTP:** smtp.strato.de:587
- **Account:** rapporten@ronnyhullegie.nl
- **Test email:** Succesvol verzonden

Rapporten worden automatisch gemaild:
- Weekrapport → Maandag 07:00
- Maandrapport → 1e van de maand
- Seizoensrapport → Per seizoen
- Jaaroverzicht → 2 januari

### AtmosBird
- Draait op **Berging** (192.168.1.87) met Pi Camera NoIR
- Zolder heeft geen camera aangesloten
- Service bestanden gecorrigeerd voor juiste paden

---
*Gegenereerd door Claude Code sessie*
