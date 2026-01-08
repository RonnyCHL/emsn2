# Sessie Samenvatting - 8 januari 2026

## Nestkast Model Retraining & Automatische Cleanup

### Probleem
Het AI model detecteerde overdag lege nestkasten niet correct. Bij daglicht (09:00) gaf het model nog steeds "bezet" met ~53% confidence terwijl de koolmees al weg was.

**Oorzaak:** Model was alleen getraind op nacht/IR beelden, kende geen daglicht beelden van lege kasten.

### Oplossing: Model Retraining

#### Training Data Preparation
- Script: `scripts/nestbox/training/prepare_training_data.py`
- Labeling strategie:
  - Dag (09:00-17:00) van alle kasten → **leeg**
  - Nacht/avond (17:00-07:00) van midden (jan 2026) → **bezet**
- Dataset: 450 leeg + 200 bezet beelden

#### Colab Training (H100 GPU)
- Notebook: `scripts/nestbox/training/nestbox_training_colab.ipynb`
- Optimalisaties:
  - `torch.compile()` voor H100 speed
  - `bfloat16` precision
  - `BATCH_SIZE = 128` (H100 heeft 80GB VRAM)
  - Data gekopieerd naar lokale SSD
- **Resultaat: 98.5% validatie accuracy**

#### Model Deployment
- Model opgeslagen op NAS: `/mnt/nas-birdnet-archive/nestbox/models/nestbox_model_latest.pt`
- Detector aangepast voor:
  - `torch.compile()` state_dict prefix (`_orig_mod.`)
  - Verschillende classifier architecturen (simpel vs complex)

**Verificatie:** Daglicht beeld wordt nu correct gedetecteerd als "leeg" met 99.98% confidence.

### Nieuwe Feature: Automatische Screenshot Cleanup

#### Doel
Schijfruimte besparen door oude lege beelden te verwijderen, bezette beelden altijd bewaren.

#### Implementatie
- Script: `scripts/nestbox/nestbox_cleanup.py`
- Retentie: **6 maanden** (180 dagen)
- Alleen verwijderen bij: **>90% confidence leeg**
- Timer: Dagelijks om 04:00

#### Bestanden
- `scripts/nestbox/nestbox_cleanup.py` - Cleanup script
- `systemd/nestbox-cleanup.service` - Systemd service
- `systemd/nestbox-cleanup.timer` - Dagelijkse timer

#### Gebruik
```bash
# Dry-run
./nestbox_cleanup.py --dry-run --verbose

# Daadwerkelijk opschonen
./nestbox_cleanup.py

# Andere retentie
./nestbox_cleanup.py --days 90
```

### Wijzigingen Overzicht

| Bestand | Wijziging |
|---------|-----------|
| `nestbox_realtime_detector.py` | torch.compile fix, classifier detectie |
| `nestbox_training_colab.ipynb` | H100 optimalisaties |
| `prepare_training_data.py` | Training data labeling |
| `nestbox_cleanup.py` | **NIEUW** - Automatische cleanup |
| `nestbox-cleanup.service` | **NIEUW** - Systemd service |
| `nestbox-cleanup.timer` | **NIEUW** - Dagelijkse timer |

### Status Services (Zolder)
- `nestbox-screenshot.timer` - Actief (elke 5 min)
- `nestbox-detector.service` - Actief (na screenshot)
- `nestbox-cleanup.timer` - **NIEUW** Actief (dagelijks 04:00)

### Open Punten
- Model monitoren of daglicht detectie stabiel blijft
- Na 6 maanden eerste cleanup resultaten evalueren
