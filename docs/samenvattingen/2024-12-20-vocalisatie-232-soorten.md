# Sessie Samenvatting: Vocalisatie Training Pipeline voor 232 Nederlandse Vogelsoorten

**Datum:** 20 december 2024
**Onderwerp:** Uitbreiding vocalisatie classifier naar alle Nederlandse vogelsoorten

## Wat is er gedaan

### 1. Nederlandse vogelsoorten database
- Complete lijst van **232 Nederlandse vogelsoorten** aangemaakt
- Georganiseerd op prioriteit:
  - Prioriteit 1 (zeer algemeen): 53 soorten
  - Prioriteit 2 (regelmatig): 124 soorten
  - Prioriteit 3 (minder algemeen): 55 soorten
- Bestand: `/mnt/nas-docker/emsn-vocalization/src/dutch_bird_species.py`

### 2. Volledig geautomatiseerde pipeline
- **full_pipeline.py** (440 regels) gemaakt met:
  - Audio download van Xeno-canto API
  - Spectrogram generatie
  - PyTorch CNN training voor song/call/alarm classificatie
  - Progress tracking in PostgreSQL voor Grafana monitoring
  - Resume capability (hervat waar gestopt)
  - Command-line opties: `--priority`, `--resume`, `--species`, `--dry-run`

### 3. Auto-continue configuratie
- `train_existing.py` aangepast om automatisch `full_pipeline.py` te starten
- Na eerste 14 soorten start automatisch training van alle 232 soorten
- Geen handmatige interventie nodig

### 4. GitHub update
- Alle scripts naar git repo gekopieerd
- Commit: `feat: vocalization training pipeline voor 232 Nederlandse vogelsoorten`
- 1316 nieuwe regels code in 5 bestanden

## Nieuwe bestanden

| Bestand | Locatie | Beschrijving |
|---------|---------|--------------|
| dutch_bird_species.py | scripts/vocalization/ | 232 soorten met wetenschappelijke namen |
| full_pipeline.py | scripts/vocalization/ | Complete download→train pipeline |
| train_existing.py | scripts/vocalization/ | Training script met auto-continue |
| auto_continue.py | scripts/vocalization/ | Monitor script voor herstart |

## Technische lessen geleerd

### 1. Hardware beperkingen bepalen software keuzes
De Intel Celeron J4125 in de Synology NAS mist AVX instructies, waardoor TensorFlow crasht. PyTorch werkt prima zonder AVX. Dit is belangrijk voor edge/embedded AI deployments.

### 2. Pragmatisch debuggen
Toen directe SSH commando's in de Docker container timeout gaven, was het effectiever om bestanden op de gemounte NAS te wijzigen die de running container automatisch oppikt.

### 3. Auto-continue patronen
Een simpele `subprocess.run()` aan het einde van een script is een robuuste manier om pipelines te chainen zonder complexe orchestration tools.

### 4. Nederlandse vogelfauna
232 vogelsoorten die in Nederland voorkomen, van de alledaagse Koolmees tot zeldzamere soorten als de Hop en Klapekster.

### 5. Xeno-canto als bron
Uitstekende open database voor vogelgeluiden met:
- Kwaliteitsratings (A/B/C)
- Type-classificaties (song/call/alarm)
- Gratis API toegang
- Wetenschappelijke metadata

## Training status

- **Container:** emsn-vocalization-pytorch
- **Geschatte doorlooptijd:** 3-5 dagen continue
- **Monitoring:** Grafana dashboard "Vocalization Training Monitor"
- **Database:** PostgreSQL tabel `vocalization_training`

## Volgende stappen (automatisch)

1. Eerste 14 soorten afronden (Roodborst t/m Boomkruiper)
2. Automatisch starten full_pipeline.py
3. 232 soorten trainen op prioriteit-volgorde
4. Resultaten zichtbaar in Grafana
