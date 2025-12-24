# Sessie 24 december 2025 - Real-time Vocalization naar Ulanzi

## Samenvatting

Vocalization classificatie (zang/roep/alarm) is nu real-time geïntegreerd in het MQTT systeem en de Ulanzi display. Voorheen was er een vertraging omdat de vocalization pas na sync naar PostgreSQL werd toegevoegd.

## Uitgevoerde werkzaamheden

### 1. Community Documentatie (emsn-vocalization repo)

- **README.md** herschreven voor BirdNET-Pi community
- **COMMUNITY_PITCH.md** aangemaakt als discussiedocument
- Modellen beschikbaar via Google Drive (197 ultimate modellen, 6.9 GB)

### 2. Berging Opgeschoond en Uitgerust

- Oude training bestanden verwijderd uit `/scripts/vocalization/`
- NAS mount toegevoegd (`/mnt/nas-docker`) voor modellen
- Vocalization enricher service geïnstalleerd en actief
- PyTorch + librosa + psycopg2 geïnstalleerd

### 3. Real-time Vocalization in MQTT Publisher

**Bestand:** `scripts/mqtt/birdnet_mqtt_publisher.py`

- Lazy-loaded vocalization classifier toegevoegd
- Audio pad aangepast naar `/home/ronny/BirdSongs/Extracted/By_Date/YYYY-MM-DD/Species/`
- MQTT bericht uitgebreid met vocalization velden:
  ```json
  {
    "species": "Kauw",
    "vocalization": "call",
    "vocalization_nl": "roep",
    "vocalization_confidence": 0.52
  }
  ```

### 4. Ulanzi Bridge Aangepast

**Bestand:** `scripts/ulanzi/ulanzi_bridge.py`

- `parse_detection_message()` toegevoegd (JSON + Apprise support)
- Vocalization uit MQTT bericht gebruiken (geen lokale classificatie nodig)
- Topics gewijzigd naar `birdnet/{station}/detection`

**Bestand:** `config/ulanzi_config.py`

- Topics gewijzigd van `emsn2/*/detection/new` naar `birdnet/*/detection`

## Resultaat

### Oude Flow (met vertraging)
```
BirdNET detectie → MQTT (zonder voc) → Ulanzi
                → Sync → PostgreSQL → Enricher → voc toegevoegd
```

### Nieuwe Flow (real-time)
```
BirdNET detectie → Publisher (+ vocalization) → MQTT → Ulanzi
                                             ↓
                           "Zolder-Kauw roep-83%"
```

## Services Status

| Pi | Service | Status |
|----|---------|--------|
| Zolder | birdnet-mqtt-publisher | Actief (met vocalization) |
| Zolder | ulanzi-bridge | Actief (JSON + vocalization) |
| Zolder | vocalization-enricher | Actief |
| Berging | birdnet-mqtt-publisher | Actief (met vocalization) |
| Berging | vocalization-enricher | Actief |

## Commits

- `f088cc0` - feat: real-time vocalization in MQTT en Ulanzi display
- `b1d98cc` - docs: README herschreven voor community gebruik (emsn-vocalization)
- `8860dd5` - docs: community pitch voor BirdNET-Pi integratie (emsn-vocalization)

## Volgende Stappen (optioneel)

- Community pitch delen op BirdNET-Pi GitHub
- Contact leggen met Nachtzuster (BirdNET-Pi maintainer)
- SQLite-only versie overwegen voor standalone gebruik
