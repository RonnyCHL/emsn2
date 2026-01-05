# Sessie Samenvatting: Nestkast AI Hertraining

**Datum:** 5 januari 2026
**Onderwerp:** Nestkast species detectie model werkte niet - slapende Koolmees niet herkend

## Probleem

Het AI model voor nestkast bezettingsdetectie herkende de slapende Koolmees in de midden nestkast niet:
- Model output: 92.7% "leeg", 7.3% "koolmees"
- Werkelijkheid: Duidelijk zichtbare vogel in screenshot
- Oorzaak: Model getraind met slechts 112 samples

## Oplossing

### 1. Handmatig event toegevoegd
- Event "bezet" + "Koolmees" voor midden nestkast geregistreerd via API
- Dashboard toont nu correcte status

### 2. Training data verzameld
- 275 koolmees screenshots (midden nestkast dec 2025 + jan 2026)
- 539 leeg screenshots (voor + achter nestkast dec 2025 + jan 2026)
- Totaal: 814 afbeeldingen (was 112)

### 3. Model hertraind via Google Colab
- Data gesync naar Google Drive via rclone
- Notebook gepusht naar GitHub voor directe Colab link
- Training met MobileNetV2 + transfer learning

### 4. Resultaat
| Metric | Oud Model | Nieuw Model |
|--------|-----------|-------------|
| Training samples | 112 | 651 |
| Beste accuracy | 92.5% | **99.4%** |
| Midden detectie | 7.3% koolmees | **99.8% koolmees** |

## Bestanden

- **Notebook:** `/home/ronny/emsn2/notebooks/nestbox_species_training.ipynb`
- **Colab link:** https://colab.research.google.com/github/RonnyCHL/emsn2/blob/main/notebooks/nestbox_species_training.ipynb
- **Model:** `/mnt/nas-birdnet-archive/nestbox/models/nestbox_species_model.pt`
- **Training data (Drive):** `gdrive:EMSN/nestbox_training/`

## Commando's voor toekomstige hertraining

```bash
# 1. Sync nieuwe training data naar Drive
rclone sync /mnt/nas-birdnet-archive/nestbox/training/ gdrive:EMSN/nestbox_training/

# 2. Train in Colab (open notebook link hierboven)

# 3. Download en installeer nieuw model
rclone copy gdrive:EMSN/nestbox_training/nestbox_species_model.pt /tmp/
cp /tmp/nestbox_species_model.pt /mnt/nas-birdnet-archive/nestbox/models/

# 4. Test
/home/ronny/emsn2/venv/bin/python3 \
  /home/ronny/emsn2/scripts/nestbox/nestbox_occupancy_detector.py \
  --all --verbose
```

## Status

- [x] Probleem geanalyseerd
- [x] Handmatig event toegevoegd
- [x] Training data verzameld (814 samples)
- [x] Data naar Google Drive gesync
- [x] Notebook naar GitHub gepusht
- [x] Model getraind in Colab (99.4% accuracy)
- [x] Model gedownload en geinstalleerd
- [x] Detectie getest - werkt correct
