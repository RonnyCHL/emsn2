#!/usr/bin/env python3
"""
EMSN 2.0 - Dagelijkse SD Kaart Backup
Maakt een incrementele rsync backup van het systeem naar NAS

Features:
- Incrementele backup met hardlinks (ruimtebesparend)
- MQTT status publishing voor monitoring
- Structured JSON logging
- Lock file om dubbele runs te voorkomen
- Automatische retentie cleanup

Draait dagelijks om 02:00 via systemd timer

Exit codes:
  0 = Success
  1 = Warning (backup gelukt met waarschuwingen)
  2 = Error (backup gefaald)
  3 = Lock error (andere backup draait al)
"""

import os
import sys
import json
import fcntl
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import smtplib
from email.mime.text import MIMEText

# Voeg parent directory toe voor imports
sys.path.insert(0, str(Path(__file__).parent))
from backup_config import (
    STATION, DAILY_DIR, LOCAL_LOG_DIR, RSYNC_EXCLUDES,
    EMAIL_CONFIG, NAS_BACKUP_BASE, RETENTION_DAYS_DAILY
)

# MQTT configuratie
MQTT_ENABLED = True
MQTT_TOPIC_STATUS = f"emsn2/{STATION}/backup/daily/status"
MQTT_TOPIC_METRICS = f"emsn2/{STATION}/backup/daily/metrics"

# Lock file
LOCK_FILE = Path(f"/tmp/sd_backup_daily_{STATION}.lock")

# Logging setup met JSON formatter
LOCAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOCAL_LOG_DIR / 'sd_backup_daily.log'


class JsonFormatter(logging.Formatter):
    """JSON formatter voor structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "station": STATION,
        }

        # Voeg extra velden toe indien aanwezig
        if hasattr(record, 'metrics'):
            log_data['metrics'] = record.metrics

        return json.dumps(log_data)


# Dual logging: JSON naar file, readable naar stdout
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(JsonFormatter())

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)


class MQTTPublisher:
    """MQTT publisher voor backup status"""

    def __init__(self):
        self.client = None
        self.connected = False
        self._load_credentials()

    def _load_credentials(self):
        """Laad MQTT credentials uit .secrets"""
        self.host = "192.168.1.178"
        self.port = 1883
        self.username = None
        self.password = None

        secrets_file = Path("/home/ronny/emsn2/.secrets")
        if secrets_file.exists():
            with open(secrets_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("MQTT_USER="):
                        self.username = line.split("=", 1)[1]
                    elif line.startswith("MQTT_PASS="):
                        self.password = line.split("=", 1)[1]

    def connect(self) -> bool:
        """Maak verbinding met MQTT broker"""
        if not MQTT_ENABLED:
            return False

        try:
            import paho.mqtt.client as mqtt

            self.client = mqtt.Client(client_id=f"backup-{STATION}-{os.getpid()}")
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)

            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()
            self.connected = True
            logger.info("MQTT verbonden")
            return True

        except ImportError:
            logger.warning("paho-mqtt niet geïnstalleerd, MQTT uitgeschakeld")
            return False
        except Exception as e:
            logger.warning(f"MQTT connectie mislukt: {e}")
            return False

    def publish_status(self, status: str, message: str, metrics: Optional[Dict] = None):
        """Publish backup status naar MQTT"""
        if not self.connected or not self.client:
            return

        try:
            payload = {
                "station": STATION,
                "status": status,  # running, success, warning, error
                "message": message,
                "timestamp": datetime.now().isoformat(),
            }
            if metrics:
                payload["metrics"] = metrics

            self.client.publish(
                MQTT_TOPIC_STATUS,
                json.dumps(payload),
                retain=True,
                qos=1
            )

            # Publiceer ook metrics apart voor Grafana
            if metrics:
                self.client.publish(
                    MQTT_TOPIC_METRICS,
                    json.dumps({
                        "station": STATION,
                        "timestamp": datetime.now().isoformat(),
                        **metrics
                    }),
                    retain=True,
                    qos=1
                )

        except Exception as e:
            logger.warning(f"MQTT publish mislukt: {e}")

    def disconnect(self):
        """Sluit MQTT verbinding"""
        if self.client and self.connected:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass


class BackupLock:
    """Context manager voor backup lock file"""

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.lock_file = None
        self.locked = False

    def __enter__(self):
        self.lock_file = open(self.lock_path, 'w')
        try:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.locked = True
            # Schrijf PID naar lock file
            self.lock_file.write(str(os.getpid()))
            self.lock_file.flush()
            return self
        except BlockingIOError:
            self.lock_file.close()
            raise RuntimeError("Andere backup draait al (lock file actief)")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_file:
            if self.locked:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            self.lock_file.close()
            try:
                self.lock_path.unlink()
            except Exception:
                pass


def send_alert(subject: str, message: str):
    """Stuur email alert bij problemen"""
    if not EMAIL_CONFIG.get('smtp_user'):
        logger.warning("Email niet geconfigureerd, skip alert")
        return

    try:
        msg = MIMEText(message)
        msg['Subject'] = f"[EMSN Backup] {subject}"
        msg['From'] = EMAIL_CONFIG['from_addr']
        msg['To'] = EMAIL_CONFIG['to_addr']

        with smtplib.SMTP(EMAIL_CONFIG['smtp_host'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['smtp_user'], EMAIL_CONFIG['smtp_pass'])
            server.send_message(msg)

        logger.info(f"Alert email verstuurd: {subject}")
    except Exception as e:
        logger.error(f"Kon alert email niet versturen: {e}")


def check_nas_mount() -> bool:
    """Controleer of NAS gemount is"""
    if not NAS_BACKUP_BASE.exists():
        raise RuntimeError(f"NAS backup directory niet gevonden: {NAS_BACKUP_BASE}")

    # Test schrijfrechten
    test_file = NAS_BACKUP_BASE / '.write_test'
    try:
        test_file.touch()
        test_file.unlink()
        return True
    except Exception as e:
        raise RuntimeError(f"Geen schrijfrechten op NAS: {e}")


def create_exclude_file() -> Path:
    """Maak tijdelijk exclude bestand voor rsync"""
    exclude_file = Path('/tmp/rsync_excludes.txt')

    with open(exclude_file, 'w') as f:
        for exclude in RSYNC_EXCLUDES:
            f.write(f"{exclude}\n")

    return exclude_file


def cleanup_old_backups(mqtt: Optional[MQTTPublisher] = None) -> int:
    """Verwijder backups ouder dan retentie periode"""
    if not DAILY_DIR.exists():
        return 0

    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS_DAILY)
    removed_count = 0

    for backup_dir in DAILY_DIR.iterdir():
        if not backup_dir.is_dir():
            continue

        try:
            # Parse datum uit directory naam (YYYY-MM-DD)
            dir_date = datetime.strptime(backup_dir.name, '%Y-%m-%d')

            if dir_date < cutoff_date:
                logger.info(f"Verwijder oude backup: {backup_dir.name}")

                # Gebruik rm -rf voor snelle verwijdering
                result = subprocess.run(
                    ['rm', '-rf', str(backup_dir)],
                    capture_output=True,
                    timeout=300
                )

                if result.returncode == 0:
                    removed_count += 1
                else:
                    logger.warning(f"Kon {backup_dir.name} niet verwijderen")

        except ValueError:
            # Geen datum-formaat, skip
            continue
        except Exception as e:
            logger.warning(f"Fout bij cleanup {backup_dir.name}: {e}")

    if removed_count > 0:
        logger.info(f"Cleanup voltooid: {removed_count} oude backup(s) verwijderd")

    return removed_count


def get_backup_stats() -> Dict[str, Any]:
    """Haal backup statistieken op (alleen count, geen size - te traag over NFS)"""
    stats = {
        "backup_count": 0,
        "oldest_backup": None,
        "newest_backup": None,
    }

    if not DAILY_DIR.exists():
        return stats

    # Tel backups en vind oudste/nieuwste (snel, alleen directory listing)
    backup_dates = []
    for backup_dir in DAILY_DIR.iterdir():
        if backup_dir.is_dir():
            try:
                datetime.strptime(backup_dir.name, '%Y-%m-%d')
                backup_dates.append(backup_dir.name)
            except ValueError:
                continue

    if backup_dates:
        backup_dates.sort()
        stats["backup_count"] = len(backup_dates)
        stats["oldest_backup"] = backup_dates[0]
        stats["newest_backup"] = backup_dates[-1]

    return stats


def run_rsync_backup(mqtt: Optional[MQTTPublisher] = None) -> tuple[bool, int, str]:
    """
    Voer rsync backup uit naar NAS

    Returns:
        tuple: (success: bool, duration_seconds: int, status: str)
        status is 'success', 'warning', of 'error'
    """
    today = datetime.now().strftime('%Y-%m-%d')
    target_dir = DAILY_DIR / today

    # Maak target directory
    target_dir.mkdir(parents=True, exist_ok=True)

    # Exclude bestand
    exclude_file = create_exclude_file()

    # Zoek vorige backup voor hard links
    previous_backups = sorted([
        d for d in DAILY_DIR.iterdir()
        if d.is_dir() and d.name != today and d.name[0].isdigit()
    ])
    link_dest_arg = []
    if previous_backups:
        link_dest_arg = ['--link-dest', str(previous_backups[-1])]
        logger.info(f"Hardlinks naar: {previous_backups[-1].name}")

    cmd = [
        'rsync',
        '-avx',
        '--delete',
        '--info=progress2,stats2',
        '--exclude-from', str(exclude_file),
        *link_dest_arg,
        '/',
        str(target_dir) + '/'
    ]

    logger.info(f"Start rsync backup naar {target_dir}")
    logger.info(f"Commando: {' '.join(cmd)}")

    if mqtt:
        mqtt.publish_status("running", f"Rsync gestart naar {today}")

    start_time = datetime.now()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5400  # 90 minuten timeout
        )

        duration = int((datetime.now() - start_time).total_seconds())

        if result.returncode == 0:
            logger.info(f"Rsync backup succesvol in {duration} seconden")
            return True, duration, "success"

        elif result.returncode == 24:
            # Returncode 24: "Partial transfer due to vanished source files"
            # Dit is normaal bij een draaiend systeem
            logger.warning(f"Rsync voltooid met waarschuwingen (code 24) in {duration} seconden")
            logger.warning("Sommige bestanden verdwenen tijdens backup (normaal)")
            return True, duration, "warning"

        elif result.returncode == 23:
            # Returncode 23: "Partial transfer due to error"
            # Vaak door permission denied op sommige bestanden
            logger.warning(f"Rsync voltooid met waarschuwingen (code 23) in {duration} seconden")
            logger.warning("Sommige bestanden konden niet gekopieerd worden (permissies)")
            return True, duration, "warning"

        else:
            logger.error(f"Rsync gefaald met code {result.returncode}")
            logger.error(f"stderr: {result.stderr[-1000:] if result.stderr else 'geen output'}")
            return False, duration, "error"

    except subprocess.TimeoutExpired:
        logger.error("Rsync timeout na 90 minuten")
        return False, 5400, "error"

    except Exception as e:
        logger.error(f"Rsync fout: {e}")
        return False, 0, "error"

    finally:
        # Cleanup exclude file
        try:
            exclude_file.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> int:
    """
    Hoofdfunctie

    Returns:
        int: Exit code (0=success, 1=warning, 2=error, 3=lock error)
    """
    mqtt = MQTTPublisher()
    exit_code = 0

    logger.info("=" * 60)
    logger.info(f"EMSN Dagelijkse Backup - Station: {STATION}")
    logger.info(f"Start: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    try:
        # Verkrijg lock
        with BackupLock(LOCK_FILE):
            # MQTT verbinding
            mqtt.connect()
            mqtt.publish_status("running", "Backup gestart")

            # Pre-flight checks
            check_nas_mount()
            logger.info("NAS mount OK")

            # Cleanup oude backups eerst
            cleanup_old_backups(mqtt)

            # Voer backup uit
            success, duration, status = run_rsync_backup(mqtt)

            # Verzamel metrics
            stats = get_backup_stats()
            metrics = {
                "duration_seconds": duration,
                "rsync_status": status,
                "backup_count": stats["backup_count"],
                "oldest_backup": stats["oldest_backup"],
                "newest_backup": stats["newest_backup"],
                "date": datetime.now().strftime('%Y-%m-%d'),
            }

            if success:
                logger.info("-" * 60)
                logger.info(f"Backup voltooid met status: {status}")
                logger.info(f"Duur: {duration} seconden ({duration // 60} min)")
                logger.info(f"Aantal backups: {stats['backup_count']} ({stats['oldest_backup']} - {stats['newest_backup']})")
                logger.info("=" * 60)

                mqtt.publish_status(status, f"Backup voltooid in {duration // 60} min", metrics)

                # Exit code 1 voor warnings, 0 voor success
                exit_code = 1 if status == "warning" else 0

            else:
                logger.error("Backup GEFAALD")
                mqtt.publish_status("error", "Backup gefaald", metrics)

                send_alert(
                    f"Dagelijkse backup GEFAALD - {STATION}",
                    f"De dagelijkse rsync backup voor {STATION} is mislukt.\n\n"
                    f"Duur: {duration} seconden\n"
                    f"Status: {status}\n\n"
                    f"Controleer de logs: {log_file}\n\n"
                    f"Tijd: {datetime.now().isoformat()}"
                )
                exit_code = 2

    except RuntimeError as e:
        if "lock" in str(e).lower():
            logger.error(f"Lock error: {e}")
            mqtt.publish_status("error", str(e))
            exit_code = 3
        else:
            logger.exception(f"Runtime error: {e}")
            mqtt.publish_status("error", str(e))
            exit_code = 2

    except Exception as e:
        logger.exception(f"Kritieke fout: {e}")
        mqtt.publish_status("error", f"Kritieke fout: {e}")

        send_alert(
            f"Dagelijkse backup KRITIEKE FOUT - {STATION}",
            f"Er is een kritieke fout opgetreden:\n\n{str(e)}\n\n"
            f"Controleer de logs: {log_file}"
        )
        exit_code = 2

    finally:
        mqtt.disconnect()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
