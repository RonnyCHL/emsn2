# Sessie Samenvatting 23 december 2025

## Onderwerp
go2rtc Health Check automatisering voor nestkast cameras

## Wat er is gedaan

### 1. go2rtc Health Check Script
- Script `/home/ronny/emsn2/scripts/nestbox/go2rtc_healthcheck.sh` werkt volledig
- Controleert elke 30 minuten of alle 3 nestkast streams actief zijn
- Bij inactieve streams: automatische restart van go2rtc container via SSH

### 2. SSH Docker Toegang (NAS → Pi)
**Probleem:** Synology DSM laadt docker group membership niet correct in SSH sessies.

**Geprobeerde oplossingen die NIET werkten:**
- `sudo synogroup --add docker ronny` - group werd toegevoegd maar niet geladen in SSH
- `sudo chown root:docker /var/run/docker.sock` - socket permissions gefixd
- NAS reboot - group membership verdween na reboot
- `sudo systemctl restart sshd` - hielp niet

**Werkende oplossing:**
```bash
# Op NAS (als root):
echo 'ronny ALL=(ALL) NOPASSWD: /usr/local/bin/docker' | sudo tee /etc/sudoers.d/ronny-docker
```

Dit staat passwordless `sudo docker` toe via SSH.

### 3. Tuya Rate Limiting
**Probleem ontdekt:** Tuya API heeft rate limiting die soms 1 of 2 van de 3 cameras blokkeert.
- Foutmelding: "请求过于频繁,请稍后再试" (Te veel requests, probeer later)
- Dit is een Tuya cloud probleem, geen lokaal probleem
- Streams "roteren" - soms werkt alleen voor, soms alleen midden, etc.

**Nog geen oplossing** - dit is een Tuya limitatie. Mogelijke opties:
- Wachten tot rate limiting verdwijnt (5-15 min)
- go2rtc config aanpassen met lagere polling rate
- Meerdere Tuya accounts gebruiken (1 per camera)

## Bestanden gewijzigd
- `/home/ronny/emsn2/scripts/nestbox/go2rtc_healthcheck.sh` - nu met `sudo docker`

## Configuratie op NAS
- `/etc/sudoers.d/ronny-docker` - sudoers regel voor docker

## Systemd Status
- `go2rtc-healthcheck.timer` - actief, draait elke 30 minuten
- `go2rtc-healthcheck.service` - oneshot service

## Volgende stappen
- Tuya rate limiting monitoren
- Eventueel go2rtc config aanpassen voor minder frequente reconnects
- Overwegen: aparte Tuya accounts per camera

## Geleerde lessen

### Synology DSM Docker Access via SSH
Synology DSM (versie 7.x) heeft een afwijkende manier van group membership laden:
- Normale Linux methode (`usermod -aG docker user`) werkt niet betrouwbaar
- DSM gebruikt `synogroup` maar dit laadt niet altijd correct in SSH sessies
- **Beste oplossing:** sudoers regel voor specifieke commands

### Tuya Cloud Beperkingen
- Tuya heeft strenge rate limiting op hun cloud API
- Meerdere gelijktijdige streams per account wordt beperkt
- go2rtc restart triggers nieuwe token requests → rate limiting
- Dit is inherent aan Tuya cloud cameras
