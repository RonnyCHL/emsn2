# Bijdragen aan EMSN 2.0

Bedankt voor je interesse in het bijdragen aan het EcoMonitoring Systeem Nijverdal! Dit document beschrijft hoe je kunt bijdragen.

## Manieren om bij te dragen

### 1. Bug Reports

Vond je een bug? Open een [GitHub Issue](https://github.com/ronnyhull/emsn2/issues) met:

- Duidelijke titel die het probleem beschrijft
- Stappen om het probleem te reproduceren
- Verwacht gedrag vs. werkelijk gedrag
- Logs of error messages (indien van toepassing)
- Omgeving (OS, Python versie, Docker versie)

### 2. Feature Requests

Heb je een idee voor een nieuwe feature? Open een Issue met:

- Beschrijving van de gewenste functionaliteit
- Use case: waarom is dit nuttig?
- Mogelijke implementatie (optioneel)

### 3. Code Contributions

#### Development Setup

```bash
# Clone de repository
git clone https://github.com/ronnyhull/emsn2.git
cd emsn2

# Maak een feature branch
git checkout -b feature/mijn-feature

# Installeer dependencies (voor vocalization)
cd scripts/vocalization
pip install -r requirements.txt
```

#### Code Style

- Python code volgt [PEP 8](https://pep8.org/)
- Documentatie in het Nederlands (code comments in Engels)
- Type hints waar mogelijk
- Docstrings voor alle publieke functies

#### Pull Request Process

1. Fork de repository
2. Maak een feature branch (`git checkout -b feature/amazing-feature`)
3. Commit je changes (`git commit -m 'feat: add amazing feature'`)
4. Push naar de branch (`git push origin feature/amazing-feature`)
5. Open een Pull Request

#### Commit Message Format

We gebruiken conventional commits:

```
type: korte beschrijving

[optioneel] Langere beschrijving

[optioneel] BREAKING CHANGE: beschrijving
```

Types:
- `feat`: nieuwe functionaliteit
- `fix`: bug fix
- `docs`: documentatie updates
- `chore`: onderhoud/opruimen
- `refactor`: code refactoring
- `test`: tests toevoegen/aanpassen

### 4. Documentatie

Verbeteringen aan documentatie zijn altijd welkom:

- Typo's corrigeren
- Voorbeelden toevoegen
- Onduidelijke secties verduidelijken
- Vertalingen (Engels)

### 5. Vogelsoorten toevoegen

Wil je een nieuwe vogelsoort toevoegen aan de classifier?

1. Voeg de soort toe aan `dutch_bird_species.py`:
```python
{
    'dutch_name': 'Nieuwe Soort',
    'scientific_name': 'Species novus',
    'priority': 2  # 1=zeer algemeen, 2=regelmatig, 3=zeldzaam
}
```

2. Test of Xeno-canto voldoende opnames heeft (minimaal 50 per type)

3. Open een PR met de toevoeging

## Vocalization Classifier Specifiek

### Model Training

Als je aan de vocalization classifier werkt:

- Test lokaal voordat je een PR opent
- Zorg dat training compleet is (status 'completed' in database)
- Documenteer accuracy resultaten

### Database Changes

Wijzigingen aan het database schema:

1. Update `create_tables.sql`
2. Update `docs/vocalization/DATABASE.md`
3. Maak migratie script indien nodig

## Code of Conduct

- Wees respectvol en constructief
- Help anderen leren
- Geef credit waar dat verschuldigd is
- Focus op het probleem, niet de persoon

## Vragen?

Open een Issue met het label `question` of neem contact op via GitHub.

---

Bedankt voor je bijdrage! Elke bijdrage, hoe klein ook, wordt gewaardeerd.
