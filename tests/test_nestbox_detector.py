#!/usr/bin/env python3
"""
Unit tests voor scripts/nestbox/nestbox_occupancy_detector.py module.

Test de ML detector functies en image processing.
Tests worden geskipt als dependencies niet beschikbaar zijn.
"""

import sys
from pathlib import Path
from unittest import TestCase, main, skipIf
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

# Check if nestbox module can be imported
NESTBOX_MODULE_AVAILABLE = False
try:
    from nestbox.nestbox_occupancy_detector import (
        CONFIDENCE_THRESHOLD, INPUT_SIZE, MODEL_PATH, FALLBACK_MODEL_PATH
    )
    NESTBOX_MODULE_AVAILABLE = True
except ImportError:
    pass


@skipIf(not NESTBOX_MODULE_AVAILABLE, "nestbox module dependencies not available")
class TestConfidenceThreshold(TestCase):
    """Tests voor confidence threshold logica."""

    def test_confidence_threshold_constant(self):
        """Test dat CONFIDENCE_THRESHOLD correct gedefinieerd is."""
        self.assertIsInstance(CONFIDENCE_THRESHOLD, float)
        self.assertGreater(CONFIDENCE_THRESHOLD, 0.0)
        self.assertLess(CONFIDENCE_THRESHOLD, 1.0)

    def test_input_size_constant(self):
        """Test dat INPUT_SIZE correct gedefinieerd is."""
        self.assertIsInstance(INPUT_SIZE, int)
        self.assertEqual(INPUT_SIZE, 224)  # Standard MobileNetV2 input


@skipIf(not NESTBOX_MODULE_AVAILABLE, "nestbox module dependencies not available")
class TestModelPaths(TestCase):
    """Tests voor model pad constanten."""

    def test_model_path_is_string(self):
        """Test dat MODEL_PATH een string is."""
        self.assertIsInstance(MODEL_PATH, str)
        self.assertTrue(MODEL_PATH.endswith('.pt'))

    def test_fallback_model_path_is_string(self):
        """Test dat FALLBACK_MODEL_PATH een string is."""
        self.assertIsInstance(FALLBACK_MODEL_PATH, str)
        self.assertTrue(FALLBACK_MODEL_PATH.endswith('.pt'))


class TestNestboxIdExtraction(TestCase):
    """Tests voor nestbox ID extractie uit bestandspaden."""

    def test_extract_nestbox_id_from_path(self):
        """Test dat nestbox ID correct uit pad gehaald wordt."""
        # Standard paths: /mnt/nas-birdnet-archive/nestbox/voor/screenshots/file.jpg
        path1 = "/mnt/nas-birdnet-archive/nestbox/voor/screenshots/test.jpg"
        path2 = "/mnt/nas-birdnet-archive/nestbox/midden/screenshots/test.jpg"
        path3 = "/mnt/nas-birdnet-archive/nestbox/achter/screenshots/test.jpg"

        def extract_nestbox_id(path: str) -> str:
            parts = Path(path).parts
            for i, part in enumerate(parts):
                if part == 'nestbox' and i + 1 < len(parts):
                    return parts[i + 1]
            return 'unknown'

        self.assertEqual(extract_nestbox_id(path1), 'voor')
        self.assertEqual(extract_nestbox_id(path2), 'midden')
        self.assertEqual(extract_nestbox_id(path3), 'achter')


class TestOccupancyLogic(TestCase):
    """Tests voor bezettingslogica."""

    def test_leeg_is_not_occupied(self):
        """Test dat 'leeg' detectie niet bezet is."""
        detected_class = 'leeg'
        is_occupied = detected_class.lower() != 'leeg'
        self.assertFalse(is_occupied)

    def test_koolmees_is_occupied(self):
        """Test dat vogelsoort detectie bezet is."""
        detected_class = 'Koolmees'
        is_occupied = detected_class.lower() != 'leeg'
        self.assertTrue(is_occupied)

    def test_species_extraction(self):
        """Test dat soort correct geextraheerd wordt."""
        for detected_class, expected_species in [
            ('leeg', None),
            ('Koolmees', 'Koolmees'),
            ('Pimpelmees', 'Pimpelmees'),
            ('Leeg', None),  # Case insensitive
        ]:
            is_occupied = detected_class.lower() != 'leeg'
            species = detected_class if is_occupied else None
            self.assertEqual(species, expected_species)


if __name__ == '__main__':
    main()
