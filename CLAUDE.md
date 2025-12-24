# EMSN 2.0 - Instructies voor Claude Code

## Project
Ecologisch Monitoring Systeem Nijverdal - Biodiversity monitoring met BirdNET-Pi
Eigenaar: Ronny Hullegie

## Gouden Regels
- BirdNET-Pi = heilig → NOOIT core files aanpassen
- Altijd backups maken voor destructieve acties
- Stap voor stap werken, elke fase testen
- **GEEN EIGEN AANNAMES** → Bij twijfel altijd vragen wat Ronny wil
- Volg afspraken exact op, verzin geen alternatieven

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
- **Modellen:** data/models/*.pt (197 ultimate modellen)
- **Backup:** /mnt/nas-birdnet-archive/getrainde_modellen_EMSN/

### Ultimate Model Architectuur
De `_ultimate` modellen hebben een diepere CNN (4 conv blokken ipv 3):
- **Standaard:** 3 conv → 128 filters → classifier 256→num_classes
- **Ultimate:** 4 conv → 256 filters → classifier 512→256→num_classes
- Classifier detecteert automatisch aan bestandsnaam of versie

### Container beheer (vereist sudo op NAS)
```bash
sudo docker restart emsn-vocalization-pytorch
sudo docker logs -f emsn-vocalization-pytorch
```

### Database tabellen
- vocalization_training - Training status per soort
- vocalization_model_versions - Model versie tracking

### Geleerde Lessen (Claude)
- BirdNET-Pi slaat audio op als **MP3**, niet WAV (librosa kan beide laden)
- NAS CIFS mount: `scp` werkt niet direct, gebruik `sudo cp` via mount
- Bij nieuwe model architectuur: services herstarten na code update
- Ultimate modellen: ~35MB per stuk, ~7GB totaal (te groot voor GitHub)

## Email (Rapporten)
- **SMTP:** smtp.strato.de:587
- **Credentials:** zie `.secrets`
- **Config:** /home/ronny/emsn2/config/email.yaml

## Nestkast Cameras (go2rtc + Tuya)

### Hardware
3 Tuya nestkast cameras met video+audio:
| Camera | Device ID | Locatie |
|--------|-----------|---------|
| voor | bf80c5603b3392da01oyt1 | Voortuin |
| midden | bf5ab17574f859aef9zbg1 | Midden (slapende Koolmees!) |
| achter | bf0e510111cdf52517rddr | Achtertuin |

### Streaming (go2rtc op NAS)
- **go2rtc UI:** http://192.168.1.25:1984
- **RTSP streams:** rtsp://192.168.1.25:8554/nestkast_{voor|midden|achter}
- **WebRTC streams:** http://192.168.1.25:1984/stream.html?src=nestkast_{id}
- **Config:** /volume1/docker/go2rtc/go2rtc.yaml (op NAS)
- **Tuya API:** protect-eu.ismartlife.me
- **Credentials:** zie `.secrets` (Tuya Smart account)

### Nestkast Monitoring API
- **Base URL:** http://192.168.1.178:8081/api/nestbox/
- **Endpoints:**
  - GET /list - Alle nestkasten
  - GET /status - Huidige status per kast
  - GET /events - Event geschiedenis
  - POST /events - Nieuw event toevoegen
  - GET /media - Screenshots/videos lijst
  - GET /media/file/{id} - Bestand downloaden
  - POST /capture/screenshot - Screenshot maken
  - POST /capture/video/start - Video opname starten
  - POST /capture/video/stop - Video opname stoppen

### Event Types (Nederlands)
`leeg`, `bezet`, `bouw`, `eieren`, `jongen`, `uitgevlogen`, `mislukt`, `onderhoud`

### Automatische Screenshots
- **Timer:** nestbox-screenshot.timer (6x/dag)
- **Tijden:** 08:00, 14:00, 22:00, 00:00, 02:00, 04:00
- **Nacht screenshots:** Voor ML slaapdetectie (capture_type=auto_night)

### Media Opslag (8TB USB schijf op NAS)
- **NFS mount:** /mnt/nas-birdnet-archive/nestbox/
- **Structuur:** {nestbox_id}/screenshots/ en {nestbox_id}/videos/
- **Paden:** /mnt/nas-birdnet-archive/nestbox/{voor|midden|achter}/{screenshots|videos}/

### Database Tabellen (PostgreSQL emsn)
- nestbox_events - Observaties (bezet, eieren, jongen, etc.)
- nestbox_media - Screenshots en video metadata

### Grafana Dashboard
- **URL:** http://192.168.1.25:3000/d/emsn-nestkast-monitoring/
- **Config:** /mnt/nas-docker/grafana/provisioning/dashboards/emsn-nestkast-monitoring.json

### Voorbeeld API Calls
```bash
# Screenshot maken
curl -X POST http://192.168.1.178:8081/api/nestbox/capture/screenshot \
  -H "Content-Type: application/json" \
  -d '{"nestbox_id": "midden", "capture_type": "manual"}'

# Event toevoegen
curl -X POST http://192.168.1.178:8081/api/nestbox/events \
  -H "Content-Type: application/json" \
  -d '{"nestbox_id": "midden", "event_type": "bezet", "species": "Koolmees"}'
```

## Commit Stijl
- feat: nieuwe functionaliteit
- fix: bug fix
- docs: documentatie update
- chore: opruimen/onderhoud
