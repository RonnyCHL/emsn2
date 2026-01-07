---
name: deploy
description: Deploy code wijzigingen naar de Pi's. Kopieert scripts, herstart services en verifieert werking.
allowed-tools: Bash, Read
---

# Code Deployment

## Wanneer Gebruiken

- Na het wijzigen van scripts in de repo
- Voor het uitrollen van nieuwe features
- Bij bug fixes die naar productie moeten

## Pre-Deploy Checklist

- [ ] Code getest lokaal
- [ ] Geen syntax errors
- [ ] Credentials niet hardcoded
- [ ] Git commit gemaakt

## Deploy Stappen

### 1. Git Pull op Pi's

```bash
# Zolder
ssh ronny@192.168.1.178 'cd /home/ronny/emsn2 && git pull origin main'

# Berging
ssh ronny@192.168.1.87 'cd /home/ronny/emsn2 && git pull origin main'
```

### 2. Scripts Kopiëren naar Actieve Locatie

De actieve scripts draaien vanuit `/home/ronny/sync/`, niet vanuit de repo.

```bash
# Sync scripts naar actieve locatie (zolder)
ssh ronny@192.168.1.178 'cp /home/ronny/emsn2/scripts/sync/*.py /home/ronny/sync/'

# Sync scripts naar actieve locatie (berging)
ssh ronny@192.168.1.87 'cp /home/ronny/emsn2/scripts/sync/*.py /home/ronny/sync/'
```

### 3. Services Herstarten

```bash
# Lifetime sync (beide Pi's)
ssh ronny@192.168.1.178 'sudo systemctl restart lifetime-sync.timer'
ssh ronny@192.168.1.87 'sudo systemctl restart lifetime-sync.timer'

# MQTT publisher (indien gewijzigd)
ssh ronny@192.168.1.178 'sudo systemctl restart birdnet-mqtt-publisher'
ssh ronny@192.168.1.87 'sudo systemctl restart birdnet-mqtt-publisher'

# AtmosBird services (berging, indien gewijzigd)
ssh ronny@192.168.1.87 'sudo systemctl restart atmosbird-capture.timer atmosbird-analysis.timer'
```

### 4. Verificatie

```bash
# Check service status
ssh ronny@192.168.1.178 'systemctl is-active lifetime-sync.timer birdnet-mqtt-publisher'
ssh ronny@192.168.1.87 'systemctl is-active lifetime-sync.timer birdnet-mqtt-publisher'

# Check logs voor errors
ssh ronny@192.168.1.178 'journalctl -u lifetime-sync.service -n 10 --no-pager'
```

## Specifieke Deployments

### Reports API

```bash
ssh ronny@192.168.1.178 'sudo systemctl restart reports-api && sleep 2 && curl -s http://localhost:8081/health'
```

### Ulanzi Bridge

```bash
ssh ronny@192.168.1.178 'sudo systemctl restart ulanzi-bridge'
```

### AtmosBird (alle services)

```bash
ssh ronny@192.168.1.87 'sudo systemctl restart atmosbird-capture.timer atmosbird-analysis.timer atmosbird-timelapse.timer atmosbird-archive-sync.timer'
```

## Rollback

Bij problemen, revert naar vorige versie:

```bash
# Op de Pi
cd /home/ronny/emsn2
git log --oneline -5  # Vind vorige commit
git checkout <commit-hash> -- scripts/sync/lifetime_sync.py
cp scripts/sync/lifetime_sync.py /home/ronny/sync/
sudo systemctl restart lifetime-sync.timer
```

## Belangrijk

- **Test eerst lokaal** voordat je deployed
- **Maak backups** van werkende configs
- **Monitor logs** na deployment
- BirdNET-Pi core files NOOIT aanpassen!
