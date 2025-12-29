#!/usr/bin/env python3
"""
AtmosBird Hardware Test Script
Test DHT22 sensor en PTC heater hardware setup.

Hardware Setup:
- DHT22 op GPIO4 (Pin 7) - temperatuur/luchtvochtigheid
- PTC Heater via IRLZ44N MOSFET op GPIO17 (Pin 11)

Aansluitingen:
- Pin 1 (3.3V) → DHT22 +
- Pin 2 (5V) → Heater via blauwe draad
- Pin 6 (GND) → DHT22 -
- Pin 7 (GPIO4) → DHT22 out (data)
- Pin 11 (GPIO17) → MOSFET Gate (heater aan/uit)
- Pin 14 (GND) → MOSFET Source

Auteur: EMSN Project
"""

import sys
import time
import math

# GPIO setup
DHT_PIN = 4      # GPIO4 voor DHT22 (D4 in board notation)
HEATER_PIN = 17  # GPIO17 voor heater MOSFET


def calculate_dewpoint(temp_c: float, humidity: float) -> float:
    """
    Bereken dauwpunt met Magnus formule.

    Args:
        temp_c: Temperatuur in Celsius
        humidity: Relatieve luchtvochtigheid in %

    Returns:
        Dauwpunt in Celsius
    """
    # Magnus constanten
    a = 17.27
    b = 237.7

    # Bereken gamma
    gamma = (a * temp_c / (b + temp_c)) + math.log(humidity / 100.0)

    # Bereken dauwpunt
    dewpoint = (b * gamma) / (a - gamma)

    return dewpoint


def test_dht22():
    """Test DHT22 sensor uitlezing met CircuitPython library."""
    print("\n" + "="*50)
    print("TEST 1: DHT22 Sensor")
    print("="*50)

    try:
        import board
        import adafruit_dht
    except ImportError as e:
        print(f"❌ CircuitPython DHT library niet geïnstalleerd!")
        print(f"   Error: {e}")
        print("   Installeer met: pip install adafruit-circuitpython-dht --break-system-packages")
        return False

    print(f"📡 DHT22 uitlezen op GPIO{DHT_PIN} (board.D4)...")

    # Maak DHT22 device object
    try:
        dht_device = adafruit_dht.DHT22(board.D4, use_pulseio=False)
    except Exception as e:
        print(f"❌ Kan DHT22 niet initialiseren: {e}")
        return False

    # Probeer 5 keer te lezen (DHT22 kan soms falen)
    for attempt in range(1, 6):
        try:
            temperature = dht_device.temperature
            humidity = dht_device.humidity

            if humidity is not None and temperature is not None:
                print(f"✅ DHT22 lezing succesvol (poging {attempt})")
                print(f"   🌡️  Temperatuur: {temperature:.1f}°C")
                print(f"   💧 Luchtvochtigheid: {humidity:.1f}%")

                # Bereken dauwpunt
                dewpoint = calculate_dewpoint(temperature, humidity)
                print(f"   🌫️  Dauwpunt: {dewpoint:.1f}°C")

                # Waarschuwingen
                if humidity > 80:
                    print(f"   ⚠️  Hoge luchtvochtigheid! Condensatie risico.")
                if temperature < dewpoint + 3:
                    print(f"   ⚠️  Temperatuur dicht bij dauwpunt! Condensatie risico.")

                dht_device.exit()
                return True
            else:
                print(f"   ⏳ Poging {attempt}: geen data, opnieuw proberen...")

        except RuntimeError as e:
            # DHT22 geeft soms RuntimeError bij leesproblemen
            print(f"   ⏳ Poging {attempt}: {e}")

        except Exception as e:
            print(f"   ⏳ Poging {attempt}: onverwachte fout: {e}")

        time.sleep(2)

    print("❌ DHT22 lezing mislukt na 5 pogingen!")
    print("   Controleer bedrading:")
    print("   - Pin 1 (3.3V) → DHT22 +")
    print("   - Pin 6 (GND) → DHT22 -")
    print("   - Pin 7 (GPIO4) → DHT22 data")
    try:
        dht_device.exit()
    except:
        pass
    return False


def test_heater():
    """Test PTC heater via MOSFET."""
    print("\n" + "="*50)
    print("TEST 2: PTC Heater (5 seconden)")
    print("="*50)

    try:
        import RPi.GPIO as GPIO
    except ImportError:
        print("❌ RPi.GPIO library niet geïnstalleerd!")
        print("   Installeer met: pip install RPi.GPIO")
        return False

    try:
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(HEATER_PIN, GPIO.OUT)

        print(f"🔌 MOSFET Gate op GPIO{HEATER_PIN}")
        print("   Heater gaat nu AAN voor 5 seconden...")
        print("   👆 Voel of de heater warm wordt!")

        # Heater AAN
        GPIO.output(HEATER_PIN, GPIO.HIGH)
        print("   🔥 Heater: AAN")

        # Countdown
        for i in range(5, 0, -1):
            print(f"   ⏱️  {i} seconden...")
            time.sleep(1)

        # Heater UIT
        GPIO.output(HEATER_PIN, GPIO.LOW)
        print("   ❄️  Heater: UIT")

        print("✅ Heater test compleet!")
        print("   Was de heater warm? Dan werkt alles!")

        return True

    except Exception as e:
        print(f"❌ Heater test mislukt: {e}")
        return False
    finally:
        GPIO.cleanup(HEATER_PIN)


def main():
    """Voer alle hardware tests uit."""
    print("\n" + "#"*50)
    print("# AtmosBird Hardware Test")
    print("# Anti-Condens Systeem")
    print("#"*50)

    results = {}

    # Test DHT22
    results['dht22'] = test_dht22()

    # Test Heater
    results['heater'] = test_heater()

    # Samenvatting
    print("\n" + "="*50)
    print("SAMENVATTING")
    print("="*50)

    all_passed = True
    for test, passed in results.items():
        status = "✅ OK" if passed else "❌ MISLUKT"
        print(f"   {test.upper()}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 Alle tests geslaagd!")
        print("   Hardware is klaar voor climate_control.py")
        return 0
    else:
        print("\n⚠️  Sommige tests mislukt!")
        print("   Controleer de bedrading en probeer opnieuw.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
