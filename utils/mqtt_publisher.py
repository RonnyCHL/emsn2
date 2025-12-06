#!/usr/bin/env python3
"""
EMSN 2.0 - MQTT Publisher Utility

Shared MQTT client for publishing sensor data, system alerts, and health status.

Broker Configuration:
- Host: 192.168.1.178 (emsn2-zolder)
- Port: 1883
- Username: ecomonitor
- Password: Nijverdal2024!

Topic Structure:
- emsn2/detections/new - New bird detections
- emsn2/hardware/{station} - Hardware metrics
- weather/meteo/* - Weather updates
- emsn2/system/alerts - Error alerts
- emsn2/system/health - Service health status
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import paho.mqtt.client as mqtt
from pathlib import Path

# MQTT Broker Configuration
MQTT_BROKER = "192.168.1.178"
MQTT_PORT = 1883
MQTT_USERNAME = "ecomonitor"
MQTT_PASSWORD = "Nijverdal2024!"
MQTT_KEEPALIVE = 60

# Topic prefixes
TOPIC_DETECTIONS = "emsn2/detections"
TOPIC_HARDWARE = "emsn2/hardware"
TOPIC_WEATHER = "weather/meteo"
TOPIC_SYSTEM = "emsn2/system"


class EMSNMQTTPublisher:
    """
    MQTT Publisher for EMSN 2.0 system.

    Handles connection, reconnection, and publishing to various topics.
    Non-blocking: MQTT failures don't stop the main sync process.
    """

    def __init__(self, client_id: str, logger: Optional[logging.Logger] = None):
        """
        Initialize MQTT publisher.

        Args:
            client_id: Unique client ID for this publisher
            logger: Optional logger instance
        """
        self.client_id = client_id
        self.logger = logger or logging.getLogger(__name__)
        self.client = None
        self.connected = False

    def connect(self) -> bool:
        """
        Connect to MQTT broker.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv311)
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish

            self.logger.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            self.client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            self.client.loop_start()

            # Wait briefly for connection
            import time
            time.sleep(1)

            return self.connected

        except Exception as e:
            self.logger.error(f"MQTT connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            self.logger.info("Disconnected from MQTT broker")

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker."""
        if rc == 0:
            self.connected = True
            self.logger.info("Successfully connected to MQTT broker")
        else:
            self.logger.error(f"MQTT connection failed with code {rc}")
            self.connected = False

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker."""
        self.connected = False
        if rc != 0:
            self.logger.warning(f"Unexpected MQTT disconnection (code {rc})")

    def _on_publish(self, client, userdata, mid):
        """Callback when message published."""
        self.logger.debug(f"Message {mid} published")

    def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False) -> bool:
        """
        Publish a message to MQTT topic.

        Args:
            topic: MQTT topic
            payload: Dictionary payload (will be JSON encoded)
            qos: Quality of Service (0, 1, or 2)
            retain: Whether to retain the message

        Returns:
            True if publish successful, False otherwise
        """
        if not self.connected:
            self.logger.warning("Not connected to MQTT broker, skipping publish")
            return False

        try:
            payload_json = json.dumps(payload)
            result = self.client.publish(topic, payload_json, qos=qos, retain=retain)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.debug(f"Published to {topic}: {payload_json[:100]}...")
                return True
            else:
                self.logger.error(f"Publish failed to {topic}: {result.rc}")
                return False

        except Exception as e:
            self.logger.error(f"Error publishing to {topic}: {e}")
            return False

    def publish_detection(self, detection_data: Dict[str, Any], station_id: str = "zolder") -> bool:
        """
        Publish a new bird detection.

        Args:
            detection_data: Detection data dict (date, time, species, confidence, etc.)
            station_id: Station identifier

        Returns:
            True if published successfully
        """
        topic = f"{TOPIC_DETECTIONS}/new"
        payload = {
            "station_id": station_id,
            "timestamp": datetime.now().isoformat(),
            **detection_data
        }
        return self.publish(topic, payload, qos=1)

    def publish_hardware_metrics(self, metrics: Dict[str, Any], station_id: str) -> bool:
        """
        Publish hardware metrics for a station.

        Args:
            metrics: Hardware metrics dict
            station_id: Station identifier (e.g., 'zolder', 'berging')

        Returns:
            True if published successfully
        """
        topic = f"{TOPIC_HARDWARE}/{station_id}"
        payload = {
            "station_id": station_id,
            "timestamp": datetime.now().isoformat(),
            **metrics
        }
        return self.publish(topic, payload, qos=0, retain=True)

    def publish_weather(self, weather_data: Dict[str, Any]) -> bool:
        """
        Publish weather data.

        Args:
            weather_data: Weather data dict

        Returns:
            True if published successfully
        """
        topic = f"{TOPIC_WEATHER}/current"
        payload = {
            "timestamp": datetime.now().isoformat(),
            **weather_data
        }
        return self.publish(topic, payload, qos=0, retain=True)

    def publish_alert(self, alert_type: str, message: str, severity: str = "warning") -> bool:
        """
        Publish a system alert.

        Args:
            alert_type: Type of alert (e.g., 'sync_failed', 'db_error')
            message: Alert message
            severity: Severity level ('info', 'warning', 'error', 'critical')

        Returns:
            True if published successfully
        """
        topic = f"{TOPIC_SYSTEM}/alerts"
        payload = {
            "timestamp": datetime.now().isoformat(),
            "alert_type": alert_type,
            "severity": severity,
            "message": message
        }
        return self.publish(topic, payload, qos=1, retain=False)

    def publish_health(self, service_name: str, status: str, details: Dict[str, Any] = None) -> bool:
        """
        Publish service health status.

        Args:
            service_name: Name of the service (e.g., 'lifetime_sync')
            status: Status ('healthy', 'degraded', 'down')
            details: Optional additional details

        Returns:
            True if published successfully
        """
        topic = f"{TOPIC_SYSTEM}/health/{service_name}"
        payload = {
            "timestamp": datetime.now().isoformat(),
            "service": service_name,
            "status": status,
            "details": details or {}
        }
        return self.publish(topic, payload, qos=0, retain=True)


def get_publisher(service_name: str, logger: Optional[logging.Logger] = None) -> EMSNMQTTPublisher:
    """
    Convenience function to create and connect an MQTT publisher.

    Args:
        service_name: Name of the service using the publisher
        logger: Optional logger instance

    Returns:
        Connected EMSNMQTTPublisher instance (or disconnected if connection failed)
    """
    publisher = EMSNMQTTPublisher(client_id=f"emsn2_{service_name}", logger=logger)
    publisher.connect()
    return publisher


if __name__ == "__main__":
    # Test the MQTT publisher
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from logger import get_logger

    test_logger = get_logger('mqtt_test')
    test_logger.info("Testing MQTT publisher...")

    publisher = get_publisher('test', test_logger)

    if publisher.connected:
        # Test various publish methods
        publisher.publish_health('test', 'healthy', {'test': 'running'})
        publisher.publish_alert('test_alert', 'This is a test alert', 'info')

        test_detection = {
            'date': '2025-12-06',
            'time': '13:00:00',
            'scientific_name': 'Parus major',
            'common_name': 'Koolmees',
            'confidence': 0.95
        }
        publisher.publish_detection(test_detection, 'test_station')

        test_logger.info("Test messages published successfully")
    else:
        test_logger.error("Could not connect to MQTT broker")

    publisher.disconnect()
    test_logger.info("MQTT test complete")
