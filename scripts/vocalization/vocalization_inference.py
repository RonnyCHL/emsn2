#!/usr/bin/env python3
"""
EMSN 2.0 - Vocalization Inference Service

Luistert naar BirdNET MQTT detecties en classificeert vocalisatie types
(song/call/alarm) met de getrainde CNN modellen.

Werkt NAAST BirdNET-Pi, raakt geen BirdNET bestanden aan.
"""

import os
import sys
import json
import time
import logging
import re
from pathlib import Path
from datetime import datetime

import numpy as np
import librosa
import torch
import torch.nn as nn
import paho.mqtt.client as mqtt


# ============================================================
# CNN Model (zelfde architectuur als Colab training)
# ============================================================

class ColabVocalizationCNN(nn.Module):
    """CNN model zoals getraind in Google Colab."""

    def __init__(self, input_shape=(128, 128), num_classes=3):
        super().__init__()

        self.features = nn.Sequential(
            # Conv block 1
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Dropout2d(0.25),

            # Conv block 2
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Dropout2d(0.25),

            # Conv block 3
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Dropout2d(0.25),
        )

        # Bereken flatten size
        h, w = input_shape[0] // 8, input_shape[1] // 8
        flatten_size = 128 * h * w

        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(flatten_size, 256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, num_classes)
        )

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return x


class ColabModelLoader:
    """Laad en gebruik Colab-getrainde modellen."""

    def __init__(self, model_path: str):
        self.device = torch.device('cpu')
        self.model = None
        self.num_classes = 3
        self.class_names = ['song', 'call', 'alarm']  # Default volgorde

        self._load(model_path)

    def _load(self, model_path: str):
        """Laad model van .pt bestand."""
        checkpoint = torch.load(model_path, map_location=self.device)

        self.num_classes = checkpoint.get('num_classes', 3)

        # Maak model met juiste input shape
        self.model = ColabVocalizationCNN(
            input_shape=(128, 128),
            num_classes=self.num_classes
        )
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.to(self.device)
        self.model.eval()

    def predict(self, spectrogram: np.ndarray) -> tuple[str, float, dict]:
        """
        Voorspel vocalisatie type.

        Args:
            spectrogram: Mel-spectrogram (128, time_frames)

        Returns:
            (predicted_class, confidence, all_probabilities)
        """
        # Resize naar 128x128 als nodig
        if spectrogram.shape != (128, 128):
            from skimage.transform import resize
            spectrogram = resize(spectrogram, (128, 128), anti_aliasing=True)

        # Naar tensor: (1, 1, 128, 128)
        x = torch.FloatTensor(spectrogram).unsqueeze(0).unsqueeze(0)
        x = x.to(self.device)

        with torch.no_grad():
            outputs = self.model(x)
            probas = torch.softmax(outputs, dim=1)[0]

        # Resultaten
        class_idx = probas.argmax().item()
        confidence = probas[class_idx].item()

        proba_dict = {
            self.class_names[i]: probas[i].item()
            for i in range(min(len(self.class_names), len(probas)))
        }

        return self.class_names[class_idx], confidence, proba_dict


# ============================================================
# Configuration
# ============================================================

MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.1.178")
MQTT_PORT = 1883
MQTT_USER = os.getenv("MQTT_USER", "ecomonitor")
MQTT_PASS = os.getenv("MQTT_PASS", "IwnadBon2iN")

# Model directory op NAS
MODELS_DIR = Path("/mnt/nas-docker/emsn-vocalization/data/models")

# BirdNET audio directory (we lezen alleen, passen niks aan!)
BIRDNET_AUDIO_DIR = Path("/home/ronny/BirdNET-Pi/BirdSongs")

# Topics
TOPIC_SUBSCRIBE = "birdnet/+/detection"
TOPIC_PUBLISH = "emsn2/vocalization"

# Spectrogram parameters (zelfde als training)
SAMPLE_RATE = 48000
N_MELS = 128
N_FFT = 2048
HOP_LENGTH = 512
FMIN = 500
FMAX = 8000
SEGMENT_DURATION = 3.0  # seconden

# Minimum confidence voor classificatie
MIN_CONFIDENCE = 0.5

# Logging
LOG_DIR = Path("/mnt/usb/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "vocalization_inference.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================
# Inference Service
# ============================================================

class VocalizationInferenceService:
    """Service die BirdNET detecties classificeert naar vocalisatie type."""

    def __init__(self):
        self.client = None
        self.connected = False
        self.models_cache = {}  # Cache geladen modellen
        self.available_models = self._scan_models()

    def _scan_models(self) -> dict:
        """Scan beschikbare modellen en maak mapping naar soortsnamen."""
        models = {}

        if not MODELS_DIR.exists():
            logger.warning(f"Models directory niet gevonden: {MODELS_DIR}")
            return models

        for model_file in MODELS_DIR.glob("*.pt"):
            # Parse bestandsnaam: merel_cnn_2025.pt of merel_cnn_2025Q4.pt -> merel
            name = model_file.stem
            # Verwijder _cnn_YYYY of _cnn_YYYYQN suffix
            species_name = re.sub(r'_cnn_\d{4}(Q\d)?$', '', name)
            species_name = species_name.replace('_', ' ').title()

            models[species_name.lower()] = model_file

        logger.info(f"Gevonden modellen: {len(models)}")
        return models

    def _normalize_species_name(self, name: str) -> str:
        """Normaliseer soortnaam voor model lookup."""
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    def _find_model(self, species_name: str) -> Path | None:
        """Vind het model voor een soort."""
        normalized = self._normalize_species_name(species_name)

        # Directe match
        if normalized in self.available_models:
            return self.available_models[normalized]

        # Probeer woord voor woord
        for key in self.available_models:
            if key in normalized or normalized in key:
                return self.available_models[key]

        return None

    def _load_model(self, model_path: Path) -> ColabModelLoader | None:
        """Laad model (met caching)."""
        path_str = str(model_path)

        if path_str in self.models_cache:
            return self.models_cache[path_str]

        try:
            logger.info(f"Laden model: {model_path.name}")
            loader = ColabModelLoader(path_str)
            self.models_cache[path_str] = loader
            return loader
        except Exception as e:
            logger.error(f"Fout bij laden model {model_path}: {e}")
            return None

    def _audio_to_spectrogram(self, audio_path: Path) -> np.ndarray | None:
        """Converteer audio naar mel-spectrogram."""
        try:
            # Laad audio
            audio, sr = librosa.load(str(audio_path), sr=SAMPLE_RATE, mono=True)

            # Neem eerste segment (of pad als te kort)
            segment_samples = int(SEGMENT_DURATION * SAMPLE_RATE)

            if len(audio) < segment_samples:
                padded = np.zeros(segment_samples)
                padded[:len(audio)] = audio
                audio = padded
            else:
                audio = audio[:segment_samples]

            # Bereken mel spectrogram
            mel_spec = librosa.feature.melspectrogram(
                y=audio,
                sr=SAMPLE_RATE,
                n_mels=N_MELS,
                n_fft=N_FFT,
                hop_length=HOP_LENGTH,
                fmin=FMIN,
                fmax=FMAX
            )

            # Convert naar dB en normaliseer
            mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
            mel_spec_norm = (mel_spec_db - mel_spec_db.min()) / (mel_spec_db.max() - mel_spec_db.min() + 1e-8)

            return mel_spec_norm

        except Exception as e:
            logger.error(f"Fout bij audio verwerking {audio_path}: {e}")
            return None

    def _find_audio_file(self, file_name: str) -> Path | None:
        """Vind het audio bestand in BirdNET directories."""
        # Probeer directe path
        direct_path = BIRDNET_AUDIO_DIR / file_name
        if direct_path.exists():
            return direct_path

        # Probeer als absoluut pad
        abs_path = Path(file_name)
        if abs_path.exists():
            return abs_path

        # Zoek in subdirectories
        for path in BIRDNET_AUDIO_DIR.rglob(Path(file_name).name):
            return path

        return None

    def classify_detection(self, detection: dict) -> dict | None:
        """
        Classificeer een BirdNET detectie.

        Returns:
            Dict met vocalization_type en confidence, of None
        """
        species = detection.get('species', '')
        file_name = detection.get('file', '')

        if not species or not file_name:
            return None

        # Vind model voor deze soort
        model_path = self._find_model(species)
        if not model_path:
            logger.debug(f"Geen model voor {species}")
            return None

        # Vind audio bestand
        audio_path = self._find_audio_file(file_name)
        if not audio_path:
            logger.warning(f"Audio niet gevonden: {file_name}")
            return None

        # Laad model
        loader = self._load_model(model_path)
        if not loader:
            return None

        # Maak spectrogram
        spectrogram = self._audio_to_spectrogram(audio_path)
        if spectrogram is None:
            return None

        # Classificeer
        try:
            voc_type, confidence, probas = loader.predict(spectrogram)

            return {
                'vocalization_type': voc_type,
                'vocalization_confidence': confidence,
                'model_used': model_path.name,
                'probabilities': probas
            }

        except Exception as e:
            logger.error(f"Classificatie fout: {e}")
            return None

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """MQTT connect callback."""
        if rc == 0:
            logger.info(f"Verbonden met MQTT broker {MQTT_BROKER}")
            self.connected = True
            client.subscribe(TOPIC_SUBSCRIBE)
            logger.info(f"Subscribed op: {TOPIC_SUBSCRIBE}")
        else:
            logger.error(f"MQTT verbinding mislukt: {rc}")
            self.connected = False

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """MQTT disconnect callback."""
        logger.warning("Verbinding met MQTT broker verbroken")
        self.connected = False

    def _on_message(self, client, userdata, msg):
        """MQTT message callback - verwerk BirdNET detectie."""
        try:
            detection = json.loads(msg.payload.decode())
            station = msg.topic.split('/')[1]

            species = detection.get('species', 'Unknown')
            confidence = detection.get('confidence', 0)

            logger.info(f"Detectie ontvangen: {species} ({confidence:.2f}) van {station}")

            # Classificeer vocalisatie
            result = self.classify_detection(detection)

            if result and result['vocalization_confidence'] >= MIN_CONFIDENCE:
                # Publiceer resultaat
                output = {
                    'timestamp': datetime.now().isoformat(),
                    'station': station,
                    'species': species,
                    'scientific_name': detection.get('scientific_name', ''),
                    'birdnet_confidence': confidence,
                    **result
                }

                topic = f"{TOPIC_PUBLISH}/{station}/{species.lower().replace(' ', '_')}"
                client.publish(topic, json.dumps(output), qos=1)

                logger.info(
                    f"Vocalisatie: {species} = {result['vocalization_type']} "
                    f"({result['vocalization_confidence']:.2%})"
                )
            else:
                if result:
                    logger.debug(f"Confidence te laag: {result['vocalization_confidence']:.2%}")

        except json.JSONDecodeError:
            logger.error(f"Ongeldige JSON: {msg.payload}")
        except Exception as e:
            logger.error(f"Fout bij verwerken bericht: {e}")

    def connect(self) -> bool:
        """Verbind met MQTT broker."""
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self.client.username_pw_set(MQTT_USER, MQTT_PASS)

            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()

            time.sleep(1)
            return self.connected

        except Exception as e:
            logger.error(f"MQTT verbinding mislukt: {e}")
            return False

    def run(self):
        """Start de service."""
        logger.info("=" * 60)
        logger.info("EMSN 2.0 - Vocalization Inference Service")
        logger.info("=" * 60)
        logger.info(f"Models directory: {MODELS_DIR}")
        logger.info(f"Beschikbare modellen: {len(self.available_models)}")
        logger.info(f"MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
        logger.info("=" * 60)

        if not self.available_models:
            logger.error("Geen modellen gevonden!")
            return

        if not self.connect():
            logger.error("Kon niet verbinden met MQTT broker")
            return

        logger.info("Service gestart, wachten op detecties...")

        try:
            while True:
                if not self.connected:
                    logger.warning("Opnieuw verbinden...")
                    self.connect()
                    time.sleep(5)
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Service gestopt")
        finally:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()


def test_single_file(audio_path: str, species: str):
    """Test classificatie op een enkel bestand."""
    print(f"\nTest: {species} - {audio_path}")
    print("=" * 50)

    service = VocalizationInferenceService()

    detection = {
        'species': species,
        'file': audio_path,
        'confidence': 0.9
    }

    start = time.time()
    result = service.classify_detection(detection)
    elapsed = time.time() - start

    if result:
        print(f"\nResultaat voor {species}:")
        print(f"  Type: {result['vocalization_type']}")
        print(f"  Confidence: {result['vocalization_confidence']:.1%}")
        print(f"  Model: {result['model_used']}")
        print(f"  Tijd: {elapsed*1000:.0f}ms")
        print(f"\n  Probabiliteiten:")
        for cls, prob in result['probabilities'].items():
            bar = "█" * int(prob * 20)
            print(f"    {cls:6s}: {bar} {prob:.1%}")
    else:
        print(f"Kon {species} niet classificeren")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='EMSN Vocalization Inference')
    parser.add_argument('--test', metavar='AUDIO_FILE', help='Test met enkel bestand')
    parser.add_argument('--species', default='Merel', help='Soortnaam voor test')

    args = parser.parse_args()

    if args.test:
        test_single_file(args.test, args.species)
    else:
        service = VocalizationInferenceService()
        service.run()
