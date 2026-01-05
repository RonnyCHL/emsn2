# Sessie Samenvatting - 5 januari 2026

## Timelapse UI Verbeteringen

### Wat is gedaan

**Nestkast Timelapse ([timelapse.html](../../reports-web/timelapse.html))**
- Verwijderknop toegevoegd bij elke timelapse met bevestigingsdialoog
- Periode display geparsed uit bestandsnaam (bijv. "22 dec 2025 - 5 jan 2026")
- Filter indicatie "(dag)" of "(nacht)" in de lijst
- Voortgangsbalk met geschatte resterende tijd bij genereren

**AtmosBird Timelapse ([atmosbird-timelapse.html](../../reports-web/atmosbird-timelapse.html))**
- Dezelfde UI verbeteringen als nestkast
- Betere tijdschatting op basis van aantal dagen (~144 screenshots/dag vs 6/dag nestkast)
- Status toont nu geschat aantal screenshots

**API Endpoints**
- `POST /api/nestbox/timelapse/delete` - Verwijder nestkast timelapse
- `POST /api/atmosbird/timelapse/delete` - Verwijder AtmosBird timelapse

### Technische Details

AtmosBird heeft ~144 screenshots per dag (elke 10 min), nestkast ~6 per dag.
De voortgangsindicator berekent nu dynamisch de geschatte tijd:
- 7 dagen AtmosBird: ~1008 screenshots → ~90 sec
- 7 dagen nestkast: ~42 screenshots → ~30 sec

### Commits
- `aa45f68` - feat: timelapse UI verbeteringen - delete, datums, voortgang
- `db30ca3` - fix: betere tijdschatting AtmosBird timelapse voortgang
