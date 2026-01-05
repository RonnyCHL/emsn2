# Sessie Samenvatting 2026-01-05

## Onderwerp: Realtime Dual Detection Service

### Aanleiding
Ronny merkte op dat dubbele detectie-meldingen op de Ulanzi display in "batches" leken te komen. Na analyse bleek dit te kloppen: de oude `dual_detection_sync.py` draaide via een timer elke 5 minuten. Dit betekende dat een zeldzame vogel (zoals een IJsvogel) die op beide stations werd gehoord, pas tot 5 minuten later op de Ulanzi zou verschijnen.

### Probleem
- Oude architectuur: timer-based polling elke 5 minuten
- Dual detecties werden gebatched en pas bij volgende sync gepubliceerd
- Worst case: ~5 minuten vertraging voor realtime notificaties

### Oplossing: Realtime MQTT Listener
Nieuwe service die continu luistert naar detecties van beide stations en direct een dual detection publiceert zodra dezelfde soort binnen 30 seconden op beide stations wordt gehoord.

### Nieuwe bestanden

#### /scripts/sync/realtime_dual_detection.py
- Luistert naar `birdnet/zolder/detection` en `birdnet/berging/detection`
- Houdt detecties bij in een thread-safe sliding window buffer (30 sec)
- Publiceert direct naar `emsn2/dual/detection/new` bij match
- Gebruikt bestaande Bayesian verification model voor score berekening
- Cooldown van 60 sec per soort om duplicaten te voorkomen
- Graceful shutdown via signal handlers
- MQTT Last Will Testament voor online/offline status

#### /systemd/realtime-dual-detection.service
- Continu draaiende service (Type=simple)
- Restart=always met RestartSec=10
- Watchdog configuratie (300 sec)

### Wijzigingen systemd

| Service | Status |
|---------|--------|
| `dual-detection.timer` | Gestopt en uitgeschakeld |
| `realtime-dual-detection.service` | Actief en enabled |

### Resultaat
- **Voorheen:** Tot 5 minuten vertraging
- **Nu:** Detectie binnen seconden op Ulanzi

### Oude sync behouden
De oude `dual_detection_sync.py` blijft beschikbaar voor database administratie (markeren `dual_detection` flag in `bird_detections` tabel voor historische data).

### Technische kwaliteit
- Thread-safe buffer met Lock()
- Hergebruik core modules (EMSNLogger, config)
- Geen hardcoded credentials
- Proper error handling en logging
- Nederlandse docstrings conform projectstandaard
