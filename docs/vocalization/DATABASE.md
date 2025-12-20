# Database Schema - Vocalization Classifier

Uitgebreide documentatie van de PostgreSQL database structuur voor het EMSN 2.0 Vocalization Classifier project.

## Overzicht

De vocalization classifier gebruikt drie database tabellen in de `emsn` database:

| Tabel | Doel | Geschatte grootte |
|-------|------|-------------------|
| `vocalization_training` | Training status en voortgang | ~232 rijen (1 per soort) |
| `xeno_canto_recordings` | Audio metadata voor wereldkaart | ~23.200 rijen (100 per soort) |
| `vocalization_confusion_matrix` | Model evaluatie resultaten | ~2.088 rijen (9 per soort) |

## Connectie Details

```
Host:     192.168.1.25
Port:     5433
Database: emsn
User:     birdpi_zolder
Password: [in credentials file]
```

---

## Tabel: vocalization_training

### Beschrijving

Centrale tracking tabel voor training status van elk vogelsoort model. Wordt real-time bijgewerkt tijdens training voor Grafana dashboard monitoring.

### Schema

```sql
CREATE TABLE vocalization_training (
    id SERIAL PRIMARY KEY,
    species_name VARCHAR(100) NOT NULL UNIQUE,
    scientific_name VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending',
    phase VARCHAR(100),
    progress_pct INTEGER DEFAULT 0,
    accuracy FLOAT,
    spectrograms_count INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Indexes
CREATE INDEX idx_vt_status ON vocalization_training(status);
CREATE INDEX idx_vt_species ON vocalization_training(species_name);
```

### Kolommen

| Kolom | Type | Nullable | Default | Beschrijving |
|-------|------|----------|---------|--------------|
| `id` | SERIAL | NO | auto | Primaire sleutel |
| `species_name` | VARCHAR(100) | NO | - | Nederlandse naam (uniek) |
| `scientific_name` | VARCHAR(100) | YES | NULL | Wetenschappelijke naam |
| `status` | VARCHAR(20) | YES | 'pending' | Huidige status |
| `phase` | VARCHAR(100) | YES | NULL | Huidige fase |
| `progress_pct` | INTEGER | YES | 0 | Voortgang 0-100 |
| `accuracy` | FLOAT | YES | NULL | Model nauwkeurigheid (0.0-1.0) |
| `spectrograms_count` | INTEGER | YES | 0 | Aantal spectrogrammen |
| `error_message` | TEXT | YES | NULL | Foutmelding bij failure |
| `started_at` | TIMESTAMP | YES | NULL | Start timestamp |
| `updated_at` | TIMESTAMP | YES | NOW() | Laatste update |
| `completed_at` | TIMESTAMP | YES | NULL | Voltooiing timestamp |

### Status waarden

| Status | Beschrijving | Typische fase |
|--------|--------------|---------------|
| `pending` | Wacht op training | - |
| `processing` | Audio downloaden of spectrogrammen genereren | "Audio downloaden", "Spectrogrammen genereren" |
| `training` | CNN model wordt getraind | "Epoch 15/30" |
| `completed` | Training succesvol voltooid | "Voltooid" |
| `failed` | Training mislukt | Zie error_message |

### Voorbeeld queries

**Huidige training status:**
```sql
SELECT species_name, status, phase, progress_pct, accuracy
FROM vocalization_training
WHERE status IN ('training', 'processing')
ORDER BY updated_at DESC;
```

**Voltooide modellen met accuracy:**
```sql
SELECT species_name, accuracy,
       completed_at - started_at as training_duration
FROM vocalization_training
WHERE status = 'completed'
ORDER BY accuracy DESC;
```

**Mislukte trainingen analyseren:**
```sql
SELECT species_name, phase, error_message, updated_at
FROM vocalization_training
WHERE status = 'failed'
ORDER BY updated_at DESC;
```

---

## Tabel: xeno_canto_recordings

### Beschrijving

Slaat metadata op van Xeno-canto audio opnames die gebruikt worden voor training. Primair doel is visualisatie van audio locaties op wereldkaart in Grafana.

### Schema

```sql
CREATE TABLE xeno_canto_recordings (
    id SERIAL PRIMARY KEY,
    species_name VARCHAR(100) NOT NULL,
    xc_id VARCHAR(20),
    country VARCHAR(100),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    vocalization_type VARCHAR(100),
    quality CHAR(1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_xc_species ON xeno_canto_recordings(species_name);
CREATE INDEX idx_xc_country ON xeno_canto_recordings(country);
CREATE INDEX idx_xc_coords ON xeno_canto_recordings(latitude, longitude);
```

### Kolommen

| Kolom | Type | Nullable | Default | Beschrijving |
|-------|------|----------|---------|--------------|
| `id` | SERIAL | NO | auto | Primaire sleutel |
| `species_name` | VARCHAR(100) | NO | - | Nederlandse naam |
| `xc_id` | VARCHAR(20) | YES | NULL | Xeno-canto recording ID |
| `country` | VARCHAR(100) | YES | NULL | Land van opname |
| `latitude` | DOUBLE PRECISION | YES | NULL | Breedtegraad |
| `longitude` | DOUBLE PRECISION | YES | NULL | Lengtegraad |
| `vocalization_type` | VARCHAR(100) | YES | NULL | Type (song, call, alarm, etc.) |
| `quality` | CHAR(1) | YES | NULL | Kwaliteit A-E |
| `created_at` | TIMESTAMP | YES | NOW() | Insert timestamp |

### Voorbeeld queries

**Alle landen met opnames:**
```sql
SELECT country, COUNT(*) as recordings
FROM xeno_canto_recordings
WHERE country IS NOT NULL
GROUP BY country
ORDER BY recordings DESC;
```

**Locaties voor wereldkaart (Grafana Geomap):**
```sql
SELECT species_name, latitude, longitude, country, vocalization_type
FROM xeno_canto_recordings
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL;
```

**Kwaliteitsverdeling:**
```sql
SELECT quality, COUNT(*) as count
FROM xeno_canto_recordings
GROUP BY quality
ORDER BY quality;
```

---

## Tabel: vocalization_confusion_matrix

### Beschrijving

Slaat confusion matrix data op na model training. Wordt gebruikt voor visualisatie van model performance per vocalisatie type.

### Schema

```sql
CREATE TABLE vocalization_confusion_matrix (
    id SERIAL PRIMARY KEY,
    species_name VARCHAR(100) NOT NULL,
    true_label VARCHAR(20) NOT NULL,
    predicted_label VARCHAR(20) NOT NULL,
    count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(species_name, true_label, predicted_label)
);

-- Indexes
CREATE INDEX idx_cm_species ON vocalization_confusion_matrix(species_name);
```

### Kolommen

| Kolom | Type | Nullable | Default | Beschrijving |
|-------|------|----------|---------|--------------|
| `id` | SERIAL | NO | auto | Primaire sleutel |
| `species_name` | VARCHAR(100) | NO | - | Nederlandse naam |
| `true_label` | VARCHAR(20) | NO | - | Echte label (song/call/alarm) |
| `predicted_label` | VARCHAR(20) | NO | - | Voorspelde label |
| `count` | INTEGER | YES | 0 | Aantal voorspellingen |
| `created_at` | TIMESTAMP | YES | NOW() | Insert timestamp |

### Confusion Matrix Structuur

Voor elke soort worden 9 rijen opgeslagen (3x3 matrix):

| true_label | predicted_label | Betekenis |
|------------|-----------------|-----------|
| alarm | alarm | True Positive (alarm correct) |
| alarm | call | False Negative (alarm als call) |
| alarm | song | False Negative (alarm als song) |
| call | alarm | False Positive (call als alarm) |
| call | call | True Positive (call correct) |
| call | song | False Negative (call als song) |
| song | alarm | False Positive (song als alarm) |
| song | call | False Negative (song als call) |
| song | song | True Positive (song correct) |

### Voorbeeld queries

**Confusion matrix voor specifieke soort:**
```sql
SELECT true_label, predicted_label, count
FROM vocalization_confusion_matrix
WHERE species_name = 'Roodborst'
ORDER BY true_label, predicted_label;
```

**Pivot query voor Grafana heatmap:**
```sql
SELECT
    species_name,
    true_label,
    SUM(CASE WHEN predicted_label = 'alarm' THEN count ELSE 0 END) as pred_alarm,
    SUM(CASE WHEN predicted_label = 'call' THEN count ELSE 0 END) as pred_call,
    SUM(CASE WHEN predicted_label = 'song' THEN count ELSE 0 END) as pred_song
FROM vocalization_confusion_matrix
GROUP BY species_name, true_label
ORDER BY species_name, true_label;
```

**Accuracy berekenen uit confusion matrix:**
```sql
SELECT
    species_name,
    ROUND(
        SUM(CASE WHEN true_label = predicted_label THEN count ELSE 0 END)::numeric /
        NULLIF(SUM(count), 0) * 100, 2
    ) as accuracy_pct
FROM vocalization_confusion_matrix
GROUP BY species_name
ORDER BY accuracy_pct DESC;
```

---

## Initialisatie SQL

Volledige SQL voor het aanmaken van alle tabellen:

```sql
-- ===========================================
-- EMSN 2.0 Vocalization Classifier Database
-- ===========================================
-- Run als postgres user:
-- docker exec -i postgres psql -U postgres -d emsn < create_tables.sql

-- Hoofd training tabel (als nog niet bestaat)
CREATE TABLE IF NOT EXISTS vocalization_training (
    id SERIAL PRIMARY KEY,
    species_name VARCHAR(100) NOT NULL UNIQUE,
    scientific_name VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending',
    phase VARCHAR(100),
    progress_pct INTEGER DEFAULT 0,
    accuracy FLOAT,
    spectrograms_count INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Xeno-canto metadata
CREATE TABLE IF NOT EXISTS xeno_canto_recordings (
    id SERIAL PRIMARY KEY,
    species_name VARCHAR(100) NOT NULL,
    xc_id VARCHAR(20),
    country VARCHAR(100),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    vocalization_type VARCHAR(100),
    quality CHAR(1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Confusion matrix data
CREATE TABLE IF NOT EXISTS vocalization_confusion_matrix (
    id SERIAL PRIMARY KEY,
    species_name VARCHAR(100) NOT NULL,
    true_label VARCHAR(20) NOT NULL,
    predicted_label VARCHAR(20) NOT NULL,
    count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(species_name, true_label, predicted_label)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_vt_status ON vocalization_training(status);
CREATE INDEX IF NOT EXISTS idx_xc_species ON xeno_canto_recordings(species_name);
CREATE INDEX IF NOT EXISTS idx_xc_country ON xeno_canto_recordings(country);
CREATE INDEX IF NOT EXISTS idx_cm_species ON vocalization_confusion_matrix(species_name);

-- Rechten voor applicatie user
GRANT SELECT, INSERT, UPDATE, DELETE ON vocalization_training TO birdpi_zolder;
GRANT SELECT, INSERT, UPDATE, DELETE ON xeno_canto_recordings TO birdpi_zolder;
GRANT SELECT, INSERT, UPDATE, DELETE ON vocalization_confusion_matrix TO birdpi_zolder;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO birdpi_zolder;
```

---

## Backup & Recovery

### Backup maken

```bash
# Volledige database backup
docker exec postgres pg_dump -U postgres emsn > emsn_backup_$(date +%Y%m%d).sql

# Alleen vocalization tabellen
docker exec postgres pg_dump -U postgres -t vocalization_training \
    -t xeno_canto_recordings -t vocalization_confusion_matrix \
    emsn > vocalization_backup_$(date +%Y%m%d).sql
```

### Restore

```bash
# Volledige restore
docker exec -i postgres psql -U postgres -d emsn < emsn_backup_20241220.sql
```

### Data opschonen

```bash
# Reset alle training data (opnieuw beginnen)
docker exec postgres psql -U postgres -d emsn -c "
    TRUNCATE vocalization_training CASCADE;
    TRUNCATE xeno_canto_recordings CASCADE;
    TRUNCATE vocalization_confusion_matrix CASCADE;
"
```

---

## Grafana Datasource

### Configuratie

```yaml
name: PostgreSQL-EMSN
type: postgres
url: 192.168.1.25:5433
database: emsn
user: birdpi_zolder
secureJsonData:
  password: [password]
jsonData:
  sslmode: disable
  maxOpenConns: 10
  maxIdleConns: 5
```

### Voorbeeld dashboard query

```sql
-- Training voortgang tabel
SELECT
    species_name as "Soort",
    status as "Status",
    phase as "Fase",
    progress_pct as "Voortgang",
    ROUND(accuracy * 100, 1) as "Accuracy %",
    spectrograms_count as "Spectrogrammen"
FROM vocalization_training
ORDER BY
    CASE status
        WHEN 'training' THEN 1
        WHEN 'processing' THEN 2
        WHEN 'completed' THEN 3
        ELSE 4
    END,
    updated_at DESC;
```

---

*Document versie: 1.0 - December 2024*
