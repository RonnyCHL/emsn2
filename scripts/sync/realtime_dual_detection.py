#!/usr/bin/env python3
"""
EMSN 2.0 - Realtime Dual Detection Service

Luistert naar MQTT detecties van beide stations (zolder + berging) en detecteert
in realtime wanneer dezelfde soort op beide stations wordt gehoord.

Dit vervangt de oude timer-based dual_detection_sync.py voor snellere notificaties.
De oude sync blijft beschikbaar voor database administratie (markeren dual_detection flag).

Auteur: Claude Code
Datum: 2026-01-05
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from threading import Lock
import signal

import paho.mqtt.client as mqtt
import psycopg2

# Add project root to path for core modules
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'config'))

from scripts.core.logging import EMSNLogger
from scripts.core.config import get_postgres_config, get_mqtt_config

# Configuration
LOG_DIR = Path("/mnt/usb/logs")
TIME_WINDOW_SECONDS = 30  # Maximale tijd tussen detecties om als dual te markeren
MIN_CONFIDENCE = 0.70     # Minimale confidence voor dual detection

# MQTT Topics
MQTT_TOPICS = {
    'zolder_detection': 'birdnet/zolder/detection',
    'berging_detection': 'birdnet/berging/detection',
    'dual_alert': 'emsn2/dual/detection/new',
    'status': 'emsn2/dual/realtime/status',
}


class DetectionBuffer:
    """
    Thread-safe buffer voor detecties per station.
    Houdt detecties bij in een sliding window.
    """

    def __init__(self, window_seconds=30):
        self.window_seconds = window_seconds
        self.lock = Lock()
        # Structure: {species: [(timestamp, confidence, station, data), ...]}
        self.detections = defaultdict(list)

    def add(self, species, confidence, station, data):
        """Voeg detectie toe en cleanup oude entries"""
        now = datetime.now()

        with self.lock:
            # Cleanup oude detecties voor deze soort
            cutoff = now - timedelta(seconds=self.window_seconds)
            self.detections[species] = [
                d for d in self.detections[species]
                if d[0] > cutoff
            ]

            # Voeg nieuwe detectie toe
            self.detections[species].append((now, confidence, station, data))

    def check_dual(self, species):
        """
        Check of er een dual detection is voor deze soort.
        Returns tuple (zolder_data, berging_data) of None.
        """
        with self.lock:
            detections = self.detections.get(species, [])

            if len(detections) < 2:
                return None

            # Zoek detecties van beide stations
            zolder = None
            berging = None

            for timestamp, confidence, station, data in detections:
                if station == 'zolder' and zolder is None:
                    zolder = (timestamp, confidence, data)
                elif station == 'berging' and berging is None:
                    berging = (timestamp, confidence, data)

            if zolder and berging:
                return (zolder, berging)

            return None

    def mark_processed(self, species):
        """Markeer detecties als verwerkt (verwijder uit buffer)"""
        with self.lock:
            if species in self.detections:
                del self.detections[species]

    def cleanup_all(self):
        """Verwijder alle verlopen detecties"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)

        with self.lock:
            for species in list(self.detections.keys()):
                self.detections[species] = [
                    d for d in self.detections[species]
                    if d[0] > cutoff
                ]
                if not self.detections[species]:
                    del self.detections[species]


class RealtimeDualDetector:
    """
    Realtime dual detection service.
    Luistert naar MQTT en detecteert dual detections binnen het tijdsvenster.
    """

    def __init__(self, logger):
        self.logger = logger
        self.buffer = DetectionBuffer(TIME_WINDOW_SECONDS)
        self.mqtt_client = None
        self.pg_conn = None
        self.running = False

        # Track welke dual detections we al hebben gepubliceerd
        # om duplicaten te voorkomen binnen korte tijd
        self.published_duals = {}  # species -> last_published_time
        self.dual_cooldown_seconds = 60  # Minimaal 60 sec tussen dual alerts voor zelfde soort

        # Bayesian model (lazy loaded)
        self.bayesian_model = None

    def connect_database(self):
        """Connect to PostgreSQL"""
        try:
            pg_config = get_postgres_config()
            self.pg_conn = psycopg2.connect(**pg_config)
            self.logger.success("Database connected")

            # Load Bayesian model
            try:
                from bayesian_verification import BayesianVerificationModel
                self.bayesian_model = BayesianVerificationModel(self.pg_conn, self.logger)
                self.bayesian_model.load_species_statistics()
                self.logger.info(f"Bayesian model loaded ({len(self.bayesian_model.species_stats)} species)")
            except Exception as e:
                self.logger.warning(f"Bayesian model not available: {e}")

            return True
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return False

    def calculate_verification_score(self, species, zolder_conf, berging_conf, time_diff):
        """Calculate verification score using Bayesian model or fallback"""
        if self.bayesian_model:
            try:
                result = self.bayesian_model.calculate_dual_verification_score(
                    species=species,
                    zolder_confidence=zolder_conf,
                    berging_confidence=berging_conf,
                    time_diff_seconds=time_diff
                )
                return result['verification_score']
            except Exception as e:
                self.logger.warning(f"Bayesian calculation failed: {e}")

        # Fallback: simple average
        return (zolder_conf + berging_conf) / 2

    def on_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        """MQTT connection callback"""
        if reason_code == 0:
            self.logger.success("MQTT connected")

            # Subscribe to detection topics
            client.subscribe(MQTT_TOPICS['zolder_detection'], qos=1)
            client.subscribe(MQTT_TOPICS['berging_detection'], qos=1)
            self.logger.info(f"Subscribed to detection topics")

            # Publish online status
            client.publish(
                MQTT_TOPICS['status'],
                json.dumps({
                    'status': 'online',
                    'timestamp': datetime.now().isoformat(),
                    'window_seconds': TIME_WINDOW_SECONDS
                }),
                qos=1,
                retain=True
            )
        else:
            self.logger.error(f"MQTT connection failed: {reason_code}")

    def on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT detection messages"""
        try:
            # Determine station from topic
            if 'zolder' in msg.topic:
                station = 'zolder'
            elif 'berging' in msg.topic:
                station = 'berging'
            else:
                return

            # Parse JSON payload
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)

            species = data.get('species')  # Dutch name
            scientific = data.get('scientific_name')
            confidence = data.get('confidence', 0)

            if not species or confidence < MIN_CONFIDENCE:
                return

            self.logger.info(f"Detection: {species} @ {station} ({confidence:.0%})")

            # Add to buffer
            self.buffer.add(species, confidence, station, data)

            # Check for dual detection
            dual = self.buffer.check_dual(species)
            if dual:
                self.handle_dual_detection(species, scientific, dual)

        except json.JSONDecodeError as e:
            self.logger.warning(f"Invalid JSON: {e}")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")

    def handle_dual_detection(self, species, scientific, dual_data):
        """Process a dual detection"""
        zolder, berging = dual_data
        zolder_time, zolder_conf, zolder_data = zolder
        berging_time, berging_conf, berging_data = berging

        # Check cooldown voor deze soort
        now = datetime.now()
        last_published = self.published_duals.get(species)
        if last_published:
            elapsed = (now - last_published).total_seconds()
            if elapsed < self.dual_cooldown_seconds:
                self.logger.info(f"Dual cooldown active for {species} ({int(elapsed)}s)")
                return

        # Calculate metrics
        time_diff = abs((zolder_time - berging_time).total_seconds())
        avg_conf = (zolder_conf + berging_conf) / 2
        verification_score = self.calculate_verification_score(
            scientific or species,
            zolder_conf,
            berging_conf,
            time_diff
        )

        # Use earlier timestamp as detection time
        detection_time = min(zolder_time, berging_time)

        # Publish dual detection alert
        alert = {
            'species': scientific or species,
            'common_name': species,
            'detection_time': detection_time.isoformat(),
            'time_diff_seconds': int(time_diff),
            'zolder_confidence': round(zolder_conf, 4),
            'berging_confidence': round(berging_conf, 4),
            'avg_confidence': round(avg_conf, 4),
            'verification_score': round(verification_score, 4),
            'realtime': True  # Flag to indicate this came from realtime service
        }

        self.mqtt_client.publish(
            MQTT_TOPICS['dual_alert'],
            json.dumps(alert),
            qos=1
        )

        self.logger.success(f"DUAL: {species} (diff: {int(time_diff)}s, score: {verification_score:.2f})")

        # Record publication time and clear buffer
        self.published_duals[species] = now
        self.buffer.mark_processed(species)

        # Cleanup old published records
        self._cleanup_published_duals()

    def _cleanup_published_duals(self):
        """Remove old entries from published_duals tracker"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.dual_cooldown_seconds * 2)

        self.published_duals = {
            species: timestamp
            for species, timestamp in self.published_duals.items()
            if timestamp > cutoff
        }

    def start(self):
        """Start the realtime dual detection service"""
        self.logger.info("=" * 60)
        self.logger.info("EMSN Realtime Dual Detection Service")
        self.logger.info(f"Window: {TIME_WINDOW_SECONDS}s | Min confidence: {MIN_CONFIDENCE}")
        self.logger.info("=" * 60)

        # Connect to database
        self.connect_database()

        # Setup MQTT client
        mqtt_config = get_mqtt_config()
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.username_pw_set(
            mqtt_config.get('username', 'ecomonitor'),
            mqtt_config.get('password', '')
        )
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message

        # Set last will (offline status)
        self.mqtt_client.will_set(
            MQTT_TOPICS['status'],
            json.dumps({
                'status': 'offline',
                'timestamp': datetime.now().isoformat()
            }),
            qos=1,
            retain=True
        )

        try:
            self.mqtt_client.connect(
                mqtt_config.get('broker', '192.168.1.178'),
                mqtt_config.get('port', 1883),
                keepalive=60
            )

            self.running = True
            self.logger.success("Service started - listening for detections")

            # Run forever
            self.mqtt_client.loop_forever()

        except KeyboardInterrupt:
            self.logger.info("Shutdown requested")
        except Exception as e:
            self.logger.error(f"Error: {e}")
        finally:
            self.stop()

    def stop(self):
        """Stop the service gracefully"""
        self.running = False

        if self.mqtt_client:
            # Publish offline status
            self.mqtt_client.publish(
                MQTT_TOPICS['status'],
                json.dumps({
                    'status': 'offline',
                    'timestamp': datetime.now().isoformat()
                }),
                qos=1,
                retain=True
            )
            self.mqtt_client.disconnect()

        if self.pg_conn:
            self.pg_conn.close()

        self.logger.info("Service stopped")


def main():
    logger = EMSNLogger('realtime_dual', LOG_DIR)

    detector = RealtimeDualDetector(logger)

    # Handle signals for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        detector.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    detector.start()


if __name__ == "__main__":
    main()
