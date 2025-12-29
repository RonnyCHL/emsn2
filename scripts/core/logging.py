#!/usr/bin/env python3
"""
EMSN 2.0 - Centrale Logger Module

Uniforme logging voor alle EMSN scripts.
Vervangt de 8+ gedupliceerde logger implementaties.

Gebruik:
    from scripts.core.logging import EMSNLogger

    logger = EMSNLogger('my_script')
    logger.info('Dit is een info bericht')
    logger.success('Operatie geslaagd')
    logger.error('Er ging iets mis')
"""

import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


# Default log directory
DEFAULT_LOG_DIR = Path('/mnt/usb/logs')


class EMSNLogger:
    """
    Uniforme logger voor EMSN scripts.

    Features:
    - Schrijft naar bestand EN console
    - Dagelijkse log rotatie (nieuw bestand per dag)
    - Ondersteunt standaard levels + 'success'
    - Consistente timestamp formatting

    Args:
        name: Naam van het script/module (wordt gebruikt in bestandsnaam)
        log_dir: Directory voor logbestanden (default: /mnt/usb/logs)
        console: Of er ook naar console geschreven moet worden (default: True)
        level: Minimum log level (default: INFO)
    """

    def __init__(
        self,
        name: str,
        log_dir: Optional[Path] = None,
        console: bool = True,
        level: int = logging.INFO
    ):
        self.name = name
        self.log_dir = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
        self.console = console
        self.level = level

        # Zorg dat log directory bestaat
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Log bestand met datum
        self._current_date = datetime.now().strftime('%Y%m%d')
        self.log_file = self.log_dir / f"{name}_{self._current_date}.log"

        # Setup Python logging (optioneel, voor compatibility)
        self._setup_python_logger()

    def _setup_python_logger(self):
        """Setup standaard Python logger voor compatibility"""
        self._logger = logging.getLogger(f"emsn.{self.name}")
        self._logger.setLevel(self.level)

        # Voorkom dubbele handlers
        if not self._logger.handlers:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

            # File handler
            fh = logging.FileHandler(self.log_file)
            fh.setFormatter(formatter)
            self._logger.addHandler(fh)

            # Console handler (indien gewenst)
            if self.console:
                ch = logging.StreamHandler(sys.stdout)
                ch.setFormatter(formatter)
                self._logger.addHandler(ch)

    def _check_date_rotation(self):
        """Check of we naar een nieuw dagbestand moeten roteren"""
        current_date = datetime.now().strftime('%Y%m%d')
        if current_date != self._current_date:
            self._current_date = current_date
            self.log_file = self.log_dir / f"{self.name}_{self._current_date}.log"
            # Reset handlers voor nieuwe dag
            self._setup_python_logger()

    def log(self, level: str, message: str):
        """
        Log een bericht met gegeven level.

        Dit is de low-level methode die direct naar bestand schrijft
        in het formaat dat consistent is met bestaande EMSN logs.

        Args:
            level: Log level (INFO, ERROR, WARNING, SUCCESS, DEBUG)
            message: Het te loggen bericht
        """
        self._check_date_rotation()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"[{timestamp}] [{level}] {message}"

        # Schrijf naar console
        if self.console:
            print(entry)

        # Schrijf naar bestand
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(entry + '\n')
        except Exception as e:
            print(f"[ERROR] Kon niet naar logbestand schrijven: {e}")

    def info(self, message: str):
        """Log een INFO bericht"""
        self.log('INFO', message)

    def error(self, message: str):
        """Log een ERROR bericht"""
        self.log('ERROR', message)

    def warning(self, message: str):
        """Log een WARNING bericht"""
        self.log('WARNING', message)

    def debug(self, message: str):
        """Log een DEBUG bericht"""
        self.log('DEBUG', message)

    def success(self, message: str):
        """Log een SUCCESS bericht (EMSN-specifiek level)"""
        self.log('SUCCESS', message)

    def critical(self, message: str):
        """Log een CRITICAL bericht"""
        self.log('CRITICAL', message)

    def exception(self, message: str, exc_info: bool = True):
        """Log een ERROR met exception info"""
        import traceback
        if exc_info:
            tb = traceback.format_exc()
            self.log('ERROR', f"{message}\n{tb}")
        else:
            self.log('ERROR', message)

    # Aliassen voor backwards compatibility met bestaande code
    warn = warning

    def __repr__(self):
        return f"EMSNLogger(name='{self.name}', log_dir='{self.log_dir}')"


# Convenience functie voor snelle logger creatie
def get_logger(name: str, log_dir: Optional[Path] = None) -> EMSNLogger:
    """
    Convenience functie om snel een logger te maken.

    Args:
        name: Naam van het script/module
        log_dir: Optionele custom log directory

    Returns:
        EMSNLogger instance
    """
    return EMSNLogger(name, log_dir)


# Module-level logger voor core module zelf
_core_logger = None

def get_core_logger() -> EMSNLogger:
    """Get de core module logger (singleton)"""
    global _core_logger
    if _core_logger is None:
        _core_logger = EMSNLogger('core')
    return _core_logger
