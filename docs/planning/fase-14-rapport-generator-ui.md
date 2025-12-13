# Fase 14: Rapport Generator UI

**Status:** Planning
**Datum:** 13 december 2025

---

## Overzicht

Uitbreiding van het rapportagesysteem met een interactieve web interface voor handmatige generatie, schrijfstijl keuze, soort-specifieke rapporten, vergelijkingen en e-mail notificaties.

---

## 1. Schrijfstijl Configuratie

### Bestand: `/home/ronny/emsn2/config/report_styles.yaml`

```yaml
styles:
  wetenschappelijk:
    name: "Wetenschappelijk"
    description: "Veldbioloog stijl - data-gedreven, droge humor, geen uitroeptekens"
    prompt: |
      Je bent een ervaren veldbioloog die een rapport opstelt voor collega's.
      Wetenschappelijk gefundeerd, data-gedreven.
      Humor is welkom, maar subtiel en droog.
      NOOIT verkleinwoorden, GEEN uitroeptekens.
      Vogelsoorten met Hoofdletter + wetenschappelijke naam cursief.

  populair:
    name: "Populair"
    description: "Toegankelijk voor breed publiek - warm, persoonlijk"
    prompt: |
      Je bent een natuurjournalist die schrijft voor een breed publiek.
      Warm en persoonlijk, alsof je een verhaal vertelt.
      Gebruik Nederlandse vogelnamen.
      Maak het levendig en toegankelijk.

  kinderen:
    name: "Kinderen (8-12 jaar)"
    description: "Educatief en enthousiast voor jonge lezers"
    prompt: |
      Je schrijft voor kinderen van 8-12 jaar.
      Gebruik eenvoudige woorden en korte zinnen.
      Maak het spannend en leuk.
      Voeg weetjes toe die kinderen interessant vinden.

  technisch:
    name: "Technisch"
    description: "Puur data, minimale tekst - voor analyse"
    prompt: |
      Genereer een beknopt technisch rapport.
      Focus op statistieken en trends.
      Minimale narratieve tekst.
      Tabellen waar mogelijk.

default_style: wetenschappelijk
```

---

## 2. Handmatige Generatie UI

### Web Interface Uitbreiding

**Locatie:** Tab of sectie in bestaande rapporten pagina

#### UI Elementen

```
┌─────────────────────────────────────────────────────────┐
│  NIEUW RAPPORT GENEREREN                                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Type rapport:  [▼ Weekrapport          ]               │
│                    Weekrapport                          │
│                    Maandrapport                         │
│                    Seizoensrapport                      │
│                    Jaaroverzicht                        │
│                    Soort-specifiek                      │
│                    Vergelijking                         │
│                                                         │
│  Periode:       [▼ Week 50 (2025)       ]               │
│                 (dynamisch op basis van type)           │
│                                                         │
│  Schrijfstijl:  [▼ Wetenschappelijk     ]               │
│                    Wetenschappelijk                     │
│                    Populair                             │
│                    Kinderen (8-12 jaar)                 │
│                    Technisch                            │
│                                                         │
│  [ ] E-mail versturen naar: [ronnyhullegie@gmail.com]   │
│                                                         │
│  [        GENEREER RAPPORT        ]                     │
│                                                         │
│  Status: ● Gereed                                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### Dynamische velden per type

| Type | Extra velden |
|------|--------------|
| Week | Week nummer + jaar dropdown |
| Maand | Maand + jaar dropdown |
| Seizoen | Seizoen (voorjaar/zomer/herfst/winter) + jaar |
| Jaar | Jaar dropdown |
| Soort-specifiek | Soort dropdown + periode |
| Vergelijking | Twee periode selectors |

---

## 3. Soort-specifiek Rapport

### Nieuw script: `species_report.py`

**Functionaliteit:**
- Alle data voor één specifieke soort
- Fenologie (eerste/laatste waarneming)
- Activiteitspatroon per uur/maand
- Weercorrelaties
- Vergelijking met vorig jaar
- Dual detection analyse
- Locatie voorkeuren (zolder vs berging)

**Voorbeeld output:** "Ekster Jaarrapport 2025"

### UI

```
┌─────────────────────────────────────────────────────────┐
│  SOORT-SPECIFIEK RAPPORT                                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Soort:         [▼ Ekster (Pica pica)   ] 🔍            │
│                 (zoekbaar, toont top 20 + zoekoptie)    │
│                                                         │
│  Periode:       [▼ Heel 2025            ]               │
│                    Heel 2025                            │
│                    Herfst 2025                          │
│                    December 2025                        │
│                    Aangepast...                         │
│                                                         │
│  Schrijfstijl:  [▼ Wetenschappelijk     ]               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Vergelijkingsrapport

### Nieuw script: `comparison_report.py`

**Functionaliteit:**
- Vergelijk twee periodes
- Verschillen in soortenaantal
- Toe-/afname per soort
- Weerverschillen
- Activiteitspatroon vergelijking

**Voorbeelden:**
- "Herfst 2024 vs Herfst 2025"
- "Week 50 vs Week 49"
- "December 2024 vs December 2025"

### UI

```
┌─────────────────────────────────────────────────────────┐
│  VERGELIJKINGSRAPPORT                                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Periode 1:     [▼ Herfst 2025          ]               │
│                                                         │
│  Periode 2:     [▼ Herfst 2024          ]               │
│                 (zelfde type als periode 1)             │
│                                                         │
│  Schrijfstijl:  [▼ Wetenschappelijk     ]               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 5. E-mail Notificatie

### Configuratie: `/home/ronny/emsn2/config/email.yaml`

```yaml
smtp:
  host: smtp.gmail.com
  port: 587
  username: emsn.nijverdal@gmail.com
  password: ${EMSN_SMTP_PASSWORD}  # Environment variable
  use_tls: true

defaults:
  from: "EMSN Nijverdal <emsn.nijverdal@gmail.com>"
  to:
    - ronnyhullegie@gmail.com

templates:
  new_report:
    subject: "EMSN {report_type}: {report_title}"
    body: |
      Beste Ronny,

      Er is een nieuw {report_type} gegenereerd:

      {report_title}
      Periode: {period}
      Detecties: {total_detections}
      Soorten: {unique_species}

      Bekijk het rapport: {report_url}

      Met vriendelijke groet,
      EMSN 2.0

notifications:
  on_weekly: true
  on_monthly: true
  on_seasonal: true
  on_yearly: true
  on_manual: true  # Bij handmatig gegenereerde rapporten
```

### Implementatie

- Nieuwe module: `scripts/utils/email_sender.py`
- Integratie in alle rapport scripts
- Optioneel PDF als bijlage

---

## 6. API Endpoints

### Nieuwe endpoints in `api.py`

| Endpoint | Methode | Beschrijving |
|----------|---------|--------------|
| `/api/styles` | GET | Lijst beschikbare schrijfstijlen |
| `/api/species` | GET | Lijst soorten (voor dropdown) |
| `/api/periods` | GET | Beschikbare periodes per type |
| `/api/generate` | POST | Start rapport generatie |
| `/api/generate/status/{id}` | GET | Status van generatie |
| `/api/email/test` | POST | Test e-mail configuratie |

### Generate Request

```json
POST /api/generate
{
  "type": "week",
  "year": 2025,
  "week": 50,
  "style": "wetenschappelijk",
  "email": true,
  "email_to": ["ronnyhullegie@gmail.com"]
}
```

### Generate Response

```json
{
  "job_id": "abc123",
  "status": "queued",
  "estimated_time": 30
}
```

---

## 7. Bestandsstructuur

```
/home/ronny/emsn2/
├── config/
│   ├── report_styles.yaml      # Schrijfstijlen
│   └── email.yaml              # E-mail configuratie
├── scripts/
│   ├── reports/
│   │   ├── weekly_report.py    # Bestaand (update voor stijl)
│   │   ├── monthly_report.py   # Bestaand (update voor stijl)
│   │   ├── seasonal_report.py  # Bestaand (update voor stijl)
│   │   ├── yearly_report.py    # Bestaand (update voor stijl)
│   │   ├── species_report.py   # NIEUW
│   │   ├── comparison_report.py # NIEUW
│   │   └── report_base.py      # NIEUW: Gedeelde functionaliteit
│   └── utils/
│       └── email_sender.py     # NIEUW
├── reports-web/
│   ├── api.py                  # Update met nieuwe endpoints
│   ├── index.html              # Update met generator UI
│   ├── app.js                  # Update met generator logica
│   └── style.css               # Update voor nieuwe UI
```

---

## 8. Implementatie Volgorde

### Fase 14a: Basis (2-3 uur)
1. [ ] `config/report_styles.yaml` aanmaken
2. [ ] `report_base.py` met gedeelde functionaliteit
3. [ ] Bestaande scripts updaten voor `--style` parameter
4. [ ] API endpoint `/api/styles`

### Fase 14b: Handmatige Generatie (2-3 uur)
5. [ ] API endpoints voor generate
6. [ ] UI uitbreiding in index.html
7. [ ] JavaScript voor generatie formulier
8. [ ] Background job handling

### Fase 14c: Soort-specifiek (2 uur)
9. [ ] `species_report.py` script
10. [ ] API endpoint `/api/species`
11. [ ] UI voor soort selectie

### Fase 14d: Vergelijking (2 uur)
12. [ ] `comparison_report.py` script
13. [ ] UI voor vergelijking

### Fase 14e: E-mail (1-2 uur)
14. [ ] `email.yaml` configuratie
15. [ ] `email_sender.py` module
16. [ ] Integratie in rapport scripts
17. [ ] Test endpoint

---

## 9. Technische Details

### Background Job Handling

Rapport generatie duurt 15-60 seconden. Opties:
- **Optie A:** Synchrone request (met loading indicator)
- **Optie B:** Async met polling (job queue)
- **Optie C:** WebSocket voor real-time updates

**Aanbeveling:** Optie A voor eenvoud. De API wacht tot generatie klaar is (~30 sec) met een timeout van 2 minuten.

### Stijl Integratie

Elke rapport class krijgt een `load_style()` methode:

```python
def load_style(self, style_name):
    with open('/home/ronny/emsn2/config/report_styles.yaml') as f:
        styles = yaml.safe_load(f)
    return styles['styles'].get(style_name, styles['styles']['wetenschappelijk'])
```

---

## 10. UI Mockup (volledig)

```
┌─────────────────────────────────────────────────────────────────┐
│  EMSN VOGELRAPPORTEN                                    [Nieuw] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  RAPPORTEN                                              │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │  📅 Week 50 (2025)          12.854 detecties  95 soorten│   │
│  │  🍂 Herfst 2025             10.929 detecties  82 soorten│   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  NIEUW RAPPORT GENEREREN                           [−]  │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │                                                         │   │
│  │  Type:    ○ Week  ○ Maand  ○ Seizoen  ○ Jaar           │   │
│  │           ○ Soort-specifiek  ○ Vergelijking             │   │
│  │                                                         │   │
│  │  Periode: [▼ Week 51 (16-22 dec 2025)    ]             │   │
│  │                                                         │   │
│  │  Stijl:   [▼ Wetenschappelijk            ]             │   │
│  │           ℹ️ Veldbioloog stijl - droge humor            │   │
│  │                                                         │   │
│  │  □ E-mail versturen naar: [ronnyhullegie@gmail.com  ]  │   │
│  │  □ PDF genereren                                        │   │
│  │                                                         │   │
│  │  [         🚀 GENEREER RAPPORT         ]                │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 11. Risico's en Mitigatie

| Risico | Impact | Mitigatie |
|--------|--------|-----------|
| API timeout bij lange generatie | Medium | Verhoog timeout, toon voortgang |
| E-mail spam filters | Laag | SPF/DKIM configureren |
| Kosten Claude API bij veel handmatig | Laag | Rate limiting, kosten display |
| Complexe UI | Medium | Stapsgewijs uitrollen |

---

## 12. Kosten Inschatting

| Rapport type | Geschatte kosten |
|--------------|------------------|
| Week | $0.01 |
| Maand | $0.02 |
| Seizoen | $0.03 |
| Jaar | $0.05 |
| Soort-specifiek | $0.02 |
| Vergelijking | $0.03 |

**Totaal bij normaal gebruik:** ~$2-3/jaar

---

*Plan opgesteld door Claude Opus 4.5 - 13 december 2025*
