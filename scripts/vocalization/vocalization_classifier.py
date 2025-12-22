#!/usr/bin/env python3
"""
EMSN 2.0 - Vocalization Classifier

Lichtgewicht classifier voor integratie met Ulanzi bridge.
Classificeert audio naar song/call/alarm.
"""

import re
import logging
from pathlib import Path

import numpy as np

# Lazy imports voor snellere startup
_torch = None
_librosa = None


def get_torch():
    """Lazy load torch."""
    global _torch
    if _torch is None:
        import torch
        _torch = torch
    return _torch


def get_librosa():
    """Lazy load librosa."""
    global _librosa
    if _librosa is None:
        import librosa
        _librosa = librosa
    return _librosa


# Configuration
MODELS_DIR = Path("/mnt/nas-docker/emsn-vocalization/data/models")
SAMPLE_RATE = 48000
N_MELS = 128
N_FFT = 2048
HOP_LENGTH = 512
FMIN = 500
FMAX = 8000
SEGMENT_DURATION = 3.0

# Vertaling naar Nederlands
VOC_TYPE_NL = {
    'song': 'zang',
    'call': 'roep',
    'alarm': 'alarm'
}

logger = logging.getLogger(__name__)


class ColabVocalizationCNN:
    """CNN model zoals getraind in Google Colab."""

    def __init__(self, input_shape=(128, 128), num_classes=3):
        torch = get_torch()
        nn = torch.nn

        self.features = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Dropout2d(0.25),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Dropout2d(0.25),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Dropout2d(0.25),
        )

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

    def __call__(self, x):
        return self.forward(x)


class VocalizationClassifier:
    """
    Classifier voor vocalisatie types (song/call/alarm).

    Gebruiksvoorbeeld:
        classifier = VocalizationClassifier()
        result = classifier.classify("Merel", "/path/to/audio.wav")
        if result:
            print(f"{result['type_nl']} ({result['confidence']:.0%})")
    """

    def __init__(self, models_dir: Path = MODELS_DIR):
        self.models_dir = Path(models_dir)
        self.models_cache = {}
        self.available_models = {}
        self._initialized = False

    def _init_lazy(self):
        """Lazy initialization - alleen laden als nodig."""
        if self._initialized:
            return
        self._scan_models()
        self._initialized = True

    def _scan_models(self):
        """Scan beschikbare modellen."""
        if not self.models_dir.exists():
            logger.warning(f"Models directory niet gevonden: {self.models_dir}")
            return

        for model_file in self.models_dir.glob("*.pt"):
            name = model_file.stem
            species_name = re.sub(r'_cnn_\d{4}(Q\d)?$', '', name)
            species_name = species_name.replace('_', ' ').title()
            self.available_models[species_name.lower()] = model_file

        logger.info(f"Vocalization classifier: {len(self.available_models)} modellen")

    def _normalize_name(self, name: str) -> str:
        """Normaliseer soortnaam."""
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    def _find_model(self, species_name: str) -> Path | None:
        """Vind model voor soort."""
        self._init_lazy()
        normalized = self._normalize_name(species_name)

        if normalized in self.available_models:
            return self.available_models[normalized]

        for key in self.available_models:
            if key in normalized or normalized in key:
                return self.available_models[key]

        return None

    def _load_model(self, model_path: Path):
        """Laad model met caching."""
        path_str = str(model_path)

        if path_str in self.models_cache:
            return self.models_cache[path_str]

        try:
            torch = get_torch()
            checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)

            num_classes = checkpoint.get('num_classes', 3)
            model = ColabVocalizationCNN(input_shape=(128, 128), num_classes=num_classes)

            # Load state dict - handle both nn.Module and regular class
            if hasattr(model.features, 'load_state_dict'):
                # It's an nn.Module
                pass
            else:
                # Rebuild as proper nn.Module
                torch = get_torch()
                nn = torch.nn

                class CNN(nn.Module):
                    def __init__(self, num_classes=3):
                        super().__init__()
                        self.features = nn.Sequential(
                            nn.Conv2d(1, 32, kernel_size=3, padding=1),
                            nn.BatchNorm2d(32),
                            nn.ReLU(),
                            nn.MaxPool2d(2),
                            nn.Dropout2d(0.25),
                            nn.Conv2d(32, 64, kernel_size=3, padding=1),
                            nn.BatchNorm2d(64),
                            nn.ReLU(),
                            nn.MaxPool2d(2),
                            nn.Dropout2d(0.25),
                            nn.Conv2d(64, 128, kernel_size=3, padding=1),
                            nn.BatchNorm2d(128),
                            nn.ReLU(),
                            nn.MaxPool2d(2),
                            nn.Dropout2d(0.25),
                        )
                        h, w = 128 // 8, 128 // 8
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

                model = CNN(num_classes)

            model.load_state_dict(checkpoint['model_state_dict'])
            model.eval()

            self.models_cache[path_str] = model
            return model

        except Exception as e:
            logger.error(f"Fout bij laden model {model_path}: {e}")
            return None

    def _audio_to_spectrogram(self, audio_path: Path) -> np.ndarray | None:
        """Converteer audio naar spectrogram."""
        try:
            librosa = get_librosa()
            audio, sr = librosa.load(str(audio_path), sr=SAMPLE_RATE, mono=True)

            segment_samples = int(SEGMENT_DURATION * SAMPLE_RATE)
            if len(audio) < segment_samples:
                padded = np.zeros(segment_samples)
                padded[:len(audio)] = audio
                audio = padded
            else:
                audio = audio[:segment_samples]

            mel_spec = librosa.feature.melspectrogram(
                y=audio, sr=SAMPLE_RATE, n_mels=N_MELS,
                n_fft=N_FFT, hop_length=HOP_LENGTH,
                fmin=FMIN, fmax=FMAX
            )

            mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
            mel_spec_norm = (mel_spec_db - mel_spec_db.min()) / (mel_spec_db.max() - mel_spec_db.min() + 1e-8)

            return mel_spec_norm

        except Exception as e:
            logger.error(f"Audio verwerking fout: {e}")
            return None

    def has_model(self, species_name: str) -> bool:
        """Check of er een model is voor deze soort."""
        self._init_lazy()
        return self._find_model(species_name) is not None

    def classify(self, species_name: str, audio_path: str | Path) -> dict | None:
        """
        Classificeer vocalisatie type.

        Args:
            species_name: Nederlandse soortnaam (bijv. "Merel")
            audio_path: Pad naar audiobestand

        Returns:
            Dict met type, type_nl, confidence, of None als niet mogelijk
        """
        model_path = self._find_model(species_name)
        if not model_path:
            return None

        audio_path = Path(audio_path)
        if not audio_path.exists():
            return None

        model = self._load_model(model_path)
        if model is None:
            return None

        spectrogram = self._audio_to_spectrogram(audio_path)
        if spectrogram is None:
            return None

        try:
            torch = get_torch()

            # Resize naar 128x128
            if spectrogram.shape != (128, 128):
                from skimage.transform import resize
                spectrogram = resize(spectrogram, (128, 128), anti_aliasing=True)

            # Naar tensor
            x = torch.FloatTensor(spectrogram).unsqueeze(0).unsqueeze(0)

            with torch.no_grad():
                outputs = model(x)
                probas = torch.softmax(outputs, dim=1)[0]

            class_names = ['song', 'call', 'alarm']
            class_idx = probas.argmax().item()
            confidence = probas[class_idx].item()
            voc_type = class_names[class_idx]

            return {
                'type': voc_type,
                'type_nl': VOC_TYPE_NL.get(voc_type, voc_type),
                'confidence': confidence,
                'model': model_path.name,
                'probabilities': {
                    name: probas[i].item()
                    for i, name in enumerate(class_names)
                }
            }

        except Exception as e:
            logger.error(f"Classificatie fout: {e}")
            return None


# Singleton instance voor hergebruik
_classifier_instance = None


def get_classifier() -> VocalizationClassifier:
    """Get singleton classifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = VocalizationClassifier()
    return _classifier_instance


def classify_vocalization(species_name: str, audio_path: str | Path) -> dict | None:
    """
    Convenience functie voor snelle classificatie.

    Args:
        species_name: Nederlandse soortnaam
        audio_path: Pad naar audiobestand

    Returns:
        Dict met type_nl en confidence, of None
    """
    return get_classifier().classify(species_name, audio_path)
