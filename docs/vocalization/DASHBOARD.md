# Grafana Dashboard Documentatie

Uitgebreide documentatie voor het "Vocalization Training Monitor" Grafana dashboard met 54 panels voor real-time monitoring van de vogelgeluid classifier training.

## Overzicht

Het dashboard biedt volledig inzicht in:
- Training voortgang per soort
- Audio data herkomst (wereldkaart)
- Model performance (confusion matrices)
- Statistieken en trends

**Dashboard UID:** `emsn-vocalization-training`
**Datasource:** PostgreSQL-EMSN

---

## Panel Categorieën

### 1. Overzicht Statistieken

| Panel | Type | Beschrijving |
|-------|------|--------------|
| Totaal Soorten | Stat | Aantal unieke soorten in database |
| Voltooide Modellen | Stat | Aantal soorten met status 'completed' |
| In Training | Stat | Aantal soorten momenteel in training |
| Gemiddelde Accuracy | Gauge | Gemiddelde accuracy over alle modellen |
| Totaal Spectrogrammen | Stat | Som van alle spectrograms_count |

### 2. Training Status

| Panel | Type | Beschrijving |
|-------|------|--------------|
| Training Voortgang | Table | Gedetailleerde tabel per soort |
| Status Verdeling | Pie Chart | Verdeling pending/training/completed/failed |
| Voortgang Timeline | Time Series | Voortgang over tijd |
| Training Snelheid | Bar Gauge | Epochs per uur per soort |

### 3. Xeno-canto Data

| Panel | Type | Beschrijving |
|-------|------|--------------|
| Audio Herkomst Wereldkaart | Geomap | Locaties van alle audio opnames |
| Landen Statistieken | Bar Chart | Aantal opnames per land |
| Kwaliteitsverdeling | Pie Chart | Verdeling A/B/C/D/E ratings |
| Vocalisatie Types | Bar Chart | Verdeling song/call/alarm |

### 4. Model Performance

| Panel | Type | Beschrijving |
|-------|------|--------------|
| Confusion Matrix | Heatmap | Per-soort confusion matrix |
| Accuracy Vergelijking | Bar Chart | Accuracy per soort |
| Top 10 Beste Modellen | Table | Hoogste accuracy scores |
| Accuracy vs Spectrogrammen | Scatter | Correlatie analyse |

### 5. Model Versies (Kwartaal Tracking)

| Panel | Type | Beschrijving |
|-------|------|--------------|
| Actieve Modellen | Table | Huidige actieve versie per soort |
| Versie Historie | Table | Alle versies met accuracy trend |
| Versie Vergelijking | Bar Chart | Accuracy per versie per soort |
| Kwartaal Statistieken | Stat | Modellen per kwartaal |

---

## Panel Configuraties

### Training Voortgang Tabel

**Query:**
```sql
SELECT
    species_name as "Soort",
    CASE status
        WHEN 'training' THEN '🔄 Training'
        WHEN 'completed' THEN '✅ Voltooid'
        WHEN 'processing' THEN '⏳ Verwerken'
        WHEN 'failed' THEN '❌ Mislukt'
        ELSE '⏸️ Wachtend'
    END as "Status",
    phase as "Fase",
    progress_pct as "Voortgang %",
    ROUND(accuracy * 100, 1) as "Accuracy %",
    spectrograms_count as "Spectrogrammen",
    CASE
        WHEN updated_at > NOW() - INTERVAL '5 minutes' THEN '🟢'
        WHEN updated_at > NOW() - INTERVAL '30 minutes' THEN '🟡'
        ELSE '🔴'
    END as "Actief"
FROM vocalization_training
ORDER BY
    CASE status
        WHEN 'training' THEN 1
        WHEN 'processing' THEN 2
        WHEN 'pending' THEN 3
        WHEN 'completed' THEN 4
        ELSE 5
    END,
    updated_at DESC;
```

**Opties:**
- Column widths: Soort 150px, Status 100px
- Pagination: 15 rijen per pagina
- Sorting: Enabled

---

### Status Verdeling Pie Chart

**Query:**
```sql
SELECT
    CASE status
        WHEN 'completed' THEN 'Voltooid'
        WHEN 'training' THEN 'Training'
        WHEN 'processing' THEN 'Verwerken'
        WHEN 'failed' THEN 'Mislukt'
        ELSE 'Wachtend'
    END as status,
    COUNT(*) as count
FROM vocalization_training
GROUP BY status;
```

**Opties:**
- Legend: Bottom
- Colors: Voltooid=#73BF69, Training=#FADE2A, Mislukt=#F2495C

---

### Wereldkaart (Geomap)

**Query:**
```sql
SELECT
    latitude as "lat",
    longitude as "lng",
    species_name as "species",
    country,
    vocalization_type as "type",
    quality
FROM xeno_canto_recordings
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL
  AND latitude BETWEEN -90 AND 90
  AND longitude BETWEEN -180 AND 180;
```

**Opties:**
- Base layer: CartoDB Positron
- Marker size: 3px
- Clustering: Enabled (zoom < 5)
- Tooltip: species, country, type

---

### Confusion Matrix Heatmap

**Query:**
```sql
SELECT
    species_name,
    true_label,
    predicted_label,
    count
FROM vocalization_confusion_matrix
WHERE species_name = '$species'
ORDER BY true_label, predicted_label;
```

**Opties:**
- Color scheme: Blues
- Cell display: Value
- Variable: species (dropdown van alle voltooide soorten)

---

### Accuracy Vergelijking

**Query:**
```sql
SELECT
    species_name as "Soort",
    ROUND(accuracy * 100, 1) as "Accuracy"
FROM vocalization_training
WHERE status = 'completed'
  AND accuracy IS NOT NULL
ORDER BY accuracy DESC
LIMIT 20;
```

**Opties:**
- Orientation: Horizontal
- Color by value: Green > 60%, Yellow 40-60%, Red < 40%

---

### Project Statistieken

**Query:**
```sql
SELECT
    COUNT(*) as "Totaal Soorten",
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as "Voltooid",
    SUM(CASE WHEN status = 'training' THEN 1 ELSE 0 END) as "In Training",
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as "Mislukt",
    SUM(spectrograms_count) as "Totaal Spectrogrammen",
    ROUND(AVG(CASE WHEN accuracy IS NOT NULL THEN accuracy END) * 100, 1) as "Gem. Accuracy %",
    ROUND(
        EXTRACT(EPOCH FROM (MAX(completed_at) - MIN(started_at))) / 3600, 1
    ) as "Training Uren"
FROM vocalization_training;
```

---

### Xeno-canto Statistieken

**Query:**
```sql
SELECT
    COUNT(*) as "Totaal Opnames",
    COUNT(DISTINCT species_name) as "Unieke Soorten",
    COUNT(DISTINCT country) as "Landen",
    ROUND(AVG(CASE WHEN quality = 'A' THEN 100
                   WHEN quality = 'B' THEN 80
                   WHEN quality = 'C' THEN 60
                   WHEN quality = 'D' THEN 40
                   ELSE 20 END), 1) as "Gem. Kwaliteit Score"
FROM xeno_canto_recordings;
```

---

## Variables

Het dashboard gebruikt de volgende template variables:

### $species

**Query:**
```sql
SELECT DISTINCT species_name
FROM vocalization_training
WHERE status = 'completed'
ORDER BY species_name;
```

**Type:** Query
**Multi-value:** No
**Include All:** No

---

## Alerts

### Training Stalled Alert

**Condition:** Geen update in 30 minuten voor training status

```sql
SELECT species_name, updated_at
FROM vocalization_training
WHERE status = 'training'
  AND updated_at < NOW() - INTERVAL '30 minutes';
```

### High Failure Rate Alert

**Condition:** Meer dan 10% van soorten gefaald

```sql
SELECT
    COUNT(*) FILTER (WHERE status = 'failed') as failed,
    COUNT(*) as total,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE status = 'failed') / COUNT(*), 1
    ) as failure_rate
FROM vocalization_training
HAVING ROUND(
    100.0 * COUNT(*) FILTER (WHERE status = 'failed') / COUNT(*), 1
) > 10;
```

---

## Dashboard JSON Export

Het volledige dashboard is geëxporteerd naar:
```
/mnt/nas-docker/emsn-vocalization/vocalization-training-dashboard.json
```

### Importeren

1. Grafana → Dashboards → Import
2. Upload JSON file of paste content
3. Selecteer datasource: `PostgreSQL-EMSN`
4. Klik Import

### Exporteren (na wijzigingen)

1. Open dashboard
2. Dashboard settings (tandwiel)
3. JSON Model (linker menu)
4. Copy to clipboard of Save to file

---

## Troubleshooting

### "No Data" in panels

1. Check datasource connectie:
   - Configuration → Data Sources → PostgreSQL-EMSN → Save & Test

2. Check of tabellen data bevatten:
   ```sql
   SELECT COUNT(*) FROM vocalization_training;
   SELECT COUNT(*) FROM xeno_canto_recordings;
   ```

3. Check time range: sommige queries gebruiken geen time filter

### Wereldkaart toont geen markers

1. Verifieer dat latitude/longitude niet NULL zijn:
   ```sql
   SELECT COUNT(*) FROM xeno_canto_recordings
   WHERE latitude IS NOT NULL;
   ```

2. Check coordinate ranges (-90 tot 90, -180 tot 180)

3. Zoom uit naar wereldniveau

### Confusion matrix leeg

1. Verifieer dat er data is voor geselecteerde soort:
   ```sql
   SELECT * FROM vocalization_confusion_matrix
   WHERE species_name = 'Roodborst';
   ```

2. Alleen voltooide modellen hebben confusion matrix data

---

## Model Versies Panels

### Actieve Modellen Tabel

**Query:**
```sql
SELECT
    v.species_name as "Soort",
    v.version as "Versie",
    ROUND((v.accuracy * 100)::numeric, 1) as "Accuracy %",
    v.training_samples as "Samples",
    v.epochs_trained as "Epochs",
    TO_CHAR(v.trained_at, 'DD-MM-YYYY HH24:MI') as "Getraind"
FROM vocalization_model_versions v
WHERE v.is_active = TRUE
ORDER BY v.accuracy DESC;
```

**Opties:**
- Visualisatie: Table
- Column widths: Soort 120px, Versie 80px
- Color by value: Accuracy kolom groen > 50%

---

### Versie Historie per Soort

**Query:**
```sql
SELECT
    species_name as "Soort",
    version as "Versie",
    ROUND((accuracy * 100)::numeric, 1) as "Accuracy %",
    training_samples as "Samples",
    CASE WHEN is_active THEN '✅' ELSE '' END as "Actief",
    TO_CHAR(trained_at, 'DD-MM-YYYY') as "Datum"
FROM vocalization_model_versions
WHERE species_name = '$species'
ORDER BY trained_at DESC;
```

**Opties:**
- Variable: $species (dropdown)
- Visualisatie: Table

---

### Versie Vergelijking Bar Chart

**Query:**
```sql
SELECT
    version as "Versie",
    species_name as "Soort",
    ROUND((accuracy * 100)::numeric, 1) as "Accuracy"
FROM vocalization_model_versions
WHERE accuracy IS NOT NULL
ORDER BY version, species_name;
```

**Opties:**
- Visualisatie: Bar Chart
- Group by: version
- Orientation: Vertical
- Legend: Bottom

---

### Kwartaal Statistieken

**Query:**
```sql
SELECT
    version as "Kwartaal",
    COUNT(*) as "Modellen",
    ROUND((AVG(accuracy) * 100)::numeric, 1) as "Gem. Accuracy %",
    SUM(training_samples) as "Totaal Samples"
FROM vocalization_model_versions
GROUP BY version
ORDER BY version DESC;
```

**Opties:**
- Visualisatie: Table of Stat panels

---

### Accuracy Trend per Soort

**Query:**
```sql
SELECT
    trained_at as time,
    species_name as metric,
    ROUND((accuracy * 100)::numeric, 1) as value
FROM vocalization_model_versions
WHERE accuracy IS NOT NULL
ORDER BY trained_at;
```

**Opties:**
- Visualisatie: Time series
- Legend: Als tabel rechts
- Tooltip: All series

---

### Beste vs Slechtste Versies

**Query:**
```sql
WITH ranked AS (
    SELECT
        species_name,
        version,
        accuracy,
        ROW_NUMBER() OVER (PARTITION BY species_name ORDER BY accuracy DESC) as best_rank,
        ROW_NUMBER() OVER (PARTITION BY species_name ORDER BY accuracy ASC) as worst_rank
    FROM vocalization_model_versions
    WHERE accuracy IS NOT NULL
)
SELECT
    species_name as "Soort",
    MAX(CASE WHEN best_rank = 1 THEN version END) as "Beste Versie",
    ROUND((MAX(CASE WHEN best_rank = 1 THEN accuracy END) * 100)::numeric, 1) as "Beste %",
    MAX(CASE WHEN worst_rank = 1 THEN version END) as "Slechtste Versie",
    ROUND((MAX(CASE WHEN worst_rank = 1 THEN accuracy END) * 100)::numeric, 1) as "Slechtste %",
    ROUND(((MAX(CASE WHEN best_rank = 1 THEN accuracy END) -
           MAX(CASE WHEN worst_rank = 1 THEN accuracy END)) * 100)::numeric, 1) as "Verschil %"
FROM ranked
GROUP BY species_name
HAVING COUNT(*) > 1
ORDER BY "Verschil %" DESC;
```

**Opties:**
- Visualisatie: Table
- Alleen zichtbaar als er meerdere versies zijn per soort

---

## Custom Panels Toevoegen

### Nieuwe SQL query panel

1. Add panel → Add new panel
2. Data source: PostgreSQL-EMSN
3. Query mode: Code
4. Schrijf SQL query
5. Selecteer visualisatie type
6. Configureer opties

### Voorbeeld: Laatste 10 voltooide modellen

```sql
SELECT
    species_name as "Soort",
    ROUND(accuracy * 100, 1) as "Accuracy %",
    completed_at as "Voltooid"
FROM vocalization_training
WHERE status = 'completed'
ORDER BY completed_at DESC
LIMIT 10;
```

Visualisatie: Table
Opties: Time column = completed_at

---

## Performance Tips

### Grote datasets

Bij veel data (>100.000 rijen):

1. **Gebruik LIMIT:**
   ```sql
   SELECT ... LIMIT 1000;
   ```

2. **Maak indexes:**
   ```sql
   CREATE INDEX idx_xc_created ON xeno_canto_recordings(created_at);
   ```

3. **Aggregeer data:**
   ```sql
   -- In plaats van alle rijen
   SELECT country, COUNT(*) FROM xeno_canto_recordings GROUP BY country;
   ```

### Refresh rates

- Overzicht panels: 30 seconden
- Detail panels: 1 minuut
- Historische data: 5 minuten

---

## Screenshots

### Training Voortgang
```
┌────────────────────────────────────────────────────────┐
│ Soort        │ Status     │ Fase       │ Voortgang │
├──────────────┼────────────┼────────────┼───────────┤
│ Ekster       │ 🔄 Training │ Epoch 17/30│    75%    │
│ Roodborst    │ ✅ Voltooid │ Voltooid   │   100%    │
│ Pimpelmees   │ ⏸️ Wachtend │ -          │     0%    │
└────────────────────────────────────────────────────────┘
```

### Status Verdeling
```
    ┌─────────────────────┐
    │  Voltooid: 1 (7%)   │
    │  Training: 1 (7%)   │
    │  Wachtend: 12 (86%) │
    └─────────────────────┘
```

---

*Document versie: 1.1 - December 2024*
*Toegevoegd: Model Versies panels voor kwartaal tracking*
