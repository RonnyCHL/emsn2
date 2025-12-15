#!/usr/bin/env python3
"""
EMSN Report Spectrograms Module
Finds and copies spectrograms for report visualization
"""

import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import psycopg2


class ReportSpectrograms:
    """Find and prepare spectrograms for reports"""

    # BirdSongs directory on Pi
    BIRDSONGS_BASE = Path("/home/ronny/BirdSongs/Extracted/By_Date")

    def __init__(self, output_dir: Path, db_connection=None):
        self.output_dir = Path(output_dir)
        self.conn = db_connection
        self.spectrograms_dir = self.output_dir / "spectrograms"
        self.spectrograms_dir.mkdir(parents=True, exist_ok=True)
        self.generated_spectrograms = []

    def find_spectrograms_for_species(
        self,
        species_name: str,
        start_date: datetime,
        end_date: datetime,
        max_count: int = 3,
        min_confidence: float = 0.7
    ) -> List[Dict]:
        """
        Find spectrograms for a species within date range

        Args:
            species_name: Dutch common name (e.g., "Ekster")
            start_date: Start of period
            end_date: End of period
            max_count: Maximum number of spectrograms to find
            min_confidence: Minimum confidence threshold

        Returns:
            List of dicts with spectrogram info
        """
        spectrograms = []

        # Convert species name to folder format (spaces to underscores)
        folder_name = species_name.replace(' ', '_')

        # Iterate through dates
        current_date = start_date
        while current_date <= end_date and len(spectrograms) < max_count:
            date_str = current_date.strftime('%Y-%m-%d')
            date_dir = self.BIRDSONGS_BASE / date_str / folder_name

            if date_dir.exists():
                # Find PNG files (spectrograms)
                png_files = sorted(date_dir.glob('*.mp3.png'))

                for png_file in png_files:
                    if len(spectrograms) >= max_count:
                        break

                    # Parse filename to get confidence
                    # Format: Species-NN-YYYY-MM-DD-birdnet-HH:MM:SS.mp3.png
                    parts = png_file.stem.replace('.mp3', '').split('-')
                    if len(parts) >= 6:
                        try:
                            confidence = int(parts[1]) / 100.0
                            if confidence >= min_confidence:
                                time_str = parts[-1]  # HH:MM:SS
                                spectrograms.append({
                                    'species': species_name,
                                    'date': date_str,
                                    'time': time_str,
                                    'confidence': confidence,
                                    'source_path': png_file,
                                    'audio_path': png_file.parent / png_file.stem.replace('.png', '')
                                })
                        except (ValueError, IndexError):
                            continue

            current_date += timedelta(days=1)

        # Sort by confidence (highest first) and return top results
        spectrograms.sort(key=lambda x: x['confidence'], reverse=True)
        return spectrograms[:max_count]

    def copy_spectrogram(self, spectrogram_info: Dict, prefix: str = "") -> Optional[Path]:
        """
        Copy a spectrogram to the output directory

        Args:
            spectrogram_info: Dict from find_spectrograms_for_species
            prefix: Optional prefix for output filename

        Returns:
            Path to copied file, or None if failed
        """
        source = spectrogram_info['source_path']
        if not source.exists():
            return None

        # Create output filename
        species_safe = spectrogram_info['species'].replace(' ', '_').lower()
        date_safe = spectrogram_info['date']
        time_safe = spectrogram_info['time'].replace(':', '')
        confidence = int(spectrogram_info['confidence'] * 100)

        output_name = f"{prefix}{species_safe}_{date_safe}_{time_safe}_{confidence}pct.png"
        output_path = self.spectrograms_dir / output_name

        try:
            shutil.copy2(source, output_path)
            self.generated_spectrograms.append(output_path)
            return output_path
        except Exception as e:
            print(f"Failed to copy spectrogram: {e}")
            return None

    def get_top_species_spectrograms(
        self,
        start_date: datetime,
        end_date: datetime,
        species_list: List[str] = None,
        max_species: int = 5,
        spectrograms_per_species: int = 1
    ) -> Dict[str, List[Dict]]:
        """
        Get spectrograms for top species in period

        Args:
            start_date: Start of period
            end_date: End of period
            species_list: Optional list of species names (uses DB if None)
            max_species: Max number of species to include
            spectrograms_per_species: Number of spectrograms per species

        Returns:
            Dict mapping species name to list of spectrogram info
        """
        if species_list is None and self.conn:
            # Get top species from database
            cur = self.conn.cursor()
            cur.execute("""
                SELECT common_name, COUNT(*) as count
                FROM bird_detections
                WHERE detection_timestamp BETWEEN %s AND %s
                AND common_name IS NOT NULL
                GROUP BY common_name
                ORDER BY count DESC
                LIMIT %s
            """, (start_date, end_date, max_species))
            species_list = [row[0] for row in cur.fetchall()]
            cur.close()

        result = {}
        for species in species_list[:max_species]:
            spectrograms = self.find_spectrograms_for_species(
                species, start_date, end_date,
                max_count=spectrograms_per_species
            )
            if spectrograms:
                result[species] = spectrograms

        return result

    def get_highlight_spectrograms(
        self,
        start_date: datetime,
        end_date: datetime,
        highlights: Dict
    ) -> List[Dict]:
        """
        Get spectrograms for highlight species (rare, new, records)

        Args:
            start_date: Start of period
            end_date: End of period
            highlights: Dict from ReportHighlights

        Returns:
            List of spectrogram info dicts
        """
        result = []

        # Priority order for highlights
        highlight_types = ['new_species', 'rare_species', 'records', 'seasonal_firsts']

        for hl_type in highlight_types:
            if hl_type in highlights and highlights[hl_type]:
                for item in highlights[hl_type][:2]:  # Max 2 per type
                    species_name = item.get('common_name') or item.get('species')
                    if species_name:
                        spectrograms = self.find_spectrograms_for_species(
                            species_name, start_date, end_date, max_count=1
                        )
                        if spectrograms:
                            spectrograms[0]['highlight_type'] = hl_type
                            result.append(spectrograms[0])

        return result[:5]  # Max 5 highlight spectrograms

    def prepare_for_report(
        self,
        start_date: datetime,
        end_date: datetime,
        top_species: List[str] = None,
        highlights: Dict = None,
        max_total: int = 8
    ) -> List[Dict]:
        """
        Prepare spectrograms for a report - copy to output dir

        Args:
            start_date: Start of period
            end_date: End of period
            top_species: List of top species names
            highlights: Dict from ReportHighlights
            max_total: Maximum total spectrograms

        Returns:
            List of spectrogram info with output paths
        """
        prepared = []

        # Get spectrograms for top species
        if top_species:
            for i, species in enumerate(top_species[:3]):  # Top 3 species
                specs = self.find_spectrograms_for_species(
                    species, start_date, end_date, max_count=1
                )
                if specs:
                    output_path = self.copy_spectrogram(specs[0], prefix=f"top{i+1}_")
                    if output_path:
                        prepared.append({
                            **specs[0],
                            'output_path': output_path,
                            'category': 'top_species'
                        })

        # Get spectrograms for highlights
        if highlights and len(prepared) < max_total:
            hl_specs = self.get_highlight_spectrograms(start_date, end_date, highlights)
            for spec in hl_specs:
                if len(prepared) >= max_total:
                    break
                output_path = self.copy_spectrogram(spec, prefix="highlight_")
                if output_path:
                    prepared.append({
                        **spec,
                        'output_path': output_path,
                        'category': 'highlight'
                    })

        return prepared

    def generate_markdown_section(self, spectrograms: List[Dict]) -> str:
        """
        Generate markdown section for spectrograms

        Args:
            spectrograms: List from prepare_for_report

        Returns:
            Markdown string
        """
        if not spectrograms:
            return ""

        md = "\n## Spectrogrammen\n\n"
        md += "Hieronder een selectie van spectrogrammen van de meest opvallende detecties.\n\n"

        for spec in spectrograms:
            output_path = spec.get('output_path')
            if output_path and output_path.exists():
                # Use relative path from reports directory
                rel_path = f"spectrograms/{output_path.name}"
                md += f"### {spec['species']}\n"
                md += f"*{spec['date']} {spec['time']} - {spec['confidence']:.0%} zekerheid*\n\n"
                md += f"![Spectrogram {spec['species']}]({rel_path})\n\n"

        return md


def test_spectrograms():
    """Test spectrogram finding"""
    from report_base import REPORTS_PATH

    spec = ReportSpectrograms(REPORTS_PATH)

    # Test finding spectrograms
    start = datetime(2025, 12, 8)
    end = datetime(2025, 12, 14)

    print("Finding spectrograms for Ekster...")
    results = spec.find_spectrograms_for_species("Ekster", start, end, max_count=3)
    for r in results:
        print(f"  - {r['date']} {r['time']}: {r['confidence']:.0%} - {r['source_path']}")

    print("\nFinding spectrograms for Roodborst...")
    results = spec.find_spectrograms_for_species("Roodborst", start, end, max_count=3)
    for r in results:
        print(f"  - {r['date']} {r['time']}: {r['confidence']:.0%} - {r['source_path']}")


if __name__ == "__main__":
    test_spectrograms()
