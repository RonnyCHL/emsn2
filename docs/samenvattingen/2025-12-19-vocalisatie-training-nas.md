# Sessie Samenvatting: Vocalisatie Training op NAS

**Datum:** 2025-12-19
**Doel:** CNN vocalisatie training verplaatsen naar NAS en automatiseren

## Wat is bereikt

### 1. Training verplaatst van Pi Zolder naar NAS
- Pi Zolder is nu schoon en dedicated voor BirdNET-Pi detectie
- Alle training draait nu in Docker container op Synology DS224Plus
- Geen impact meer op vogeldetectie

### 2. Automatische Training Pipeline
- **auto_trainer.py** - Haalt automatisch top 15 soorten uit BirdNET database
- Soorten geselecteerd op basis van:
  - Minimaal 20 detecties
  - Minimaal 70% confidence
- Per soort: download Xeno-canto audio, genereer spectrogrammen, train CNN

### 3. Grafana Dashboard
- Nieuw dashboard: "EMSN - Vocalisatie Training"
- URL: http://192.168.1.25:3000/d/emsn-vocalization-training/
- Toont: status per soort, voortgang %, audio files, spectrogrammen, accuracy
- Auto-refresh elke 30 seconden

### 4. Homer Dashboard Link
- Nieuwe sectie "AI & Training" toegevoegd
- Link naar Vocalisatie Training dashboard

### 5. Automatische Database Sync
- Systemd timer `sync-birdnet-nas.timer`
- Synchroniseert BirdNET database elke nacht om 02:00 naar NAS
- Container krijgt zo steeds nieuwste detectiedata

## Technische Details

### Docker Setup op NAS
**Locatie:** `/volume1/docker/emsn-vocalization/`

**Bestanden:**
- `Dockerfile` - Python 3.11 + TensorFlow + librosa
- `docker-compose.yml` - Container configuratie
- `src/auto_trainer.py` - Training pipeline
- `src/collectors/xeno_canto.py` - Xeno-canto scraper met paginatie

**Starten:**
```bash
cd /volume1/docker/emsn-vocalization
sudo docker compose up -d
```

### PostgreSQL Tabel
```sql
CREATE TABLE vocalization_training (
    id SERIAL PRIMARY KEY,
    species_name VARCHAR(100),
    scientific_name VARCHAR(100),
    status VARCHAR(20),  -- pending, downloading, processing, training, completed, failed
    phase VARCHAR(50),
    progress_pct INTEGER,
    audio_files INTEGER,
    spectrograms INTEGER,
    accuracy FLOAT,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Database Connectie
- Host: 192.168.1.25
- Port: 5433
- Database: emsn
- User: birdpi_zolder
- Password: REDACTED_DB_PASS

## Xeno-canto Paginatie Fix
De originele collector vond maar 30 resultaten per pagina. Opgelost door paginatie toe te voegen in `_parse_html_search()`:
- Iterreert door meerdere pagina's
- Verzamelt unieke recording IDs
- Haalt details op per recording

## Volgende Stappen
1. Training laten lopen - eerste soort (Roodborst) is gestart
2. Resultaten monitoren via Grafana dashboard
3. Getrainde modellen kunnen later gebruikt worden voor vocalisatie classificatie (zang/roep/alarm)

## Gerelateerde Bestanden
- `/mnt/nas-docker/emsn-vocalization/` - Docker setup
- `/mnt/nas-docker/grafana/dashboards/vocalization-training-dashboard.json`
- `/mnt/nas-docker/homer/config.yml` - Homer met nieuwe link
- `/etc/systemd/system/sync-birdnet-nas.timer` - Database sync timer
