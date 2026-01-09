#!/usr/bin/env python3
"""
FlySafe Radar Color Analyzer
=============================

Analyzes FlySafe radar images to detect bird migration intensity
based on color coding.

Color Intensity Mapping:
- Blue/Dark Green (low values): Minimal migration
- Light Green: Low migration
- Yellow: Moderate migration
- Orange: High migration
- Red: Very high migration

The analyzer:
1. Loads radar image
2. Defines Region of Interest (ROI) for Netherlands
3. Analyzes color distribution
4. Calculates migration intensity score
5. Determines predominant direction (if detectable)

Author: Claude Sonnet 4.5 & Ronny Hullegie
"""

import sys
import numpy as np
from pathlib import Path
from PIL import Image
from typing import Dict, Tuple, Optional
import json

# Import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.logging import get_logger

# Centrale logger
logger = get_logger('flysafe_color_analyzer')


class RadarColorAnalyzer:
    """Analyzes radar images for bird migration intensity"""

    # Color thresholds in RGB for migration intensity
    # These are approximations - may need calibration with actual images
    COLOR_RANGES = {
        'very_high': {  # Red
            'r_min': 200, 'r_max': 255,
            'g_min': 0,   'g_max': 100,
            'b_min': 0,   'b_max': 100
        },
        'high': {  # Orange
            'r_min': 200, 'r_max': 255,
            'g_min': 100, 'g_max': 200,
            'b_min': 0,   'b_max': 100
        },
        'moderate': {  # Yellow
            'r_min': 200, 'r_max': 255,
            'g_min': 200, 'g_max': 255,
            'b_min': 0,   'b_max': 150
        },
        'low': {  # Light Green
            'r_min': 100, 'r_max': 200,
            'g_min': 200, 'g_max': 255,
            'b_min': 100, 'b_max': 200
        },
        'minimal': {  # Dark Green/Blue
            'r_min': 0,   'r_max': 100,
            'g_min': 100, 'g_max': 200,
            'b_min': 100, 'b_max': 255
        }
    }

    def __init__(self):
        pass

    def load_image(self, image_path: str) -> Optional[np.ndarray]:
        """Load radar image and convert to numpy array"""
        try:
            img = Image.open(image_path)
            img_array = np.array(img)

            logger.info(f"Loaded image: {image_path}")
            logger.info(f"Image shape: {img_array.shape}")

            return img_array

        except Exception as e:
            logger.error(f"Failed to load image {image_path}: {e}")
            return None

    def define_roi(self, img_shape: Tuple[int, int], region='netherlands') -> Tuple[slice, slice]:
        """
        Define Region of Interest based on radar coverage

        For now, use center portion of image
        In production, would use actual geographic coordinates
        """
        height, width = img_shape[:2]

        if region == 'netherlands':
            # Approximate Netherlands region (center-north of radar coverage)
            row_start = int(height * 0.2)
            row_end = int(height * 0.7)
            col_start = int(width * 0.3)
            col_end = int(width * 0.7)
        else:
            # Full image
            row_start, row_end = 0, height
            col_start, col_end = 0, width

        return (slice(row_start, row_end), slice(col_start, col_end))

    def count_color_pixels(self, img_array: np.ndarray, color_range: dict) -> int:
        """Count pixels within specified color range"""
        if len(img_array.shape) == 2:
            # Grayscale image
            logger.warning("Grayscale image - color analysis not applicable")
            return 0

        r, g, b = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2]

        mask = (
            (r >= color_range['r_min']) & (r <= color_range['r_max']) &
            (g >= color_range['g_min']) & (g <= color_range['g_max']) &
            (b >= color_range['b_min']) & (b <= color_range['b_max'])
        )

        return int(np.sum(mask))

    def analyze_intensity(self, img_array: np.ndarray, roi: Optional[Tuple[slice, slice]] = None) -> Dict:
        """
        Analyze migration intensity from image

        Returns dict with:
        - intensity: categorical level
        - percentages: breakdown by color category
        - score: numeric intensity score (0-100)
        - total_pixels: total analyzed pixels
        """
        if roi:
            roi_array = img_array[roi]
        else:
            roi_array = img_array

        total_pixels = roi_array.shape[0] * roi_array.shape[1]
        logger.info(f"Analyzing {total_pixels:,} pixels")

        # Count pixels for each intensity level
        color_counts = {}
        for level, color_range in self.COLOR_RANGES.items():
            count = self.count_color_pixels(roi_array, color_range)
            color_counts[level] = count

        # Calculate percentages
        percentages = {
            level: (count / total_pixels * 100) if total_pixels > 0 else 0
            for level, count in color_counts.items()
        }

        # Calculate weighted intensity score (0-100)
        weights = {
            'minimal': 0,
            'low': 25,
            'moderate': 50,
            'high': 75,
            'very_high': 100
        }

        score = sum(
            percentages[level] * weights[level] / 100
            for level in percentages
        )

        # Determine categorical intensity
        if percentages['very_high'] > 10:
            intensity = 'very_high'
        elif percentages['high'] > 15:
            intensity = 'high'
        elif percentages['moderate'] > 20:
            intensity = 'moderate'
        elif percentages['low'] > 20:
            intensity = 'low'
        else:
            intensity = 'minimal'

        result = {
            'intensity': intensity,
            'score': round(score, 2),
            'percentages': {k: round(v, 2) for k, v in percentages.items()},
            'pixel_counts': color_counts,
            'total_pixels': total_pixels
        }

        logger.info(f"Intensity: {intensity} (score: {score:.1f})")
        logger.info(f"Distribution: {json.dumps(result['percentages'], indent=2)}")

        return result

    def detect_direction(self, img_array: np.ndarray, roi: Optional[Tuple[slice, slice]] = None) -> Optional[str]:
        """
        Attempt to detect predominant migration direction

        This is a simplified heuristic - actual direction detection
        would require temporal analysis of multiple frames.

        Returns: cardinal direction string or None
        """
        if roi:
            roi_array = img_array[roi]
        else:
            roi_array = img_array

        # Divide into quadrants
        height, width = roi_array.shape[:2]
        mid_h, mid_w = height // 2, width // 2

        quadrants = {
            'NW': roi_array[:mid_h, :mid_w],
            'NE': roi_array[:mid_h, mid_w:],
            'SW': roi_array[mid_h:, :mid_w],
            'SE': roi_array[mid_h:, mid_w:]
        }

        # Count high-intensity pixels per quadrant
        quadrant_scores = {}
        for direction, quad_array in quadrants.items():
            # Count yellow, orange, red pixels
            score = 0
            for level in ['moderate', 'high', 'very_high']:
                score += self.count_color_pixels(quad_array, self.COLOR_RANGES[level])

            quadrant_scores[direction] = score

        # Determine predominant direction
        if max(quadrant_scores.values()) > 0:
            predominant = max(quadrant_scores, key=quadrant_scores.get)
            logger.info(f"Predominant quadrant: {predominant}")
            return predominant

        return None

    def analyze_image(self, image_path: str, region='netherlands') -> Optional[Dict]:
        """
        Full analysis of radar image

        Returns complete analysis dict or None if failed
        """
        logger.info(f"=== Analyzing radar image: {image_path} ===")

        img_array = self.load_image(image_path)
        if img_array is None:
            return None

        roi = self.define_roi(img_array.shape, region=region)

        intensity_result = self.analyze_intensity(img_array, roi)
        direction = self.detect_direction(img_array, roi)

        result = {
            'image_path': str(image_path),
            'region': region,
            'roi_shape': (roi[0].stop - roi[0].start, roi[1].stop - roi[1].start),
            'intensity': intensity_result['intensity'],
            'intensity_score': intensity_result['score'],
            'color_distribution': intensity_result['percentages'],
            'pixel_counts': intensity_result['pixel_counts'],
            'direction': direction,
            'analysis_metadata': {
                'total_pixels_analyzed': intensity_result['total_pixels'],
                'color_ranges_used': list(self.COLOR_RANGES.keys())
            }
        }

        logger.info(f"=== Analysis Complete ===")
        return result


def main():
    """Main entry point for standalone testing"""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze FlySafe radar images')
    parser.add_argument('image_path', help='Path to radar image')
    parser.add_argument('--region', default='netherlands', help='Region to analyze')
    parser.add_argument('--output', help='Output JSON file for results')

    args = parser.parse_args()

    analyzer = RadarColorAnalyzer()
    result = analyzer.analyze_image(args.image_path, region=args.region)

    if result:
        print("\n=== Analysis Result ===")
        print(json.dumps(result, indent=2))

        if args.output:
            with open(args.output, 'w') as f:
                json.dumps(result, f, indent=2)
            print(f"\nResults saved to: {args.output}")
    else:
        print("Analysis failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
