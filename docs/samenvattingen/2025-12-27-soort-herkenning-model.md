# Sessie Samenvatting 27 December 2025 - Soort-Herkenning Model

## Wat is er gedaan

### 1. Soort-Herkenning Model Getraind
- **Probleem**: Het oude model was alleen getraind op nacht screenshots en detecteerde overdag ten onrechte "bezet"
- **Oplossing**: Nieuw model getraind met dag EN nacht screenshots
- **Classes**: `['koolmees', 'leeg']` (ipv alleen bezet/leeg)
- **Accuracy**: 92.6% op validatie set
- **Training**: Google Colab met A100 GPU (Colab Pro+)
- **Model locatie**: `/mnt/nas-birdnet-archive/nestbox/models/nestbox_species_model.pt`

### 2. Training Data Voorbereiding
- Screenshots gesorteerd in training mappen via script
- Totaal 139 screenshots: 119 leeg, 20 koolmees
- Data geüpload naar Google Drive via rclone
- Split: 80% train, 20% validation

### 3. Detector Script Geüpdatet
**Bestand**: `/home/ronny/emsn2/scripts/nestbox/nestbox_occupancy_detector.py`

Wijzigingen:
- `predict_image()` accepteert nu `classes` parameter uit checkpoint
- Retourneert `species` veld (None als leeg, anders soortnaam)
- `save_to_database()` slaat species op in nieuwe kolom
- Backward compatible met oude modellen (fallback naar bezet/leeg)

### 4. Database Schema Uitgebreid
```sql
ALTER TABLE nestbox_occupancy ADD COLUMN species VARCHAR(100);
```

### 5. Grafana Dashboard ML Panels Gefixed
- Datasource type gecorrigeerd naar `grafana-postgresql-datasource`
- Numerieke waarden met value mappings (0=LEEG, 1=BEZET, 2=KOOLMEES)
- Kleuren: blauw=LEEG, oranje=BEZET, groen=KOOLMEES

## Technische Details

### Model Architectuur
- MobileNetV2 met aangepaste classifier
- Transfer learning van ImageNet weights
- Input size: 224x224 pixels
- Classifier: Dropout → Linear(1280,128) → ReLU → Dropout → Linear(128, num_classes)

### Training Parameters (Colab)
- Epochs: 30
- Batch size: 32
- Learning rate: 0.001
- Optimizer: Adam
- Data augmentation: rotation, flip, color jitter

### Checkpoint Structuur
```python
{
    'model_state_dict': ...,
    'classes': ['koolmees', 'leeg'],
    'architecture': 'mobilenet_v2',
    'train_samples': 112,
    'best_val_acc': 92.6
}
```

## Bestanden Gewijzigd/Gemaakt

| Bestand | Actie |
|---------|-------|
| `scripts/nestbox/nestbox_occupancy_detector.py` | Gewijzigd - species support |
| `notebooks/nestbox_species_training.ipynb` | Gemaakt - Colab training notebook |
| `docs/samenvattingen/2025-12-27-soort-herkenning-model.md` | Gemaakt |

## Workflow voor Nieuwe Soorten Toevoegen

1. Verzamel screenshots van de nieuwe soort in `/mnt/nas-birdnet-archive/nestbox/training/{soortnaam}/`
2. Upload naar Google Drive: `rclone copy /path/to/training gdrive:EMSN/nestbox_species/`
3. Open Colab notebook en pas `CLASSES` aan
4. Train model en download naar NAS
5. Model wordt automatisch gebruikt bij volgende detectie run

## Geleerde Lessen

1. **Grafana Stat panels met strings**: Werken niet goed met string values - gebruik numerieke waarden met value mappings
2. **Datasource type**: Moet `grafana-postgresql-datasource` zijn, niet `postgres`
3. **Model fallback**: Altijd een FALLBACK_MODEL_PATH definiëren voor backward compatibility
4. **Training data balans**: Meer samples van ondervertegenwoordigde classes verzamelen voor betere accuracy

## Volgende Stappen

- [ ] Meer koolmees screenshots verzamelen voor hogere accuracy
- [ ] Pimpelmees toevoegen aan model (als die verschijnt)
- [ ] Confidence threshold toevoegen aan dashboard (toon alleen bij >70% confidence)
- [ ] Historische species data visualiseren in Grafana
