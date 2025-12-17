# Handmatige Vogelwaarneming via Home Assistant

**Datum:** 2025-12-17
**Status:** Voltooid

## Samenvatting

Een Home Assistant dashboard en API voor het handmatig toevoegen van vogelwaarnemingen aan de BirdNET-Pi database. Dit is voor situaties waarin je buiten bent en een vogel hoort die BirdNET-Pi gemist heeft.

## Wat is gebouwd

### 1. API Endpoints (Python Flask)

Toegevoegd aan `/home/ronny/emsn2/reports-web/api.py`:

| Endpoint | Methode | Functie |
|----------|---------|---------|
| `/api/manual-detection` | POST | Voeg handmatige waarneming toe |
| `/api/bird-species` | GET | Haal vogelsoorten lijst op (met zoekfunctie) |
| `/api/manual-detections` | GET | Bekijk handmatig toegevoegde waarnemingen |

**POST payload voorbeeld:**
```json
{
  "common_name": "Buizerd",
  "timestamp": "2025-12-17T14:30:00",
  "signal_quality": "duidelijk",
  "notes": "Vloog over richting NO"
}
```

### 2. Home Assistant Helpers

| Entity ID | Type | Functie |
|-----------|------|---------|
| `input_select.vogel_soort` | Dropdown | 150+ vogelsoorten |
| `input_select.geluidskwaliteit` | Dropdown | Duidelijk / Zwak / Ver weg |
| `input_datetime.waarneming_tijd` | DateTime | Aangepaste tijd |
| `input_boolean.gebruik_huidige_tijd` | Toggle | Huidige tijd gebruiken |
| `input_text.vogel_opmerking` | Tekstveld | Opmerkingen |

### 3. Home Assistant Script

`script.vogel_waarneming_opslaan` - Roept de API aan met de ingevulde gegevens.

### 4. Dashboard

Nieuw dashboard: **EMSN-Vogels** (`vogels-dashboard.yaml`)
- Invoerformulier met alle velden
- Tips voor gebruik
- Link naar recente waarnemingen

### 5. REST Command

```yaml
rest_command:
  post_vogel_waarneming:
    url: "http://192.168.1.178:8081/api/manual-detection"
    method: POST
    ...
```

## Database Opslag

Handmatige waarnemingen worden opgeslagen in de `bird_detections` tabel met:
- `station`: 'berging'
- `confidence`: 1.0000 (hoogste waarde)
- `file_name`: `[HANDMATIG] Kwaliteit: <kwaliteit> | <opmerking>`
- `detected_by_berging`: TRUE

Dit maakt het eenvoudig om handmatige entries te filteren:
```sql
SELECT * FROM bird_detections WHERE file_name LIKE '[HANDMATIG]%';
```

## Gebruik

1. Open Home Assistant
2. Ga naar **EMSN-Vogels** dashboard
3. Selecteer de vogelsoort (zoekbaar door te typen)
4. Kies geluidskwaliteit
5. Optioneel: schakel "Gebruik huidige tijd" uit en stel een andere tijd in
6. Optioneel: voeg een opmerking toe
7. Klik op **Opslaan**

## Toekomstige Uitbreidingen

- [ ] Database migratie uitvoeren voor dedicated `source`, `signal_quality`, `notes` kolommen
- [ ] Grafana dashboard voor handmatige waarnemingen
- [ ] Zoekfunctie in vogelsoorten dropdown (HACS custom card)
- [ ] Push notificatie na opslaan

## Bestanden

- `/home/ronny/emsn2/reports-web/api.py` - API endpoints
- `/home/ronny/emsn2/database/migrations/016_manual_detections.sql` - DB migratie (optioneel)
- Home Assistant config:
  - `configuration.yaml` - rest_command + dashboard registratie
  - `vogels-dashboard.yaml` - Dashboard layout
  - `input_select.yaml`, `input_text.yaml`, etc. - Helpers
