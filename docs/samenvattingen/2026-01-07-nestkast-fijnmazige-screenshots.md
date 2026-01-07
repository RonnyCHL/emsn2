# Sessie Samenvatting - 7 januari 2026

## Nestkast Fijnmazige Screenshots & Tijdlijn Dashboard

### Wijzigingen

#### 1. Screenshot Interval (5 minuten)
De nestbox-screenshot.timer is aangepast van elk uur naar elke 5 minuten voor fijnmazigere tracking van Koolmees aankomst/vertrek tijden.

**Bestand:** `/etc/systemd/system/nestbox-screenshot.timer`
```ini
[Timer]
OnCalendar=*-*-* *:00,05,10,15,20,25,30,35,40,45,50,55:00
Persistent=true
RandomizedDelaySec=30
```

**Opslagberekening:**
- 288 screenshots/dag/nestkast × 3 nestkasten × 35KB = ~30MB/dag
- ~10GB/jaar met 6.4TB beschikbaar op NAS

#### 2. Dashboard Update - Slaapplaats Status
Alle drie nestkast status panels hebben nu "slaapplaats" status mapping:
- Kleur: semi-dark-purple
- Icoon: 🌙 Slaapplaats

#### 3. Nieuw Panel - Aankomst/Vertrek Tijdlijn
Tabel panel toegevoegd die alle slaapplaats, bezet en leeg events toont:
- Tijdstip (DD-MM-YYYY HH:MI)
- Nestkast
- Status
- Soort

**SQL Query:**
```sql
SELECT TO_CHAR(event_timestamp, 'DD-MM-YYYY HH24:MI') as tijdstip,
       INITCAP(nestbox_id) as nestkast,
       event_type as status,
       COALESCE(species, '-') as soort
FROM nestbox_events
WHERE event_type IN ('slaapplaats', 'leeg', 'bezet')
  AND $__timeFilter(event_timestamp)
ORDER BY event_timestamp DESC
```

### Technische Notities

**Grafana Provisioning vs Database:**
Omdat `allowUiUpdates: true` staat in de provisioning config, heeft de database versie voorrang. Dashboard wijzigingen moeten via de Grafana API gedaan worden:

```bash
# Dashboard ophalen
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://192.168.1.25:3000/api/dashboards/uid/emsn-nestkast-monitoring"

# Dashboard opslaan
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dashboard": {...}, "overwrite": true}' \
  "http://192.168.1.25:3000/api/dashboards/db"
```

### Huidige Status
- Koolmees slaapt 's nachts in nestkast "midden"
- AI detectie draait elk uur
- Screenshots elke 5 minuten voor fijnmazige tracking
- Dashboard toont aankomst/vertrek tijdlijn

### Volgende Stappen
- Observeren of 5-minuten interval genoeg detail geeft
- Na enkele dagen: eerste analyse van aankomst/vertrek patronen
