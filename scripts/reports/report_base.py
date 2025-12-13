#!/usr/bin/env python3
"""
EMSN Report Base Class
Shared functionality for all report generators
"""

import os
import sys
import yaml
import subprocess
from pathlib import Path
from datetime import datetime
import psycopg2
from anthropic import Anthropic

# Configuration
DB_HOST = "192.168.1.25"
DB_PORT = 5433
DB_NAME = "emsn"
DB_USER = "birdpi_zolder"
DB_PASSWORD = os.getenv("EMSN_DB_PASSWORD", "REDACTED_DB_PASS")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

REPORTS_PATH = Path("/home/ronny/emsn2/reports")
CONFIG_PATH = Path("/home/ronny/emsn2/config")
STYLES_FILE = CONFIG_PATH / "report_styles.yaml"


class ReportBase:
    """Base class for all EMSN report generators"""

    def __init__(self):
        self.conn = None
        self.client = None
        self.style = None
        self.style_name = None

        if not ANTHROPIC_API_KEY:
            print("ERROR: ANTHROPIC_API_KEY environment variable not set")
            sys.exit(1)

        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)

    def connect_db(self):
        """Connect to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            return True
        except Exception as e:
            print(f"ERROR: Database connection failed: {e}")
            return False

    def close_db(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def load_styles(self):
        """Load all available styles from config"""
        if not STYLES_FILE.exists():
            print(f"WARNING: Styles file not found: {STYLES_FILE}")
            return self._default_styles()

        with open(STYLES_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def get_style(self, style_name=None):
        """Get a specific style configuration"""
        styles_config = self.load_styles()

        if style_name is None:
            style_name = styles_config.get('default_style', 'wetenschappelijk')

        styles = styles_config.get('styles', {})
        if style_name not in styles:
            print(f"WARNING: Style '{style_name}' not found, using default")
            style_name = styles_config.get('default_style', 'wetenschappelijk')

        self.style_name = style_name
        self.style = styles.get(style_name, self._default_style())
        return self.style

    def get_style_prompt(self):
        """Get the prompt for the current style"""
        if self.style is None:
            self.get_style()
        return self.style.get('prompt', '')

    def list_styles(self):
        """List all available styles"""
        styles_config = self.load_styles()
        styles = styles_config.get('styles', {})
        return {
            name: {
                'name': style.get('name', name),
                'description': style.get('description', '')
            }
            for name, style in styles.items()
        }

    def _default_styles(self):
        """Return default styles if config file not found"""
        return {
            'default_style': 'wetenschappelijk',
            'styles': {
                'wetenschappelijk': self._default_style()
            }
        }

    def _default_style(self):
        """Return default wetenschappelijk style"""
        return {
            'name': 'Wetenschappelijk',
            'description': 'Veldbioloog stijl',
            'prompt': '''Je bent een ervaren veldbioloog die een rapport opstelt.
Wetenschappelijk gefundeerd, data-gedreven, droge humor.
Vogelsoorten met Hoofdletter + wetenschappelijke naam.'''
        }

    def generate_with_claude(self, prompt, max_tokens=4000):
        """Generate text using Claude API"""
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text
        except Exception as e:
            print(f"ERROR: Claude API error: {e}")
            return None

    def update_web_index(self):
        """Update the web reports index"""
        try:
            subprocess.run([
                '/home/ronny/emsn2/venv/bin/python3',
                '/home/ronny/emsn2/reports-web/generate_index.py'
            ], check=True, capture_output=True)
            print("Web index updated")
        except Exception as e:
            print(f"WARNING: Could not update web index: {e}")

    def format_number(self, num):
        """Format number with thousand separators"""
        return f"{num:,}".replace(",", ".")

    def get_common_name(self, scientific_name):
        """Get Dutch common name for a species"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT common_name FROM bird_detections
            WHERE species = %s AND common_name IS NOT NULL
            LIMIT 1
        """, (scientific_name,))
        result = cur.fetchone()
        cur.close()
        return result[0] if result else scientific_name

    def get_all_species(self):
        """Get list of all detected species with counts"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT
                common_name,
                species,
                COUNT(*) as total
            FROM bird_detections
            WHERE common_name IS NOT NULL
            GROUP BY common_name, species
            ORDER BY total DESC
        """)
        species = [
            {
                'common_name': row[0],
                'scientific_name': row[1],
                'total': row[2]
            }
            for row in cur.fetchall()
        ]
        cur.close()
        return species


def get_available_styles():
    """Standalone function to get available styles (for API)"""
    base = ReportBase.__new__(ReportBase)
    base.style = None
    base.style_name = None
    return base.list_styles()


if __name__ == "__main__":
    # Test the base class
    base = ReportBase()
    print("Available styles:")
    for name, info in base.list_styles().items():
        print(f"  - {name}: {info['description']}")
