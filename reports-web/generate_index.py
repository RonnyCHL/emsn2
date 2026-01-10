#!/usr/bin/env python3
"""
Generate JSON index of all EMSN reports for web interface
"""

import json
import re
from pathlib import Path
from datetime import datetime

REPORTS_DIR = Path("/mnt/nas-reports")
OUTPUT_FILE = Path("/home/ronny/emsn2/reports-web/reports.json")

def parse_report_filename(filename):
    """Parse report filename to extract metadata"""
    # Weekly: 2025-W50-Weekrapport.md
    # Monthly: 2025-12-Maandrapport.md
    # Seasonal: 2025-Herfst-Seizoensrapport.md
    # Yearly: 2025-Jaaroverzicht.md

    week_match = re.match(r'(\d{4})-W(\d{2})-Weekrapport\.md', filename)
    if week_match:
        year = int(week_match.group(1))
        week = int(week_match.group(2))
        return {
            'type': 'week',
            'year': year,
            'week': week,
            'title': f'Week {week}',
            'filename': filename
        }

    month_match = re.match(r'(\d{4})-(\d{2})-Maandrapport\.md', filename)
    if month_match:
        year = int(month_match.group(1))
        month = int(month_match.group(2))
        month_names = ['januari', 'februari', 'maart', 'april', 'mei', 'juni',
                      'juli', 'augustus', 'september', 'oktober', 'november', 'december']
        return {
            'type': 'month',
            'year': year,
            'month': month,
            'title': month_names[month - 1].capitalize(),
            'filename': filename
        }

    # Seasonal: 2025-Herfst-Seizoensrapport.md or 2025-2026-Winter-Seizoensrapport.md
    season_match = re.match(r'(\d{4}(?:-\d{4})?)-(\w+)-Seizoensrapport\.md', filename)
    if season_match:
        year = season_match.group(1)
        season = season_match.group(2)
        return {
            'type': 'season',
            'year': year,
            'season': season,
            'title': f'{season} {year}',
            'filename': filename
        }

    # Yearly: 2025-Jaaroverzicht.md
    year_match = re.match(r'(\d{4})-Jaaroverzicht\.md', filename)
    if year_match:
        year = int(year_match.group(1))
        return {
            'type': 'year',
            'year': year,
            'title': f'Jaaroverzicht {year}',
            'filename': filename
        }

    # Species: Soort-Merel.md
    species_match = re.match(r'Soort-(.+)\.md', filename)
    if species_match:
        species_name = species_match.group(1).replace('-', ' ')
        return {
            'type': 'species',
            'year': datetime.now().year,
            'species': species_name,
            'title': species_name,
            'filename': filename
        }

    # Comparison: Vergelijking-Week-1-2025-vs-Week-2-2025.md
    comparison_match = re.match(r'Vergelijking-(.+)\.md', filename)
    if comparison_match:
        comparison_title = comparison_match.group(1).replace('-', ' ')
        return {
            'type': 'comparison',
            'year': datetime.now().year,
            'title': comparison_title,
            'filename': filename
        }

    return None

def parse_report_frontmatter(filepath):
    """Parse YAML frontmatter from report to get stats"""
    stats = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

        # Extract frontmatter
        frontmatter_match = re.match(r'---\n(.*?)\n---', content, re.DOTALL)
        if frontmatter_match:
            frontmatter = frontmatter_match.group(1)

            # Parse key fields
            for line in frontmatter.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()

                    if key == 'period':
                        stats['period'] = value
                    elif key == 'total_detections':
                        stats['total_detections'] = int(value)
                    elif key == 'unique_species':
                        stats['unique_species'] = int(value)
                    elif key == 'generated':
                        stats['generated'] = value
                    elif key == 'month':
                        stats['month_name'] = value

    return stats

def generate_index():
    """Generate index of all reports"""
    reports = []

    if not REPORTS_DIR.exists():
        print(f"❌ Reports directory not found: {REPORTS_DIR}")
        return

    # Scan for all markdown reports
    for md_file in sorted(REPORTS_DIR.glob("*.md"), reverse=True):
        metadata = parse_report_filename(md_file.name)
        if not metadata:
            continue

        # Add file stats
        file_stats = md_file.stat()
        metadata['filesize'] = file_stats.st_size
        metadata['modified'] = datetime.fromtimestamp(file_stats.st_mtime).isoformat()

        # Parse frontmatter for detailed stats
        stats = parse_report_frontmatter(md_file)
        metadata.update(stats)

        reports.append(metadata)

    # Write JSON
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'reports': reports,
            'generated': datetime.now().isoformat(),
            'total_reports': len(reports)
        }, f, ensure_ascii=False, indent=2)

    print(f"✅ Generated index with {len(reports)} reports")
    print(f"📄 Output: {OUTPUT_FILE}")

if __name__ == '__main__':
    generate_index()
