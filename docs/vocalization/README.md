# EMSN 2.0 Vocalization Classifier

**Geautomatiseerde vogelgeluid classificatie voor 232 Nederlandse vogelsoorten**

Een volledig geautomatiseerde pipeline voor het trainen van CNN-modellen die vogelgeluiden classificeren naar type: **song** (zang), **call** (roep), of **alarm** (alarmroep).

> **Uniek project:** Dit is voor zover bekend het eerste open-source systeem dat automatisch per vogelsoort een vocalisatie classifier traint. BirdNET identificeert soorten, maar maakt geen onderscheid tussen zang, roep en alarm. Dit project vult die leemte.

## Inhoudsopgave

1. [Overzicht](#overzicht)
2. [Architectuur](#architectuur)
3. [Vereisten](#vereisten)
4. [Installatie](#installatie)
5. [Gebruik](#gebruik)
6. [Database Schema](#database-schema)
7. [API Integraties](#api-integraties)
8. [Monitoring](#monitoring)
9. [Technische Details](#technische-details)
10. [Troubleshooting](#troubleshooting)
11. [Licentie](#licentie)

---

## Overzicht

### Wat doet dit project?

Dit project traint machine learning modellen die vogelgeluiden kunnen classificeren naar vocalisatie type:

| Type | Beschrijving | Voorbeeld |
|------|--------------|-----------|
| **Song** | Territoriaal gezang, vaak complex en melodieus | Merelzang in de ochtend |
| **Call** | Korte contactroepen tussen vogels | Korte "tjink" van een Vink |
| **Alarm** | Waarschuwingsroepen bij gevaar | Alarmroep bij roofvogel |

### Belangrijkste kenmerken

- **232 Nederlandse vogelsoorten** - Complete lijst van alle regelmatig voorkomende vogels
- **Volledig geautomatiseerd** - Draait dagen zonder tussenkomst
- **Xeno-canto integratie** - Download automatisch trainingsdata
- **PyTorch CNN** - Werkt op CPUs zonder AVX ondersteuning
- **Real-time monitoring** - Grafana dashboard met voortgang panels
- **Resume capability** - Hervat waar gestopt na onderbreking
- **Kwartaal versioning** - Automatische hertraining elk kwartaal (2025Q1, 2025Q2, etc.)
- **Best model tracking** - Database selecteert automatisch beste model per soort

### Pipeline stappen

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────┐
│  Xeno-canto     │───▶│  Spectrogram     │───▶│  CNN Training   │───▶│  Model       │
│  Audio Download │    │  Generatie       │    │  (PyTorch)      │    │  (.pt file)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘    └──────────────┘
        │                       │                      │                     │
        ▼                       ▼                      ▼                     ▼
   MP3 bestanden          Mel-spectrogrammen      Epoch updates         Confusion
   per type               als NumPy arrays        naar database         matrix data
```

---

## Architectuur

### Componenten

```
emsn-vocalization/
├── src/
│   ├── collectors/
│   │   └── xeno_canto.py          # Xeno-canto API client
│   ├── processors/
│   │   └── spectrogram_generator.py   # Audio → Spectrogram
│   └── classifiers/
│       └── cnn_classifier_pytorch.py  # PyTorch CNN model
├── full_pipeline.py               # Hoofdscript voor 232 soorten
├── train_existing.py              # Training op bestaande data
├── dutch_bird_species.py          # Soortenlijst met metadata
├── create_tables.sql              # Database schema
├── Dockerfile.pytorch             # Container definitie
└── docker-compose.yml             # Container orchestratie
```

### Data flow

```
                     ┌─────────────────────────────────────────────────────────┐
                     │                    Docker Container                      │
                     │                 (emsn-vocalization-pytorch)              │
                     │                                                          │
Xeno-canto ─────────▶│  1. Download audio (150 samples/type)                   │
    API              │                    ▼                                     │
                     │  2. Genereer spectrogrammen (128x128 mel)                │
                     │                    ▼                                     │
                     │  3. Train CNN (30 epochs, batch=64)                      │
                     │                    ▼                                     │
                     │  4. Sla model op (.pt bestand)                           │
                     └──────────────────────┬──────────────────────────────────┘
                                            │
                                            ▼
                     ┌─────────────────────────────────────────────────────────┐
                     │                    PostgreSQL                            │
                     │                                                          │
                     │  vocalization_training      - Training status/voortgang  │
                     │  xeno_canto_recordings      - Audio locatie metadata     │
                     │  vocalization_confusion_matrix - Model resultaten        │
                     │                                                          │
                     └──────────────────────┬──────────────────────────────────┘
                                            │
                                            ▼
                     ┌─────────────────────────────────────────────────────────┐
                     │                    Grafana                               │
                     │                 (54 panels)                              │
                     │                                                          │
                     │  - Training voortgang per soort                          │
                     │  - Wereldkaart audio locaties                            │
                     │  - Confusion matrices                                    │
                     │  - Accuracy trends                                       │
                     │                                                          │
                     └─────────────────────────────────────────────────────────┘
```

---

## Vereisten

### Hardware

| Component | Minimum | Aanbevolen |
|-----------|---------|------------|
| CPU | x86_64 (geen AVX nodig) | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Opslag | 50 GB | 200+ GB |
| Netwerk | Internet voor Xeno-canto | Stabiele verbinding |

**Let op:** Dit project is geoptimaliseerd voor CPUs *zonder* AVX ondersteuning (zoals Intel Celeron J4125 in Synology NAS). TensorFlow zou crashen op deze hardware, maar PyTorch werkt prima.

### Software

- Docker & Docker Compose
- PostgreSQL 13+
- Python 3.11+ (in container)
- Grafana 9+ (voor monitoring)

### Accounts

- **Xeno-canto API key** (gratis): https://xeno-canto.org/explore/api

---

## Installatie

### 1. Clone repository

```bash
git clone https://github.com/[username]/emsn2.git
cd emsn2
```

### 2. Kopieer bestanden naar NAS

```bash
# Pas paden aan voor jouw setup
cp -r scripts/vocalization/* /mnt/nas-docker/emsn-vocalization/
```

### 3. Maak database tabellen

```bash
# SSH naar NAS
ssh admin@192.168.1.25

# Voer SQL uit
docker exec -i postgres psql -U postgres -d emsn < /volume1/docker/emsn-vocalization/create_tables.sql
```

### 4. Configureer environment

```bash
# In docker-compose.yml of als environment variables
export XENO_CANTO_API_KEY="jouw_api_key_hier"
export PG_HOST="192.168.1.25"
export PG_PORT="5433"
export PG_DB="emsn"
export PG_USER="birdpi_zolder"
export PG_PASS="jouw_wachtwoord"
```

### 5. Build en start container

```bash
cd /mnt/nas-docker/emsn-vocalization

# Build PyTorch image
docker build -f Dockerfile.pytorch -t emsn-vocalization-pytorch .

# Start training
docker run -d \
  --name emsn-vocalization-pytorch \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/src:/app/src \
  -e XENO_CANTO_API_KEY="$XENO_CANTO_API_KEY" \
  emsn-vocalization-pytorch \
  python full_pipeline.py
```

---

## Gebruik

### Volledige pipeline (232 soorten)

```bash
# Train alle soorten op prioriteit volgorde
python full_pipeline.py

# Alleen prioriteit 1 soorten (algemeen)
python full_pipeline.py --priority 1

# Specifieke soort
python full_pipeline.py --species "Merel"

# Dry run (toon wat zou worden gedaan)
python full_pipeline.py --dry-run
```

### Training op bestaande spectrogrammen

```bash
# Train op data die al gedownload is
python train_existing.py

# Train specifieke soort
python train_existing.py --species "Merel"

# Forceer hertraining (ook als model al bestaat)
python train_existing.py --force

# Train met specifieke versie
python train_existing.py --version 2025Q4

# Skip species die al completed zijn, start fresh
python train_existing.py --no-continue
```

### Handmatig spectrogram genereren

```bash
python -m src.processors.spectrogram_generator \
  --input-dir data/raw/xeno-canto-merel \
  --output-dir data/spectrograms-merel \
  --segment-duration 3.0 \
  --n-mels 128
```

### Handmatig audio downloaden

```bash
python -m src.collectors.xeno_canto \
  --species "Turdus merula" \
  --types song call alarm \
  --quality A B \
  --samples 50 \
  --api-key "$XENO_CANTO_API_KEY"
```

---

## Database Schema

### Tabel: vocalization_training

Tracking van training status per soort.

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
```

### Tabel: vocalization_model_versions

Kwartaal versie tracking voor periodieke hertraining.

```sql
CREATE TABLE vocalization_model_versions (
    id SERIAL PRIMARY KEY,
    species_name VARCHAR(100) NOT NULL,
    version VARCHAR(10) NOT NULL,        -- bijv. '2025Q1', '2025Q4'
    model_file VARCHAR(255) NOT NULL,    -- bijv. 'merel_cnn_2025Q4.pt'
    accuracy FLOAT,
    is_active BOOLEAN DEFAULT FALSE,     -- TRUE = beste model voor deze soort
    training_samples INTEGER,
    epochs_trained INTEGER,
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(species_name, version)
);
```

Het systeem selecteert automatisch het beste model per soort op basis van accuracy.

| Kolom | Type | Beschrijving |
|-------|------|--------------|
| species_name | VARCHAR | Nederlandse naam (bijv. "Roodborst") |
| scientific_name | VARCHAR | Wetenschappelijke naam (bijv. "Erithacus rubecula") |
| status | VARCHAR | pending, processing, training, completed, failed |
| phase | VARCHAR | Huidige fase (bijv. "Epoch 15/30") |
| progress_pct | INTEGER | Voortgang 0-100% |
| accuracy | FLOAT | Uiteindelijke model nauwkeurigheid |
| spectrograms_count | INTEGER | Aantal spectrogrammen |
| error_message | TEXT | Foutmelding bij failure |

### Tabel: xeno_canto_recordings

Metadata van gedownloade audio voor wereldkaart visualisatie.

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
```

### Tabel: vocalization_confusion_matrix

Confusion matrix data voor dashboard visualisatie.

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
```

---

## API Integraties

### Xeno-canto API v3

[Xeno-canto](https://xeno-canto.org) is een open database met vogelgeluiden uit de hele wereld.

**API Key verkrijgen:**
1. Maak account op https://xeno-canto.org
2. Ga naar https://xeno-canto.org/explore/api
3. Genereer API key

**Rate limiting:** 2 seconden tussen requests (automatisch ingebouwd)

**Query format:**
```
GET https://xeno-canto.org/api/3/recordings
?query=sp:"Erithacus rubecula" type:song q:A
&key=JOUW_API_KEY
```

**Response structuur:**
```json
{
  "recordings": [
    {
      "id": "123456",
      "sp": "Erithacus rubecula",
      "en": "European Robin",
      "type": "song",
      "q": "A",
      "cnt": "Netherlands",
      "lat": "52.1234",
      "lng": "5.5678",
      "file": "https://..."
    }
  ]
}
```

### Fallback: Web Scraping

Als geen API key beschikbaar is, wordt web scraping gebruikt:
- Langzamer (extra verzoeken nodig)
- Parse HTML van explore pagina
- Haal details per opname op

---

## Monitoring

### Grafana Dashboard

Het dashboard "Vocalization Training Monitor" bevat 54 panels:

**Overzicht:**
- Training voortgang tabel
- Status verdeling (pie chart)
- Totale spectrogrammen
- Gemiddelde accuracy

**Details per soort:**
- Huidige fase en voortgang
- Accuracy trend over epochs
- Training snelheid (epochs/uur)

**Xeno-canto data:**
- Wereldkaart met audio locaties
- Landen statistieken
- Kwaliteitsverdeling

**Model analyse:**
- Confusion matrix per soort
- Accuracy vergelijking
- Correlatie spectrogrammen vs accuracy

### Dashboard importeren

1. Ga naar Grafana → Dashboards → Import
2. Upload `/mnt/nas-docker/emsn-vocalization/vocalization-training-dashboard.json`
3. Selecteer PostgreSQL datasource

---

## Technische Details

### CNN Architectuur

```python
VocalizationCNN(
  # Conv block 1
  Conv2d(1, 32, kernel_size=3, padding=1)
  BatchNorm2d(32)
  ReLU()
  MaxPool2d(2, 2)
  Dropout2d(0.25)

  # Conv block 2
  Conv2d(32, 64, kernel_size=3, padding=1)
  ...

  # Conv block 3
  Conv2d(64, 128, kernel_size=3, padding=1)
  ...

  # Conv block 4
  Conv2d(128, 256, kernel_size=3, padding=1)
  BatchNorm2d(256)
  ReLU()
  AdaptiveAvgPool2d((1, 1))  # Global average pooling

  # Classifier
  Flatten()
  Linear(256, 128)
  ReLU()
  Dropout(0.5)
  Linear(128, 3)  # song, call, alarm
)
```

**Parameters:** ~500K trainable parameters

### Spectrogram configuratie

| Parameter | Waarde | Beschrijving |
|-----------|--------|--------------|
| Sample rate | 22050 Hz | Audio sample rate |
| n_mels | 128 | Mel filterbank bins |
| n_fft | 2048 | FFT window size |
| hop_length | 512 | STFT hop length |
| Segment duur | 3.0 sec | Audio segment lengte |
| Output size | 128x128 | Spectrogram dimensies |

### Training parameters

| Parameter | Waarde | Opmerking |
|-----------|--------|-----------|
| Epochs | 25 (max) | Verlaagd van 30, early stopping compenseert |
| Batch size | 128 | Verhoogd van 64 voor snellere training |
| Early stopping | 5 epochs patience | Verlaagd van 7 voor snellere convergentie |
| Learning rate | 0.001 (Adam) | Start learning rate |
| LR scheduler | ReduceLROnPlateau (patience=3) | Agressievere scheduling |
| Test split | 20% | Stratified split |
| Class weighting | Ja | Automatisch berekend voor imbalance |
| Max samples/klasse | 800 | Voorkomt te grote datasets |
| DataLoader workers | 0 | Inline loading (stabiel op NAS) |

### Nederlandse vogelsoorten

De lijst bevat 232 soorten, georganiseerd op prioriteit:

| Prioriteit | Beschrijving | Aantal |
|------------|--------------|--------|
| 1 | Zeer algemeen (dagelijks te zien) | 53 |
| 2 | Regelmatig voorkomend | 124 |
| 3 | Minder algemeen / zeldzaam | 55 |

---

## Troubleshooting

### Container start niet

```bash
# Check logs
docker logs emsn-vocalization-pytorch

# Rebuild image
docker build -f Dockerfile.pytorch -t emsn-vocalization-pytorch . --no-cache
```

### Database connectie mislukt

```bash
# Test connectie
psql -h 192.168.1.25 -p 5433 -U birdpi_zolder -d emsn

# Check PostgreSQL status
docker logs postgres
```

### Training blijft hangen

1. Check database status:
```sql
SELECT species_name, status, phase, updated_at
FROM vocalization_training
WHERE status = 'training';
```

2. Handmatig status resetten:
```sql
UPDATE vocalization_training
SET status = 'pending', phase = 'Reset'
WHERE species_name = 'Soort naam';
```

### Xeno-canto API errors

- **401 Unauthorized**: Controleer API key
- **429 Too Many Requests**: Rate limiting actief, wacht
- **"only accepts tags"**: Gebruik format `sp:"naam"` niet `naam`

### Geen GPU beschikbaar

Dit is normaal op NAS hardware. PyTorch valt automatisch terug op CPU. Training duurt langer maar werkt correct.

---

## Licentie

Dit project is onderdeel van EMSN 2.0 (Ecologisch Monitoring Systeem Nijverdal).

| Component | Licentie | Toelichting |
|-----------|----------|-------------|
| **Code** | [Apache 2.0](../../LICENSE) | Vrij te gebruiken, ook commercieel, met bronvermelding |
| **Modellen** | [CC BY-NC 4.0](../../MODELS_LICENSE) | Alleen niet-commercieel gebruik; voor commercieel: neem contact op |
| **Audio data** | Xeno-canto CC licenties | Check individuele opnames voor specifieke voorwaarden |

### Citeren

Als je dit project gebruikt in onderzoek of publicaties, citeer dan:

```bibtex
@software{emsn2_vocalization,
  author       = {Hullegie, Ronny},
  title        = {EMSN 2.0 Vocalization Classifier},
  year         = {2025},
  publisher    = {GitHub},
  url          = {https://github.com/ronnyhull/emsn2}
}
```

Zie ook [CITATION.cff](../../CITATION.cff) voor formele citatie-informatie.

---

## Contact

**Project:** EMSN 2.0 - Ecologisch Monitoring Systeem Nijverdal
**Auteur:** Ronny Hullegie
**GitHub:** https://github.com/[username]/emsn2

---

*Laatst bijgewerkt: December 2025*

---

## Changelog

### v2.1 (December 2025)
- **Bug fix:** numpy float64 naar Python float conversie voor PostgreSQL compatibiliteit
- **Bug fix:** DataLoader workers van 2 naar 0 voor stabiliteit op NAS (voorkomt worker crashes)
- **Bug fix:** Volume mount voor train_existing.py zodat code changes live doorwerken
- Licentie structuur toegevoegd (Apache 2.0 code, CC BY-NC 4.0 modellen)
- CITATION.cff voor Zenodo DOI

### v2.0 (December 2025)
- Kwartaal versioning systeem toegevoegd
- Training parameters geoptimaliseerd (40-50% sneller)
- Best model tracking - database selecteert automatisch beste model per soort
- Bug fix: completion status update na confusion matrix save

### v1.0 (December 2024)
- Initiële release
- PyTorch CNN voor 232 Nederlandse vogelsoorten
- Xeno-canto integratie
- Grafana dashboard
