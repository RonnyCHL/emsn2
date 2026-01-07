---
name: session-end
description: Sluit een werksessie netjes af met samenvatting en git commit. Gebruik aan het einde van elke sessie of wanneer de gebruiker klaar is.
---

# Sessie Afsluiten

## Wanneer Gebruiken

- Aan het einde van elke werksessie
- Wanneer Ronny zegt "we zijn klaar" of "sessie afsluiten"
- Na het afronden van een grote taak

## Stappen

### 1. Samenvatting Maken

Maak een bestand in `/home/ronny/emsn2/docs/samenvattingen/` met format:
`sessie_YYYY-MM-DD_onderwerp.md`

Inhoud:
```markdown
# Sessie Samenvatting - [Datum]

## Onderwerp
[Korte beschrijving van de sessie]

## Uitgevoerde Taken
- [Taak 1]
- [Taak 2]

## Gewijzigde Bestanden
- `pad/naar/bestand.py` - [wat gewijzigd]

## Technische Details
[Relevante technische informatie voor toekomstige referentie]

## Open Punten
- [ ] [Eventuele vervolgacties]

## Notities
[Overige opmerkingen]
```

### 2. Git Status Controleren

```bash
cd /home/ronny/emsn2
git status
git diff --stat
```

### 3. Committen en Pushen

```bash
git add -A
git commit -m "docs: sessie samenvatting [onderwerp]"
git push origin main
```

## Belangrijk

- Documentatie altijd in het **Nederlands**
- Commit messages in het **Engels** (conventie)
- Controleer of alle wijzigingen meegenomen zijn
- Vermeld geen credentials in samenvattingen
