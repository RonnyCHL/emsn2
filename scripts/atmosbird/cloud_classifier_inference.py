#!/usr/bin/env python3
"""
Cloud Classifier Inference voor Raspberry Pi
Gebruik het getrainde ONNX model voor bewolkingsdetectie.

Dit script vervangt de eenvoudige OpenCV-gebaseerde bewolkingsdetectie
met een getraind CNN model voor nauwkeurigere resultaten.

Installatie:
    pip install onnxruntime pillow numpy

Gebruik:
    from cloud_classifier_inference import CloudClassifierONNX

    classifier = CloudClassifierONNX('/path/to/cloud_classifier.onnx')
    result = classifier.predict('/path/to/sky_image.jpg')
    print(f"Bewolking: {result['cloud_coverage_percent']:.1f}%")

Model training:
    Zie notebooks/EMSN_Cloud_Classifier_Colab.ipynb in de emsn-vocalization repo.
"""

import sys
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Dict, Union, Optional

# Import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.logging import get_logger

# Probeer onnxruntime te importeren
try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    ort = None

# Centrale logger
logger = get_logger('cloud_classifier_inference')


class CloudClassifierONNX:
    """ONNX-based cloud classifier voor Raspberry Pi."""

    CLASS_NAMES = ['helder', 'gedeeltelijk', 'bewolkt']
    IMAGE_SIZE = 224

    # ImageNet normalization
    MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __init__(self, model_path: Union[str, Path]):
        """
        Laad ONNX model.

        Args:
            model_path: Pad naar het ONNX model bestand

        Raises:
            ImportError: Als onnxruntime niet geïnstalleerd is
            FileNotFoundError: Als het model bestand niet bestaat
        """
        if not ONNX_AVAILABLE:
            raise ImportError(
                "onnxruntime is niet geïnstalleerd. "
                "Installeer met: pip install onnxruntime"
            )

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model niet gevonden: {self.model_path}")

        # Laad ONNX model met CPU provider (Pi heeft geen CUDA)
        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=['CPUExecutionProvider']
        )
        self.input_name = self.session.get_inputs()[0].name

        logger.info(f"Cloud classifier geladen: {self.model_path}")

    def preprocess(self, image_path: Union[str, Path]) -> np.ndarray:
        """
        Preprocess beeld voor model input.

        Args:
            image_path: Pad naar het beeld

        Returns:
            Numpy array met shape [1, 3, 224, 224]
        """
        # Laad en resize
        img = Image.open(image_path).convert('RGB')
        img = img.resize((self.IMAGE_SIZE, self.IMAGE_SIZE), Image.BILINEAR)

        # Naar numpy array [H, W, C] -> [C, H, W]
        img_array = np.array(img, dtype=np.float32) / 255.0
        img_array = (img_array - self.MEAN) / self.STD
        img_array = np.transpose(img_array, (2, 0, 1))  # HWC -> CHW

        # Voeg batch dimensie toe [1, C, H, W]
        return np.expand_dims(img_array, 0)

    def predict(self, image_path: Union[str, Path]) -> Dict:
        """
        Voorspel bewolkingsklasse en percentage.

        Args:
            image_path: Pad naar het hemelbeeld

        Returns:
            dict met:
                - class_name: voorspelde klasse ('helder', 'gedeeltelijk', 'bewolkt')
                - class_index: klasse index (0-2)
                - probabilities: dict met kans per klasse
                - cloud_coverage_percent: geschat bewolkingspercentage (0-100)
                - confidence: hoogste waarschijnlijkheid
        """
        # Preprocess
        input_tensor = self.preprocess(image_path)

        # Inference
        outputs = self.session.run(None, {self.input_name: input_tensor})
        logits = outputs[0][0]  # [num_classes]

        # Softmax (numeriek stabiel)
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / exp_logits.sum()

        # Resultaat
        class_idx = int(np.argmax(probs))

        # Bereken bewolkingspercentage (gewogen som)
        # helder=0%, gedeeltelijk=50%, bewolkt=100%
        weights = np.array([0.0, 50.0, 100.0])
        cloud_coverage = float(np.sum(probs * weights))

        return {
            'class_name': self.CLASS_NAMES[class_idx],
            'class_index': class_idx,
            'probabilities': {
                name: float(prob) for name, prob in zip(self.CLASS_NAMES, probs)
            },
            'cloud_coverage_percent': cloud_coverage,
            'confidence': float(probs[class_idx])
        }


# Singleton instance voor hergebruik
_classifier_instance: Optional[CloudClassifierONNX] = None


def get_classifier(model_path: Optional[Union[str, Path]] = None) -> Optional[CloudClassifierONNX]:
    """
    Get or create classifier singleton.

    Args:
        model_path: Pad naar ONNX model (alleen nodig bij eerste aanroep)

    Returns:
        CloudClassifierONNX instance of None als model niet beschikbaar
    """
    global _classifier_instance

    if _classifier_instance is None and model_path:
        try:
            _classifier_instance = CloudClassifierONNX(model_path)
        except Exception as e:
            logger.warning(f"Kon cloud classifier niet laden: {e}")
            return None

    return _classifier_instance


def predict_cloud_coverage(
    image_path: Union[str, Path],
    model_path: Optional[Union[str, Path]] = None
) -> Optional[Dict]:
    """
    Convenience functie voor cloud coverage voorspelling.

    Gebruikt singleton classifier voor efficiëntie.

    Args:
        image_path: Pad naar hemelbeeld
        model_path: Pad naar ONNX model (default: scripts/atmosbird/cloud_classifier.onnx)

    Returns:
        Prediction dict of None bij fout
    """
    if model_path is None:
        # Default pad
        model_path = Path(__file__).parent / 'cloud_classifier.onnx'

    classifier = get_classifier(model_path)
    if classifier is None:
        return None

    try:
        return classifier.predict(image_path)
    except Exception as e:
        logger.error(f"Cloud coverage prediction failed: {e}")
        return None


# Test code
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Gebruik: python cloud_classifier_inference.py <image.jpg> [model.onnx]")
        print("\nAls geen model opgegeven, zoekt in dezelfde directory naar cloud_classifier.onnx")
        sys.exit(1)

    image_path = sys.argv[1]
    model_path = sys.argv[2] if len(sys.argv) > 2 else None

    if model_path is None:
        # Zoek model in dezelfde directory
        default_model = Path(__file__).parent / 'cloud_classifier.onnx'
        if default_model.exists():
            model_path = default_model
        else:
            print(f"Model niet gevonden: {default_model}")
            print("Geef het model pad op als tweede argument.")
            sys.exit(1)

    # Test
    classifier = CloudClassifierONNX(model_path)
    result = classifier.predict(image_path)

    print(f"\nBeeld: {image_path}")
    print(f"Klasse: {result['class_name']}")
    print(f"Bewolking: {result['cloud_coverage_percent']:.1f}%")
    print(f"Confidence: {result['confidence']:.1%}")
    print(f"\nProbabilities:")
    for name, prob in result['probabilities'].items():
        print(f"  {name}: {prob:.1%}")
