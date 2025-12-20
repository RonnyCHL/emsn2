# Installatiehandleiding - Vocalization Classifier

Stap-voor-stap handleiding voor het installeren en configureren van de EMSN 2.0 Vocalization Classifier op een Synology NAS of vergelijkbaar systeem.

## Inhoudsopgave

1. [Systeemvereisten](#systeemvereisten)
2. [Voorbereiding](#voorbereiding)
3. [Database Setup](#database-setup)
4. [Docker Installatie](#docker-installatie)
5. [Configuratie](#configuratie)
6. [Training Starten](#training-starten)
7. [Grafana Dashboard](#grafana-dashboard)
8. [Verificatie](#verificatie)

---

## Systeemvereisten

### Hardware

| Component | Minimum | Aanbevolen |
|-----------|---------|------------|
| CPU | x86_64 dual-core | Quad-core |
| RAM | 4 GB | 8+ GB |
| Opslag | 50 GB vrij | 200+ GB |
| Netwerk | Internet toegang | Stabiele verbinding |

### Software

- Docker 20.10+
- Docker Compose 2.0+
- PostgreSQL 13+ (kan in Docker)
- Git (optioneel, voor updates)

### Accounts (gratis)

- Xeno-canto account voor API key

---

## Voorbereiding

### Stap 1: Clone of kopieer bestanden

**Via Git:**
```bash
git clone https://github.com/[username]/emsn2.git
cd emsn2
```

**Handmatig:**
```bash
# Kopieer bestanden naar NAS share
scp -r scripts/vocalization/* admin@192.168.1.25:/volume1/docker/emsn-vocalization/
```

### Stap 2: Maak directories

```bash
# SSH naar NAS
ssh admin@192.168.1.25

# Maak directory structuur
mkdir -p /volume1/docker/emsn-vocalization/{data,logs,models,src}
mkdir -p /volume1/docker/emsn-vocalization/data/{raw,spectrograms}
```

### Stap 3: Xeno-canto API key

1. Ga naar https://xeno-canto.org
2. Maak account of log in
3. Navigeer naar https://xeno-canto.org/explore/api
4. Klik "Generate API key"
5. Kopieer de key (bewaar veilig!)

---

## Database Setup

### Optie A: Bestaande PostgreSQL gebruiken

Als je al een PostgreSQL server hebt:

```bash
# Connect naar bestaande database
psql -h 192.168.1.25 -p 5433 -U postgres -d emsn

# Voer setup script uit
\i /path/to/create_tables.sql
```

### Optie B: Nieuwe PostgreSQL in Docker

```yaml
# docker-compose.postgres.yml
version: '3.8'
services:
  postgres:
    image: postgres:15
    container_name: postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: emsn
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: your_secure_password
    volumes:
      - ./postgres_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"
```

```bash
# Start PostgreSQL
docker-compose -f docker-compose.postgres.yml up -d

# Wacht 10 seconden voor startup
sleep 10
```

### Database tabellen aanmaken

```bash
# Kopieer SQL bestand naar container
docker cp create_tables.sql postgres:/tmp/

# Voer uit
docker exec postgres psql -U postgres -d emsn -f /tmp/create_tables.sql
```

**Of handmatig:**
```sql
-- Connect
docker exec -it postgres psql -U postgres -d emsn

-- Maak tabellen
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
CREATE INDEX idx_vt_status ON vocalization_training(status);
CREATE INDEX idx_xc_species ON xeno_canto_recordings(species_name);
CREATE INDEX idx_cm_species ON vocalization_confusion_matrix(species_name);
```

### Applicatie user aanmaken

```sql
-- Maak user
CREATE USER birdpi_zolder WITH PASSWORD 'your_password';

-- Geef rechten
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO birdpi_zolder;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO birdpi_zolder;
```

---

## Docker Installatie

### Stap 1: Dockerfile controleren

Zorg dat `Dockerfile.pytorch` aanwezig is:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Systeem dependencies
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# PyTorch CPU (geen AVX nodig)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Python packages
RUN pip install --no-cache-dir \
    numpy \
    librosa \
    scikit-learn \
    tqdm \
    requests \
    matplotlib \
    seaborn \
    psycopg2-binary

# Source code
COPY src/ /app/src/
COPY *.py /app/

# Directories
RUN mkdir -p /app/data/raw /app/data/models /app/logs

CMD ["python", "train_existing.py"]
```

### Stap 2: docker-compose.yml maken

```yaml
version: '3.8'

services:
  vocalization-trainer:
    build:
      context: .
      dockerfile: Dockerfile.pytorch
    image: emsn-vocalization-pytorch
    container_name: emsn-vocalization-pytorch
    restart: "no"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./src:/app/src
    environment:
      - XENO_CANTO_API_KEY=${XENO_CANTO_API_KEY}
      - PG_HOST=192.168.1.25
      - PG_PORT=5433
      - PG_DB=emsn
      - PG_USER=birdpi_zolder
      - PG_PASS=${PG_PASS}
    # Resource limits
    cpu_shares: 512
    mem_limit: 4g
    network_mode: bridge
```

### Stap 3: Environment variabelen

Maak `.env` bestand:

```bash
# .env
XENO_CANTO_API_KEY=jouw_api_key_hier
PG_PASS=jouw_database_wachtwoord
```

### Stap 4: Build image

```bash
cd /volume1/docker/emsn-vocalization

# Build
docker-compose build

# Of handmatig
docker build -f Dockerfile.pytorch -t emsn-vocalization-pytorch .
```

---

## Configuratie

### Bestand: full_pipeline.py

Check de configuratie bovenaan het bestand:

```python
# Database config
PG_HOST = os.environ.get('PG_HOST', '192.168.1.25')
PG_PORT = os.environ.get('PG_PORT', '5433')
PG_DB = os.environ.get('PG_DB', 'emsn')
PG_USER = os.environ.get('PG_USER', 'birdpi_zolder')
PG_PASS = os.environ.get('PG_PASS', 'your_password')

# Training parameters
SAMPLES_PER_TYPE = 150      # Audio samples per type
MAX_SPECTROGRAMS_PER_CLASS = 1000
EPOCHS = 30
BATCH_SIZE = 64
PATIENCE = 7
```

### Bestand: dutch_bird_species.py

Bevat alle 232 soorten. Pas prioriteiten aan indien gewenst:

```python
# Prioriteit 1 = zeer algemeen (53 soorten)
# Prioriteit 2 = regelmatig (124 soorten)
# Prioriteit 3 = minder algemeen (55 soorten)

DUTCH_BIRD_SPECIES = [
    ("Koolmees", "Parus major", "koolmees", 1),
    ("Pimpelmees", "Cyanistes caeruleus", "pimpelmees", 1),
    # ...
]
```

---

## Training Starten

### Methode 1: Docker Compose

```bash
# Start training
docker-compose up -d

# Volg logs
docker-compose logs -f
```

### Methode 2: Docker run

```bash
# Interactief (voor debugging)
docker run -it \
  --name emsn-vocalization-pytorch \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/src:/app/src \
  -e XENO_CANTO_API_KEY="$XENO_CANTO_API_KEY" \
  -e PG_HOST="192.168.1.25" \
  -e PG_PORT="5433" \
  -e PG_DB="emsn" \
  -e PG_USER="birdpi_zolder" \
  -e PG_PASS="$PG_PASS" \
  emsn-vocalization-pytorch \
  python full_pipeline.py

# Detached (achtergrond)
docker run -d \
  --name emsn-vocalization-pytorch \
  # ... zelfde opties ...
```

### Methode 3: Specifieke soorten

```bash
# Alleen prioriteit 1
docker exec emsn-vocalization-pytorch python full_pipeline.py --priority 1

# Specifieke soort
docker exec emsn-vocalization-pytorch python full_pipeline.py --species "Merel"

# Dry run (test)
docker exec emsn-vocalization-pytorch python full_pipeline.py --dry-run
```

---

## Grafana Dashboard

### Stap 1: PostgreSQL datasource toevoegen

1. Open Grafana (http://192.168.1.25:3000)
2. Configuration → Data Sources → Add data source
3. Selecteer PostgreSQL
4. Configureer:
   - Name: `PostgreSQL-EMSN`
   - Host: `192.168.1.25:5433`
   - Database: `emsn`
   - User: `birdpi_zolder`
   - Password: `your_password`
   - SSL Mode: `disable`
5. Save & Test

### Stap 2: Dashboard importeren

1. Dashboards → Import
2. Upload JSON file: `vocalization-training-dashboard.json`
3. Selecteer datasource: `PostgreSQL-EMSN`
4. Import

### Stap 3: Dashboard openen

Navigeer naar:
- Dashboards → Vocalization Training Monitor

---

## Verificatie

### Check 1: Container status

```bash
docker ps | grep vocalization
# Moet "Up" tonen
```

### Check 2: Logs

```bash
docker logs emsn-vocalization-pytorch --tail 50
# Moet training output tonen
```

### Check 3: Database

```bash
docker exec postgres psql -U postgres -d emsn -c \
  "SELECT species_name, status, phase FROM vocalization_training LIMIT 5;"
# Moet rijen tonen
```

### Check 4: Bestanden

```bash
ls -la data/models/
# Moet .pt bestanden tonen na voltooiing

ls -la data/spectrograms-*/
# Moet spectrogram directories tonen
```

### Check 5: Grafana

Open dashboard en verifieer:
- Training voortgang tabel toont data
- Status verdeling pie chart werkt
- Geen "No Data" panels

---

## Troubleshooting

### Container start niet

```bash
# Check logs voor errors
docker logs emsn-vocalization-pytorch

# Herbouw image
docker build -f Dockerfile.pytorch -t emsn-vocalization-pytorch . --no-cache
```

### Database connectie faalt

```bash
# Test connectie
docker exec emsn-vocalization-pytorch python -c "
import psycopg2
conn = psycopg2.connect(
    host='192.168.1.25',
    port='5433',
    database='emsn',
    user='birdpi_zolder',
    password='your_password'
)
print('Connected!')
conn.close()
"
```

### Xeno-canto download faalt

```bash
# Test API key
curl "https://xeno-canto.org/api/3/recordings?query=sp:Parus+major&key=YOUR_KEY" | head
```

### Geheugen problemen

```bash
# Verhoog geheugen limiet in docker-compose.yml
mem_limit: 6g
```

---

## Volgende Stappen

Na succesvolle installatie:

1. **Monitor training** via Grafana dashboard
2. **Check logs** periodiek voor errors
3. **Backup models** na voltooiing:
   ```bash
   cp -r data/models /backup/vocalization-models-$(date +%Y%m%d)
   ```

Training duurt 3-5 dagen voor alle 232 soorten, afhankelijk van hardware.

---

*Document versie: 1.0 - December 2024*
