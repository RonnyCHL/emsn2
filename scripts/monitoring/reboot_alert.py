#!/usr/bin/env python3
"""
EMSN Reboot Alert Service

Detecteert reboots en stuurt alerts via MQTT en optioneel email.
Draait eenmalig bij elke boot via systemd.

Analyseert:
- Shutdown type (clean vs unexpected)
- Laatste kernel messages voor crash info
- Uptime history

Ronny Hullegie - EMSN 2.0
Modernized: 2026-01-09 - Type hints, proper exception handling
"""

import os
import sys
import json
import subprocess
import socket
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Add core modules path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import paho.mqtt.client as mqtt
    from core.config import get_mqtt_config
except ImportError as e:
    print(f"Import error: {e}")
    mqtt = None

# Configuratie
STATION_NAME = socket.gethostname()
STATE_FILE = Path("/var/lib/emsn/reboot_state.json")
LOG_FILE = Path("/mnt/usb/logs/reboot_alert.log")

# MQTT Topics
MQTT_TOPIC_REBOOT = f"emsn2/{STATION_NAME.replace('emsn2-', '')}/reboot"
MQTT_TOPIC_ALERT = "emsn2/alerts"


def log(message: str):
    """Log naar file en stdout"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"Log write error: {e}")


def get_boot_info() -> Dict[str, Any]:
    """Verzamel boot informatie."""
    info: Dict[str, Any] = {
        "hostname": STATION_NAME,
        "boot_time": datetime.now().isoformat(),
        "boot_id": None,
        "previous_boot_id": None,
        "shutdown_type": "unknown",
        "kernel_panic": False,
        "oom_killer": False,
        "watchdog_reset": False,
        "power_loss": False,
        "uptime_seconds": 0
    }

    # Huidige boot ID
    try:
        result = subprocess.run(
            ["journalctl", "--list-boots", "-o", "json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            boots = json.loads(result.stdout)
            if boots:
                info["boot_id"] = boots[-1].get("boot_id")
                if len(boots) > 1:
                    info["previous_boot_id"] = boots[-2].get("boot_id")
    except Exception as e:
        log(f"Boot ID error: {e}")

    # Check kernel messages voor crash indicaties
    try:
        result = subprocess.run(
            ["dmesg"], capture_output=True, text=True, timeout=10
        )
        dmesg = result.stdout.lower()

        if "kernel panic" in dmesg or "oops" in dmesg:
            info["kernel_panic"] = True
            info["shutdown_type"] = "crash"

        if "out of memory" in dmesg or "oom" in dmesg:
            info["oom_killer"] = True
            info["shutdown_type"] = "oom"

        if "watchdog" in dmesg and ("reset" in dmesg or "timeout" in dmesg):
            info["watchdog_reset"] = True
            info["shutdown_type"] = "watchdog"

    except Exception as e:
        log(f"dmesg error: {e}")

    # Check vorige boot logs voor shutdown reden
    if info["previous_boot_id"]:
        try:
            result = subprocess.run(
                ["journalctl", f"_BOOT_ID={info['previous_boot_id']}",
                 "-p", "warning", "-n", "50", "--no-pager"],
                capture_output=True, text=True, timeout=10
            )
            prev_logs = result.stdout.lower()

            # Check voor clean shutdown
            if "shutting down" in prev_logs or "system halt" in prev_logs:
                if info["shutdown_type"] == "unknown":
                    info["shutdown_type"] = "clean"

            # Check voor power issues
            if "voltage" in prev_logs or "under-voltage" in prev_logs:
                info["power_loss"] = True
                if info["shutdown_type"] == "unknown":
                    info["shutdown_type"] = "power"

        except Exception as e:
            log(f"Previous boot log error: {e}")

    # Uptime
    try:
        with open("/proc/uptime") as f:
            info["uptime_seconds"] = int(float(f.read().split()[0]))
    except (IOError, ValueError, OSError) as e:
        log(f"Uptime read error: {e}")

    return info


def load_previous_state() -> Dict[str, Any]:
    """Laad vorige shutdown state."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError, OSError) as e:
            log(f"State load error: {e}")
    return {}


def save_current_state(info: Dict[str, Any]) -> None:
    """Sla huidige state op voor volgende boot."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "last_boot": info["boot_time"],
            "boot_id": info["boot_id"],
            "hostname": info["hostname"]
        }
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log(f"State save error: {e}")


def determine_reboot_reason(info: Dict[str, Any], prev_state: Dict[str, Any]) -> str:
    """Bepaal de meest waarschijnlijke reboot reden."""

    if info["kernel_panic"]:
        return "Kernel panic/crash gedetecteerd"

    if info["oom_killer"]:
        return "Out-of-Memory killer actief geweest"

    if info["watchdog_reset"]:
        return "Hardware watchdog timeout (systeem vastgelopen)"

    if info["power_loss"]:
        return "Mogelijke stroomonderbreking of undervoltage"

    if info["shutdown_type"] == "clean":
        return "Normale shutdown/reboot"

    if not prev_state:
        return "Eerste boot na installatie monitoring"

    return "Onverwachte reboot (reden onbekend)"


def send_mqtt_alert(info: Dict[str, Any], reason: str) -> bool:
    """Stuur reboot alert via MQTT."""
    if mqtt is None:
        log("MQTT library niet beschikbaar")
        return False

    try:
        mqtt_config = get_mqtt_config()
        # Config gebruikt 'broker' ipv 'host'
        broker = mqtt_config.get("broker") or mqtt_config.get("host", "localhost")
        port = mqtt_config.get("port", 1883)

        client = mqtt.Client(client_id=f"reboot-alert-{STATION_NAME}")

        if mqtt_config.get("username"):
            client.username_pw_set(
                mqtt_config["username"],
                mqtt_config["password"]
            )

        client.connect(broker, port, 60)

        # Reboot info bericht
        reboot_msg: Dict[str, Any] = {
            "timestamp": info["boot_time"],
            "hostname": info["hostname"],
            "reason": reason,
            "shutdown_type": info["shutdown_type"],
            "details": {
                "kernel_panic": info["kernel_panic"],
                "oom_killer": info["oom_killer"],
                "watchdog_reset": info["watchdog_reset"],
                "power_loss": info["power_loss"]
            }
        }

        client.publish(
            MQTT_TOPIC_REBOOT,
            json.dumps(reboot_msg),
            qos=1,
            retain=True
        )

        # Alert bericht (alleen bij onverwachte reboot)
        if info["shutdown_type"] not in ["clean"]:
            alert_msg: Dict[str, Any] = {
                "timestamp": info["boot_time"],
                "source": info["hostname"],
                "level": "warning" if info["shutdown_type"] == "unknown" else "critical",
                "type": "reboot",
                "message": f"🔄 {info['hostname']}: {reason}"
            }

            client.publish(
                MQTT_TOPIC_ALERT,
                json.dumps(alert_msg),
                qos=1
            )

        client.disconnect()
        log(f"MQTT alert verzonden naar {broker}")
        return True

    except (ConnectionError, OSError, ValueError) as e:
        import traceback
        log(f"MQTT error: {e}")
        log(f"Traceback: {traceback.format_exc()}")
        return False


def main() -> None:
    """Main entry point voor reboot alert service."""
    log("=" * 50)
    log(f"Reboot Alert Service gestart op {STATION_NAME}")

    # Verzamel informatie
    boot_info = get_boot_info()
    prev_state = load_previous_state()
    reason = determine_reboot_reason(boot_info, prev_state)

    log(f"Boot time: {boot_info['boot_time']}")
    log(f"Shutdown type: {boot_info['shutdown_type']}")
    log(f"Reden: {reason}")

    # Details loggen
    if boot_info["kernel_panic"]:
        log("⚠️  Kernel panic gedetecteerd!")
    if boot_info["oom_killer"]:
        log("⚠️  OOM killer was actief!")
    if boot_info["watchdog_reset"]:
        log("⚠️  Watchdog reset gedetecteerd!")
    if boot_info["power_loss"]:
        log("⚠️  Mogelijke power loss!")

    # MQTT alert sturen
    send_mqtt_alert(boot_info, reason)

    # State opslaan
    save_current_state(boot_info)

    log("Reboot Alert Service voltooid")
    log("=" * 50)


if __name__ == "__main__":
    main()
