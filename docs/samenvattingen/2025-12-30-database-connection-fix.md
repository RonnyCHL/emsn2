# Sessie Samenvatting - 30 december 2025

## Onderwerp
Database connection leak fix en Ulanzi detection age filter

## Probleem 1: Database Connection Slots Vol
Op 28 december was de PostgreSQL database onbereikbaar:
```
FATAL: remaining connection slots are reserved for roles with the SUPERUSER attribute
```

### Oorzaak
Twee scripts lieten database connecties open in "idle in transaction" status:
- `cooldown_display.py` - draait continu, lekte elke 30 seconden
- `vocalization_enricher.py` - lekte bij elke batch verwerking

**Root cause:** psycopg2 gebruikt standaard transactie modus. De `with cursor:` context manager sluit wel de cursor, maar niet de transactie.

### Oplossing
`autocommit = True` toegevoegd aan beide scripts bij database connectie:
```python
self.pg_conn = psycopg2.connect(**PG_CONFIG)
self.pg_conn.autocommit = True  # Voorkom idle in transaction
```

### Resultaat
| Metric | Voor | Na |
|--------|------|-----|
| Idle in transaction | 2+ | 0 |
| Connection slots vrij | 0 | 87 |

## Probleem 2: Ulanzi Detection Age
De MQTT publisher stuurde detecties tot 1 uur oud naar de Ulanzi.

### Oplossing
Age filter aangepast van 1 uur naar 15 minuten:
```python
MAX_DETECTION_AGE_SECONDS = 900  # 15 minuten
```

## Bestanden Gewijzigd

### Zolder
- `scripts/ulanzi/cooldown_display.py` - autocommit + context managers
- `scripts/vocalization/vocalization_enricher.py` - autocommit + context managers
- `scripts/mqtt/birdnet_mqtt_publisher.py` - age filter 15 min

### Berging
- `scripts/vocalization/vocalization_enricher.py` - gekopieerd van zolder

## Services Herstart
- emsn-cooldown-display.service (zolder)
- vocalization-enricher.service (zolder + berging)
- birdnet-mqtt-publisher.service (zolder)

## Verificatie
- Anti-spam cooldown werkt: 96% Ekster detecties geblokkeerd
- Grafana dashboard "Actieve Cooldowns" toont leesbare tijden (HH:MM:SS)
- Geen idle in transaction connecties meer

## Geleerde Les
Bij psycopg2: gebruik `autocommit=True` voor scripts die continu draaien of alleen SELECT queries uitvoeren. Dit voorkomt dat transacties open blijven staan.
