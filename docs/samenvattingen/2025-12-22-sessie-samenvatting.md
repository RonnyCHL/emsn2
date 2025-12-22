# EMSN 2.0 - Sessie Samenvatting 22 december 2025

## Hoofdprobleem opgelost: Python stdlib conflict

### Probleem
De Python standaard library module `secrets` werd overschaduwd door onze eigen `/home/ronny/emsn2/config/secrets.py`. Dit veroorzaakte:
- `ImportError: cannot import name 'randbits' from 'secrets'`
- Librosa (audio processing) kon niet laden
- Vocalization classifier faalde

### Oplossing
- `config/secrets.py` hernoemd naar `config/emsn_secrets.py`
- Alle 31 imports in de codebase geüpdatet
- Services herstart

---

## Vocalization Types op Ulanzi

### Hoe het werkt
Er zijn **twee** confidence waarden:
1. **BirdNET confidence** (70% threshold in webui) - "Dit is een Merel"
2. **Vocalization confidence** (40% threshold) - "Dit is roep/zang/alarm"

### Display logica
- Vocalization confidence < 40%: `Zolder-Merel-85%`
- Vocalization confidence ≥ 40%: `Zolder-Merel roep-85%`

De vocalization threshold bepaalt alleen of het type erbij staat, niet of de notificatie getoond wordt.

### Threshold aangepast
- Was: 50%
- Nu: 40%
- Reden: Meer vocalization types tonen (bijv. Zanglijster met 41% confidence)

---

## Berging Audio Toegang

### Probleem
Vocalization enricher kon alleen zolder audio verwerken, niet berging.

### Oplossing
SSHFS mount toegevoegd:
```
/mnt/berging-audio -> ronny@192.168.1.87:/home/ronny/BirdSongs
```

Toegevoegd aan `/etc/fstab` voor automatische mount.

### vocalization_enricher.py aangepast
```python
AUDIO_PATHS = {
    'zolder': Path('/home/ronny/BirdSongs/Extracted/By_Date'),
    'berging': Path('/mnt/berging-audio/Extracted/By_Date')  # Via SSHFS
}
```

Nu worden beide stations verrijkt met vocalization data.

---

## Andere fixes

### cooldown_display.py
- Database reconnect mechanisme toegevoegd
- Service bleef hangen bij "connection already closed" errors
- Nu automatische reconnect bij connectie verlies

### vocalization-enricher.service
- Memory limit toegevoegd (1GB max)
- Service gebruikte 2GB+ na lang draaien
- Voorkomt memory leaks

### Berging station
- Git repo geüpdatet met `git pull --rebase`
- `.secrets` bestand gekopieerd naar berging
- birdnet-mqtt-publisher service herstart

---

## Systeem Audit Resultaat

**Score: 9.5/10**

- 75.811 detecties opgeslagen
- 78 unieke soorten
- 13.679 dual detections (35% overlap)
- 26+ dagen uptime
- Alle services operationeel

Volledige audit rapport: `2025-12-22-systeem-audit-compleet.md`

---

## Commits vandaag
1. `b428a68` - fix: secrets.py hernoemd naar emsn_secrets.py
2. `7a61222` - docs: Compleet systeem audit 2025-12-22
3. `6c28751` - fix: vocalization verbeteringen + berging audio mount

---

## Training nieuwe modellen
Gebruiker is bezig met trainen van nieuwe/betere vocalization modellen voor alle Nederlandse soorten. Na training:
- Nieuwe `.pt` bestanden naar `/mnt/nas-docker/emsn-vocalization/data/models/`
- Services herstarten: `sudo systemctl restart ulanzi-bridge vocalization-enricher`
