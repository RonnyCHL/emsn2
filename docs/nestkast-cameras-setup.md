# Nestkast Cameras Setup - EMSN

## Overzicht

3 Tuya nestkast cameras met video+audio streaming via go2rtc.

| Camera | Device ID | Locatie |
|--------|-----------|---------|
| Nestkast Voor | bf80c5603b3392da01oyt1 | Voortuin |
| Nestkast Midden | bf5ab17574f859aef9zbg1 | Midden |
| Nestkast Achter | bf0e510111cdf52517rddr | Achtertuin |

## Componenten

- **go2rtc**: Video+audio streaming via WebRTC
- **UniFi Protect**: Opnames en beheer (alleen video)
- **Homer**: Dashboard links

## Installatie

### Stap 1: go2rtc op NAS installeren

SSH naar de NAS of gebruik de terminal:

```bash
# Maak directory
sudo mkdir -p /volume1/docker/go2rtc

# Kopieer config bestanden
sudo cp /volume1/homes/ronny/emsn2/config/go2rtc/* /volume1/docker/go2rtc/

# Of via mount vanaf Pi:
sudo cp /home/ronny/emsn2/config/go2rtc/* /mnt/nas-docker/go2rtc/
```

Start de container:

```bash
cd /volume1/docker/go2rtc
sudo docker-compose up -d
```

### Stap 2: Homer updaten

```bash
sudo bash /home/ronny/emsn2/scripts/setup_nestcams_homer.sh
```

### Stap 3: Testen

- **go2rtc UI**: http://192.168.1.25:1984
- **Nestkast Voor**: http://192.168.1.25:1984/stream.html?src=nestkast_voor
- **Nestkast Midden**: http://192.168.1.25:1984/stream.html?src=nestkast_midden
- **Nestkast Achter**: http://192.168.1.25:1984/stream.html?src=nestkast_achter

## URLs

| Service | URL |
|---------|-----|
| go2rtc Web UI | http://192.168.1.25:1984 |
| go2rtc API | http://192.168.1.25:1984/api |
| RTSP streams | rtsp://192.168.1.25:8554/nestkast_voor |
| UniFi Protect | https://192.168.1.1/protect/devices |
| Homer Dashboard | http://192.168.1.25:8181 |

## Troubleshooting

### Camera stream werkt niet

1. Check go2rtc logs:
   ```bash
   docker logs go2rtc
   ```

2. Verifieer Tuya credentials in go2rtc.yaml

3. Test API:
   ```bash
   curl http://192.168.1.25:1984/api/streams
   ```

### Geen audio

- go2rtc ondersteunt Tuya audio via WebRTC
- Gebruik de go2rtc stream URLs, niet UniFi Protect

## Config bestanden

- go2rtc config: `/volume1/docker/go2rtc/go2rtc.yaml`
- Docker compose: `/volume1/docker/go2rtc/docker-compose.yml`
- Homer config: `/volume1/docker/homer/config.yml`
