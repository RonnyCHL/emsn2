# Sessie Samenvatting: SD Backup Streaming Fix

**Datum:** 28 december 2025
**Focus:** Wekelijkse backup fix met streaming compressie

## Probleem

De wekelijkse SD backup om 03:00 faalde met:
```
Onvoldoende vrije ruimte in /tmp: 3.8GB (minimaal 10GB nodig)
```

De 238GB SD kaart paste niet in /tmp voor compressie.

## Oplossing: Streaming Direct naar NAS

Aangepast `sd_backup_weekly.py` om direct te streamen zonder lokale temp ruimte:

```python
# Nieuwe aanpak: dd | pigz direct naar NAS
cmd = f'dd if={device} bs=4M status=progress 2>&1 | {gzip_cmd} > {output_path}'
```

Dit elimineert de noodzaak voor lokale opslag - data gaat direct van SD → compressie → NAS.

## Testresultaten

- **Start:** 12:27
- **Voltooid:** 13:27 (61 minuten)
- **Input:** 238.3 GB SD kaart
- **Output:** 39.60 GB gecomprimeerd (83% compressie!)
- **Locatie:** `/mnt/nas-birdnet-archive/sd-backups/zolder/images/emsn2-zolder-2025-12-28.img.gz`
- **Email alert:** Succesvol verstuurd

## Acties Uitgevoerd

1. **sd_backup_weekly.py** - Streaming compressie geïmplementeerd
2. **Berging Pi** - Backup scripts en services gesyncroniseerd en geïnstalleerd
3. **EMSN-Handboek-v1.0.md** - Backup sectie uitgebreid met volledige documentatie

## Huidige Backup Status

| Timer | Zolder | Berging | Volgende Run |
|-------|--------|---------|--------------|
| sd-backup-database.timer | ✅ OK | ✅ OK | Elk uur :15 |
| sd-backup-daily.timer | ✅ OK | ✅ OK | 02:00 |
| sd-backup-weekly.timer | ✅ Getest | ⏳ Zondag | Zondag 03:00 |
| sd-backup-cleanup.timer | ✅ OK | ✅ OK | 02:30 |

## Opmerkingen

- NFS root squashing vereist chmod 777 op backup directories (reeds gedaan)
- rsync exit code 23 geaccepteerd als succes (permission issues door root squashing)
- pigz (parallelle gzip) gebruikt voor snellere compressie
- 40GB gecomprimeerd formaat is goed beheersbaar (7 weken = ~280GB per Pi)

## Volgende Stappen

- Wachten op automatische weekly backup komende zondag (Berging test)
- Monitoren of daily backups succesvol blijven draaien
