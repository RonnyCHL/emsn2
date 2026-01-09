#!/usr/bin/env python3
"""
EMSN 2.0 - Centrale Logger Module

Uniforme logging voor alle EMSN scripts.
Vervangt de 8+ gedupliceerde logger implementaties.

Gebruik:
    from scripts.core.logging import EMSNLogger, get_logger

    # Simpele logger
    logger = get_logger('my_script')
    logger.info('Dit is een info bericht')
    logger.success('Operatie geslaagd')
    logger.error('Er ging iets mis')

    # Met MQTT publishing
    logger = get_logger('my_script', mqtt_topic='emsn2/logs/my_script')
    logger.info('Dit wordt ook naar MQTT gepublished')

    # Met JSON formatting
    logger = get_logger('my_script', json_format=True)
    logger.info('message', extra={'key': 'value'})

Modernized: 2026-01-09 - Added MQTT publishing, JSON format, structured logging
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict


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
    - Optionele MQTT publishing
    - Optionele JSON formatting

    Args:
        name: Naam van het script/module (wordt gebruikt in bestandsnaam)
        log_dir: Directory voor logbestanden (default: /mnt/usb/logs)
        console: Of er ook naar console geschreven moet worden (default: True)
        level: Minimum log level (default: INFO)
        mqtt_topic: Optionele MQTT topic voor log publishing (default: None)
        json_format: Gebruik JSON format voor log entries (default: False)
    """

    def __init__(
        self,
        name: str,
        log_dir: Optional[Path] = None,
        console: bool = True,
        level: int = logging.INFO,
        mqtt_topic: Optional[str] = None,
        json_format: bool = False
    ):
        self.name = name
        self.log_dir = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
        self.console = console
        self.level = level
        self.mqtt_topic = mqtt_topic
        self.json_format = json_format

        # MQTT client (lazy loading)
        self._mqtt_client: Any = None
        self._mqtt_connected: bool = False

        # Zorg dat log directory bestaat
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Log bestand met datum
        self._current_date = datetime.now().strftime('%Y%m%d')
        self.log_file = self.log_dir / f"{name}_{self._current_date}.log"

        # Setup Python logging (optioneel, voor compatibility)
        self._setup_python_logger()

        # Connect MQTT if topic specified
        if mqtt_topic:
            self._connect_mqtt()

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

    def _connect_mqtt(self) -> bool:
        """Connect to MQTT broker for log publishing."""
        try:
            import paho.mqtt.client as mqtt
            from .config import get_mqtt_config

            config = get_mqtt_config()
            self._mqtt_client = mqtt.Client(client_id=f"logger-{self.name}-{datetime.now().timestamp():.0f}")

            if config.get('username') and config.get('password'):
                self._mqtt_client.username_pw_set(config['username'], config['password'])

            self._mqtt_client.connect(config['broker'], config['port'], keepalive=60)
            self._mqtt_client.loop_start()
            self._mqtt_connected = True
            return True

        except ImportError:
            # paho-mqtt not installed
            return False
        except Exception:
            # Connection failed, continue without MQTT
            return False

    def _publish_mqtt(self, level: str, message: str, extra: Optional[Dict[str, Any]] = None):
        """Publish log entry to MQTT."""
        if not self._mqtt_connected or not self._mqtt_client or not self.mqtt_topic:
            return

        try:
            payload = {
                "timestamp": datetime.now().isoformat(),
                "logger": self.name,
                "level": level,
                "message": message
            }
            if extra:
                payload["extra"] = extra

            self._mqtt_client.publish(self.mqtt_topic, json.dumps(payload), qos=0)
        except Exception:
            pass  # Don't fail logging if MQTT fails

    def log(self, level: str, message: str, extra: Optional[Dict[str, Any]] = None):
        """
        Log een bericht met gegeven level.

        Dit is de low-level methode die direct naar bestand schrijft
        in het formaat dat consistent is met bestaande EMSN logs.

        Args:
            level: Log level (INFO, ERROR, WARNING, SUCCESS, DEBUG)
            message: Het te loggen bericht
            extra: Optionele extra data (alleen voor JSON format)
        """
        self._check_date_rotation()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Format entry based on json_format setting
        if self.json_format:
            entry_dict = {
                "timestamp": timestamp,
                "logger": self.name,
                "level": level,
                "message": message
            }
            if extra:
                entry_dict["extra"] = extra
            entry = json.dumps(entry_dict, ensure_ascii=False)
        else:
            entry = f"[{timestamp}] [{level}] {message}"

        # Schrijf naar console
        if self.console:
            print(entry)

        # Schrijf naar bestand
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(entry + '\n')
        except (IOError, OSError) as e:
            print(f"[ERROR] Kon niet naar logbestand schrijven: {e}")

        # Publish to MQTT if configured
        self._publish_mqtt(level, message, extra)

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

    def disconnect(self):
        """Disconnect MQTT client if connected."""
        if self._mqtt_client and self._mqtt_connected:
            try:
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
            except Exception:
                pass
            finally:
                self._mqtt_connected = False

    def __repr__(self):
        return f"EMSNLogger(name='{self.name}', log_dir='{self.log_dir}', mqtt={self.mqtt_topic})"

    def __del__(self):
        """Cleanup MQTT connection on garbage collection."""
        self.disconnect()


# Convenience functie voor snelle logger creatie
def get_logger(
    name: str,
    log_dir: Optional[Path] = None,
    mqtt_topic: Optional[str] = None,
    json_format: bool = False
) -> EMSNLogger:
    """
    Convenience functie om snel een logger te maken.

    Args:
        name: Naam van het script/module
        log_dir: Optionele custom log directory
        mqtt_topic: Optionele MQTT topic voor log publishing
        json_format: Gebruik JSON format voor log entries

    Returns:
        EMSNLogger instance
    """
    return EMSNLogger(name, log_dir, mqtt_topic=mqtt_topic, json_format=json_format)


# Module-level logger voor core module zelf
_core_logger = None

def get_core_logger() -> EMSNLogger:
    """Get de core module logger (singleton)"""
    global _core_logger
    if _core_logger is None:
        _core_logger = EMSNLogger('core')
    return _core_logger
