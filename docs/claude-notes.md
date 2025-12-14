# Claude Code Notities - EMSN Project

Geleerde lessen en belangrijke observaties voor toekomstige sessies.

## Netwerk & Infrastructuur

### NAS Proxy Beperkingen
- De NAS (192.168.1.25) draait nginx als reverse proxy
- **Probleem:** Statische files in subdirectories worden NIET automatisch geserveerd
- **Oplossing:** Maak een dedicated Python HTTP server op de Pi voor statische content
- Voorbeeld: Screenshot server op poort 8082 ipv via NAS proxy

### Systemd Service Herstart Loop
- Bij `Restart=always` met `RestartSec=10` kan een service in een herstart-loop komen
- **Probleem:** Port "Address already in use" als vorige instantie nog niet volledig gestopt is
- **Oplossing:**
  1. Gebruik `TCPServer.allow_reuse_address = True` via subclass
  2. `systemctl stop` + `systemctl reset-failed` + wacht voordat je herstart
  3. Check met `pgrep -f scriptname` of proces echt gestopt is

## Ulanzi TC001 / AWTRIX Light

### API Details
- IP: 192.168.1.11
- `/api/screen` retourneert array van 256 integers (32x8 pixels)
- Elke integer is RGB packed: `color = (R << 16) | (G << 8) | B`
- Unpack met: `r = (color >> 16) & 0xFF`, etc.

### Screenshot Vergroting
- Native resolutie: 32x8 pixels (te klein om te lezen)
- Gebruik `Image.NEAREST` bij resize voor pixel-perfect scaling
- 10x schaling (320x80) is goed leesbaar

### Screenshot Timing
- Tekst scrollt van rechts naar links op de Ulanzi
- Bij `scroll_speed=80` duurt het ~1.5-2 seconden voordat vogelnaam zichtbaar is
- **Geteste delays:**
  - 0.5s = te vroeg (alleen station-prefix zichtbaar: "BERGING-I")
  - 4.0s = te laat (notificatie kan al voorbij zijn, toont klok)
  - **2.5s = optimaal** - vogelnaam zichtbaar, notificatie nog actief

## Database (PostgreSQL)

### Cooldown Tabel Structuur
De `ulanzi_cooldown_status` tabel heeft:
- `species_nl` (UNIQUE) - Nederlandse soortnaam
- `expires_at` - Timestamp wanneer cooldown verloopt
- `cooldown_seconds` - De toegepaste cooldown (kan smart-adjusted zijn)

### Tijd Formatting in SQL
Voor HH:MM:SS weergave van interval:
```sql
TO_CHAR((expires_at - NOW()), 'HH24:MI:SS')
TO_CHAR((seconds || ' seconds')::interval, 'HH24:MI:SS')
```

## Grafana

### Plugin Problemen Vermijden
- **`marcusolsson-dynamictext-panel`** is vaak niet geïnstalleerd
- Gebruik in plaats daarvan standaard `text` panel met `mode: "markdown"`
- Markdown ondersteunt afbeeldingen: `[![alt](url)](url)`
- Links werken gewoon: `[tekst](url)`

### Tijdzone Correctie in Queries
- Database slaat timestamps op in UTC
- Voor lokale tijd in output: `timestamp AT TIME ZONE 'Europe/Amsterdam'`
- Voorbeeld: `TO_CHAR(timestamp AT TIME ZONE 'Europe/Amsterdam', 'HH24:MI:SS')`

### Nederlandse Labels in SQL
- Gebruik `CASE WHEN` voor vertalingen:
```sql
CASE rarity_tier
  WHEN 'abundant' THEN 'Algemeen'
  WHEN 'common' THEN 'Gewoon'
  WHEN 'uncommon' THEN 'Ongewoon'
  WHEN 'rare' THEN 'Zeldzaam'
  WHEN 'legendary' THEN 'Legendarisch'
END as "Zeldzaamheid"
```

### Image in Table
- Gebruik `custom.cellOptions.type: "image"` voor inline afbeeldingen
- URL moet volledig pad zijn (http://...)

### Heatmap voor Tijdreeksen
- Goede visualisatie voor activiteit per soort over tijd
- Gebruik `date_trunc('hour', timestamp)` voor aggregatie

### Dashboard API Update
```bash
cat dashboard.json | jq '{dashboard: ., overwrite: true}' | \
  curl -s -X POST -H "Content-Type: application/json" \
  -u "admin:password" -d @- "http://host:3000/api/dashboards/db"
```

### Provisioned Dashboards
- **Wat zijn ze?** Dashboards die automatisch uit JSON-bestanden geladen worden
- **Locatie:** `/mnt/nas-docker/grafana/dashboards/` (bij ons)
- **Probleem:** `"Cannot save provisioned dashboard"` bij API updates
- **Oplossing:** JSON-bestanden direct aanpassen met `sudo`, dan herladen:
```bash
# Herlaad provisioned dashboards zonder restart
curl -X POST -u "admin:password" \
  "http://host:3000/api/admin/provisioning/dashboards/reload"
```
- **Voordeel:** Dashboards in versiebeheer, reproduceerbaar

### Dashboard Vertalingen met Python
Bij veel tekst-vervangingen is `sed` gevaarlijk (kan JSON breken).
Gebruik Python voor veilige JSON-manipulatie:
```python
import json

def translate_recursive(obj, translations):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == 'title' and value in translations:
                obj[key] = translations[value]
            else:
                translate_recursive(value, translations)
    elif isinstance(obj, list):
        for item in obj:
            translate_recursive(item, translations)
```

## MQTT

### Retained Messages
- Gebruik `retain=True` voor status topics die HA moet onthouden
- Handig voor sensoren die niet constant updaten

### Meerdere Publishers
- Let op dat er niet meerdere scripts naar dezelfde topics schrijven
- Consolideer naar één publisher service per topic-groep

## Smart Cooldown Systeem

### Multiplier Logica
- **Lagere multiplier = kortere cooldown = MEER notificaties**
- Voorbeeld berekening: `base * time * season * weekend`
- Altijd clampen tussen min/max om extreme waarden te voorkomen

### Tijdsperiodes
```
Dawn:      05:00-08:00  (ochtendkoor, veel activiteit)
Morning:   08:00-12:00
Afternoon: 12:00-17:00  (baseline)
Evening:   17:00-20:00  (avondactiviteit)
Night:     20:00-05:00  (uilen, minder algemeen)
```

## Best Practices

### Service Dependencies
Altijd `After=` en `Wants=` gebruiken voor afhankelijkheden:
```ini
After=network.target mnt-nas\x2dreports.mount
Wants=network-online.target
```

### Cleanup Jobs
- Gebruik timer (niet cron) voor systemd omgevingen
- Draai cleanup jobs 's nachts (03:00)
- Verwijder ook orphaned database records

---
*Laatst bijgewerkt: 14 december 2025*
