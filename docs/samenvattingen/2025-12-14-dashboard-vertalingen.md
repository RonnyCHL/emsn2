# Sessie Samenvatting: Dashboard Vertalingen naar Nederlands

**Datum:** 14 december 2025 (late avond)
**Type:** Vertaling en lokalisatie

## Overzicht

Alle 14 Grafana dashboards zijn volledig naar het Nederlands vertaald.

## Dashboard Overzicht

| # | Dashboard | Nieuwe Titel | Type |
|---|-----------|-------------|------|
| 1 | Species Overview | EMSN - Soorten Overzicht | API |
| 2 | Species Deep Dive | EMSN - Soorten Analyse | Provisioned |
| 3 | Data Quality | EMSN - Data Kwaliteit | Provisioned |
| 4 | Database Monitoring | EMSN - Database Monitoring | API |
| 5 | Dual Detections | EMSN - Dubbele Detecties | Provisioned |
| 6 | Hardware Performance | EMSN - Hardware Prestaties | Provisioned |
| 7 | Anomaly Detection | EMSN - Anomalie Detectie | API |
| 8 | Migration Monitor | EMSN - Vogeltrek Monitor | Provisioned |
| 9 | Weather vs Birds | EMSN - Weer vs Vogels | Provisioned |
| 10 | PDF Reports | EMSN - PDF Rapporten | Provisioned |
| 11 | Meteo Station | EMSN Meteo Station | API (was al NL) |
| 12 | Ulanzi Notifications | EMSN Ulanzi Notificaties | API |
| 13 | AtmosBird | AtmosBird - Hemel Monitoring | API |
| 14 | FlySafe Radar | FlySafe Radar - Vogeltrek | API |

## Vertaalde Termen

### Algemeen
| Engels | Nederlands |
|--------|------------|
| Confidence | Zekerheid |
| Detections | Detecties/Waarnemingen |
| Species | Soorten |
| Dual Detection | Dubbele Detectie |
| Sky Monitoring | Hemel Monitoring |
| Bird Migration | Vogeltrek |

### Rarity Tiers
| Engels | Nederlands |
|--------|------------|
| abundant | Algemeen |
| common | Gewoon |
| uncommon | Ongewoon |
| rare | Zeldzaam |
| legendary | Legendarisch |

### Database/Technisch
| Engels | Nederlands |
|--------|------------|
| Table Sizes | Tabel Groottes |
| Active Connections | Actieve Connecties |
| Data Freshness | Data Versheid |
| Cache Hit Ratio | Cache Trefkans |
| Query Performance | Query Prestaties |

## Technische Details

### Provisioned vs API Dashboards
- **7 dashboards waren "provisioned"** - geladen uit JSON-bestanden
- **7 dashboards waren normaal** - aanpasbaar via API
- Provisioned dashboards geven foutmelding: `"Cannot save provisioned dashboard"`

### Oplossing voor Provisioned Dashboards
1. JSON-bestanden direct aanpassen: `/mnt/nas-docker/grafana/dashboards/`
2. Vereist sudo rechten (bestanden zijn root-owned)
3. Herladen via API: `POST /api/admin/provisioning/dashboards/reload`

### Vertaalmethode
- **sed** voor eenvoudige vervangingen (risico op JSON-corruptie)
- **Python** voor complexe vertalingen (veiliger):
```python
def translate_recursive(obj, translations):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == 'title' and value in translations:
                obj[key] = translations[value]
```

## Bestanden Gewijzigd

### Provisioned Dashboard Bestanden (NAS)
- `/mnt/nas-docker/grafana/dashboards/species-deep-dive.json`
- `/mnt/nas-docker/grafana/dashboards/data-quality.json`
- `/mnt/nas-docker/grafana/dashboards/dual-detections.json`
- `/mnt/nas-docker/grafana/dashboards/hardware-performance.json`
- `/mnt/nas-docker/grafana/dashboards/migration-monitor.json`
- `/mnt/nas-docker/grafana/dashboards/pdf-reports.json`
- `/mnt/nas-docker/grafana/dashboards/weather-vs-birds.json`

### Documentatie
- `/home/ronny/emsn2/docs/claude-notes.md` - Provisioned dashboards info toegevoegd

## Geleerde Lessen

1. **Provisioned dashboards** kunnen niet via API gewijzigd worden
2. **sed op JSON** is gevaarlijk - gebruik Python voor complexe wijzigingen
3. **Grafana reload API** werkt zonder volledige herstart
4. **Emojis in panel titels** blijven gewoon werken

---
*Gegenereerd door Claude Code sessie*
