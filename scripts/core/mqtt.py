#!/usr/bin/env python3
"""
EMSN 2.0 - Centrale MQTT Module

Gedeelde MQTT client en publisher voor alle EMSN scripts.
Vervangt 4+ gedupliceerde MQTTPublisher implementaties.

Gebruik:
    from scripts.core.mqtt import EMSNMQTTClient, MQTTPublisher

    # Simple publisher (voor scripts die alleen publiceren)
    publisher = MQTTPublisher(logger)
    publisher.publish('emsn2/test', {'message': 'hello'})

    # Full client (voor scripts die ook subscriben)
    client = EMSNMQTTClient(logger)
    client.subscribe('birdnet/#', callback)
    client.run_forever()
"""

import json
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

import paho.mqtt.client as mqtt

from .config import get_mqtt_config
from .network import HOSTS, PORTS


class MQTTPublisher:
    """
    Simpele MQTT publisher voor scripts die alleen berichten versturen.

    Dit is de meest gebruikte pattern in EMSN scripts - connect, publish, disconnect.
    Ondersteunt automatische reconnect en JSON serialisatie.

    Args:
        logger: EMSNLogger instance voor logging
        config: Optionele MQTT config dict (default: uit emsn_secrets)
        client_id: Optionele client ID (default: auto-generated)
    """

    def __init__(
        self,
        logger=None,
        config: Optional[Dict[str, Any]] = None,
        client_id: Optional[str] = None
    ):
        self.logger = logger
        self.config = config or get_mqtt_config()
        self.client_id = client_id
        self.client: Optional[mqtt.Client] = None
        self.connected = False

    def _log(self, level: str, message: str):
        """Log via logger of print als fallback"""
        if self.logger:
            getattr(self.logger, level.lower(), self.logger.info)(message)
        else:
            print(f"[{level}] {message}")

    def connect(self) -> bool:
        """
        Maak verbinding met MQTT broker.

        Returns:
            True als verbinding succesvol, False anders
        """
        try:
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.client_id
            )

            # Set credentials
            username = self.config.get('username')
            password = self.config.get('password')
            if username and password:
                self.client.username_pw_set(username, password)

            # Connection callbacks
            def on_connect(client, userdata, flags, rc, properties=None):
                if rc == 0:
                    self.connected = True
                    self._log('INFO', f"MQTT connected to {self.config.get('broker')}")
                else:
                    self.connected = False
                    self._log('ERROR', f"MQTT connection failed: rc={rc}")

            def on_disconnect(client, userdata, flags, rc, properties=None):
                self.connected = False
                if rc != 0:
                    self._log('WARNING', f"MQTT unexpected disconnect: rc={rc}")

            self.client.on_connect = on_connect
            self.client.on_disconnect = on_disconnect

            # Connect
            broker = self.config.get('broker', HOSTS['mqtt_primary'])
            port = self.config.get('port', PORTS['mqtt'])

            self.client.connect(broker, port, keepalive=60)
            self.client.loop_start()

            # Wacht kort op verbinding
            time.sleep(0.5)
            return self.connected

        except Exception as e:
            self._log('ERROR', f"MQTT connect error: {e}")
            return False

    def disconnect(self):
        """Verbreek MQTT verbinding"""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
            self.client = None
            self.connected = False

    def ensure_connected(self) -> bool:
        """Zorg dat er een verbinding is, maak er een als nodig"""
        if not self.connected or not self.client:
            return self.connect()
        return True

    def publish(
        self,
        topic: str,
        payload: Union[Dict, str, bytes],
        qos: int = 1,
        retain: bool = False
    ) -> bool:
        """
        Publiceer een bericht naar MQTT topic.

        Args:
            topic: MQTT topic
            payload: Bericht (dict wordt automatisch naar JSON geconverteerd)
            qos: Quality of Service level (0, 1, of 2)
            retain: Of het bericht retained moet worden

        Returns:
            True als publicatie succesvol
        """
        if not self.ensure_connected():
            return False

        try:
            # Converteer dict naar JSON
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            elif isinstance(payload, bytes):
                pass  # Gebruik bytes direct
            else:
                payload = str(payload)

            result = self.client.publish(topic, payload, qos=qos, retain=retain)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self._log('DEBUG', f"Published to {topic}")
                return True
            else:
                self._log('WARNING', f"Publish failed: {topic} rc={result.rc}")
                return False

        except Exception as e:
            self._log('ERROR', f"Publish error: {e}")
            return False

    def publish_json(self, topic: str, data: Dict, **kwargs) -> bool:
        """Convenience method voor JSON publicatie"""
        return self.publish(topic, data, **kwargs)

    def publish_status(self, base_topic: str, status: str, details: Optional[Dict] = None):
        """
        Publiceer status update.

        Args:
            base_topic: Basis topic (bijv. 'emsn2/sync')
            status: Status string (bijv. 'running', 'completed', 'error')
            details: Optionele extra details
        """
        payload = {
            'status': status,
            'timestamp': datetime.now().isoformat(),
        }
        if details:
            payload.update(details)

        self.publish(f"{base_topic}/status", payload, retain=True)

    def __enter__(self):
        """Context manager support"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.disconnect()


class EMSNMQTTClient(MQTTPublisher):
    """
    Volledige MQTT client voor scripts die ook subscriben.

    Breidt MQTTPublisher uit met subscribe functionaliteit
    en message handling.

    Gebruik:
        client = EMSNMQTTClient(logger)

        @client.on_message('birdnet/+/detection')
        def handle_detection(topic, payload):
            print(f"Detection: {payload}")

        client.run_forever()
    """

    def __init__(self, logger=None, config: Optional[Dict] = None, client_id: Optional[str] = None):
        super().__init__(logger, config, client_id)
        self._message_handlers: Dict[str, List[Callable]] = {}
        self._subscriptions: List[tuple] = []

    def subscribe(
        self,
        topic: str,
        callback: Optional[Callable] = None,
        qos: int = 1
    ):
        """
        Subscribe op een MQTT topic.

        Args:
            topic: MQTT topic (wildcards + en # ondersteund)
            callback: Functie die aangeroepen wordt bij berichten
            qos: Quality of Service level
        """
        self._subscriptions.append((topic, qos))

        if callback:
            if topic not in self._message_handlers:
                self._message_handlers[topic] = []
            self._message_handlers[topic].append(callback)

    def on_message(self, topic: str):
        """
        Decorator voor message handlers.

        Gebruik:
            @client.on_message('birdnet/#')
            def handle(topic, payload):
                pass
        """
        def decorator(func: Callable):
            self.subscribe(topic, func)
            return func
        return decorator

    def connect(self) -> bool:
        """Connect en setup message handler"""
        if not super().connect():
            return False

        # Setup message callback
        def on_message(client, userdata, msg):
            self._handle_message(msg)

        self.client.on_message = on_message

        # Subscribe op alle topics
        for topic, qos in self._subscriptions:
            self.client.subscribe(topic, qos)
            self._log('INFO', f"Subscribed to {topic}")

        return True

    def _handle_message(self, msg):
        """Verwerk inkomend bericht"""
        topic = msg.topic
        try:
            # Probeer JSON te parsen
            payload = json.loads(msg.payload.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = msg.payload

        # Zoek matching handlers
        for pattern, handlers in self._message_handlers.items():
            if self._topic_matches(pattern, topic):
                for handler in handlers:
                    try:
                        handler(topic, payload)
                    except Exception as e:
                        self._log('ERROR', f"Handler error for {topic}: {e}")

    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """Check of topic matched met pattern (met wildcards)"""
        pattern_parts = pattern.split('/')
        topic_parts = topic.split('/')

        for i, p in enumerate(pattern_parts):
            if p == '#':
                return True  # # matcht alles vanaf hier
            if i >= len(topic_parts):
                return False
            if p != '+' and p != topic_parts[i]:
                return False

        return len(pattern_parts) == len(topic_parts)

    def run_forever(self):
        """Start de MQTT loop (blocking)"""
        if not self.ensure_connected():
            raise ConnectionError("Could not connect to MQTT broker")

        self._log('INFO', "Starting MQTT client loop")
        try:
            self.client.loop_forever()
        except KeyboardInterrupt:
            self._log('INFO', "MQTT client stopped by user")
        finally:
            self.disconnect()

    def run_in_background(self):
        """Start de MQTT loop in background (non-blocking)"""
        if not self.ensure_connected():
            raise ConnectionError("Could not connect to MQTT broker")

        self.client.loop_start()
        self._log('INFO', "MQTT client running in background")


# Convenience functies
def publish_once(topic: str, payload: Any, logger=None) -> bool:
    """
    Publiceer een enkel bericht en disconnect.

    Args:
        topic: MQTT topic
        payload: Bericht data
        logger: Optionele logger

    Returns:
        True als succesvol
    """
    with MQTTPublisher(logger) as pub:
        return pub.publish(topic, payload)


def get_mqtt_publisher(logger=None) -> MQTTPublisher:
    """
    Factory functie voor MQTTPublisher.

    Args:
        logger: Optionele logger

    Returns:
        Geconfigureerde MQTTPublisher instance
    """
    return MQTTPublisher(logger)


def get_mqtt_client(logger=None) -> EMSNMQTTClient:
    """
    Factory functie voor EMSNMQTTClient.

    Args:
        logger: Optionele logger

    Returns:
        Geconfigureerde EMSNMQTTClient instance
    """
    return EMSNMQTTClient(logger)
