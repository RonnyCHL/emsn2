#!/usr/bin/env python3
"""
AtmosBird Climate Control Service
Anti-condens systeem voor camera behuizing.

Hardware:
- DHT22 sensor op GPIO4 - temperatuur/luchtvochtigheid
- PTC Heater 5V via IRLZ44N MOSFET op GPIO17

Logica:
- Heater AAN als: RH > 80% OF temp < dauwpunt + 3°C
- Heater UIT als: RH < 75% EN temp > dauwpunt + 5°C (hysteresis)
- Settings worden geladen uit PostgreSQL database

Auteur: EMSN Project
"""

import sys
import time
import math
import signal
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

# Project root voor imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import psycopg2
from core.config import get_postgres_config
from core.logging import get_logger

# GPIO pins
DHT_PIN = 4       # GPIO4 voor DHT22
HEATER_PIN = 17   # GPIO17 voor heater MOSFET

# Default climate thresholds (worden overschreven door database)
RH_HIGH = 80.0
RH_LOW = 75.0
DEWPOINT_MARGIN_ON = 3.0
DEWPOINT_MARGIN_OFF = 5.0
READ_INTERVAL = 30
MAX_HEATER_TIME = 600
COOLDOWN_TIME = 120

# Database config via core.config
PG_CONFIG = get_postgres_config()

# Centrale logger
logger = get_logger('climate_control')


@dataclass
class ClimateState:
    """Huidige klimaat status."""
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    dewpoint: Optional[float] = None
    heater_on: bool = False
    heater_reason: str = 'off'
    heater_start_time: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    last_reading: Optional[datetime] = None
    read_errors: int = 0


class ClimateController:
    """Controller voor anti-condens systeem."""

    def __init__(self):
        self.state = ClimateState()
        self.running = False
        self.dht_device = None
        self.gpio_initialized = False
        self.pg_conn = None
        self.settings = {}
        self.loop_count = 0

    def load_settings(self) -> dict:
        """Laad thresholds uit database of gebruik defaults."""
        defaults = {
            'rh_high': RH_HIGH,
            'rh_low': RH_LOW,
            'dewpoint_margin_on': DEWPOINT_MARGIN_ON,
            'dewpoint_margin_off': DEWPOINT_MARGIN_OFF,
            'max_heater_time': MAX_HEATER_TIME,
            'cooldown_time': COOLDOWN_TIME,
            'read_interval': READ_INTERVAL
        }

        try:
            conn = psycopg2.connect(**PG_CONFIG)
            cur = conn.cursor()
            cur.execute("SELECT setting_key, setting_value FROM atmosbird_climate_settings")
            for key, value in cur.fetchall():
                if key in defaults:
                    defaults[key] = value
            cur.close()
            conn.close()
            logger.info(f"Settings geladen: RH>{defaults['rh_high']}%, dewpoint+{defaults['dewpoint_margin_on']}°C")
        except Exception as e:
            logger.warning(f"Kon settings niet laden uit DB, gebruik defaults: {e}")

        return defaults

    def log_to_database(self):
        """Log huidige status naar PostgreSQL."""
        if self.state.temperature is None:
            return

        try:
            if not self.pg_conn or self.pg_conn.closed:
                self.pg_conn = psycopg2.connect(**PG_CONFIG)

            cur = self.pg_conn.cursor()
            cur.execute("""
                INSERT INTO atmosbird_climate
                (temperature, humidity, dewpoint, heater_on, heater_reason, read_errors, station)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                self.state.temperature,
                self.state.humidity,
                self.state.dewpoint,
                self.state.heater_on,
                self.state.heater_reason,
                self.state.read_errors,
                'berging'
            ))
            self.pg_conn.commit()
            cur.close()

        except Exception as e:
            logger.error(f"Database log fout: {e}")
            if self.pg_conn:
                try:
                    self.pg_conn.rollback()
                except (Exception, OSError):
                    pass  # Rollback is non-critical
                try:
                    self.pg_conn.close()
                except (Exception, OSError):
                    pass  # Connection cleanup is non-critical
                self.pg_conn = None

    def get_heater_reason(self) -> str:
        """Bepaal reden voor huidige heater status."""
        if self.in_cooldown():
            return 'cooldown'
        if not self.state.heater_on:
            return 'off'
        if self.state.humidity and self.state.humidity > self.settings.get('rh_high', RH_HIGH):
            return 'rh_high'
        if self.state.temperature and self.state.dewpoint:
            if self.state.temperature < self.state.dewpoint + self.settings.get('dewpoint_margin_on', DEWPOINT_MARGIN_ON):
                return 'dewpoint_close'
        return 'hysteresis'

    def setup(self) -> bool:
        """Initialiseer hardware."""
        # Setup GPIO voor heater
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(HEATER_PIN, GPIO.OUT)
            GPIO.output(HEATER_PIN, GPIO.LOW)
            self.gpio_initialized = True
            logger.info(f"GPIO{HEATER_PIN} geconfigureerd voor heater")
        except ImportError:
            logger.error("RPi.GPIO niet geïnstalleerd!")
            return False
        except Exception as e:
            logger.error(f"GPIO setup mislukt: {e}")
            return False

        # Setup DHT22 sensor
        try:
            import board
            import adafruit_dht
            self.dht_device = adafruit_dht.DHT22(board.D4, use_pulseio=False)
            logger.info(f"DHT22 geconfigureerd op GPIO{DHT_PIN}")
        except ImportError:
            logger.error("adafruit-circuitpython-dht niet geïnstalleerd!")
            return False
        except Exception as e:
            logger.error(f"DHT22 setup mislukt: {e}")
            return False

        # Test database connectie
        try:
            conn = psycopg2.connect(**PG_CONFIG)
            conn.close()
            logger.info("PostgreSQL connectie OK")
        except Exception as e:
            logger.warning(f"PostgreSQL connectie mislukt: {e} (logging disabled)")

        return True

    def cleanup(self):
        """Cleanup hardware bij afsluiten."""
        logger.info("Cleanup...")

        # Heater uit
        if self.gpio_initialized:
            try:
                import RPi.GPIO as GPIO
                GPIO.output(HEATER_PIN, GPIO.LOW)
                GPIO.cleanup(HEATER_PIN)
                logger.info("Heater uitgeschakeld")
            except (ImportError, RuntimeError):
                pass  # GPIO cleanup is non-critical

        # DHT cleanup
        if self.dht_device:
            try:
                self.dht_device.exit()
            except (AttributeError, RuntimeError):
                pass  # DHT cleanup is non-critical

        # Database connectie sluiten
        if self.pg_conn:
            try:
                self.pg_conn.close()
            except (Exception, OSError):
                pass  # Connection cleanup is non-critical

    def calculate_dewpoint(self, temp_c: float, humidity: float) -> float:
        """Bereken dauwpunt met Magnus formule."""
        a = 17.27
        b = 237.7
        gamma = (a * temp_c / (b + temp_c)) + math.log(humidity / 100.0)
        return (b * gamma) / (a - gamma)

    def read_sensor(self) -> bool:
        """Lees DHT22 sensor met meerdere retries voor lange kabel."""
        if not self.dht_device:
            return False

        # Retries voor lange kabel - balans tussen snelheid en betrouwbaarheid
        max_retries = 4
        retry_delay = 2.0  # seconden tussen retries (DHT22 minimum)

        for attempt in range(max_retries):
            try:
                temperature = self.dht_device.temperature
                humidity = self.dht_device.humidity

                if temperature is not None and humidity is not None:
                    self.state.temperature = temperature
                    self.state.humidity = humidity
                    self.state.dewpoint = self.calculate_dewpoint(temperature, humidity)
                    self.state.last_reading = datetime.now()
                    self.state.read_errors = 0

                    logger.info(
                        f"Sensor: {temperature:.1f}°C, {humidity:.1f}% RH, "
                        f"dauwpunt: {self.state.dewpoint:.1f}°C"
                    )
                    return True

            except RuntimeError as e:
                # Normale DHT fouten - alleen loggen bij laatste retry
                if attempt >= 2:
                    logger.warning(f"Sensor leesfout: {e} (poging {attempt + 1}/{max_retries})")

            except Exception as e:
                logger.error(f"Onverwachte sensor fout: {e}")

            # Wacht even voor volgende poging (behalve laatste)
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

        # Alle retries gefaald
        self.state.read_errors += 1
        if self.state.read_errors <= 3:
            logger.warning(f"Sensor niet leesbaar na {max_retries} pogingen (fout #{self.state.read_errors})")
        return False

    def set_heater(self, on: bool):
        """Zet heater aan of uit."""
        try:
            import RPi.GPIO as GPIO
            GPIO.output(HEATER_PIN, GPIO.HIGH if on else GPIO.LOW)

            if on and not self.state.heater_on:
                self.state.heater_start_time = datetime.now()
                logger.info("🔥 Heater AAN")
            elif not on and self.state.heater_on:
                self.state.heater_start_time = None
                logger.info("❄️  Heater UIT")

            self.state.heater_on = on

        except Exception as e:
            logger.error(f"Heater schakelfout: {e}")

    def check_heater_timeout(self) -> bool:
        """Check of heater te lang aan staat."""
        if not self.state.heater_on or not self.state.heater_start_time:
            return False

        max_time = self.settings.get('max_heater_time', MAX_HEATER_TIME)
        runtime = (datetime.now() - self.state.heater_start_time).total_seconds()
        if runtime > max_time:
            logger.warning(f"Heater timeout na {runtime:.0f}s - cooldown gestart")
            self.state.cooldown_until = datetime.now()
            return True

        return False

    def in_cooldown(self) -> bool:
        """Check of we in cooldown periode zijn."""
        if not self.state.cooldown_until:
            return False

        cooldown = self.settings.get('cooldown_time', COOLDOWN_TIME)
        elapsed = (datetime.now() - self.state.cooldown_until).total_seconds()
        if elapsed > cooldown:
            self.state.cooldown_until = None
            logger.info("Cooldown periode voorbij")
            return False

        return True

    def should_heat(self) -> bool:
        """Bepaal of heater aan moet."""
        if self.state.temperature is None or self.state.humidity is None:
            return False

        if self.state.read_errors > 10:
            logger.warning("Te veel leesfouten - heater uit voor veiligheid")
            return False

        if self.in_cooldown():
            return False

        temp = self.state.temperature
        rh = self.state.humidity
        dewpoint = self.state.dewpoint

        rh_high = self.settings.get('rh_high', RH_HIGH)
        rh_low = self.settings.get('rh_low', RH_LOW)
        margin_on = self.settings.get('dewpoint_margin_on', DEWPOINT_MARGIN_ON)
        margin_off = self.settings.get('dewpoint_margin_off', DEWPOINT_MARGIN_OFF)

        if self.state.heater_on:
            if rh < rh_low and temp > dewpoint + margin_off:
                return False
            return True
        else:
            if rh > rh_high:
                logger.info(f"Hoge RH ({rh:.1f}%) - heater nodig")
                return True
            if temp < dewpoint + margin_on:
                logger.info(f"Temp ({temp:.1f}°C) dicht bij dauwpunt ({dewpoint:.1f}°C) - heater nodig")
                return True
            return False

    def control_loop(self):
        """Hoofdloop voor klimaatregeling."""
        # Laad settings bij start
        self.settings = self.load_settings()

        logger.info("Climate control loop gestart")
        logger.info(f"Thresholds: RH>{self.settings['rh_high']}% of temp<dauwpunt+{self.settings['dewpoint_margin_on']}°C")

        while self.running:
            # Lees sensor
            self.read_sensor()

            # Check heater timeout
            if self.check_heater_timeout():
                self.set_heater(False)
            else:
                need_heat = self.should_heat()
                self.set_heater(need_heat)

            # Update heater reason
            self.state.heater_reason = self.get_heater_reason()

            # Log naar database
            self.log_to_database()

            # Herlaad settings elke 20 loops (~10 minuten)
            self.loop_count += 1
            if self.loop_count >= 20:
                self.settings = self.load_settings()
                self.loop_count = 0

            # Wacht tot volgende meting
            interval = self.settings.get('read_interval', READ_INTERVAL)
            time.sleep(interval)

    def run(self):
        """Start de service."""
        logger.info("="*50)
        logger.info("AtmosBird Climate Control")
        logger.info("="*50)

        if not self.setup():
            logger.error("Setup mislukt - kan niet starten")
            return 1

        self.running = True

        def signal_handler(sig, frame):
            logger.info(f"Signal {sig} ontvangen - stoppen...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            self.control_loop()
        except Exception as e:
            logger.error(f"Onverwachte fout: {e}")
            return 1
        finally:
            self.cleanup()

        logger.info("Climate control gestopt")
        return 0


def main():
    """Entry point."""
    controller = ClimateController()
    sys.exit(controller.run())


if __name__ == "__main__":
    main()
