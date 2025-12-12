# EMSN Documentatie

Ecologisch Monitoring Systeem Nijverdal - Technische documentatie.

## Inhoud

| Document | Beschrijving |
|----------|--------------|
| [infrastructuur.md](infrastructuur.md) | Netwerk, servers, database |
| [grafana-dashboards.md](grafana-dashboards.md) | Dashboards maken en beheren |
| [homer-dashboard.md](homer-dashboard.md) | Homer homepage configuratie |
| [fase-10-flysafe-radar.md](fase-10-flysafe-radar.md) | FlySafe radar integratie |

## Quick Reference

### Belangrijke URLs

| Service | URL |
|---------|-----|
| Homer Dashboard | http://192.168.1.25:8080 |
| Grafana | http://192.168.1.25:3000 |
| pgAdmin | http://192.168.1.25:5050 |
| BirdNET Zolder | http://192.168.1.178 |
| BirdNET Berging | http://192.168.1.87 |
| Ulanzi Display | http://192.168.1.11 |
| Rapporten | http://192.168.1.25/rapporten/ |

### Database Verbinding

```bash
PGPASSWORD='REDACTED_DB_PASS' psql -h 192.168.1.25 -p 5433 -U birdpi_zolder -d emsn
```

### Grafana API

```bash
curl -H "Authorization: Bearer REDACTED_GRAFANA_TOKEN" \
  http://192.168.1.25:3000/api/...
```

### NAS SSH

```bash
sshpass -p 'REDACTED_DB_PASS' ssh ronny@192.168.1.25
```

## Project Structuur

```
/home/ronny/emsn2/
├── docs/                    # Deze documentatie
├── grafana/                 # Dashboard JSON bestanden
├── scripts/
│   ├── flysafe/            # FlySafe radar scripts
│   ├── reports/            # Rapport generatie
│   └── ...
└── venv/                    # Python virtual environment
```

## Changelog

### December 2024

**Fase 10: FlySafe Radar Integratie**
- KNMI BirdTAM radar scraping
- Kleur-gebaseerde intensiteitsanalyse
- Correlatie met BirdNET detecties
- Ulanzi alerts bij hoge vogeltrek
- Voorspellingsmodule
- Seizoensanalyse
- Soort-specifieke correlatie

**Dashboards toegevoegd:**
- FlySafe Radar (v1 en v2)
- EMSN Meteo Station
