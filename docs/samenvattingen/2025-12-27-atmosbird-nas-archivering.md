# Sessie Samenvatting: AtmosBird NAS Archivering

**Datum:** 2025-12-27
**Focus:** AtmosBird foto archivering naar NAS 8TB USB schijf

## Uitgevoerd

### Probleem
- AtmosBird foto's stonden alleen op lokale USB stick (29GB) op Pi Berging
- USB stick zou op termijn vol raken
- NAS heeft 8TB USB schijf met 7.2TB vrij

### Oplossing: Archivering naar NAS

#### 1. Database Uitbreiding
- Nieuwe kolom `archive_path` toegevoegd aan `sky_observations` tabel
- Houdt referentie naar permanente locatie op NAS

#### 2. Archief Directory Structuur
```
/mnt/nas-birdnet-archive/atmosbird/
├── ruwe_foto/          # Alle foto's (datum-structuur behouden)
│   └── 2025/12/27/
├── timelapse/          # Gegenereerde timelapses
├── thumbnails/         # 320x180 previews voor dashboards
└── detecties/          # Speciale detecties (toekomstig)
```

#### 3. Sync Script (atmosbird_archive_sync.py)
Functies:
- Rsync foto's naar NAS (--ignore-existing)
- Rsync timelapses naar NAS
- Genereer thumbnails (320x180, 75% JPEG kwaliteit)
- Update database `archive_path` voor alle gesynte bestanden
- Cleanup lokale bestanden ouder dan 7 dagen
- Alleen verwijderen als bestand op NAS bestaat

#### 4. Systemd Timer
- `atmosbird-archive-sync.timer` - draait elk uur op :30
- Persistent=true voor gemiste runs
- RandomizedDelaySec=300 om load te spreiden

## Resultaat Eerste Sync

| Metric | Waarde |
|--------|--------|
| Foto's gesynct | 2.222 |
| Thumbnails gemaakt | 2.222 |
| Database updates | 2.222 |
| Lokaal opgeruimd | 1.216 (ouder dan 7 dagen) |
| Duur | 361 seconden |

### Opslag Na Sync
| Locatie | Ruwe foto's | Totaal |
|---------|-------------|--------|
| Lokaal USB | 1.6 GB | ~2.7 GB |
| NAS Archief | 3.4 GB | ~4.5 GB |

## Bestanden

### Nieuw
- `/scripts/atmosbird/atmosbird_archive_sync.py` - Sync script
- `/systemd/atmosbird-archive-sync.service` - Systemd service
- `/systemd/atmosbird-archive-sync.timer` - Systemd timer

### Gewijzigd
- `CLAUDE.md` - AtmosBird sectie toegevoegd met opslag architectuur

### Gedeployed (berging)
- `/home/ronny/emsn2/scripts/atmosbird/atmosbird_archive_sync.py`
- `/etc/systemd/system/atmosbird-archive-sync.service`
- `/etc/systemd/system/atmosbird-archive-sync.timer`

## Architectuur

```
Pi Berging                              NAS (8TB USB)
┌─────────────────┐    elk uur         ┌──────────────────────────┐
│ /mnt/usb/       │ ─── rsync ──────►  │ /mnt/nas-birdnet-archive │
│ atmosbird/      │                    │ /atmosbird/              │
│ (7 dagen)       │                    │ (permanent)              │
└────────┬────────┘                    └──────────────────────────┘
         │                                         │
         ▼                                         ▼
  image_path (lokaal)                    archive_path (NAS)
         └──────────────► PostgreSQL ◄─────────────┘
```

## Timer Status
```
atmosbird-archive-sync.timer - Elk uur foto's archiveren
  Active: active (waiting)
  Trigger: elke :30
```
