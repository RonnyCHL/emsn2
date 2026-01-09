#!/usr/bin/env python3
"""
EMSN 2.0 - Zeldzame Detecties Export voor Waarneming.nl

Exporteert rare/legendary BirdNET detecties met audio naar aparte map,
klaar voor upload naar waarneming.nl.

Gebruik:
    python rare_detections_export.py              # Laatste dag
    python rare_detections_export.py --days 7     # Laatste 7 dagen
    python rare_detections_export.py --all        # Alles opnieuw
    python rare_detections_export.py --dry-run    # Preview zonder actie
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import get_postgres_config

# Configuratie
EXPORT_DIR = Path("/mnt/nas-birdnet-archive/waarneming-export")
AUDIO_ARCHIVE = Path("/mnt/nas-birdnet-archive/audio")
TRACKING_FILE = EXPORT_DIR / ".exported_ids.json"
LOG_FILE = Path("/mnt/usb/logs/rare_export.log")

RARITY_TIERS = ("legendary", "rare")
MIN_CONFIDENCE = 0.70
LOCATION = {"name": "Nijverdal", "lat": 52.360179, "lon": 6.472626}


@dataclass
class Detection:
    """Representatie van een zeldzame vogeldetectie."""

    id: int
    station: str
    timestamp: datetime
    detection_date: date
    detection_time: time
    species: str
    common_name: str
    confidence: float
    file_name: str | None
    rarity_tier: str | None
    dual_detection: bool
    vocalization_type: str | None

    @property
    def safe_name(self) -> str:
        return self.common_name.replace(" ", "_").replace("/", "-")

    @property
    def time_str(self) -> str:
        return self.detection_time.strftime("%H%M%S")

    @property
    def export_basename(self) -> str:
        return f"{self.detection_date}_{self.time_str}_{self.safe_name}"

    def audio_path(self) -> Path | None:
        """Zoek audio bestand in NAS archief."""
        if not self.file_name:
            return None

        year = self.timestamp.strftime("%Y")
        month = self.timestamp.strftime("%m")

        candidates = [
            AUDIO_ARCHIVE / self.station / year / month / self.file_name,
            AUDIO_ARCHIVE / self.station / year / self.file_name,
        ]

        for path in candidates:
            if path.exists():
                return path
        return None

    def to_metadata(self) -> dict[str, Any]:
        """Genereer metadata dict voor waarneming.nl."""
        return {
            "soort": self.common_name,
            "wetenschappelijke_naam": self.species,
            "datum": str(self.detection_date),
            "tijd": str(self.detection_time),
            "locatie": LOCATION["name"],
            "coordinaten": {"lat": LOCATION["lat"], "lon": LOCATION["lon"]},
            "station": self.station,
            "confidence": round(self.confidence, 4),
            "rarity": self.rarity_tier,
            "dual_detection": self.dual_detection,
            "vocalization": self.vocalization_type,
            "bron": "BirdNET-Pi / EMSN 2.0",
            "audio_bestand": self.file_name,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Detection:
        return cls(
            id=row["id"],
            station=row["station"],
            timestamp=row["detection_timestamp"],
            detection_date=row["date"],
            detection_time=row["time"],
            species=row["species"],
            common_name=row["common_name"],
            confidence=float(row["confidence"]),
            file_name=row["file_name"],
            rarity_tier=row["rarity_tier"],
            dual_detection=row["dual_detection"] or False,
            vocalization_type=row["vocalization_type"],
        )


@dataclass
class ExportResult:
    """Resultaat van een export operatie."""

    detection: Detection
    success: bool = False
    error: str | None = None
    audio_path: Path | None = None


@dataclass
class ExportStats:
    """Statistieken van de export run."""

    found: int = 0
    new: int = 0
    exported: int = 0
    failed: int = 0
    species: dict[str, int] = field(default_factory=dict)


class RareDetectionsExporter:
    """Exporteert zeldzame detecties naar waarneming.nl formaat."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.pg_config = get_postgres_config()
        self.exported_ids: set[int] = set()
        self.logger = self._setup_logging()

    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger("rare_export")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(LOG_FILE)
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            logger.addHandler(handler)

        return logger

    def _connect(self) -> psycopg2.extensions.connection:
        return psycopg2.connect(**self.pg_config)

    def load_exported_ids(self) -> None:
        """Laad eerder geëxporteerde detectie IDs."""
        if TRACKING_FILE.exists():
            with open(TRACKING_FILE, encoding="utf-8") as f:
                self.exported_ids = set(json.load(f))

    def save_exported_ids(self) -> None:
        """Sla geëxporteerde IDs op."""
        TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TRACKING_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(self.exported_ids), f)

    def fetch_rare_detections(self, days: int | None = None) -> list[Detection]:
        """Haal zeldzame detecties op uit database."""
        query = """
            SELECT
                bd.id, bd.station, bd.detection_timestamp, bd.date, bd.time,
                bd.species, bd.common_name, bd.confidence, bd.file_name,
                bd.rarity_tier, bd.dual_detection, bd.vocalization_type
            FROM bird_detections bd
            JOIN species_rarity_cache src ON bd.common_name = src.species_nl
            WHERE src.rarity_tier = ANY(%s)
              AND bd.confidence >= %s
              AND bd.deleted = false
              AND bd.file_name IS NOT NULL
        """
        params: list[Any] = [list(RARITY_TIERS), MIN_CONFIDENCE]

        if days is not None:
            query += " AND bd.date >= CURRENT_DATE - INTERVAL '%s days'"
            params.append(days)

        query += " ORDER BY bd.detection_timestamp DESC"

        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return [Detection.from_row(row) for row in cur.fetchall()]

    def export_detection(self, detection: Detection) -> ExportResult:
        """Exporteer een enkele detectie."""
        result = ExportResult(detection=detection)

        species_dir = EXPORT_DIR / detection.safe_name
        audio_source = detection.audio_path()

        if not audio_source:
            result.error = f"Audio niet gevonden: {detection.file_name}"
            return result

        if self.dry_run:
            result.success = True
            return result

        species_dir.mkdir(parents=True, exist_ok=True)

        # Kopieer audio
        audio_dest = species_dir / f"{detection.export_basename}.mp3"
        if not audio_dest.exists():
            shutil.copy2(audio_source, audio_dest)
        result.audio_path = audio_dest

        # Schrijf metadata
        metadata_path = species_dir / f"{detection.export_basename}.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(detection.to_metadata(), f, ensure_ascii=False, indent=2)

        result.success = True
        return result

    def run(self, days: int | None = 1, reset: bool = False) -> ExportStats:
        """Voer de export uit."""
        stats = ExportStats()

        # Haal detecties op
        detections = self.fetch_rare_detections(days)
        stats.found = len(detections)

        if not detections:
            return stats

        # Filter al geëxporteerde
        if not reset:
            self.load_exported_ids()

        new_detections = [d for d in detections if d.id not in self.exported_ids]
        stats.new = len(new_detections)

        if not new_detections:
            return stats

        # Maak export directory
        if not self.dry_run:
            EXPORT_DIR.mkdir(parents=True, exist_ok=True)

        # Export
        for detection in new_detections:
            result = self.export_detection(detection)

            if result.success:
                stats.exported += 1
                self.exported_ids.add(detection.id)
                stats.species[detection.common_name] = (
                    stats.species.get(detection.common_name, 0) + 1
                )
                self.logger.info(
                    "Exported: %s %s (%s)",
                    detection.common_name,
                    detection.detection_date,
                    detection.station,
                )
            else:
                stats.failed += 1
                self.logger.warning(
                    "Failed: %s - %s", detection.common_name, result.error
                )

        # Sla tracking op
        if not self.dry_run:
            self.save_exported_ids()

        return stats


def print_summary(stats: ExportStats, dry_run: bool = False) -> None:
    """Print samenvatting naar console."""
    mode = "[DRY RUN] " if dry_run else ""
    print(f"\n{mode}Samenvatting:")
    print(f"  Gevonden:    {stats.found} zeldzame detecties")
    print(f"  Nieuw:       {stats.new}")
    print(f"  Geëxporteerd: {stats.exported}")
    if stats.failed:
        print(f"  Mislukt:     {stats.failed}")

    if stats.species:
        print(f"\nPer soort:")
        for species, count in sorted(stats.species.items()):
            print(f"  {species}: {count}")

    print(f"\nExport map: {EXPORT_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export zeldzame detecties voor waarneming.nl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Aantal dagen terug (default: 1)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Exporteer alles opnieuw (negeer tracking)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Alleen tonen, niet kopiëren",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("EMSN 2.0 - Zeldzame Detecties Export")
    print("=" * 60)
    print(f"Rarity tiers: {', '.join(RARITY_TIERS)}")
    print(f"Min confidence: {MIN_CONFIDENCE:.0%}")

    days = None if args.all else args.days
    print(f"Periode: {'alles' if days is None else f'laatste {days} dag(en)'}")

    if args.dry_run:
        print("Mode: DRY RUN")

    exporter = RareDetectionsExporter(dry_run=args.dry_run)
    stats = exporter.run(days=days, reset=args.all)

    print_summary(stats, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
