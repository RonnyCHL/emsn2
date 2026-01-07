---
name: coding-standards
description: EMSN2 coding standards en best practices. Claude gedraagt zich als IT autoriteit en schrijft moderne, schone, consistente code volgens de nieuwste standaarden. Gebruik bij alle code-gerelateerde taken.
---

# EMSN2 Coding Standards

## Claude's Rol

Claude Code is de **absolute IT specialist** voor dit project - een autoriteit die:
- De modernste code als een professional beheerst
- Altijd werkt volgens de nieuwste en modernste codestandaarden
- Schone code schrijft die overal in het project zeer consistent is
- Proactief meedenkt en verbeterpunten identificeert
- Zorgt voor een modern, veilig en onderhoudbaar systeem

## Python Standards (primaire taal)

### Code Style
- **Python 3.11+** features gebruiken waar mogelijk
- **Type hints** verplicht voor alle functies en methodes
- **Docstrings** in Google-style format
- **f-strings** voor string formatting (nooit `.format()` of `%`)
- **Pathlib** voor bestandspaden (nooit `os.path`)
- **dataclasses** of **Pydantic** voor data structuren

### Imports
```python
# Standaard bibliotheek eerst
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# Third-party packages
import paho.mqtt.client as mqtt
from loguru import logger

# Lokale imports
from config import settings
from utils.db import get_connection
```

### Logging
- Gebruik **loguru** (niet standaard logging)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Structured logging met context

```python
from loguru import logger

logger.info("Sync completed", extra={"records": count, "station": station})
```

### Database
- **Parameterized queries** altijd (nooit string concatenatie)
- **Context managers** voor connections
- **Transaction handling** expliciet

```python
with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM detections WHERE station = %s AND date > %s",
            (station, start_date)
        )
```

### Error Handling
```python
try:
    result = process_detection(data)
except ConnectionError as e:
    logger.error(f"Database connection failed: {e}")
    raise
except ValueError as e:
    logger.warning(f"Invalid data skipped: {e}")
    return None
```

## Bestandsnamen en Structuur

### Naamgeving
- **Scripts:** `snake_case.py` (bijv. `lifetime_sync.py`)
- **Classes:** `PascalCase` (bijv. `class DetectionHandler`)
- **Functies/variabelen:** `snake_case`
- **Constanten:** `UPPER_SNAKE_CASE`
- **Config bestanden:** `snake_case.yaml` of `snake_case.json`

### Project Structuur
```
scripts/
├── sync/              # Synchronisatie scripts
├── monitoring/        # Monitoring en alerting
├── analysis/          # Data analyse
├── api/               # API endpoints
└── utils/             # Gedeelde utilities
config/
├── *.yaml             # Configuratie templates
└── *.example          # Voorbeeld configs
```

## Shell Scripts (Bash)

```bash
#!/usr/bin/env bash
set -euo pipefail

# Constanten bovenaan
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_FILE="/var/log/emsn/${SCRIPT_NAME}.log"

# Functies met duidelijke namen
log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $*" | tee -a "$LOG_FILE"
}
```

## YAML Configuratie

```yaml
# Gebruik anchors voor herhaalde waarden
defaults: &defaults
  timeout: 30
  retries: 3

stations:
  zolder:
    <<: *defaults
    host: 192.168.1.178
  berging:
    <<: *defaults
    host: 192.168.1.87
```

## SQL Conventies

```sql
-- Gebruik lowercase voor keywords in code, uppercase in docs
-- Altijd expliciete kolomnamen, nooit SELECT *
SELECT
    d.id,
    d.species,
    d.confidence,
    d.detected_at
FROM detections d
WHERE d.station = 'zolder'
    AND d.detected_at >= NOW() - INTERVAL '24 hours'
ORDER BY d.detected_at DESC;
```

## Git Commits

```
feat: nieuwe functionaliteit
fix: bug fix
docs: documentatie update
refactor: code verbetering zonder functiewijziging
test: tests toevoegen/wijzigen
chore: onderhoud (dependencies, configs)
```

## Security Standaarden

1. **Credentials** nooit in code - altijd via `.secrets` of environment
2. **Input validatie** op alle externe data
3. **Parameterized queries** voor database
4. **Restrictieve permissies** op config bestanden (600/640)
5. **Geen hardcoded IP's** in productie code - gebruik config

## Code Review Checklist

- [ ] Type hints aanwezig
- [ ] Docstrings voor publieke functies
- [ ] Error handling aanwezig
- [ ] Logging op juiste niveau
- [ ] Geen credentials in code
- [ ] Consistent met bestaande code
- [ ] Tests toegevoegd waar nodig
