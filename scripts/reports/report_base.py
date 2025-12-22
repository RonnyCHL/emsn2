#!/usr/bin/env python3
"""
EMSN Report Base Class
Shared functionality for all report generators
"""

import os
import sys
import yaml
import subprocess
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime
import psycopg2
from anthropic import Anthropic

# Import secrets
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
try:
    from emsn_secrets import get_postgres_config
    _pg = get_postgres_config()
except ImportError:
    _pg = {'host': '192.168.1.25', 'port': 5433, 'database': 'emsn',
           'user': 'birdpi_zolder', 'password': os.environ.get('EMSN_DB_PASSWORD', '')}

# Configuration (from secrets)
DB_HOST = _pg.get('host', '192.168.1.25')
DB_PORT = _pg.get('port', 5433)
DB_NAME = _pg.get('database', 'emsn')
DB_USER = _pg.get('user', 'birdpi_zolder')
DB_PASSWORD = _pg.get('password', '') or os.getenv("EMSN_DB_PASSWORD", "")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SMTP_PASSWORD = os.getenv("EMSN_SMTP_PASSWORD")

REPORTS_PATH = Path("/mnt/nas-reports")
CONFIG_PATH = Path("/home/ronny/emsn2/config")
STYLES_FILE = CONFIG_PATH / "report_styles.yaml"
EMAIL_FILE = CONFIG_PATH / "email.yaml"


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

    def load_email_config(self):
        """Load email configuration from yaml file"""
        if not EMAIL_FILE.exists():
            print("WARNING: Email config file not found")
            return None
        with open(EMAIL_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def send_email(self, subject, body, report_type="weekly"):
        """Send report via email (legacy method - same content to all recipients)"""
        config = self.load_email_config()
        if not config:
            print("WARNING: No email config, skipping email")
            return False

        # Check if auto_send is enabled for this report type
        auto_send = config.get('reports', {}).get('auto_send', {})
        if not auto_send.get(report_type, False):
            print(f"INFO: Email disabled for {report_type} reports")
            return False

        if not SMTP_PASSWORD:
            print("WARNING: EMSN_SMTP_PASSWORD not set, skipping email")
            return False

        smtp_config = config.get('smtp', {})
        email_config = config.get('email', {})
        recipients_config = config.get('recipients', [])

        # Filter recipients: only auto mode + correct report type
        recipients = []
        for r in recipients_config:
            if isinstance(r, str):
                # Old format - include all
                recipients.append(r)
            elif isinstance(r, dict):
                # New format - check mode and report_types
                if r.get('mode', 'auto') == 'auto':
                    report_types = r.get('report_types', ['weekly', 'monthly', 'seasonal', 'yearly'])
                    if report_type in report_types:
                        recipients.append(r.get('email'))

        if not recipients:
            print(f"INFO: No auto-recipients configured for {report_type} reports")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{email_config.get('from_name', 'EMSN')} <{email_config.get('from_address')}>"
            msg['To'] = ', '.join(recipients)

            # Plain text version
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)

            # Connect and send
            server = smtplib.SMTP(smtp_config.get('host'), smtp_config.get('port', 587))
            if smtp_config.get('use_tls', True):
                server.starttls()
            server.login(smtp_config.get('username'), SMTP_PASSWORD)
            server.sendmail(
                email_config.get('from_address'),
                recipients,
                msg.as_string()
            )
            server.quit()

            print(f"SUCCESS: Email sent to {', '.join(recipients)}")
            return True

        except Exception as e:
            print(f"ERROR: Failed to send email: {e}")
            return False

    def get_recipients_by_style(self, report_type="weekly"):
        """
        Get recipients grouped by their preferred style.

        Returns dict: {style_name: [list of email addresses]}
        """
        config = self.load_email_config()
        if not config:
            return {}

        # Check if auto_send is enabled for this report type
        auto_send = config.get('reports', {}).get('auto_send', {})
        if not auto_send.get(report_type, False):
            print(f"INFO: Email disabled for {report_type} reports")
            return {}

        recipients_config = config.get('recipients', [])
        by_style = {}

        for r in recipients_config:
            if isinstance(r, str):
                # Old format - use default style
                style = 'wetenschappelijk'
                email = r
                mode = 'auto'
                report_types = ['weekly', 'monthly', 'seasonal', 'yearly']
            elif isinstance(r, dict):
                email = r.get('email')
                mode = r.get('mode', 'auto')
                style = r.get('style', 'wetenschappelijk')
                report_types = r.get('report_types', ['weekly', 'monthly', 'seasonal', 'yearly'])
            else:
                continue

            # Filter: only auto mode + correct report type
            if mode == 'auto' and report_type in report_types:
                if style not in by_style:
                    by_style[style] = []
                by_style[style].append(email)

        return by_style

    def send_email_to_recipients(self, subject, body, recipients):
        """
        Send email with given body to specific recipients.

        Args:
            subject: Email subject
            body: Email body text
            recipients: List of email addresses

        Returns: True if sent successfully
        """
        if not recipients:
            return False

        config = self.load_email_config()
        if not config:
            print("WARNING: No email config, skipping email")
            return False

        if not SMTP_PASSWORD:
            print("WARNING: EMSN_SMTP_PASSWORD not set, skipping email")
            return False

        smtp_config = config.get('smtp', {})
        email_config = config.get('email', {})

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{email_config.get('from_name', 'EMSN')} <{email_config.get('from_address')}>"
            msg['To'] = ', '.join(recipients)

            # Plain text version
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)

            # Connect and send
            server = smtplib.SMTP(smtp_config.get('host'), smtp_config.get('port', 587))
            if smtp_config.get('use_tls', True):
                server.starttls()
            server.login(smtp_config.get('username'), SMTP_PASSWORD)
            server.sendmail(
                email_config.get('from_address'),
                recipients,
                msg.as_string()
            )
            server.quit()

            print(f"SUCCESS: Email sent to {', '.join(recipients)}")
            return True

        except Exception as e:
            print(f"ERROR: Failed to send email: {e}")
            return False

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
