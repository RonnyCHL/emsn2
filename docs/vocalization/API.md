# API Documentatie - Xeno-canto Integratie

Gedetailleerde documentatie over de Xeno-canto API integratie voor het EMSN 2.0 Vocalization Classifier project.

## Overzicht

[Xeno-canto](https://xeno-canto.org) is een citizen science project en online database voor het delen van vogelgeluiden uit de hele wereld. Het bevat meer dan 800.000 opnames van 10.000+ vogelsoorten.

De EMSN Vocalization Classifier gebruikt Xeno-canto als primaire databron voor trainingsaudio.

---

## API Versies

### API v3 (Aanbevolen)

**Vereist API key** - Sneller en betrouwbaarder.

```
Base URL: https://xeno-canto.org/api/3/recordings
```

### Web Scraping Fallback

**Geen API key nodig** - Langzamer, parse HTML pagina's.

```
Base URL: https://xeno-canto.org/explore
```

---

## API Key Verkrijgen

1. **Account aanmaken**: Ga naar https://xeno-canto.org en maak een gratis account
2. **API pagina**: Navigeer naar https://xeno-canto.org/explore/api
3. **Key genereren**: Klik op "Generate API key"
4. **Opslaan**: Kopieer de key en sla veilig op

**Belangrijk:** De API key is persoonlijk en mag niet gedeeld worden.

---

## API v3 Documentatie

### Request Format

```http
GET https://xeno-canto.org/api/3/recordings
  ?query=<search_query>
  &key=<api_key>
  &per_page=<number>
  &page=<number>
```

### Query Syntax

De query gebruikt een tag-gebaseerde syntax:

| Tag | Beschrijving | Voorbeeld |
|-----|--------------|-----------|
| `sp:` | Species (wetenschappelijke naam) | `sp:"Turdus merula"` |
| `en:` | Engelse naam | `en:"Common Blackbird"` |
| `type:` | Vocalisatie type | `type:song` |
| `q:` | Kwaliteit (A-E) | `q:A` |
| `cnt:` | Land | `cnt:"Netherlands"` |
| `rec:` | Recordist | `rec:"John Smith"` |
| `len:` | Lengte (seconden) | `len:">30"` |

### Voorbeeld Requests

**Zoek Merel zang met hoge kwaliteit:**
```http
GET https://xeno-canto.org/api/3/recordings
  ?query=sp:"Turdus merula" type:song q:A
  &key=YOUR_API_KEY
  &per_page=100
```

**Zoek alarmroepen uit Nederland:**
```http
GET https://xeno-canto.org/api/3/recordings
  ?query=sp:"Erithacus rubecula" type:alarm cnt:"Netherlands"
  &key=YOUR_API_KEY
```

### Response Format

```json
{
  "numRecordings": "1234",
  "numSpecies": "1",
  "page": 1,
  "numPages": 13,
  "recordings": [
    {
      "id": "123456",
      "gen": "Turdus",
      "sp": "merula",
      "ssp": "",
      "group": "birds",
      "en": "Common Blackbird",
      "rec": "Recordist Name",
      "cnt": "Netherlands",
      "loc": "Amsterdam, Noord-Holland",
      "lat": "52.3676",
      "lng": "4.9041",
      "alt": "0",
      "type": "song",
      "sex": "male",
      "stage": "adult",
      "method": "field recording",
      "url": "//xeno-canto.org/123456",
      "file": "//xeno-canto.org/123456/download",
      "file-name": "XC123456-Turdus-merula.mp3",
      "sono": {
        "small": "//xeno-canto.org/sounds/uploaded/...",
        "med": "...",
        "large": "...",
        "full": "..."
      },
      "osci": {
        "small": "...",
        "med": "...",
        "large": "..."
      },
      "lic": "//creativecommons.org/licenses/by-nc-sa/4.0/",
      "q": "A",
      "length": "1:23",
      "time": "05:30",
      "date": "2024-05-15",
      "uploaded": "2024-05-16",
      "also": ["Parus major", "Fringilla coelebs"],
      "rmk": "Beautiful dawn chorus recording",
      "bird-seen": "yes",
      "animal-seen": "yes",
      "playback-used": "no",
      "temp": "12",
      "regnr": "",
      "auto": "yes",
      "dvc": "Zoom H5",
      "mic": "Sennheiser ME66",
      "smp": "48000"
    }
  ]
}
```

### Response Velden

| Veld | Type | Beschrijving |
|------|------|--------------|
| `id` | string | Unieke recording ID |
| `gen` | string | Genus |
| `sp` | string | Species |
| `en` | string | Engelse naam |
| `cnt` | string | Land |
| `lat` | string | Breedtegraad |
| `lng` | string | Lengtegraad |
| `type` | string | Vocalisatie type |
| `q` | string | Kwaliteit (A-E) |
| `length` | string | Duur (mm:ss) |
| `file` | string | Download URL |
| `lic` | string | Licentie URL |

---

## Python Client Implementatie

### XenoCantoClient Klasse

```python
from src.collectors.xeno_canto import XenoCantoClient, Recording

# Initialiseer client
client = XenoCantoClient(
    download_dir="data/raw/xeno-canto",
    api_key="YOUR_API_KEY"  # Of via XENO_CANTO_API_KEY env var
)

# Zoek opnames
recordings = client.search(
    species="Turdus merula",
    vocalization_type="song",
    quality=["A", "B"],
    max_results=100
)

# Download dataset
dataset = client.download_dataset(
    species="Turdus merula",
    vocalization_types=["song", "call", "alarm"],
    quality=["A", "B"],
    samples_per_type=50
)
```

### Recording Dataclass

```python
@dataclass
class Recording:
    id: str                 # XC ID
    species: str            # Wetenschappelijke naam
    species_common: str     # Engelse naam
    vocalization_type: str  # Origineel type
    quality: str            # A-E
    length: str             # Duur
    country: str            # Land
    recordist: str          # Opname maker
    url: str                # Xeno-canto URL
    download_url: str       # MP3 download URL
    license: str            # Licentie

    @property
    def filename(self) -> str:
        """Genereer bestandsnaam."""
        voc_type = self.normalize_vocalization_type(self.vocalization_type)
        return f"XC{self.id}_{self.species.replace(' ', '_').lower()}_{voc_type}.mp3"

    @staticmethod
    def normalize_vocalization_type(voc_type: str) -> str:
        """Normaliseer naar song/call/alarm."""
        voc_lower = voc_type.lower()

        if any(p in voc_lower for p in ['song', 'zang', 'singing']):
            return 'song'
        if any(p in voc_lower for p in ['alarm', 'warning', 'distress']):
            return 'alarm'
        return 'call'  # Default
```

### Download Methoden

```python
# Enkele opname downloaden
path = client.download(recording, subdir="song")

# Complete dataset downloaden
dataset = client.download_dataset(
    species="Erithacus rubecula",
    vocalization_types=["song", "call", "alarm"],
    quality=["A", "B", "C"],
    samples_per_type=150
)
# Returns: {"song": [Path, ...], "call": [Path, ...], "alarm": [Path, ...]}
```

---

## Rate Limiting

Xeno-canto API heeft rate limiting. De client respecteert dit automatisch:

```python
class XenoCantoClient:
    def __init__(self):
        self.request_delay = 2.0  # 2 seconden tussen requests

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request = time.time()
```

**Best practices:**
- Minimaal 2 seconden tussen API requests
- Maximaal 500 resultaten per pagina
- Batch downloads vermijden tijdens piekuren

---

## Vocalisatie Type Mapping

Xeno-canto gebruikt diverse type beschrijvingen. Deze worden genormaliseerd:

### Song (Zang)

```
song, zang, singing, subsong, dawn song, full song,
melodious, phrase, motif, advertising song
```

### Call (Roep)

```
call, roep, contact, flight call, begging, feeding,
chip, chirp, twitter, chatter
```

### Alarm

```
alarm, warning, alert, distress, scolding,
mobbing, predator alarm, danger call
```

---

## Kwaliteitsratings

Xeno-canto gebruikt een A-E kwaliteitsschaal:

| Rating | Beschrijving | Aanbevolen voor training |
|--------|--------------|--------------------------|
| **A** | Uitstekend - zeer helder, geen ruis | Ja (primair) |
| **B** | Goed - helder, minimale ruis | Ja |
| **C** | Acceptabel - bruikbaar maar met ruis | Ja (voor meer data) |
| **D** | Matig - significante ruis | Nee |
| **E** | Slecht - moeilijk te identificeren | Nee |

De pipeline gebruikt standaard A, B en C kwaliteit:
```python
quality=["A", "B", "C"]
```

---

## Licenties

Alle Xeno-canto opnames hebben Creative Commons licenties:

| Licentie | Gebruik |
|----------|---------|
| CC BY | Vrij te gebruiken met naamsvermelding |
| CC BY-NC | Niet-commercieel met naamsvermelding |
| CC BY-NC-SA | Niet-commercieel, zelfde licentie |
| CC BY-NC-ND | Niet-commercieel, geen bewerkingen |

**Voor dit project:**
- Training data: Toegestaan onder alle CC licenties
- Model output: Geen directe audio reproductie
- Naamsvermelding: Metadata wordt opgeslagen

---

## Database Integratie

Audio metadata wordt opgeslagen in PostgreSQL:

```python
def save_xeno_canto_metadata(species_name: str, recordings: list):
    """Sla metadata op voor wereldkaart visualisatie."""
    conn = get_pg()
    cur = conn.cursor()

    # Verwijder oude data
    cur.execute(
        "DELETE FROM xeno_canto_recordings WHERE species_name = %s",
        (species_name,)
    )

    # Insert nieuwe data
    for rec in recordings[:100]:  # Max 100 per soort
        cur.execute("""
            INSERT INTO xeno_canto_recordings
            (species_name, xc_id, country, latitude, longitude,
             vocalization_type, quality)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            species_name,
            rec.get('id', ''),
            rec.get('cnt', ''),
            float(rec.get('lat', 0)) if rec.get('lat') else None,
            float(rec.get('lng', 0)) if rec.get('lng') else None,
            rec.get('type', ''),
            rec.get('q', '')
        ))

    conn.commit()
```

---

## Error Handling

### Veelvoorkomende fouten

| Error | Oorzaak | Oplossing |
|-------|---------|-----------|
| 401 Unauthorized | Ongeldige API key | Check key, genereer nieuwe |
| 429 Too Many Requests | Rate limit bereikt | Verhoog request_delay |
| 404 Not Found | Opname verwijderd | Skip en ga door |
| Timeout | Trage verbinding | Verhoog timeout |

### Retry Logic

```python
def _search_with_retry(self, query: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            response = self.session.get(
                self.API_V3_URL,
                params={'query': query, 'key': self.api_key},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))  # Exponential backoff
            else:
                raise
```

---

## Voorbeeld Workflow

### Complete pipeline voor één soort

```python
#!/usr/bin/env python3
from src.collectors.xeno_canto import XenoCantoClient

# 1. Initialiseer client
client = XenoCantoClient(
    download_dir="data/raw/xeno-canto-roodborst",
    api_key="YOUR_API_KEY"
)

# 2. Download audio per type
dataset = client.download_dataset(
    species="Erithacus rubecula",
    vocalization_types=["song", "call", "alarm"],
    quality=["A", "B", "C"],
    samples_per_type=150
)

# 3. Toon resultaten
for voc_type, files in dataset.items():
    print(f"{voc_type}: {len(files)} bestanden")

# Output:
# song: 142 bestanden
# call: 138 bestanden
# alarm: 89 bestanden
```

### Metadata ophalen voor wereldkaart

```python
import requests

def fetch_locations(species_name: str, scientific_name: str, api_key: str):
    """Haal locaties op voor dashboard visualisatie."""
    url = f"https://xeno-canto.org/api/3/recordings"
    params = {
        'query': f'sp:"{scientific_name}"',
        'key': api_key,
        'per_page': 100
    }

    response = requests.get(url, params=params, timeout=30)
    data = response.json()

    locations = []
    for rec in data.get('recordings', []):
        if rec.get('lat') and rec.get('lng'):
            locations.append({
                'species': species_name,
                'lat': float(rec['lat']),
                'lng': float(rec['lng']),
                'country': rec.get('cnt', ''),
                'type': rec.get('type', '')
            })

    return locations
```

---

## Referenties

- **Xeno-canto Website:** https://xeno-canto.org
- **API Documentatie:** https://xeno-canto.org/explore/api
- **Terms of Use:** https://xeno-canto.org/terms

---

*Document versie: 1.0 - December 2024*
