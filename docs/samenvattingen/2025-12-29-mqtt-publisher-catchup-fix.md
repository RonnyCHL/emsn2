# Sessie Samenvatting - 29 december 2025 (avond)

## Probleem
Ulanzi display toonde oude vogeldetecties. Onderzoek wees uit dat de MQTT publisher vastgelopen was.

## Oorzaak
1. **State file achtergebleven**: De `birdnet_mqtt_zolder_state.json` was blijven staan op ID 32316 (28 december 13:20)
2. **Pi herstart**: Na reboot op 29 december 11:12 probeerde de publisher 2200+ oude detecties in te halen
3. **CPU-storm**: Elke detectie kreeg vocalization classificatie (CPU-intensief) → 85% CPU-load
4. **Oude detecties naar Ulanzi**: Alle achterstallige detecties werden als "nieuw" naar MQTT gestuurd

## Root cause
De state wordt alleen bijgewerkt na succesvolle `publish_detection()`. Als de vocalization classifier crasht of vastloopt, returned de functie nooit `True` en blijft de state steken.

## Oplossing
Twee beveiligingen toegevoegd aan `birdnet_mqtt_publisher.py`:

### 1. Startup catchup protection
```python
def _check_catchup_needed(self):
    # Bij startup: check of backlog > 50 detecties
    # Zo ja: spring direct naar huidige ID
    # Voorkomt CPU-storm bij herstart na crash/stroomuitval
```

### 2. Age filter
```python
def _is_detection_too_old(self, detection):
    # Detecties ouder dan 1 uur worden niet naar MQTT gestuurd
    # State wordt wel bijgewerkt
    # Vangt edge cases waarbij catchup niet triggert
```

## Configuratie
```python
MAX_CATCHUP_DETECTIONS = 50  # Skip als backlog groter is
MAX_DETECTION_AGE_SECONDS = 3600  # 1 uur max leeftijd
```

## Getest
- Backlog van 100 detecties → automatisch overgeslagen met warning in log
- Service draait stabiel met normale CPU-load

## Bestanden gewijzigd
- `/home/ronny/emsn2/scripts/mqtt/birdnet_mqtt_publisher.py`

## Notitie
Oude detecties gaan niet verloren - ze worden gesynchroniseerd naar PostgreSQL via `lifetime_sync`. De MQTT publisher is alleen voor realtime Ulanzi notificaties.
