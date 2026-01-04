# Sessie Samenvatting: AtmosBird Livestream

**Datum:** 2026-01-04
**Onderwerp:** Livestream voor AtmosBird hemelcamera

## Wat is gedaan

### 1. AtmosBird Livestream Service
Nieuwe systemd service aangemaakt die de Pi Camera NoIR streamt via TCP:
- **Service:** `atmosbird-stream.service` op Pi Berging
- **Resolutie:** 1920x1080 @ 15fps
- **Codec:** H.264 (Main profile, level 4.1)
- **Bitrate:** 2 Mbps
- **Poort:** TCP 8889

### 2. go2rtc Integratie
AtmosBird toegevoegd aan de bestaande go2rtc configuratie op de NAS:
- Stream beschikbaar via WebRTC, RTSP en HLS
- Preload ingeschakeld voor permanente beschikbaarheid

### 3. Slim Schakelen Camera
De Pi Camera kan maar door één proces tegelijk gebruikt worden. Oplossing:
- `atmosbird-capture.service` stopt nu eerst de livestream
- Maakt de foto (elke 10 minuten)
- Start de livestream weer op
- Stream onderbreking: ~5 seconden

### 4. Homer Dashboard
Link toegevoegd in sectie "Natuur Monitoring"

## Nieuwe/Gewijzigde Bestanden

### Nieuw
- `/home/ronny/emsn2/systemd/atmosbird-stream.service` - Livestream service

### Gewijzigd
- `/home/ronny/emsn2/systemd/atmosbird-capture.service` - Stream stop/start toegevoegd
- `/volume1/docker/go2rtc/go2rtc.yaml` (NAS) - AtmosBird stream toegevoegd
- `/volume1/docker/homer/config.yml` (NAS) - Livestream link toegevoegd

### Configuratie op Pi Berging
- `/etc/sudoers.d/atmosbird-capture` - Permissies voor stream beheer
- `opencv-python-headless` geïnstalleerd in venv

## Toegang tot Livestream

| Methode | URL |
|---------|-----|
| WebRTC (browser) | http://192.168.1.25:1984/stream.html?src=atmosbird |
| RTSP (VLC) | rtsp://192.168.1.25:8554/atmosbird |
| HLS | http://192.168.1.25:1984/api/stream.m3u8?src=atmosbird |
| go2rtc UI | http://192.168.1.25:1984 |
| Homer | http://192.168.1.25:8181 → Natuur Monitoring |

## Technische Details

### Stream Architectuur
```
Pi Berging (192.168.1.87)          NAS (192.168.1.25)
┌─────────────────────┐            ┌─────────────────────┐
│ rpicam-vid          │            │ go2rtc              │
│ TCP server :8889    │◄───────────│ TCP client          │
│                     │            │                     │
│ atmosbird-stream    │            │ WebRTC :8555        │
│ .service            │            │ RTSP :8554          │
└─────────────────────┘            │ HTTP :1984          │
                                   └─────────────────────┘
```

### Foto Capture Flow
```
Timer (elke 10 min)
    │
    ▼
ExecStartPre: stop atmosbird-stream
    │
    ▼
ExecStartPre: sleep 1
    │
    ▼
ExecStart: atmosbird_capture.py
    │
    ▼
ExecStopPost: start atmosbird-stream
```

## Notities
- Foto's worden nog steeds elke 10 minuten gemaakt
- Stream pauzeert automatisch voor ~5 seconden tijdens capture
- Bij problemen met camera "busy": check of beide services niet tegelijk draaien
