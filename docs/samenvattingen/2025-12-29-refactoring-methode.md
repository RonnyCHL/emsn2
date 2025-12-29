# EMSN 2.0 - Refactoring Methode

**Datum:** 29 december 2025
**Auteur:** Claude Code (IT Specialist)

---

## Doel

Alle Python scripts migreren van gedistribueerde credentials naar gecentraliseerde core modules, waardoor:
- Geen hardcoded passwords meer in de codebase
- Consistente code style over alle scripts
- Eenvoudig onderhoud bij wijzigingen in credentials
- Betere security (credentials alleen in `.secrets` bestand)

---

## Core Modules Structuur

```
/home/ronny/emsn2/scripts/core/
├── __init__.py          # Package marker
├── config.py            # get_postgres_config(), get_mqtt_config()
├── logging.py           # EMSNLogger class
├── network.py           # HOSTS dictionary
└── mqtt.py              # MQTT utilities
```

### config.py - Credentials laden

```python
def get_postgres_config() -> dict:
    """Laad PostgreSQL credentials uit .secrets bestand."""
    secrets = _load_secrets()
    return {
        'host': secrets.get('PG_HOST', '192.168.1.25'),
        'port': int(secrets.get('PG_PORT', 5433)),
        'database': secrets.get('PG_DB', 'emsn'),
        'user': secrets.get('PG_USER', 'birdpi_zolder'),
        'password': secrets.get('PG_PASS', '')
    }

def get_mqtt_config() -> dict:
    """Laad MQTT credentials uit .secrets bestand."""
    secrets = _load_secrets()
    return {
        'broker': secrets.get('MQTT_BROKER', '192.168.1.178'),
        'port': int(secrets.get('MQTT_PORT', 1883)),
        'username': secrets.get('MQTT_USER', 'ecomonitor'),
        'password': secrets.get('MQTT_PASS', '')
    }
```

---

## Refactoring Stappen

### Stap 1: Identificeer oude imports

Zoek naar scripts met oude import patronen:

```bash
grep -rl "from emsn_secrets\|from station_config" --include="*.py"
```

### Stap 2: Vervang imports

**VOOR (oud):**
```python
# Import secrets
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
try:
    from emsn_secrets import get_postgres_config
    _pg = get_postgres_config()
except ImportError:
    _pg = {'host': '192.168.1.25', 'port': 5433, 'database': 'emsn',
           'user': 'birdpi_zolder', 'password': os.environ.get('EMSN_DB_PASSWORD', '')}

DB_CONFIG = {
    'host': _pg.get('host', '192.168.1.25'),
    'port': _pg.get('port', 5433),
    'database': _pg.get('database', 'emsn'),
    'user': _pg.get('user', 'birdpi_zolder'),
    'password': _pg.get('password', '')
}
```

**NA (nieuw):**
```python
# Import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import get_postgres_config

DB_CONFIG = get_postgres_config()
```

### Stap 3: Pas sys.path aan

De `sys.path.insert()` moet verwijzen naar de `scripts/` directory:

| Script locatie | sys.path insert |
|----------------|-----------------|
| `scripts/script.py` | `Path(__file__).parent` |
| `scripts/subdir/script.py` | `Path(__file__).parent.parent` |
| `scripts/subdir/subsubdir/script.py` | `Path(__file__).parent.parent.parent` |

### Stap 4: Verifieer syntax

```bash
python3 -c "
import sys
from pathlib import Path
with open('script.py') as f:
    content = f.read()
exec(compile(content, 'script.py', 'exec'), {'__name__': '__test__'})
print('Syntax OK')
"
```

### Stap 5: Test imports

```bash
python3 -c "
from core.config import get_postgres_config, get_mqtt_config
pg = get_postgres_config()
print(f'PostgreSQL: {pg[\"host\"]}:{pg[\"port\"]}')
"
```

---

## Checklist per Script

- [ ] Oude imports verwijderd (`from emsn_secrets`, `from station_config`)
- [ ] Nieuwe import toegevoegd (`from core.config import get_postgres_config`)
- [ ] `sys.path.insert()` verwijst naar juiste directory
- [ ] Fallback config dictionaries verwijderd (redundant)
- [ ] Syntax getest
- [ ] Import getest

---

## Veelvoorkomende Patronen

### Pattern 1: Direct gebruik

```python
from core.config import get_postgres_config
DB_CONFIG = get_postgres_config()

conn = psycopg2.connect(**DB_CONFIG)
```

### Pattern 2: Met fallback (voor Docker containers)

```python
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from core.config import get_postgres_config
    _pg = get_postgres_config()
except ImportError:
    _pg = {}

# Fallback naar environment variables
PG_HOST = _pg.get('host') or os.environ.get('PG_HOST', '192.168.1.25')
```

### Pattern 3: Met EMSNLogger

```python
from core.config import get_postgres_config
from core.logging import EMSNLogger

class MyScript:
    def __init__(self):
        self.logger = EMSNLogger('my-script')
        self.pg_config = get_postgres_config()

    def log(self, level, message):
        self.logger.log(level, message)
```

---

## Resultaten

### Statistieken

| Metric | Waarde |
|--------|--------|
| Totaal scripts gerefactord | 21 |
| Regels code verwijderd | 272 |
| Regels code toegevoegd | 116 |
| Netto reductie | 156 regels |

### Gerefactorde Scripts

**reports/**
- report_base.py
- monthly_report.py
- report_highlights.py

**flysafe/**
- flysafe_scraper.py
- migration_alerts.py
- migration_forecast.py
- radar_correlation.py
- seasonal_analysis.py
- species_correlation.py

**maintenance/**
- database_backup.py
- database_cleanup.py
- system_health_check.py

**monitoring/**
- network_monitor.py

**atmosbird/**
- atmosbird_archive_sync.py

**sync/**
- bayesian_verification.py
- lifetime_sync.py

**ulanzi/**
- screenshot_cleanup.py

**root scripts/**
- hardware_metrics.py
- system_inventory.py
- timer_timeline.py
- train_existing_v2.py

---

## Git Commits

```
ce3446c refactor: introduceer core modules en verwijder code duplicatie
7ef0ebb refactor: alle scripts migreren naar core modules
```

---

## Lessen Geleerd

1. **Consistent pad berekenen:** Gebruik altijd `Path(__file__).parent` relatief aan het script
2. **Fallbacks minimaliseren:** Core modules hebben ingebouwde fallbacks
3. **Test vroeg:** Syntax check na elke wijziging voorkomt cascading errors
4. **Batch verwerking:** Groepeer vergelijkbare scripts voor efficiënte refactoring
5. **Documenteer patronen:** Consistente code style maakt onderhoud eenvoudiger

---

*Gegenereerd door Claude Code - EMSN 2.0 IT Specialist*
