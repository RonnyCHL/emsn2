# Sessie Samenvatting: Crash Recovery Hardening

**Datum:** 27 december 2025
**Onderwerp:** Systeem robuustheid bij stroomuitval en crashes

---

## Uitgevoerde Verbeteringen

### 1. NAS Mounts - nofail toegevoegd

**Probleem:** Zonder `nofail` blokkeert de boot als NAS niet bereikbaar is.

**Oplossing:** `nofail` toegevoegd aan alle NAS mounts in `/etc/fstab`:

**Zolder:**
```
//192.168.1.25/emsn-AIRapporten ... nofail,x-systemd.automount
192.168.1.25:/volumeUSB1/usbshare ... nofail,x-systemd.automount
```

**Berging:**
```
//192.168.1.25/docker ... nofail
192.168.1.25:/volumeUSB1/usbshare ... nofail,x-systemd.automount
```

---

### 2. SQLite WAL Mode

**Probleem:** Default `delete` journal mode kan data verliezen bij crash.

**Oplossing:** WAL (Write-Ahead Logging) geactiveerd op beide Pi's:
```sql
PRAGMA journal_mode=WAL;
```

**Voordelen WAL mode:**
- Schrijfoperaties blokkeren lezers niet
- Betere crash recovery
- Minder disk I/O
- Database blijft consistent bij stroomuitval

---

### 3. Hardware Watchdog

**Probleem:** Vastgelopen systeem blijft hangen tot handmatige herstart.

**Oplossing:** Hardware watchdog geactiveerd op beide Pi's:

**Geinstalleerd:**
- `watchdog` package
- `bcm2835_wdt` kernel module

**Configuratie (`/etc/watchdog.conf`):**
```
watchdog-device = /dev/watchdog
watchdog-timeout = 15
interval = 10
max-load-1 = 24
min-memory = 1
```

**Werking:**
- Watchdog daemon "pet" de hardware watchdog elke 10 seconden
- Als systeem vastloopt en 15 seconden geen "pet", herstart Pi automatisch
- Ook herstart bij extreme load (>24) of geheugen vol

---

## Bestaande Robuustheid (was al goed)

| Component | Instelling | Effect |
|-----------|------------|--------|
| EMSN Services | `Restart=always` | Herstarten automatisch na crash |
| Backup Timers | `Persistent=true` | Gemiste runs worden ingehaald |
| USB Mounts | `nofail` | Boot door als USB niet aanwezig |
| Filesystem | ext4 + journaling | Herstelt na crash |

---

## Volledige Crash Recovery Flow

```
Stroomuitval
    │
    ▼
Pi herstart
    │
    ├── Filesystem check (journaling) ──► Automatisch herstel
    │
    ├── USB mounts (nofail) ──► Boot door als niet aanwezig
    │
    ├── NAS mounts (nofail) ──► Boot door als niet bereikbaar
    │
    ├── Services starten (Restart=always) ──► BirdNET, MQTT, API
    │
    ├── Timers starten (Persistent=true) ──► Gemiste backups inhalen
    │
    └── Watchdog start ──► Bewaakt systeem voor toekomstige hangs
```

---

## Geleerde Lessen (Claude)

### WAL mode is persistent
- Eenmaal ingesteld blijft WAL mode behouden
- Creëert extra bestanden: `birds.db-wal` en `birds.db-shm`
- Bij backup: neem alle 3 bestanden mee, of doe eerst `PRAGMA wal_checkpoint;`

### Watchdog configuratie
- Raspberry Pi hardware watchdog max timeout = 15 seconden
- Te lage timeout kan false positives geven bij zware workloads
- `max-load-1 = 24` is conservatief (Pi heeft 4 cores)

### nofail vs x-systemd.automount
- `nofail`: boot door als mount faalt
- `x-systemd.automount`: mount on-demand bij eerste toegang
- Samen gebruiken is het veiligst voor netwerk mounts
