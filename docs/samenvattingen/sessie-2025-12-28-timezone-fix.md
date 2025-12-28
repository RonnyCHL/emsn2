# Sessie 2025-12-28: Timezone & Sync Fixes

## Problemen Opgelost

### 1. Grafana Tijden 1 Uur Verkeerd
- **Probleem:** Berging detecties toonden 21:23 terwijl het 20:23 was
- **Oorzaak:** Grafana interpreteerde `timestamp without time zone` als UTC en voegde +1 uur toe
- **Oplossing:** Query aangepast van `detection_timestamp as "Tijd"` naar `time::varchar as "Uur"` in Soorten Overzicht dashboard

### 2. Zolder Lifetime Sync Gestopt
- **Probleem:** Sync timer was disabled sinds 15:37, data liep 5+ uur achter
- **Oorzaak:** Service file miste `--station zolder` argument na script update
- **Oplossing:** 
  ```bash
  sudo sed -i 's|lifetime_sync.py|lifetime_sync.py --station zolder|' /etc/systemd/system/lifetime-sync.service
  sudo systemctl daemon-reload
  sudo systemctl enable --now lifetime-sync.timer
  ```

### 3. MQTT Bridge Offline
- **Probleem:** Dashboard toonde "Offline" voor MQTT Bridge
- **Oorzaak 1:** Bridge config miste authenticatie credentials
- **Oorzaak 2:** Dashboard query checkte op "geen disconnected events" ipv "laatste status is connected"
- **Oplossing:** 
  - Credentials toegevoegd aan `/etc/mosquitto/conf.d/bridge-berging.conf`
  - Dashboard query verbeterd om laatste event status te checken

## Bestanden Gewijzigd (buiten git)

| Bestand | Locatie | Wijziging |
|---------|---------|-----------|
| lifetime-sync.service | /etc/systemd/system/ | `--station zolder` toegevoegd |
| bridge-berging.conf | /etc/mosquitto/conf.d/ | Credentials toegevoegd |
| Soorten Overzicht | Grafana | Query tijd kolom aangepast |
| Systeem Overzicht | Grafana | MQTT Bridge query verbeterd |

## Geleerde Lessen

1. **Grafana + timestamp without time zone:** Gebruik `time::varchar` of `date || time` om timezone conversie te voorkomen
2. **Systemd service updates:** Na script wijzigingen die nieuwe arguments vereisen, ook service files updaten
3. **MQTT Bridge auth:** Bij bridges naar andere hosts altijd `remote_username` en `remote_password` toevoegen
