# EMSN 2.0 - Instructies voor Claude Code

## Project
EcoMonitoring Systeem Nijverdal - Biodiversity monitoring met BirdNET-Pi
Eigenaar: Ronny Hullegie

## Gouden Regels
- BirdNET-Pi = heilig → NOOIT core files aanpassen
- Altijd backups maken voor destructieve acties
- Stap voor stap werken, elke fase testen

## Werkwijze
- Start sessie: lees eerst /docs/ voor huidige status
- Einde sessie: samenvatting opslaan in /docs/samenvattingen/
- Daarna committen en pushen naar GitHub
- Documentatie in het Nederlands

## Mappenstructuur
- /docs/ - documentatie en samenvattingen
- /docs/samenvattingen/ - sessie samenvattingen
- /scripts/ - alle Python scripts
- /config/ - configuratie voorbeelden
- /systemd/ - service en timer bestanden

## Locaties
- Actieve sync scripts: /home/ronny/sync/
- Nieuwste sync code: /home/ronny/emsn2/scripts/sync/
- BirdNET-Pi database: /home/ronny/BirdNET-Pi/scripts/birds.db
- AI Rapporten: /mnt/nas-reports (NAS share)
- Reports API: http://192.168.1.178:8081

## Netwerk
- **Pi Zolder (emsn2-zolder):** 192.168.1.178 - BirdNET-Pi, MQTT broker (hoofd), API server
- **Pi Berging (emsn2-berging):** 192.168.1.87 - BirdNET-Pi, AtmosBird (Pi Camera NoIR), MQTT bridge
- **NAS (DS224Plus):** 192.168.1.25 - Opslag, PostgreSQL, Grafana, Homer

## MQTT
- **Hoofdbroker:** Zolder (192.168.1.178:1883)
- **Bridges:** Bidirectioneel - Berging ↔ Zolder
- **Credentials:** ecomonitor/REDACTED_DB_PASS
- **Topics:**
  - emsn2/{station}/# - Systeem data
  - birdnet/{station}/detection - Live detecties
  - birdnet/{station}/stats - Statistieken
  - emsn2/bridge/status - Bridge status
- **Services:**
  - mqtt-bridge-monitor.service - Continu monitoring
  - birdnet-mqtt-publisher.service - BirdNET → MQTT
  - mqtt-failover.timer - Health check (5 min)
- **Config:** /home/ronny/emsn2/config/mosquitto-*.conf

## NAS Shares
  - //192.168.1.25/docker → /mnt/nas-docker
  - //192.168.1.25/emsn-AIRapporten → /mnt/nas-reports
- **Credentials:** /etc/nas-reports-credentials (ronny/REDACTED_DB_PASS)
- **Let op:** NAS proxy blokkeert POST requests - gebruik directe Pi IP voor API calls
- **Grafana:** http://192.168.1.25:3000 (admin/emsn2024)

## Email (Rapporten)
- **SMTP:** smtp.strato.de:587
- **Account:** rapporten@ronnyhullegie.nl
- **Wachtwoord:** REDACTED_SMTP_PASS
- **Config:** /home/ronny/emsn2/config/email.yaml

## Commit Stijl
- feat: nieuwe functionaliteit
- fix: bug fix
- docs: documentatie update
- chore: opruimen/onderhoud
