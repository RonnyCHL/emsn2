---
name: nestkast-check
description: Controleer nestkast camera systeem. Check go2rtc streams, API status, screenshots en events.
allowed-tools: Bash, Read
---

# Nestkast Monitoring Check

## Wanneer Gebruiken

- Controleren of camera streams werken
- Troubleshooting screenshot capturing
- Event tracking verificatie

## Camera Overzicht

| Nestkast | Device ID | Status Check |
|----------|-----------|--------------|
| voor | bf80c5603b3392da01oyt1 | Voortuin |
| midden | bf5ab17574f859aef9zbg1 | Midden (slapende Koolmees!) |
| achter | bf0e510111cdf52517rddr | Achtertuin |

## Stream Status

### go2rtc Web UI

Open in browser: http://192.168.1.25:1984

### Stream Test

```bash
# Check of streams beschikbaar zijn
curl -s http://192.168.1.25:1984/api/streams | jq .

# Specifieke stream info
curl -s http://192.168.1.25:1984/api/streams/nestkast_voor | jq .
curl -s http://192.168.1.25:1984/api/streams/nestkast_midden | jq .
curl -s http://192.168.1.25:1984/api/streams/nestkast_achter | jq .
```

### RTSP Connectiviteit

```bash
# Test RTSP stream (5 seconden)
ffprobe -v quiet -show_entries format=duration -of csv=p=0 \
    -rtsp_transport tcp \
    "rtsp://192.168.1.25:8554/nestkast_midden" 2>&1 | head -5
```

## API Status

### Health Check

```bash
curl -s http://192.168.1.178:8081/health | jq .
```

### Nestkast Lijst

```bash
curl -s http://192.168.1.178:8081/api/nestbox/list | jq .
```

### Huidige Status

```bash
curl -s http://192.168.1.178:8081/api/nestbox/status | jq .
```

## Screenshots

### Recente Screenshots

```bash
# Via API
curl -s http://192.168.1.178:8081/api/nestbox/media?type=screenshot | jq '.[-5:]'

# Direct op NAS
ls -lt /mnt/nas-birdnet-archive/nestbox/midden/screenshots/ | head -10
```

### Handmatige Screenshot

```bash
curl -X POST http://192.168.1.178:8081/api/nestbox/capture/screenshot \
    -H "Content-Type: application/json" \
    -d '{"nestbox_id": "midden", "capture_type": "manual"}'
```

### Screenshot Timer

```bash
# Timer status (6x per dag)
ssh ronny@192.168.1.178 'systemctl status nestbox-screenshot.timer --no-pager'

# Laatste runs
ssh ronny@192.168.1.178 'journalctl -u nestbox-screenshot.service -n 20 --no-pager'
```

## Events

### Recente Events

```bash
curl -s http://192.168.1.178:8081/api/nestbox/events | jq '.[-10:]'
```

### Event Toevoegen

```bash
curl -X POST http://192.168.1.178:8081/api/nestbox/events \
    -H "Content-Type: application/json" \
    -d '{"nestbox_id": "midden", "event_type": "bezet", "species": "Koolmees", "notes": "Via Claude"}'
```

### Event Types

`leeg`, `bezet`, `bouw`, `eieren`, `jongen`, `uitgevlogen`, `mislukt`, `onderhoud`

## Database Check

```bash
PGPASSWORD=$(grep PG_PASSWORD /home/ronny/emsn2/.secrets | cut -d= -f2) \
psql -h 192.168.1.25 -p 5433 -U emsn -d emsn -c "
SELECT
    ne.nestbox_id,
    ne.event_type,
    ne.species,
    ne.observed_at,
    ne.notes
FROM nestbox_events ne
ORDER BY ne.observed_at DESC
LIMIT 10;
"
```

## go2rtc Container

```bash
# Container status (op NAS via SSH)
ssh admin@192.168.1.25 'sudo docker ps | grep go2rtc'

# Container logs
ssh admin@192.168.1.25 'sudo docker logs go2rtc --tail 50'

# Restart indien nodig
ssh admin@192.168.1.25 'sudo docker restart go2rtc'
```

## Grafana Dashboard

URL: http://192.168.1.25:3000/d/emsn-nestkast-monitoring/

## Veelvoorkomende Problemen

| Probleem | Check | Oplossing |
|----------|-------|-----------|
| Stream offline | go2rtc logs | Restart container |
| Screenshot mislukt | API logs | Check NAS mount |
| Tuya auth error | Token verlopen | Update credentials in go2rtc.yaml |
| API timeout | Service status | Restart reports-api |
