# Homer Dashboard - EMSN

## Toegang

- **URL:** http://192.168.1.25:8080
- **Config locatie:** `/volume1/docker/homer/config.yml` (op NAS)
- **NAS IP:** 192.168.1.25
- **NAS User:** ronny
- **NAS Password:** REDACTED_DB_PASS

## SSH Toegang tot NAS

```bash
# Met password prompt
ssh ronny@192.168.1.25

# Met sshpass (automatisch)
sshpass -p 'REDACTED_DB_PASS' ssh -o StrictHostKeyChecking=no ronny@192.168.1.25
```

## Config Bestand Structuur

```yaml
# EMSN - Homer Dashboard Configuration
---
title: "EMSN"
subtitle: "Ecologisch Monitoring Systeem Nijverdal"
logo: "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/bird.png"

header: true
footer: '<p>Ecologisch Monitoring Systeem Nijverdal</p>'

colors:
  light:
    highlight-primary: "#3367d6"
    # ... kleuren
  dark:
    highlight-primary: "#3367d6"
    # ... kleuren

services:
  - name: "Sectie Naam"
    icon: "fas fa-icon"
    items:
      - name: "Item Naam"
        logo: "https://url/naar/logo.png"
        subtitle: "Beschrijving"
        url: "http://url"
        target: "_blank"
```

## Nieuwe Link Toevoegen

### 1. Config uitlezen

```bash
sshpass -p 'REDACTED_DB_PASS' ssh ronny@192.168.1.25 \
  "cat /volume1/docker/homer/config.yml"
```

### 2. Config aanpassen

```bash
sshpass -p 'REDACTED_DB_PASS' ssh ronny@192.168.1.25 \
  "cat > /volume1/docker/homer/config.yml << 'EOF'
# Volledige config hier
EOF"
```

### 3. Item toevoegen aan bestaande sectie

Voeg toe onder de juiste `items:` lijst:

```yaml
      - name: "Nieuwe Dashboard"
        icon: "fas fa-chart-line"
        subtitle: "Beschrijving"
        url: "http://192.168.1.25:3000/d/uid/naam"
        target: "_blank"
```

## Huidige Secties

| Sectie | Icon | Items |
|--------|------|-------|
| Monitoring | `fa-chart-line` | Grafana, Meteo Station, FlySafe Radar, etc. |
| Vogelstations | `fa-dove` | EMSN2-Zolder, EMSN2-Berging |
| AI Rapporten | `fa-file-alt` | Vogelrapporten |
| Database & Infrastructure | `fa-database` | pgAdmin |
| Hardware & IoT | `fa-microchip` | Ulanzi, Davis WeatherLink |
| Documentation & Links | `fa-book` | GitHub, docs, etc. |

## Veelgebruikte Icons

```
fas fa-chart-line      - Grafieken/monitoring
fas fa-dove            - Vogels
fas fa-satellite-dish  - Radar
fas fa-thermometer-half - Temperatuur/weer
fas fa-cloud-sun       - Weer
fas fa-moon            - Nacht/sky
fas fa-database        - Database
fas fa-file-pdf        - PDF rapporten
fas fa-microchip       - Hardware
fas fa-tv              - Display
```

Meer icons: https://fontawesome.com/icons

## Dashboard Icons (logo's)

Gebruik Walkxcode's dashboard-icons:
```
https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/[naam].png
```

Voorbeelden:
- `grafana.png`
- `home-assistant.png`
- `pgadmin.png`
- `github.png`

Overzicht: https://github.com/walkxcode/dashboard-icons

## Grafana Dashboard URLs

Format:
```
http://192.168.1.25:3000/d/[UID]/[slug]?orgId=1&from=[time]&to=now
```

Voorbeelden:
```
http://192.168.1.25:3000/d/emsn-meteo/emsn-meteo-station?orgId=1&from=now-24h&to=now
http://192.168.1.25:3000/d/flysafe-radar/flysafe-radar-bird-migration?orgId=1&from=now-7d&to=now
```

## Troubleshooting

### Homer laadt niet na config change
- Check YAML syntax (spaties, geen tabs!)
- Gebruik online YAML validator

### SSH permission denied
```bash
# Check of sshpass geïnstalleerd is
which sshpass

# Installeer indien nodig
sudo apt-get install sshpass
```

### Config backup maken
```bash
sshpass -p 'REDACTED_DB_PASS' ssh ronny@192.168.1.25 \
  "cp /volume1/docker/homer/config.yml /volume1/docker/homer/config.yml.backup"
```
