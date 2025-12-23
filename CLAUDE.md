# EMSN 2.0 - Instructies voor Claude Code

## Project
Ecologisch Monitoring Systeem Nijverdal - Biodiversity monitoring met BirdNET-Pi
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

## Credentials
**Alle credentials staan in `.secrets` (niet in git!)**
Lees dit bestand voor database, NAS, MQTT, Grafana en email wachtwoorden.

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
- **NAS (DS224Plus):** 192.168.1.25 - Opslag, PostgreSQL (port 5433), Grafana
- **Homer Dashboard:** http://192.168.1.25:8181/ - Startpagina met alle links
- **Ulanzi TC001:** 192.168.1.11 - AWTRIX Light LED matrix display

## Ulanzi Display
- **IP:** 192.168.1.11
- **API:** http://192.168.1.11/api (AWTRIX Light)
- **Endpoints:**
  - /api/notify - Notificaties sturen
  - /api/screen - Screenshot (32x8 pixel array)
  - /api/stats - Device status
- **Services:**
  - ulanzi-bridge.service - MQTT → Display notificaties
  - ulanzi-screenshot.service - Automatische screenshots
- **Config:** /home/ronny/emsn2/config/ulanzi_config.py
- **Screenshots:** /mnt/nas-reports/ulanzi-screenshots/
- **Screenshot Server:** http://192.168.1.178:8082 (serveert screenshots)
- **Dashboard:** http://192.168.1.25:3000/d/emsn-ulanzi-notifications/

## MQTT
- **Hoofdbroker:** Zolder (192.168.1.178:1883)
- **Bridges:** Bidirectioneel - Berging ↔ Zolder
- **Credentials:** zie `.secrets`
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
- **Credentials:** zie `.secrets`
- **Let op:** NAS proxy blokkeert POST requests - gebruik directe Pi IP voor API calls
- **Grafana:** http://192.168.1.25:3000

## Vocalization System

### BELANGRIJK: Twee Aparte Repo's!
- **Training code:** https://github.com/RonnyCHL/emsn-vocalization (community, MIT license)
- **EMSN integratie:** /home/ronny/emsn2/scripts/vocalization/ (alleen enricher)

**Alles over training (notebooks, modellen, Colab) hoort in emsn-vocalization!**

### Lokale Repo (~/emsn-vocalization)
- **Colab notebooks:** notebooks/*.ipynb
- **Training scripts:** train_existing.py, full_pipeline.py
- **CNN classifier:** src/classifiers/cnn_inference.py
- **Modellen:** trained-models/*.pt (niet in git, te groot)

### EMSN2 Integratie (/scripts/vocalization/)
- **vocalization_enricher.py** - Database integratie (EMSN-specifiek)
- **vocalization_classifier.py** - Lokale kopie van cnn_inference.py

### NAS Docker Container
- **Container:** emsn-vocalization-pytorch
- **Locatie:** /volume1/docker/emsn-vocalization (op NAS)
- **Mount Pi:** /mnt/nas-docker/emsn-vocalization
- **Modellen:** data/models/*.pt (196 soorten)

### Container beheer (vereist sudo op NAS)
```bash
sudo docker restart emsn-vocalization-pytorch
sudo docker logs -f emsn-vocalization-pytorch
```

### Database tabellen
- vocalization_training - Training status per soort
- vocalization_model_versions - Model versie tracking

## Email (Rapporten)
- **SMTP:** smtp.strato.de:587
- **Credentials:** zie `.secrets`
- **Config:** /home/ronny/emsn2/config/email.yaml

## Commit Stijl
- feat: nieuwe functionaliteit
- fix: bug fix
- docs: documentatie update
- chore: opruimen/onderhoud
