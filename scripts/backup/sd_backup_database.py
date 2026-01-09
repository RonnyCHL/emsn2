#!/usr/bin/env python3
"""
EMSN 2.0 - Uurlijkse Database Backup
Maakt een gecomprimeerde dump van de BirdNET-Pi database (birds.db)

Draait elk uur via systemd timer
Maximaal 1 uur aan detecties kwijt bij crash
"""

import os
import sys
import subprocess
import shutil
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

# Voeg parent directory toe voor imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from backup_config import (
    STATION, DATABASE_DIR, LOCAL_LOG_DIR, BIRDNET_DB,
    EMAIL_CONFIG
)
from core.logging import get_logger

# Centrale logger
logger = get_logger('sd_backup_database')


def send_alert(subject: str, message: str):
    """Stuur email alert bij problemen"""
    if not EMAIL_CONFIG['smtp_user']:
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

    except Exception as e:
        logger.error(f"Kon alert email niet versturen: {e}")


def backup_sqlite_database():
    """Maak backup van SQLite database met .dump commando"""
    now = datetime.now()
    timestamp = now.strftime('%Y-%m-%d-%H')
    dump_name = f"birds-{timestamp}.sql"
    compressed_name = f"{dump_name}.gz"

    # Maak output directory
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    # Check of database bestaat
    if not BIRDNET_DB.exists():
        raise RuntimeError(f"Database niet gevonden: {BIRDNET_DB}")

    # Tijdelijke dump file
    temp_dump = Path(f'/tmp/{dump_name}')
    final_path = DATABASE_DIR / compressed_name

    logger.info(f"Database: {BIRDNET_DB}")
    logger.info(f"Grootte: {BIRDNET_DB.stat().st_size / (1024**2):.1f} MB")

    try:
        # Maak SQL dump met sqlite3
        # Gebruik .dump voor volledige export inclusief schema
        cmd = f'sqlite3 "{BIRDNET_DB}" .dump > "{temp_dump}"'

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minuten timeout
        )

        if result.returncode != 0:
            raise RuntimeError(f"sqlite3 dump gefaald: {result.stderr}")

        if not temp_dump.exists() or temp_dump.stat().st_size == 0:
            raise RuntimeError("Dump bestand is leeg of niet aangemaakt")

        dump_size = temp_dump.stat().st_size
        logger.info(f"Dump grootte: {dump_size / (1024**2):.1f} MB")

        # Comprimeer met gzip
        gzip_cmd = 'pigz' if shutil.which('pigz') else 'gzip'
        compress_cmd = f"{gzip_cmd} -c {temp_dump} > {final_path}"

        result = subprocess.run(
            compress_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            raise RuntimeError(f"Compressie gefaald: {result.stderr}")

        compressed_size = final_path.stat().st_size
        ratio = (1 - compressed_size / dump_size) * 100
        logger.info(f"Gecomprimeerd: {compressed_size / (1024**2):.1f} MB ({ratio:.0f}% bespaard)")

        return final_path

    finally:
        # Cleanup temp file
        if temp_dump.exists():
            temp_dump.unlink()


def backup_config_files():
    """
    Kopieer ook belangrijke configuratie bestanden
    Dit is een lichtgewicht backup die elk uur meedraait
    """
    from backup_config import CONFIG_DIR, CONFIG_FILES

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    latest_dir = CONFIG_DIR / 'latest'
    latest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0

    for config_pattern in CONFIG_FILES:
        config_path = Path(config_pattern)

        # Verwerk glob patterns
        if '*' in config_pattern:
            parent = config_path.parent
            pattern = config_path.name
            if parent.exists():
                for f in parent.glob(pattern):
                    try:
                        dest = latest_dir / f.name
                        shutil.copy2(f, dest)
                        copied += 1
                    except Exception as e:
                        logger.debug(f"Kon {f} niet kopieren: {e}")
        else:
            try:
                # Check eerst of we leesrechten hebben
                if not os.access(config_pattern, os.R_OK):
                    continue

                if config_path.exists():
                    if config_path.is_dir():
                        dest_dir = latest_dir / config_path.name
                        if dest_dir.exists():
                            shutil.rmtree(dest_dir)
                        shutil.copytree(config_path, dest_dir)
                    else:
                        shutil.copy2(config_path, latest_dir / config_path.name)
                    copied += 1
            except PermissionError:
                # Skip bestanden waar we geen toegang toe hebben
                pass
            except Exception as e:
                logger.debug(f"Kon {config_path} niet kopieren: {e}")

    return copied


def get_database_stats() -> dict:
    """Verzamel statistieken over database backups"""
    stats = {'count': 0, 'size': 0, 'oldest': None, 'newest': None}

    if not DATABASE_DIR.exists():
        return stats

    backups = sorted(DATABASE_DIR.glob('*.sql.gz'))

    if backups:
        stats['count'] = len(backups)
        stats['size'] = sum(f.stat().st_size for f in backups)
        stats['oldest'] = backups[0].name
        stats['newest'] = backups[-1].name

    return stats


def main():
    """Hoofdfunctie"""
    logger.info("=" * 60)
    logger.info(f"EMSN Database Backup - Station: {STATION}")
    logger.info(f"Start: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    try:
        # Backup database
        backup_path = backup_sqlite_database()
        logger.info(f"Database backup: {backup_path}")

        # Backup config files
        config_count = backup_config_files()
        logger.info(f"Config bestanden gekopieerd: {config_count}")

        # Statistieken
        stats = get_database_stats()
        logger.info("-" * 60)
        logger.info(f"Totaal {stats['count']} database backups ({stats['size'] / (1024**2):.0f} MB)")
        if stats['oldest']:
            logger.info(f"Oudste: {stats['oldest']}")
            logger.info(f"Nieuwste: {stats['newest']}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.exception(f"Kritieke fout: {e}")

        # Alleen alert sturen als 3 opeenvolgende backups falen
        # (voorkom spam bij incidentele problemen)
        error_count_file = LOCAL_LOG_DIR / 'db_backup_errors'

        try:
            if error_count_file.exists():
                count = int(error_count_file.read_text().strip())
            else:
                count = 0

            count += 1
            error_count_file.write_text(str(count))

            if count >= 3:
                send_alert(
                    f"Database backup GEFAALD - {STATION}",
                    f"De database backup is {count}x achter elkaar mislukt.\n\n"
                    f"Laatste fout: {str(e)}\n\n"
                    f"Controleer de logs: {log_file}"
                )
                # Reset teller na alert
                error_count_file.unlink()
        except Exception:
            pass

        return 1


if __name__ == "__main__":
    sys.exit(main())
