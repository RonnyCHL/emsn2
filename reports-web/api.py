#!/usr/bin/env python3
"""
EMSN Reports API - Flask server for serving reports and generating PDFs
"""

import os
import sys
import subprocess
import threading
import smtplib
import yaml
import signal
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
from flask import Flask, send_file, request, jsonify, send_from_directory
from flask_cors import CORS
import tempfile

# Add scripts path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'reports'))
from report_base import get_available_styles

app = Flask(__name__)
CORS(app)

REPORTS_DIR = Path("/mnt/nas-reports")
WEB_DIR = Path("/home/ronny/emsn2/reports-web")
SCRIPTS_DIR = Path("/home/ronny/emsn2/scripts/reports")
CONFIG_DIR = Path("/home/ronny/emsn2/config")
ASSETS_DIR = Path("/home/ronny/emsn2/assets")
EMAIL_CONFIG_FILE = CONFIG_DIR / "email.yaml"
EMAIL_LOG_FILE = REPORTS_DIR / "email_history.json"
EMAIL_TRACKING_FILE = REPORTS_DIR / "email_tracking.json"
VENV_PYTHON = "/home/ronny/emsn2/venv/bin/python3"

# Base URL for email links
BASE_URL = "http://192.168.1.178:8081"

# PDF Template and Logo paths
PDF_TEMPLATE = WEB_DIR / "emsn-template.tex"
LOGO_PATH = ASSETS_DIR / "logo-pdf.png"  # Optimized version for PDFs

# Track running report generations
running_jobs = {}

@app.route('/')
def index():
    """Serve the main index page"""
    return send_from_directory(WEB_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_file(filename):
    """Serve static files (HTML, CSS, JS, JSON)"""
    return send_from_directory(WEB_DIR, filename)

@app.route('/reports/<path:filename>')
def serve_report(filename):
    """Serve markdown report files"""
    return send_from_directory(REPORTS_DIR, filename)


def generate_pdf_with_logo(md_path, output_pdf_path, title=None):
    """
    Generate PDF from markdown with EMSN logo header using pandoc + XeLaTeX.

    Args:
        md_path: Path to markdown file
        output_pdf_path: Path for output PDF
        title: Optional title override

    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    from datetime import datetime

    try:
        # Read and prepare markdown content
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract and remove YAML frontmatter, parse metadata
        metadata = {}
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    metadata = yaml.safe_load(parts[1]) or {}
                except:
                    pass
                content = parts[2].strip()

        # Use title from metadata if not provided
        if not title:
            title = metadata.get('title', 'EMSN Rapport')

        # Get date from metadata or use today
        report_date = metadata.get('date', datetime.now().strftime('%d %B %Y'))

        # Write cleaned content to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp_md:
            tmp_md.write(content)
            tmp_md_path = Path(tmp_md.name)

        try:
            # Build pandoc command with template
            cmd = [
                'pandoc',
                str(tmp_md_path),
                '-o', str(output_pdf_path),
                '--pdf-engine=xelatex',
                '-V', f'title={title}',
                '-V', f'date={report_date}',
                '-V', f'logo-path={LOGO_PATH}',
                '--resource-path', f'{REPORTS_DIR}:{ASSETS_DIR}',
            ]

            # Use custom template if it exists
            if PDF_TEMPLATE.exists():
                cmd.extend(['--template', str(PDF_TEMPLATE)])
            else:
                # Fallback to basic styling without template
                cmd.extend([
                    '-V', 'geometry:margin=2.5cm',
                    '-V', 'fontsize=11pt',
                ])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                return False, f"pandoc error: {result.stderr}"

            return True, None

        finally:
            # Clean up temp markdown
            if tmp_md_path.exists():
                tmp_md_path.unlink()

    except subprocess.TimeoutExpired:
        return False, "PDF generation timed out"
    except Exception as e:
        return False, str(e)


@app.route('/api/pdf')
def generate_pdf():
    """Generate PDF from markdown report with EMSN logo header"""
    filename = request.args.get('file')

    if not filename:
        return jsonify({'error': 'No file specified'}), 400

    md_path = REPORTS_DIR / filename

    if not md_path.exists():
        return jsonify({'error': 'Report not found'}), 404

    # Create temporary PDF file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        pdf_path = Path(tmp.name)

    try:
        # Generate PDF with logo using helper function
        success, error = generate_pdf_with_logo(md_path, pdf_path)

        if not success:
            if pdf_path.exists():
                pdf_path.unlink()
            return jsonify({'error': f'PDF generation failed: {error}'}), 500

        # Send PDF file
        pdf_filename = filename.replace('.md', '.pdf')
        response = send_file(
            pdf_path,
            as_attachment=True,
            download_name=pdf_filename,
            mimetype='application/pdf'
        )

        # Clean up PDF after sending
        @response.call_on_close
        def cleanup():
            try:
                pdf_path.unlink()
            except:
                pass

        return response

    except Exception as e:
        if pdf_path.exists():
            pdf_path.unlink()
        return jsonify({'error': str(e)}), 500

@app.route('/api/styles')
def get_styles():
    """Get available writing styles"""
    try:
        styles = get_available_styles()
        return jsonify({
            'styles': [
                {
                    'id': name,
                    'name': info['name'],
                    'description': info['description']
                }
                for name, info in styles.items()
            ],
            'default': 'wetenschappelijk'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schedule/skipped')
def get_skipped_reports():
    """Get log of skipped report generations (smart scheduling)"""
    try:
        skip_log = REPORTS_DIR / "skip_log.json"
        if not skip_log.exists():
            return jsonify({'skipped': []})

        with open(skip_log, 'r') as f:
            logs = json.load(f)

        return jsonify({'skipped': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate', methods=['POST'])
def generate_report():
    """Generate a report on demand"""
    data = request.json

    report_type = data.get('type')  # week, month, season, year, species, comparison
    style = data.get('style', 'wetenschappelijk')

    if not report_type:
        return jsonify({'error': 'Report type required'}), 400

    # Build command based on report type
    env = os.environ.copy()
    env['ANTHROPIC_API_KEY'] = os.getenv('ANTHROPIC_API_KEY', '')
    env['EMSN_DB_PASSWORD'] = os.getenv('EMSN_DB_PASSWORD', 'REDACTED_DB_PASS')

    if report_type == 'week':
        script = SCRIPTS_DIR / 'weekly_report.py'
        cmd = [VENV_PYTHON, str(script), '--style', style]
        # Manual generation via web UI always forces (skips minimum check)
        cmd.append('--force')

    elif report_type == 'month':
        script = SCRIPTS_DIR / 'monthly_report.py'
        month = data.get('month')
        year = data.get('year')
        cmd = [VENV_PYTHON, str(script), '--style', style]
        if month:
            cmd.extend(['--month', str(month)])
        if year:
            cmd.extend(['--year', str(year)])

    elif report_type == 'season':
        script = SCRIPTS_DIR / 'seasonal_report.py'
        season = data.get('season')
        year = data.get('year')
        cmd = [VENV_PYTHON, str(script), '--style', style]
        if season:
            cmd.extend(['--season', season])
        if year:
            cmd.extend(['--year', str(year)])

    elif report_type == 'year':
        script = SCRIPTS_DIR / 'yearly_report.py'
        year = data.get('year')
        cmd = [VENV_PYTHON, str(script), '--style', style]
        if year:
            cmd.extend(['--year', str(year)])

    elif report_type == 'species':
        script = SCRIPTS_DIR / 'species_report.py'
        species = data.get('species')
        if not species:
            return jsonify({'error': 'Species name required'}), 400
        cmd = [VENV_PYTHON, str(script), '--species', species, '--style', style]

    elif report_type == 'comparison':
        script = SCRIPTS_DIR / 'comparison_report.py'
        period1 = data.get('period1')
        period2 = data.get('period2')
        if not period1 or not period2:
            return jsonify({'error': 'Both periods required'}), 400
        cmd = [VENV_PYTHON, str(script), '--period1', period1, '--period2', period2, '--style', style]

    else:
        return jsonify({'error': f'Unknown report type: {report_type}'}), 400

    # Check if script exists
    if not script.exists():
        return jsonify({'error': f'Report script not found: {script.name}'}), 404

    # Run the report generation
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            # Refresh the reports index
            subprocess.run([
                VENV_PYTHON,
                str(WEB_DIR / 'generate_index.py')
            ], capture_output=True)

            return jsonify({
                'success': True,
                'message': 'Report generated successfully',
                'output': result.stdout
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Report generation failed',
                'output': result.stdout,
                'stderr': result.stderr
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Report generation timed out'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/species')
def get_species():
    """Get list of all species for species report selection"""
    try:
        import psycopg2

        conn = psycopg2.connect(
            host="192.168.1.25",
            port=5433,
            database="emsn",
            user="birdpi_zolder",
            password=os.getenv("EMSN_DB_PASSWORD", "REDACTED_DB_PASS")
        )
        cur = conn.cursor()

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

        species_list = [
            {
                'common_name': row[0],
                'scientific_name': row[1],
                'total_detections': row[2]
            }
            for row in cur.fetchall()
        ]

        cur.close()
        conn.close()

        return jsonify({'species': species_list})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/periods')
def get_periods():
    """Get available periods for comparison reports"""
    try:
        import psycopg2

        conn = psycopg2.connect(
            host="192.168.1.25",
            port=5433,
            database="emsn",
            user="birdpi_zolder",
            password=os.getenv("EMSN_DB_PASSWORD", "REDACTED_DB_PASS")
        )
        cur = conn.cursor()

        # Get available weeks
        cur.execute("""
            SELECT DISTINCT
                EXTRACT(YEAR FROM detection_timestamp)::int as year,
                EXTRACT(WEEK FROM detection_timestamp)::int as week
            FROM bird_detections
            ORDER BY year DESC, week DESC
            LIMIT 52
        """)
        weeks = [{'year': row[0], 'week': row[1], 'label': f'{row[0]}-W{row[1]:02d}'} for row in cur.fetchall()]

        # Get available months
        cur.execute("""
            SELECT DISTINCT
                EXTRACT(YEAR FROM detection_timestamp)::int as year,
                EXTRACT(MONTH FROM detection_timestamp)::int as month
            FROM bird_detections
            ORDER BY year DESC, month DESC
            LIMIT 24
        """)
        month_names = ['Jan', 'Feb', 'Mrt', 'Apr', 'Mei', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec']
        months = [{'year': row[0], 'month': row[1], 'label': f'{month_names[row[1]-1]} {row[0]}'} for row in cur.fetchall()]

        # Get available seasons
        cur.execute("""
            SELECT DISTINCT EXTRACT(YEAR FROM detection_timestamp)::int as year
            FROM bird_detections
            ORDER BY year DESC
        """)
        years = [row[0] for row in cur.fetchall()]
        seasons = []
        season_names = [('winter', 'Winter'), ('spring', 'Voorjaar'), ('summer', 'Zomer'), ('autumn', 'Herfst')]
        for year in years:
            for season_id, season_name in season_names:
                seasons.append({
                    'year': year,
                    'season': season_id,
                    'label': f'{season_name} {year}'
                })

        cur.close()
        conn.close()

        return jsonify({
            'weeks': weeks,
            'months': months,
            'seasons': seasons,
            'years': years
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# EMAIL MANAGEMENT API
# =============================================================================

def load_email_config():
    """Load email configuration from yaml file"""
    if not EMAIL_CONFIG_FILE.exists():
        return None
    with open(EMAIL_CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_email_config(config):
    """Save email configuration to yaml file"""
    with open(EMAIL_CONFIG_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def load_email_history():
    """Load email send history from JSON file"""
    import json
    if not EMAIL_LOG_FILE.exists():
        return []
    try:
        with open(EMAIL_LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def log_email_sent(report_file, recipients, status='success', error=None):
    """Log an email send event"""
    import json
    from datetime import datetime

    history = load_email_history()

    entry = {
        'timestamp': datetime.now().isoformat(),
        'report': report_file,
        'recipients': recipients if isinstance(recipients, list) else [recipients],
        'status': status,
        'error': error
    }

    # Add to beginning (newest first)
    history.insert(0, entry)

    # Keep only last 100 entries
    history = history[:100]

    with open(EMAIL_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    return entry


@app.route('/api/email/history')
def get_email_history():
    """Get email send history"""
    history = load_email_history()
    return jsonify({
        'history': history,
        'count': len(history)
    })


# =============================================================================
# EMAIL TRACKING & UNSUBSCRIBE
# =============================================================================

def generate_unsubscribe_token(email):
    """Generate a simple token for unsubscribe links"""
    import hashlib
    # Simple hash - not cryptographically secure but sufficient for this use case
    secret = "emsn2024vogelmonitoring"
    return hashlib.sha256(f"{email}:{secret}".encode()).hexdigest()[:16]


def verify_unsubscribe_token(email, token):
    """Verify an unsubscribe token"""
    return token == generate_unsubscribe_token(email)


def load_email_tracking():
    """Load email tracking data"""
    import json
    if not EMAIL_TRACKING_FILE.exists():
        return {'opens': [], 'clicks': []}
    try:
        with open(EMAIL_TRACKING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {'opens': [], 'clicks': []}


def log_email_open(email, report):
    """Log when an email is opened (via tracking pixel)"""
    import json
    from datetime import datetime

    tracking = load_email_tracking()
    tracking['opens'].append({
        'timestamp': datetime.now().isoformat(),
        'email': email,
        'report': report
    })
    # Keep last 500 entries
    tracking['opens'] = tracking['opens'][-500:]

    with open(EMAIL_TRACKING_FILE, 'w', encoding='utf-8') as f:
        json.dump(tracking, f, indent=2, ensure_ascii=False)


@app.route('/api/email/track/<report>/<email_hash>.gif')
def track_email_open(report, email_hash):
    """Tracking pixel endpoint - logs when email is opened"""
    from flask import Response

    # Log the open (we can't verify email here, just log the hash)
    try:
        tracking = load_email_tracking()
        from datetime import datetime
        tracking['opens'].append({
            'timestamp': datetime.now().isoformat(),
            'email_hash': email_hash,
            'report': report
        })
        tracking['opens'] = tracking['opens'][-500:]

        import json
        with open(EMAIL_TRACKING_FILE, 'w', encoding='utf-8') as f:
            json.dump(tracking, f, indent=2, ensure_ascii=False)
    except:
        pass

    # Return a 1x1 transparent GIF
    gif_data = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    return Response(gif_data, mimetype='image/gif')


@app.route('/api/email/tracking')
def get_email_tracking():
    """Get email tracking statistics"""
    tracking = load_email_tracking()

    # Aggregate opens by report
    opens_by_report = {}
    for entry in tracking.get('opens', []):
        report = entry.get('report', 'unknown')
        if report not in opens_by_report:
            opens_by_report[report] = {'count': 0, 'last_open': None}
        opens_by_report[report]['count'] += 1
        opens_by_report[report]['last_open'] = entry.get('timestamp')

    return jsonify({
        'total_opens': len(tracking.get('opens', [])),
        'opens_by_report': opens_by_report,
        'recent_opens': tracking.get('opens', [])[-20:]
    })


@app.route('/unsubscribe')
def unsubscribe_page():
    """Show unsubscribe confirmation page"""
    email = request.args.get('email', '')
    token = request.args.get('token', '')

    if not email or not token:
        return """
        <html><head><title>EMSN - Afmelden</title>
        <style>body{font-family:sans-serif;max-width:600px;margin:50px auto;padding:20px;}</style>
        </head><body>
        <h1>Ongeldige link</h1>
        <p>De afmeldlink is ongeldig of verlopen.</p>
        </body></html>
        """, 400

    if not verify_unsubscribe_token(email, token):
        return """
        <html><head><title>EMSN - Afmelden</title>
        <style>body{font-family:sans-serif;max-width:600px;margin:50px auto;padding:20px;}</style>
        </head><body>
        <h1>Ongeldige token</h1>
        <p>De afmeldlink is ongeldig. Neem contact op met emsn@ronnyhullegie.nl</p>
        </body></html>
        """, 400

    return f"""
    <html><head><title>EMSN - Afmelden</title>
    <style>
        body{{font-family:sans-serif;max-width:600px;margin:50px auto;padding:20px;text-align:center;}}
        .btn{{background:#22c55e;color:white;padding:15px 30px;border:none;border-radius:8px;font-size:16px;cursor:pointer;margin:10px;}}
        .btn-danger{{background:#ef4444;}}
        .btn:hover{{opacity:0.9;}}
    </style>
    </head><body>
    <h1>EMSN Vogelrapporten - Afmelden</h1>
    <p>Wilt u zich afmelden voor automatische rapportverzending?</p>
    <p><strong>{email}</strong></p>
    <form method="POST" action="/api/email/unsubscribe">
        <input type="hidden" name="email" value="{email}">
        <input type="hidden" name="token" value="{token}">
        <button type="submit" class="btn btn-danger">Ja, afmelden</button>
        <a href="/" class="btn" style="text-decoration:none;display:inline-block;">Annuleren</a>
    </form>
    <p style="margin-top:30px;color:#666;font-size:14px;">
        U kunt zich later opnieuw aanmelden via de beheerder.
    </p>
    </body></html>
    """


@app.route('/api/email/unsubscribe', methods=['POST'])
def process_unsubscribe():
    """Process unsubscribe request"""
    email = request.form.get('email', '')
    token = request.form.get('token', '')

    if not email or not verify_unsubscribe_token(email, token):
        return """
        <html><head><title>EMSN - Fout</title>
        <style>body{font-family:sans-serif;max-width:600px;margin:50px auto;padding:20px;}</style>
        </head><body>
        <h1>Fout</h1>
        <p>Ongeldige afmeldverzoek.</p>
        </body></html>
        """, 400

    # Update recipient to manual mode
    config = load_email_config()
    if config:
        recipients = config.get('recipients', [])
        for r in recipients:
            if isinstance(r, dict) and r.get('email', '').lower() == email.lower():
                r['mode'] = 'manual'
                r['unsubscribed_at'] = datetime.now().isoformat()
                break

        save_email_config(config)

        # Log the unsubscribe
        log_email_sent(
            'UNSUBSCRIBE',
            [email],
            status='unsubscribed',
            error=None
        )

    return f"""
    <html><head><title>EMSN - Afgemeld</title>
    <style>
        body{{font-family:sans-serif;max-width:600px;margin:50px auto;padding:20px;text-align:center;}}
        .success{{color:#22c55e;font-size:48px;}}
    </style>
    </head><body>
    <div class="success">✓</div>
    <h1>Uitgeschreven</h1>
    <p>U bent afgemeld voor automatische EMSN vogelrapporten.</p>
    <p><strong>{email}</strong></p>
    <p style="margin-top:30px;color:#666;">
        U ontvangt geen automatische rapporten meer.<br>
        U kunt nog wel handmatig rapporten ontvangen van de beheerder.
    </p>
    </body></html>
    """


def get_email_footer(recipient_email, report_name):
    """Generate email footer with unsubscribe link and tracking pixel"""
    token = generate_unsubscribe_token(recipient_email)
    email_hash = generate_unsubscribe_token(recipient_email)[:8]

    unsubscribe_url = f"{BASE_URL}/unsubscribe?email={recipient_email}&token={token}"
    tracking_url = f"{BASE_URL}/api/email/track/{report_name}/{email_hash}.gif"

    footer = f"""

---

U ontvangt deze email omdat u zich heeft aangemeld voor EMSN vogelrapporten.
Wilt u geen automatische rapporten meer ontvangen? Klik hier om af te melden:
{unsubscribe_url}

EMSN Vogelmonitoring Nijverdal | www.ronnyhullegie.nl

<img src="{tracking_url}" width="1" height="1" alt="">
"""
    return footer


@app.route('/api/email/recipients')
def get_email_recipients():
    """Get list of all email recipients with their settings"""
    config = load_email_config()
    if not config:
        return jsonify({'error': 'Email config not found'}), 500

    recipients = config.get('recipients', [])
    # Handle old format (list of strings) vs new format (list of dicts)
    formatted_recipients = []
    for r in recipients:
        if isinstance(r, str):
            # Old format - convert to new
            formatted_recipients.append({
                'email': r,
                'name': '',
                'mode': 'auto',
                'style': 'wetenschappelijk',
                'report_types': ['weekly', 'monthly', 'seasonal', 'yearly']
            })
        else:
            # Ensure style field exists
            if 'style' not in r:
                r['style'] = 'wetenschappelijk'
            formatted_recipients.append(r)

    return jsonify({
        'recipients': formatted_recipients,
        'smtp_configured': bool(config.get('smtp', {}).get('host'))
    })


@app.route('/api/email/recipients', methods=['POST'])
def add_or_update_recipient():
    """Add or update an email recipient"""
    data = request.json
    email = data.get('email', '').strip().lower()

    if not email or '@' not in email:
        return jsonify({'error': 'Ongeldig e-mailadres'}), 400

    config = load_email_config()
    if not config:
        return jsonify({'error': 'Email config not found'}), 500

    recipients = config.get('recipients', [])

    # Convert old format if needed
    new_recipients = []
    for r in recipients:
        if isinstance(r, str):
            new_recipients.append({
                'email': r,
                'name': '',
                'mode': 'auto',
                'report_types': ['weekly', 'monthly', 'seasonal', 'yearly']
            })
        else:
            new_recipients.append(r)

    # Check if recipient exists
    existing_idx = None
    for i, r in enumerate(new_recipients):
        if r.get('email', '').lower() == email:
            existing_idx = i
            break

    new_recipient = {
        'email': email,
        'name': data.get('name', ''),
        'mode': data.get('mode', 'auto'),
        'style': data.get('style', 'wetenschappelijk'),
        'report_types': data.get('report_types', ['weekly', 'monthly', 'seasonal', 'yearly'])
    }

    if existing_idx is not None:
        new_recipients[existing_idx] = new_recipient
        message = f'Ontvanger {email} bijgewerkt'
    else:
        new_recipients.append(new_recipient)
        message = f'Ontvanger {email} toegevoegd'

    config['recipients'] = new_recipients
    save_email_config(config)

    return jsonify({'success': True, 'message': message})


@app.route('/api/email/recipients/<path:email>', methods=['DELETE'])
def delete_recipient(email):
    """Delete an email recipient"""
    email = email.strip().lower()

    config = load_email_config()
    if not config:
        return jsonify({'error': 'Email config not found'}), 500

    recipients = config.get('recipients', [])

    # Filter out the recipient
    new_recipients = []
    found = False
    for r in recipients:
        r_email = r.get('email', r) if isinstance(r, dict) else r
        if r_email.lower() != email:
            new_recipients.append(r)
        else:
            found = True

    if not found:
        return jsonify({'error': f'Ontvanger {email} niet gevonden'}), 404

    config['recipients'] = new_recipients
    save_email_config(config)

    return jsonify({'success': True, 'message': f'Ontvanger {email} verwijderd'})


@app.route('/api/email/send-copy', methods=['POST'])
def send_report_copy():
    """Send a copy of an existing report to specified recipients"""
    data = request.json
    report_file = data.get('report')
    recipient_emails = data.get('recipients', [])

    if not report_file:
        return jsonify({'error': 'Geen rapport opgegeven'}), 400

    if not recipient_emails:
        return jsonify({'error': 'Geen ontvangers opgegeven'}), 400

    # Check if report exists
    report_path = REPORTS_DIR / report_file
    if not report_path.exists():
        return jsonify({'error': f'Rapport niet gevonden: {report_file}'}), 404

    # Load email config
    config = load_email_config()
    if not config:
        return jsonify({'error': 'Email config not found'}), 500

    smtp_password = os.getenv('EMSN_SMTP_PASSWORD')
    if not smtp_password:
        return jsonify({'error': 'SMTP wachtwoord niet geconfigureerd'}), 500

    # Read report content
    with open(report_path, 'r', encoding='utf-8') as f:
        report_content = f.read()

    # Extract title from frontmatter or filename
    title = report_file.replace('.md', '')
    if report_content.startswith('---'):
        try:
            frontmatter_end = report_content.index('---', 3)
            frontmatter = yaml.safe_load(report_content[3:frontmatter_end])
            if frontmatter.get('type') == 'weekrapport':
                title = f"Weekrapport Week {frontmatter.get('week', '')} - {frontmatter.get('year', '')}"
            elif frontmatter.get('type') == 'maandrapport':
                title = f"Maandrapport {frontmatter.get('month', '')} {frontmatter.get('year', '')}"
        except:
            pass

    # Create email
    smtp_config = config.get('smtp', {})
    email_config = config.get('email', {})

    try:
        msg = MIMEMultipart('mixed')
        msg['Subject'] = f"EMSN Rapport: {title}"
        msg['From'] = f"{email_config.get('from_name', 'EMSN')} <{email_config.get('from_address', smtp_config.get('username'))}>"
        msg['To'] = ', '.join(recipient_emails)

        # Email body with personalized footer per recipient
        base_body = f"""Beste vogelliefhebber,

Hierbij ontvangt u het EMSN vogelrapport: {title}

Dit rapport is gegenereerd door het Ecologisch Monitoring Systeem Nijverdal (EMSN),
een citizen science project voor het monitoren van de lokale vogelpopulatie in
Nijverdal en omgeving. Met behulp van BirdNET-Pi wordt 24/7 de vogelactiviteit
geregistreerd via geluidsherkenning.

Het rapport bevat:
- Overzicht van waargenomen vogelsoorten
- Activiteitspatronen en trends
- Bijzondere waarnemingen

Het volledige rapport is als PDF bijgevoegd.

Heeft u vragen of opmerkingen? Neem gerust contact op.

Met vriendelijke groet,

Ronny Hullegie
EMSN Vogelmonitoring Nijverdal
https://www.ronnyhullegie.nl
"""
        # Add unsubscribe footer for first recipient (simplified - same email to all)
        report_name = report_file.replace('.md', '').replace(' ', '_')
        footer = get_email_footer(recipient_emails[0], report_name)
        body = base_body + footer

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Generate PDF from markdown with EMSN logo
        pdf_filename = report_file.replace('.md', '.pdf')
        pdf_path = REPORTS_DIR / pdf_filename

        try:
            # Create PDF with logo using helper function
            success, error = generate_pdf_with_logo(report_path, pdf_path, title=title)

            if not success:
                return jsonify({'error': f'PDF generatie mislukt: {error}'}), 500

            # Read PDF and attach
            with open(pdf_path, 'rb') as pdf_file:
                attachment = MIMEApplication(pdf_file.read(), _subtype='pdf')
                attachment['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
                msg.attach(attachment)

        except Exception as e:
            return jsonify({'error': f'PDF generatie fout: {str(e)}'}), 500

        # Send email
        server = smtplib.SMTP(smtp_config.get('host'), smtp_config.get('port', 587))
        if smtp_config.get('use_tls', True):
            server.starttls()
        server.login(smtp_config.get('username'), smtp_password)
        server.sendmail(
            email_config.get('from_address', smtp_config.get('username')),
            recipient_emails,
            msg.as_string()
        )
        server.quit()

        # Log successful send
        log_email_sent(report_file, recipient_emails, status='success')

        return jsonify({
            'success': True,
            'message': f'Rapport verstuurd naar {len(recipient_emails)} ontvanger(s)'
        })

    except smtplib.SMTPAuthenticationError:
        log_email_sent(report_file, recipient_emails, status='failed', error='SMTP authenticatie mislukt')
        return jsonify({'error': 'SMTP authenticatie mislukt'}), 500
    except Exception as e:
        log_email_sent(report_file, recipient_emails, status='failed', error=str(e))
        return jsonify({'error': f'Verzenden mislukt: {str(e)}'}), 500


@app.route('/api/email/test', methods=['POST'])
def test_email():
    """Send a test email to verify configuration"""
    data = request.json
    test_email = data.get('email', '').strip()

    if not test_email or '@' not in test_email:
        return jsonify({'error': 'Ongeldig e-mailadres'}), 400

    config = load_email_config()
    if not config:
        return jsonify({'error': 'Email config not found'}), 500

    smtp_password = os.getenv('EMSN_SMTP_PASSWORD')
    if not smtp_password:
        return jsonify({'error': 'SMTP wachtwoord niet geconfigureerd (EMSN_SMTP_PASSWORD)'}), 500

    smtp_config = config.get('smtp', {})
    email_config = config.get('email', {})

    try:
        msg = MIMEText("""Dit is een testbericht van EMSN Vogelmonitoring.

Als u deze e-mail ontvangt, is de e-mailconfiguratie correct ingesteld.

Met vriendelijke groet,
EMSN Vogelmonitoring Nijverdal
""", 'plain', 'utf-8')
        msg['Subject'] = "EMSN Test E-mail"
        msg['From'] = f"{email_config.get('from_name', 'EMSN')} <{email_config.get('from_address', smtp_config.get('username'))}>"
        msg['To'] = test_email

        server = smtplib.SMTP(smtp_config.get('host'), smtp_config.get('port', 587))
        if smtp_config.get('use_tls', True):
            server.starttls()
        server.login(smtp_config.get('username'), smtp_password)
        server.sendmail(
            email_config.get('from_address', smtp_config.get('username')),
            [test_email],
            msg.as_string()
        )
        server.quit()

        return jsonify({'success': True, 'message': f'Test e-mail verstuurd naar {test_email}'})

    except smtplib.SMTPAuthenticationError:
        return jsonify({'error': 'SMTP authenticatie mislukt - controleer wachtwoord'}), 500
    except Exception as e:
        return jsonify({'error': f'Verzenden mislukt: {str(e)}'}), 500


# =============================================================================
# REPORT DATA API
# =============================================================================

@app.route('/api/report-data')
def get_report_data():
    """Get parsed data from a report for interactive display"""
    filename = request.args.get('file')
    if not filename:
        return jsonify({'error': 'No file specified'}), 400

    report_path = REPORTS_DIR / filename
    if not report_path.exists():
        return jsonify({'error': 'Report not found'}), 404

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse YAML frontmatter
        data = {}
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                import yaml
                frontmatter = yaml.safe_load(parts[1])
                if frontmatter:
                    data = frontmatter

        # Parse top species from markdown
        import re
        species_match = re.search(r'### Top 10 Soorten\n([\s\S]*?)(?=\n###|\n---|\n##|$)', content)
        if species_match:
            species_data = []
            for line in species_match.group(1).strip().split('\n'):
                match = re.match(r'^\d+\.\s*\*\*([^*]+)\*\*:\s*([\d,]+)\s*detecties', line)
                if match:
                    species_data.append({
                        'name': match.group(1),
                        'count': int(match.group(2).replace(',', ''))
                    })
            data['top_species'] = species_data

        # Parse hourly activity if present
        hourly_match = re.search(r'Drukste uur:\s*(\d+):00-\d+:00\s*\(([,\d]+)\s*detecties\)', content)
        if hourly_match:
            data['busiest_hour'] = int(hourly_match.group(1))
            data['busiest_hour_count'] = int(hourly_match.group(2).replace(',', ''))

        return jsonify({'data': data})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# SCHEDULE API
# =============================================================================

@app.route('/api/schedule')
def get_schedule():
    """Get the current report generation schedule from systemd timers"""
    try:
        result = subprocess.run(
            ['systemctl', 'list-timers', '--all', '--no-pager'],
            capture_output=True, text=True
        )

        schedules = []
        for line in result.stdout.split('\n'):
            if 'emsn-' in line and 'report' in line:
                parts = line.split()
                if len(parts) >= 8:
                    # Parse the timer info
                    next_run = ' '.join(parts[0:4]) if parts[0] != '-' else 'Niet gepland'
                    timer_name = parts[-2] if parts[-2].endswith('.timer') else parts[-1]

                    # Map timer names to readable names
                    timer_map = {
                        'emsn-weekly-report.timer': ('Weekrapport', 'Elke maandag 07:00'),
                        'emsn-monthly-report.timer': ('Maandrapport', '1e van de maand 08:00'),
                        'emsn-yearly-report.timer': ('Jaarrapport', '2 januari 08:00'),
                        'emsn-seasonal-report-winter.timer': ('Seizoensrapport Winter', '1 maart 07:00'),
                        'emsn-seasonal-report-spring.timer': ('Seizoensrapport Voorjaar', '1 juni 07:00'),
                        'emsn-seasonal-report-summer.timer': ('Seizoensrapport Zomer', '1 september 07:00'),
                        'emsn-seasonal-report-autumn.timer': ('Seizoensrapport Herfst', '1 december 07:00'),
                    }

                    name, schedule = timer_map.get(timer_name, (timer_name, 'Onbekend'))
                    schedules.append({
                        'name': name,
                        'schedule': schedule,
                        'next_run': next_run,
                        'timer': timer_name,
                        'active': 'active' in line.lower()
                    })

        return jsonify({'schedules': schedules})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schedule/history')
def get_generation_history():
    """Get recent report generation history from systemd journal"""
    try:
        # Get journal entries for report services
        result = subprocess.run([
            'journalctl', '-u', 'emsn-*-report.service',
            '--since', '7 days ago',
            '--no-pager', '-q',
            '-o', 'json'
        ], capture_output=True, text=True, timeout=10)

        history = []

        # Also check recent report files as a simpler approach
        if REPORTS_DIR.exists():
            import json as json_module
            from datetime import datetime

            reports = sorted(REPORTS_DIR.glob('*.md'), key=lambda x: x.stat().st_mtime, reverse=True)[:10]
            for report in reports:
                stat = report.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime)

                # Determine report type from filename
                filename = report.name
                if 'Weekrapport' in filename:
                    report_type = 'Weekrapport'
                elif 'Maandrapport' in filename:
                    report_type = 'Maandrapport'
                elif 'Seizoensrapport' in filename or 'Seasonal' in filename:
                    report_type = 'Seizoensrapport'
                elif 'Jaaroverzicht' in filename or 'Yearly' in filename:
                    report_type = 'Jaarrapport'
                else:
                    report_type = 'Rapport'

                history.append({
                    'filename': filename,
                    'type': report_type,
                    'generated': mtime.strftime('%Y-%m-%d %H:%M'),
                    'size': f'{stat.st_size / 1024:.1f} KB',
                    'status': 'success'
                })

        return jsonify({'history': history})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schedule/quick-generate', methods=['POST'])
def quick_generate():
    """Quick generate a report with predefined settings"""
    data = request.json
    action = data.get('action')

    if not action:
        return jsonify({'error': 'Action required'}), 400

    env = os.environ.copy()
    env['ANTHROPIC_API_KEY'] = os.getenv('ANTHROPIC_API_KEY', '')
    env['EMSN_DB_PASSWORD'] = os.getenv('EMSN_DB_PASSWORD', 'REDACTED_DB_PASS')
    env['EMSN_SMTP_PASSWORD'] = os.getenv('EMSN_SMTP_PASSWORD', '')

    # Map action to command
    if action == 'week':
        script = SCRIPTS_DIR / 'weekly_report.py'
        cmd = [VENV_PYTHON, str(script)]
    elif action == 'week-kort':
        script = SCRIPTS_DIR / 'weekly_report.py'
        cmd = [VENV_PYTHON, str(script), '--format', 'kort']
    elif action == 'week-spectrograms':
        script = SCRIPTS_DIR / 'weekly_report.py'
        cmd = [VENV_PYTHON, str(script), '--spectrograms']
    elif action == 'month':
        script = SCRIPTS_DIR / 'monthly_report.py'
        cmd = [VENV_PYTHON, str(script)]
    elif action == 'season':
        script = SCRIPTS_DIR / 'seasonal_report.py'
        cmd = [VENV_PYTHON, str(script)]
    else:
        return jsonify({'error': f'Unknown action: {action}'}), 400

    if not script.exists():
        return jsonify({'error': f'Script not found: {script.name}'}), 404

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300
        )

        # Refresh index
        subprocess.run([
            VENV_PYTHON,
            str(WEB_DIR / 'generate_index.py')
        ], capture_output=True)

        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': f'Rapport succesvol gegenereerd',
                'output': result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Generatie mislukt',
                'output': result.stdout,
                'stderr': result.stderr
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout - rapport generatie duurde te lang'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# PENDING REPORTS - Review Workflow API
# =============================================================================

import psycopg2
from psycopg2.extras import RealDictCursor
import json

DB_CONFIG = {
    "host": "192.168.1.25",
    "port": 5433,
    "database": "emsn",
    "user": "birdpi_zolder",
    "password": os.environ.get("EMSN_DB_PASSWORD", "REDACTED_DB_PASS")
}


def get_db_connection():
    """Get database connection for pending reports"""
    return psycopg2.connect(**DB_CONFIG)


@app.route('/api/pending')
def get_pending_reports():
    """Get all pending reports awaiting review"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT
                id,
                report_type,
                report_title,
                report_filename,
                markdown_path,
                pdf_path,
                status,
                created_at,
                expires_at,
                custom_text,
                reviewer_notes,
                notification_sent,
                CASE
                    WHEN expires_at IS NOT NULL THEN
                        ROUND(EXTRACT(EPOCH FROM (expires_at - NOW())) / 3600, 1)
                    ELSE NULL
                END as hours_until_expiry
            FROM pending_reports
            WHERE status = 'pending'
            ORDER BY created_at DESC
        """)

        reports = cur.fetchall()

        # Convert datetime objects to strings
        for r in reports:
            if r['created_at']:
                r['created_at'] = r['created_at'].isoformat()
            if r['expires_at']:
                r['expires_at'] = r['expires_at'].isoformat()

        cur.close()
        conn.close()

        return jsonify({
            'pending_reports': reports,
            'count': len(reports)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pending/<int:report_id>')
def get_pending_report(report_id):
    """Get a specific pending report by ID"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT * FROM pending_reports WHERE id = %s
        """, (report_id,))

        report = cur.fetchone()
        cur.close()
        conn.close()

        if not report:
            return jsonify({'error': 'Report not found'}), 404

        # Convert datetime objects
        for key in ['created_at', 'expires_at', 'reviewed_at', 'sent_at', 'notification_sent_at']:
            if report.get(key):
                report[key] = report[key].isoformat()

        # Load markdown content
        md_path = Path(report['markdown_path'])
        if md_path.exists():
            with open(md_path, 'r', encoding='utf-8') as f:
                report['markdown_content'] = f.read()
        else:
            report['markdown_content'] = None

        return jsonify(report)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pending/<int:report_id>/preview')
def preview_pending_report(report_id):
    """Get markdown content for preview (raw or with custom text inserted)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT markdown_path, custom_text, custom_text_position
            FROM pending_reports WHERE id = %s
        """, (report_id,))

        report = cur.fetchone()
        cur.close()
        conn.close()

        if not report:
            return jsonify({'error': 'Report not found'}), 404

        md_path = Path(report['markdown_path'])
        if not md_path.exists():
            return jsonify({'error': 'Markdown file not found'}), 404

        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # If custom_text exists, show where it will be inserted
        if report['custom_text']:
            position = report['custom_text_position'] or 'after_intro'
            custom_block = f"\n\n---\n\n**Persoonlijke notitie:**\n\n{report['custom_text']}\n\n---\n\n"

            # Insert at appropriate position (simplified for now)
            if position == 'after_intro':
                # Find first ## heading and insert after its paragraph
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith('## ') and i > 10:  # Skip title area
                        content = '\n'.join(lines[:i]) + custom_block + '\n'.join(lines[i:])
                        break

        return jsonify({
            'content': content,
            'has_custom_text': bool(report['custom_text'])
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pending/<int:report_id>/update', methods=['POST'])
def update_pending_report(report_id):
    """Update custom text or reviewer notes for a pending report"""
    try:
        data = request.json
        custom_text = data.get('custom_text', '').strip()
        reviewer_notes = data.get('reviewer_notes', '').strip()
        custom_text_position = data.get('custom_text_position', 'after_intro')

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE pending_reports
            SET custom_text = %s,
                reviewer_notes = %s,
                custom_text_position = %s
            WHERE id = %s AND status = 'pending'
            RETURNING id
        """, (custom_text or None, reviewer_notes or None, custom_text_position, report_id))

        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        if not result:
            return jsonify({'error': 'Report not found or already processed'}), 404

        return jsonify({
            'success': True,
            'message': 'Rapport bijgewerkt'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def send_approved_report_emails(report_file, report_title, report_type):
    """Send approved report to all auto-mode recipients for this report type"""
    results = {'sent_count': 0, 'failed_count': 0, 'recipients': []}

    # Map report_type to recipient report_types
    type_map = {
        'weekly': 'weekly',
        'monthly': 'monthly',
        'seasonal': 'seasonal',
        'yearly': 'yearly'
    }
    recipient_type = type_map.get(report_type, report_type)

    # Load email config
    config = load_email_config()
    if not config:
        return results

    smtp_password = os.getenv('EMSN_SMTP_PASSWORD')
    if not smtp_password:
        return results

    # Get auto-mode recipients for this report type
    recipients = config.get('recipients', [])
    auto_recipients = []
    for r in recipients:
        if isinstance(r, dict):
            if r.get('mode') == 'auto' and recipient_type in r.get('report_types', []):
                auto_recipients.append(r)
        elif isinstance(r, str):
            # Old format - include all
            auto_recipients.append({'email': r, 'name': ''})

    if not auto_recipients:
        return results

    # Check if report exists
    report_path = REPORTS_DIR / report_file
    if not report_path.exists():
        return results

    # Read report content
    with open(report_path, 'r', encoding='utf-8') as f:
        report_content = f.read()

    smtp_config = config.get('smtp', {})
    email_config = config.get('email', {})

    # Generate PDF once
    pdf_filename = report_file.replace('.md', '.pdf')
    pdf_path = REPORTS_DIR / pdf_filename

    try:
        success, error = generate_pdf_with_logo(report_path, pdf_path, title=report_title)
        if not success:
            print(f"PDF generation failed: {error}")
            return results
    except Exception as e:
        print(f"PDF generation error: {e}")
        return results

    # Read PDF for attachment
    with open(pdf_path, 'rb') as pdf_file:
        pdf_data = pdf_file.read()

    # Send to each recipient
    for recipient in auto_recipients:
        email_addr = recipient.get('email') if isinstance(recipient, dict) else recipient
        name = recipient.get('name', '') if isinstance(recipient, dict) else ''

        try:
            msg = MIMEMultipart('mixed')
            msg['Subject'] = f"EMSN Rapport: {report_title}"
            msg['From'] = f"{email_config.get('from_name', 'EMSN')} <{email_config.get('from_address', smtp_config.get('username'))}>"
            msg['To'] = email_addr

            # Email body
            greeting = f"Beste {name}" if name else "Beste vogelliefhebber"
            body = f"""{greeting},

Hierbij ontvangt u het EMSN vogelrapport: {report_title}

Dit rapport is gegenereerd door het Ecologisch Monitoring Systeem Nijverdal (EMSN),
een citizen science project voor het monitoren van de lokale vogelpopulatie in
Nijverdal en omgeving. Met behulp van BirdNET-Pi wordt 24/7 de vogelactiviteit
geregistreerd via geluidsherkenning.

Het volledige rapport is als PDF bijgevoegd.

Met vriendelijke groet,

Ronny Hullegie
EMSN Vogelmonitoring Nijverdal
https://www.ronnyhullegie.nl
"""
            report_name = report_file.replace('.md', '').replace(' ', '_')
            footer = get_email_footer(email_addr, report_name)
            body += footer

            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # Attach PDF
            attachment = MIMEApplication(pdf_data, _subtype='pdf')
            attachment['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
            msg.attach(attachment)

            # Send
            server = smtplib.SMTP(smtp_config.get('host'), smtp_config.get('port', 587))
            if smtp_config.get('use_tls', True):
                server.starttls()
            server.login(smtp_config.get('username'), smtp_password)
            server.sendmail(
                email_config.get('from_address', smtp_config.get('username')),
                [email_addr],
                msg.as_string()
            )
            server.quit()

            results['sent_count'] += 1
            results['recipients'].append({'email': email_addr, 'status': 'success'})

            # Log successful send
            log_email_sent(report_file, [email_addr], status='success')

        except Exception as e:
            results['failed_count'] += 1
            results['recipients'].append({'email': email_addr, 'status': 'failed', 'error': str(e)})
            log_email_sent(report_file, [email_addr], status='failed', error=str(e))

    return results


@app.route('/api/pending/<int:report_id>/approve', methods=['POST'])
def approve_pending_report(report_id):
    """Approve a pending report and trigger sending"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get report details
        cur.execute("""
            SELECT * FROM pending_reports WHERE id = %s AND status = 'pending'
        """, (report_id,))
        report = cur.fetchone()

        if not report:
            cur.close()
            conn.close()
            return jsonify({'error': 'Report not found or already processed'}), 404

        # Update status to approved
        cur.execute("""
            UPDATE pending_reports
            SET status = 'approved', reviewed_at = NOW()
            WHERE id = %s
            RETURNING id
        """, (report_id,))

        conn.commit()
        cur.close()
        conn.close()

        # Get report file info
        report_file = report['report_filename']
        report_title = report['report_title']
        report_type = report['report_type']
        custom_text = report.get('custom_text')
        custom_text_position = report.get('custom_text_position', 'after_intro')

        # Insert custom text into markdown if present
        if custom_text:
            md_path = Path(report['markdown_path'])
            if md_path.exists():
                with open(md_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                custom_block = f"\n\n---\n\n**Persoonlijke notitie:**\n\n{custom_text}\n\n---\n\n"

                # Insert at appropriate position
                if custom_text_position == 'after_intro':
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith('## ') and i > 10:
                            content = '\n'.join(lines[:i]) + custom_block + '\n'.join(lines[i:])
                            break
                elif custom_text_position == 'before_intro':
                    # Insert after frontmatter
                    if '---' in content:
                        parts = content.split('---', 2)
                        if len(parts) >= 3:
                            content = parts[0] + '---' + parts[1] + '---' + custom_block + parts[2]
                elif custom_text_position == 'before_conclusion':
                    # Insert before last ## section
                    lines = content.split('\n')
                    last_section = len(lines) - 1
                    for i in range(len(lines) - 1, -1, -1):
                        if lines[i].startswith('## '):
                            last_section = i
                            break
                    content = '\n'.join(lines[:last_section]) + custom_block + '\n'.join(lines[last_section:])
                else:  # after_conclusion - append at end
                    content = content + custom_block

                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(content)

        # Send email to all auto-mode recipients for this report type
        email_results = send_approved_report_emails(report_file, report_title, report_type)

        # Update sent_at in database
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE pending_reports
            SET sent_at = NOW()
            WHERE id = %s
        """, (report_id,))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f"Rapport '{report_title}' goedgekeurd en verzonden naar {email_results['sent_count']} ontvanger(s).",
            'email_results': email_results
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pending/<int:report_id>/reject', methods=['POST'])
def reject_pending_report(report_id):
    """Reject a pending report (won't be sent)"""
    try:
        data = request.json
        reason = data.get('reason', '').strip()

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE pending_reports
            SET status = 'rejected',
                reviewed_at = NOW(),
                reviewer_notes = COALESCE(reviewer_notes || E'\n\nAfgewezen: ', 'Afgewezen: ') || %s
            WHERE id = %s AND status = 'pending'
            RETURNING id
        """, (reason or 'Geen reden opgegeven', report_id))

        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        if not result:
            return jsonify({'error': 'Report not found or already processed'}), 404

        return jsonify({
            'success': True,
            'message': 'Rapport afgewezen en zal niet worden verzonden'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pending/history')
def get_pending_history():
    """Get history of all processed pending reports"""
    try:
        limit = request.args.get('limit', 20, type=int)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT
                id,
                report_type,
                report_title,
                report_filename,
                status,
                created_at,
                reviewed_at,
                sent_at,
                reviewer_notes
            FROM pending_reports
            WHERE status != 'pending'
            ORDER BY COALESCE(reviewed_at, created_at) DESC
            LIMIT %s
        """, (limit,))

        reports = cur.fetchall()

        for r in reports:
            for key in ['created_at', 'reviewed_at', 'sent_at']:
                if r.get(key):
                    r[key] = r[key].isoformat()

        cur.close()
        conn.close()

        return jsonify({
            'history': reports,
            'count': len(reports)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Helper function to create a pending report (called from report generators)
def create_pending_report(report_type, report_title, report_filename, markdown_path,
                          pdf_path=None, expires_hours=24, report_data=None,
                          send_notification=True):
    """
    Create a new pending report entry.

    Args:
        report_type: 'weekly', 'monthly', 'seasonal', 'yearly'
        report_title: Human-readable title
        report_filename: Filename (e.g., '2025-W51-Weekrapport.md')
        markdown_path: Full path to markdown file
        pdf_path: Full path to PDF file (optional)
        expires_hours: Hours until auto-approval (None for no expiry)
        report_data: Dict with additional metadata (stored as JSONB)
        send_notification: Whether to send Ulanzi + email notification

    Returns: pending report ID
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        expires_at = None
        if expires_hours:
            cur.execute("SELECT NOW() + INTERVAL '%s hours'", (expires_hours,))
            expires_at = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO pending_reports
            (report_type, report_title, report_filename, markdown_path, pdf_path,
             expires_at, report_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            report_type,
            report_title,
            report_filename,
            str(markdown_path),
            str(pdf_path) if pdf_path else None,
            expires_at,
            json.dumps(report_data) if report_data else None
        ))

        report_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        # Send notification
        if send_notification and report_id:
            send_pending_report_notification(report_id, report_type, report_title)

        return report_id

    except Exception as e:
        print(f"ERROR creating pending report: {e}")
        return None


# =============================================================================
# NOTIFICATION FUNCTIONS
# =============================================================================

import requests

ULANZI_IP = "192.168.1.11"
ULANZI_API = f"http://{ULANZI_IP}/api"


def send_ulanzi_notification(text, color="#FFAA00", duration=20, icon=None):
    """
    Send a notification to the Ulanzi TC001 display.

    Args:
        text: Text to display
        color: Hex color for text
        duration: Duration in seconds
        icon: Icon name or number (optional)
    """
    try:
        payload = {
            "text": text,
            "color": color,
            "duration": duration * 10,  # AWTRIX uses deciseconds
            "scrollSpeed": 80,
            "stack": True,  # Queue if another notification is showing
        }

        if icon:
            payload["icon"] = icon

        response = requests.post(
            f"{ULANZI_API}/notify",
            json=payload,
            timeout=5
        )
        return response.status_code == 200

    except requests.exceptions.RequestException as e:
        print(f"Ulanzi notification failed: {e}")
        return False


def send_pending_report_email_notification(report_type, report_title, review_url):
    """Send email notification about pending report"""
    try:
        config = load_email_config()
        if not config:
            return False

        smtp_password = os.getenv('EMSN_SMTP_PASSWORD')
        if not smtp_password:
            return False

        smtp_config = config.get('smtp', {})
        email_config = config.get('email', {})

        # Send to admin email (first recipient or default)
        admin_email = email_config.get('admin_email', 'ronny@ronnyhullegie.nl')

        type_labels = {
            'weekly': 'Weekrapport',
            'monthly': 'Maandrapport',
            'seasonal': 'Seizoensrapport',
            'yearly': 'Jaarrapport'
        }
        type_label = type_labels.get(report_type, report_type)

        msg = MIMEText(f"""Beste Ronny,

Er staat een nieuw {type_label} klaar voor review:

{report_title}

Je kunt het rapport bekijken en goedkeuren via:
{review_url}

Als je het rapport niet binnen 24 uur beoordeelt, wordt het automatisch goedgekeurd en verzonden.

Met vriendelijke groet,
EMSN Vogelmonitoring
""", 'plain', 'utf-8')

        msg['Subject'] = f"EMSN: Nieuw {type_label} wacht op review"
        msg['From'] = f"{email_config.get('from_name', 'EMSN')} <{email_config.get('from_address', smtp_config.get('username'))}>"
        msg['To'] = admin_email

        server = smtplib.SMTP(smtp_config.get('host'), smtp_config.get('port', 587))
        if smtp_config.get('use_tls', True):
            server.starttls()
        server.login(smtp_config.get('username'), smtp_password)
        server.sendmail(
            email_config.get('from_address', smtp_config.get('username')),
            [admin_email],
            msg.as_string()
        )
        server.quit()

        return True

    except Exception as e:
        print(f"Email notification failed: {e}")
        return False


def send_pending_report_notification(report_id, report_type, report_title):
    """
    Send notifications (Ulanzi + Email) about a new pending report.
    Updates the notification_sent flag in database.
    """
    try:
        type_labels = {
            'weekly': 'Weekrapport',
            'monthly': 'Maandrapport',
            'seasonal': 'Seizoen',
            'yearly': 'Jaarrapport'
        }
        type_label = type_labels.get(report_type, 'Rapport')

        # Send to Ulanzi display
        ulanzi_text = f"Nieuw {type_label} wacht op review"
        ulanzi_success = send_ulanzi_notification(
            text=ulanzi_text,
            color="#FFAA00",  # Orange/amber for attention
            duration=30,
            icon="4886"  # Document/clipboard icon
        )

        # Generate review URL
        review_url = "http://192.168.1.25/rapporten/#review"

        # Send email notification
        email_success = send_pending_report_email_notification(
            report_type, report_title, review_url
        )

        # Update notification status in database
        if ulanzi_success or email_success:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE pending_reports
                    SET notification_sent = TRUE,
                        notification_sent_at = NOW()
                    WHERE id = %s
                """, (report_id,))
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"Failed to update notification status: {e}")

        return ulanzi_success or email_success

    except Exception as e:
        print(f"Notification error: {e}")
        return False


# =============================================================================
# MANUAL BIRD DETECTION API - Home Assistant Integration
# =============================================================================

@app.route('/api/manual-detection', methods=['POST'])
def add_manual_detection():
    """
    Add a manually observed bird detection from Home Assistant.

    Expected JSON payload:
    {
        "common_name": "Ekster",
        "scientific_name": "Pica pica",  # Optional, will be looked up if not provided
        "timestamp": "2025-12-17T14:30:00",  # Optional, defaults to now
        "signal_quality": "duidelijk",  # duidelijk, zwak, ver_weg
        "notes": "Vloog over de tuin"  # Optional
    }
    """
    try:
        data = request.json

        if not data:
            return jsonify({'error': 'Geen data ontvangen'}), 400

        common_name = data.get('common_name', '').strip()
        if not common_name:
            return jsonify({'error': 'Soort naam is verplicht'}), 400

        signal_quality = data.get('signal_quality', 'duidelijk')
        if signal_quality not in ['duidelijk', 'zwak', 'ver_weg']:
            return jsonify({'error': 'Ongeldige geluidskwaliteit'}), 400

        notes = data.get('notes', '').strip()

        # Parse timestamp or use current time
        from datetime import datetime
        timestamp_str = data.get('timestamp')
        if timestamp_str:
            try:
                detection_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Ongeldig tijdstip formaat'}), 400
        else:
            detection_time = datetime.now()

        # Get scientific name - first try from request, then lookup
        scientific_name = data.get('scientific_name', '').strip()

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if not scientific_name:
            # Look up scientific name from existing detections
            cur.execute("""
                SELECT species FROM bird_detections
                WHERE common_name = %s
                LIMIT 1
            """, (common_name,))
            result = cur.fetchone()
            if result:
                scientific_name = result['species']
            else:
                # Try case-insensitive match
                cur.execute("""
                    SELECT species, common_name FROM bird_detections
                    WHERE LOWER(common_name) = LOWER(%s)
                    LIMIT 1
                """, (common_name,))
                result = cur.fetchone()
                if result:
                    scientific_name = result['species']
                    common_name = result['common_name']  # Use correct casing
                else:
                    scientific_name = 'Unknown species'

        # Build notes with metadata
        full_notes = f"[HANDMATIG] Kwaliteit: {signal_quality}"
        if notes:
            full_notes += f" | {notes}"

        # Insert into bird_detections
        # Note: We use file_name to store metadata since the table might not have
        # the source/signal_quality/notes columns yet
        cur.execute("""
            INSERT INTO bird_detections (
                station,
                detection_timestamp,
                date,
                time,
                species,
                common_name,
                confidence,
                latitude,
                longitude,
                cutoff,
                week,
                sensitivity,
                overlap,
                file_name,
                detected_by_zolder,
                detected_by_berging,
                dual_detection,
                rarity_score,
                rarity_tier,
                added_to_db
            ) VALUES (
                'berging',
                %s,
                %s,
                %s,
                %s,
                %s,
                1.0000,
                52.3676,
                6.4673,
                0.0,
                %s,
                1.0,
                0.0,
                %s,
                FALSE,
                TRUE,
                FALSE,
                0,
                NULL,
                NOW()
            )
            RETURNING id
        """, (
            detection_time,
            detection_time.date(),
            detection_time.time(),
            scientific_name,
            common_name,
            detection_time.isocalendar()[1],  # Week number
            full_notes  # Store in file_name as metadata marker
        ))

        new_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'{common_name} toegevoegd aan database',
            'detection_id': new_id,
            'timestamp': detection_time.isoformat(),
            'scientific_name': scientific_name
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/bird-species')
def get_bird_species_list():
    """
    Get list of bird species for the Home Assistant dropdown.
    Returns the most common species observed + allows searching.
    """
    try:
        search = request.args.get('search', '').strip().lower()
        limit = request.args.get('limit', 200, type=int)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if search:
            # Search mode - find matching species
            cur.execute("""
                SELECT DISTINCT common_name, species as scientific_name, COUNT(*) as count
                FROM bird_detections
                WHERE LOWER(common_name) LIKE %s
                  AND common_name NOT IN ('Dog', 'Engine', 'Human vocal', 'Human whistle', 'Siren', 'Fireworks', 'Power tools')
                GROUP BY common_name, species
                ORDER BY count DESC
                LIMIT %s
            """, (f'%{search}%', limit))
        else:
            # Default - return most common species
            cur.execute("""
                SELECT DISTINCT common_name, species as scientific_name, COUNT(*) as count
                FROM bird_detections
                WHERE common_name NOT IN ('Dog', 'Engine', 'Human vocal', 'Human whistle', 'Siren', 'Fireworks', 'Power tools')
                  AND common_name NOT LIKE '%%(%%'
                GROUP BY common_name, species
                ORDER BY count DESC
                LIMIT %s
            """, (limit,))

        species = cur.fetchall()
        cur.close()
        conn.close()

        # Format for Home Assistant input_select
        species_list = [
            {
                'name': s['common_name'],
                'scientific': s['scientific_name'],
                'label': f"{s['common_name']} ({s['scientific_name']})",
                'count': s['count']
            }
            for s in species
        ]

        return jsonify({
            'species': species_list,
            'total': len(species_list)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/manual-detections')
def get_manual_detections():
    """Get list of manually added detections"""
    try:
        limit = request.args.get('limit', 50, type=int)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT
                id,
                common_name,
                species as scientific_name,
                detection_timestamp,
                file_name as notes,
                confidence
            FROM bird_detections
            WHERE file_name LIKE '[HANDMATIG]%%'
            ORDER BY detection_timestamp DESC
            LIMIT %s
        """, (limit,))

        detections = cur.fetchall()
        cur.close()
        conn.close()

        # Format timestamps
        for d in detections:
            if d['detection_timestamp']:
                d['detection_timestamp'] = d['detection_timestamp'].isoformat()

        return jsonify({
            'detections': detections,
            'total': len(detections)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# MEDIA ARCHIVE API - Audio & Spectrogram Playback
# =============================================================================

ARCHIVE_BASE = Path("/mnt/nas-birdnet-archive")


@app.route('/api/archive/species')
def get_archive_species():
    """Get list of species available in the archive with counts"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT
                species,
                station,
                COUNT(*) as count,
                MIN(detection_date) as first_date,
                MAX(detection_date) as last_date
            FROM media_archive
            GROUP BY species, station
            ORDER BY count DESC
        """)

        results = cur.fetchall()
        cur.close()
        conn.close()

        # Format dates
        for r in results:
            if r['first_date']:
                r['first_date'] = r['first_date'].isoformat()
            if r['last_date']:
                r['last_date'] = r['last_date'].isoformat()

        # Group by species
        species_dict = {}
        for r in results:
            sp = r['species']
            if sp not in species_dict:
                species_dict[sp] = {
                    'species': sp,
                    'total': 0,
                    'stations': {},
                    'first_date': r['first_date'],
                    'last_date': r['last_date']
                }
            species_dict[sp]['total'] += r['count']
            species_dict[sp]['stations'][r['station']] = r['count']

        species_list = sorted(species_dict.values(), key=lambda x: x['total'], reverse=True)

        return jsonify({
            'species': species_list,
            'total_species': len(species_list),
            'total_recordings': sum(s['total'] for s in species_list)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/archive/recordings')
def get_archive_recordings():
    """
    Get recordings from the archive with filtering options.

    Query params:
        species: Filter by species name
        station: Filter by station (zolder/berging)
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        min_confidence: Minimum confidence (0-1)
        limit: Max results (default 100)
        offset: Pagination offset
    """
    try:
        species = request.args.get('species')
        station = request.args.get('station')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        min_confidence = request.args.get('min_confidence', type=float)
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Build query with filters
        query = """
            SELECT
                ma.id,
                ma.detection_id,
                ma.station,
                ma.species,
                ma.confidence,
                ma.detection_date,
                ma.archive_audio_path,
                ma.archive_spectrogram_path,
                ma.original_audio_filename,
                ma.file_size_bytes,
                ma.archived_at,
                bd.common_name,
                bd.time as detection_time,
                bd.rarity_score,
                bd.vocalization_type
            FROM media_archive ma
            LEFT JOIN bird_detections bd ON ma.detection_id = bd.id
            WHERE 1=1
        """
        params = []

        if species:
            query += " AND ma.species = %s"
            params.append(species)

        if station:
            query += " AND ma.station = %s"
            params.append(station)

        if date_from:
            query += " AND ma.detection_date >= %s"
            params.append(date_from)

        if date_to:
            query += " AND ma.detection_date <= %s"
            params.append(date_to)

        if min_confidence is not None:
            query += " AND ma.confidence >= %s"
            params.append(min_confidence)

        # Count total with same filters (use copy of params before adding limit/offset)
        count_params = params.copy()
        count_query = "SELECT COUNT(*) FROM media_archive ma WHERE 1=1"
        if species:
            count_query += " AND ma.species = %s"
        if station:
            count_query += " AND ma.station = %s"
        if date_from:
            count_query += " AND ma.detection_date >= %s"
        if date_to:
            count_query += " AND ma.detection_date <= %s"
        if min_confidence is not None:
            count_query += " AND ma.confidence >= %s"

        cur.execute(count_query, count_params)
        count_result = cur.fetchone()
        total = list(count_result.values())[0] if hasattr(count_result, 'values') else count_result[0]

        # Add ordering and pagination
        query += " ORDER BY ma.detection_date DESC, ma.archived_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cur.execute(query, params)
        recordings = cur.fetchall()

        cur.close()
        conn.close()

        # Format results
        for r in recordings:
            if r['detection_date']:
                r['detection_date'] = r['detection_date'].isoformat()
            if r['archived_at']:
                r['archived_at'] = r['archived_at'].isoformat()
            if r['detection_time']:
                r['detection_time'] = str(r['detection_time'])
            # Add URLs for media access
            r['audio_url'] = f"/api/archive/audio/{r['id']}"
            r['spectrogram_url'] = f"/api/archive/spectrogram/{r['id']}"

        return jsonify({
            'recordings': recordings,
            'total': total,
            'limit': limit,
            'offset': offset
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/archive/audio/<int:recording_id>')
def serve_archive_audio(recording_id):
    """Serve audio file from archive"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT archive_audio_path, original_audio_filename
            FROM media_archive WHERE id = %s
        """, (recording_id,))

        record = cur.fetchone()
        cur.close()
        conn.close()

        if not record:
            return jsonify({'error': 'Recording not found'}), 404

        audio_path = ARCHIVE_BASE / record['archive_audio_path']

        if not audio_path.exists():
            return jsonify({'error': 'Audio file not found on disk'}), 404

        return send_file(
            audio_path,
            mimetype='audio/mpeg',
            as_attachment=False,
            download_name=record['original_audio_filename']
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/archive/spectrogram/<int:recording_id>')
def serve_archive_spectrogram(recording_id):
    """Serve spectrogram image from archive"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT archive_spectrogram_path, original_spectrogram_filename
            FROM media_archive WHERE id = %s
        """, (recording_id,))

        record = cur.fetchone()
        cur.close()
        conn.close()

        if not record:
            return jsonify({'error': 'Recording not found'}), 404

        if not record['archive_spectrogram_path']:
            return jsonify({'error': 'No spectrogram available'}), 404

        spec_path = ARCHIVE_BASE / record['archive_spectrogram_path']

        if not spec_path.exists():
            return jsonify({'error': 'Spectrogram file not found on disk'}), 404

        return send_file(
            spec_path,
            mimetype='image/png',
            as_attachment=False
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/archive/stats')
def get_archive_stats():
    """Get overall archive statistics"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT
                COUNT(*) as total_recordings,
                COUNT(DISTINCT species) as unique_species,
                SUM(file_size_bytes) as total_size_bytes,
                MIN(detection_date) as earliest_date,
                MAX(detection_date) as latest_date,
                COUNT(*) FILTER (WHERE station = 'zolder') as zolder_count,
                COUNT(*) FILTER (WHERE station = 'berging') as berging_count
            FROM media_archive
        """)

        stats = cur.fetchone()

        # Get top 10 species
        cur.execute("""
            SELECT species, COUNT(*) as count
            FROM media_archive
            GROUP BY species
            ORDER BY count DESC
            LIMIT 10
        """)
        top_species = cur.fetchall()

        # Get recordings per month
        cur.execute("""
            SELECT
                DATE_TRUNC('month', detection_date) as month,
                COUNT(*) as count
            FROM media_archive
            GROUP BY DATE_TRUNC('month', detection_date)
            ORDER BY month DESC
            LIMIT 12
        """)
        monthly = cur.fetchall()

        cur.close()
        conn.close()

        # Format
        if stats['earliest_date']:
            stats['earliest_date'] = stats['earliest_date'].isoformat()
        if stats['latest_date']:
            stats['latest_date'] = stats['latest_date'].isoformat()

        if stats['total_size_bytes']:
            stats['total_size_gb'] = round(stats['total_size_bytes'] / (1024**3), 2)

        for m in monthly:
            if m['month']:
                m['month'] = m['month'].strftime('%Y-%m')

        return jsonify({
            'stats': stats,
            'top_species': top_species,
            'monthly_counts': monthly
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/archive/random')
def get_random_recording():
    """Get a random recording (optionally filtered by species)"""
    try:
        species = request.args.get('species')
        station = request.args.get('station')

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT
                ma.id,
                ma.species,
                ma.station,
                ma.detection_date,
                ma.confidence,
                ma.archive_audio_path,
                ma.archive_spectrogram_path,
                bd.common_name,
                bd.time as detection_time
            FROM media_archive ma
            LEFT JOIN bird_detections bd ON ma.detection_id = bd.id
            WHERE 1=1
        """
        params = []

        if species:
            query += " AND ma.species = %s"
            params.append(species)

        if station:
            query += " AND ma.station = %s"
            params.append(station)

        query += " ORDER BY RANDOM() LIMIT 1"

        cur.execute(query, params)
        recording = cur.fetchone()

        cur.close()
        conn.close()

        if not recording:
            return jsonify({'error': 'No recordings found'}), 404

        # Format
        if recording['detection_date']:
            recording['detection_date'] = recording['detection_date'].isoformat()
        if recording['detection_time']:
            recording['detection_time'] = str(recording['detection_time'])

        recording['audio_url'] = f"/api/archive/audio/{recording['id']}"
        recording['spectrogram_url'] = f"/api/archive/spectrogram/{recording['id']}"

        return jsonify(recording)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# NESTBOX MONITORING API - Broedseizoen tracking & media capture
# =============================================================================

# Opslag op 8TB USB share op NAS
NESTBOX_MEDIA_BASE = Path("/mnt/nas-birdnet-archive/nestbox")


@app.route('/api/nestbox/list')
def get_nestboxes():
    """Get list of all nestboxes"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT * FROM nestboxes ORDER BY id")
        nestboxes = cur.fetchall()

        cur.close()
        conn.close()

        return jsonify({'nestboxes': nestboxes})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/status')
def get_nestbox_status():
    """Get current status of all nestboxes"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT * FROM v_nestbox_current_status")
        status = cur.fetchall()

        cur.close()
        conn.close()

        return jsonify({'status': status})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/events', methods=['GET'])
def get_nestbox_events():
    """Get nestbox events with optional filtering"""
    try:
        nestbox_id = request.args.get('nestbox_id')
        event_type = request.args.get('event_type')
        limit = request.args.get('limit', 100, type=int)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        query = "SELECT * FROM nestbox_events WHERE 1=1"
        params = []

        if nestbox_id:
            query += " AND nestbox_id = %s"
            params.append(nestbox_id)

        if event_type:
            query += " AND event_type = %s"
            params.append(event_type)

        query += " ORDER BY event_timestamp DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, params)
        events = cur.fetchall()

        cur.close()
        conn.close()

        # Format timestamps
        for e in events:
            if e.get('event_timestamp'):
                e['event_timestamp'] = e['event_timestamp'].isoformat()
            if e.get('added_to_db'):
                e['added_to_db'] = e['added_to_db'].isoformat()

        return jsonify({'events': events, 'total': len(events)})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/events', methods=['POST'])
def add_nestbox_event():
    """Add a new nestbox event"""
    try:
        data = request.get_json()

        required = ['nestbox_id', 'event_type']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            INSERT INTO nestbox_events
            (nestbox_id, event_type, event_timestamp, species, egg_count, chick_count, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['nestbox_id'],
            data['event_type'],
            data.get('event_timestamp', datetime.now()),
            data.get('species'),
            data.get('egg_count'),
            data.get('chick_count'),
            data.get('notes')
        ))

        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'success': True, 'id': result['id']})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/media', methods=['GET'])
def get_nestbox_media():
    """Get nestbox media (screenshots/videos)"""
    try:
        nestbox_id = request.args.get('nestbox_id')
        media_type = request.args.get('media_type')
        date_from = request.args.get('date_from')
        limit = request.args.get('limit', 50, type=int)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        query = "SELECT * FROM nestbox_media WHERE 1=1"
        params = []

        if nestbox_id:
            query += " AND nestbox_id = %s"
            params.append(nestbox_id)

        if media_type:
            query += " AND media_type = %s"
            params.append(media_type)

        if date_from:
            query += " AND captured_at >= %s"
            params.append(date_from)

        query += " ORDER BY captured_at DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, params)
        media = cur.fetchall()

        cur.close()
        conn.close()

        # Format and add URLs
        for m in media:
            if m.get('captured_at'):
                m['captured_at'] = m['captured_at'].isoformat()
            if m.get('created_at'):
                m['created_at'] = m['created_at'].isoformat()
            m['url'] = f"/api/nestbox/media/file/{m['id']}"

        return jsonify({'media': media, 'total': len(media)})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/media/file/<int:media_id>')
def serve_nestbox_media(media_id):
    """Serve nestbox media file"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT * FROM nestbox_media WHERE id = %s", (media_id,))
        record = cur.fetchone()

        cur.close()
        conn.close()

        if not record:
            return jsonify({'error': 'Media not found'}), 404

        file_path = NESTBOX_MEDIA_BASE / record['file_path']

        if not file_path.exists():
            return jsonify({'error': 'File not found on disk'}), 404

        mimetype = 'image/jpeg' if record['media_type'] == 'screenshot' else 'video/mp4'

        return send_file(file_path, mimetype=mimetype)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/capture/screenshot', methods=['POST'])
def capture_nestbox_screenshot():
    """Capture screenshot from nestbox camera stream"""
    try:
        data = request.get_json()
        nestbox_id = data.get('nestbox_id')

        if not nestbox_id:
            return jsonify({'error': 'nestbox_id required'}), 400

        # Ensure directory exists
        date_str = datetime.now().strftime('%Y/%m/%d')
        save_dir = NESTBOX_MEDIA_BASE / nestbox_id / 'screenshots' / date_str
        save_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{nestbox_id}_{timestamp}.jpg"
        file_path = save_dir / filename

        # Capture from go2rtc RTSP stream using ffmpeg
        # go2rtc streams are named nestkast_voor, nestkast_midden, nestkast_achter
        stream_url = f"rtsp://192.168.1.25:8554/nestkast_{nestbox_id}"

        import subprocess
        result = subprocess.run([
            'ffmpeg', '-y',
            '-rtsp_transport', 'tcp',
            '-i', stream_url,
            '-frames:v', '1',
            '-q:v', '2',
            str(file_path)
        ], capture_output=True, timeout=30)

        if result.returncode != 0:
            return jsonify({'error': 'Screenshot capture failed', 'details': result.stderr.decode()}), 500

        # Get file size
        file_size = file_path.stat().st_size

        # Save to database
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        relative_path = f"{nestbox_id}/screenshots/{date_str}/{filename}"
        capture_type = data.get('capture_type', 'manual')

        cur.execute("""
            INSERT INTO nestbox_media
            (nestbox_id, media_type, capture_type, file_path, file_name, file_size_bytes, captured_at)
            VALUES (%s, 'screenshot', %s, %s, %s, %s, NOW())
            RETURNING id
        """, (nestbox_id, capture_type, relative_path, filename, file_size))

        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'id': result['id'],
            'file_path': relative_path,
            'url': f"/api/nestbox/media/file/{result['id']}"
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/capture/video/status', methods=['GET'])
def get_recording_status():
    """Get status of active recordings"""
    try:
        active = {}
        for nestbox_id in ['voor', 'midden', 'achter']:
            recording_flag = Path(f"/tmp/nestbox_recording_{nestbox_id}.pid")
            active[nestbox_id] = recording_flag.exists()
        return jsonify({'active': active})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/capture/video/start', methods=['POST'])
def start_nestbox_video():
    """Start video recording from nestbox camera"""
    try:
        data = request.get_json()
        nestbox_id = data.get('nestbox_id')

        if not nestbox_id:
            return jsonify({'error': 'nestbox_id required'}), 400

        # Check if already recording
        recording_flag = Path(f"/tmp/nestbox_recording_{nestbox_id}.pid")
        if recording_flag.exists():
            return jsonify({'error': 'Already recording', 'nestbox_id': nestbox_id}), 400

        # Ensure directory exists
        date_str = datetime.now().strftime('%Y/%m/%d')
        save_dir = NESTBOX_MEDIA_BASE / nestbox_id / 'videos' / date_str
        save_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{nestbox_id}_{timestamp}.mp4"
        file_path = save_dir / filename

        # Start ffmpeg recording in background
        # go2rtc streams are named nestkast_voor, nestkast_midden, nestkast_achter
        stream_url = f"rtsp://192.168.1.25:8554/nestkast_{nestbox_id}"

        import subprocess
        process = subprocess.Popen([
            'ffmpeg', '-y',
            '-rtsp_transport', 'tcp',
            '-fflags', '+genpts+discardcorrupt',
            '-use_wallclock_as_timestamps', '1',
            '-i', stream_url,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-r', '15',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            str(file_path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Save PID and file info
        with open(recording_flag, 'w') as f:
            f.write(f"{process.pid}\n{file_path}\n{nestbox_id}\n{nestbox_id}/videos/{date_str}/{filename}")

        return jsonify({
            'success': True,
            'message': 'Recording started',
            'nestbox_id': nestbox_id,
            'pid': process.pid
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/capture/video/stop', methods=['POST'])
def stop_nestbox_video():
    """Stop video recording and save to database"""
    try:
        data = request.get_json()
        nestbox_id = data.get('nestbox_id')

        if not nestbox_id:
            return jsonify({'error': 'nestbox_id required'}), 400

        recording_flag = Path(f"/tmp/nestbox_recording_{nestbox_id}.pid")

        if not recording_flag.exists():
            return jsonify({'error': 'No active recording', 'nestbox_id': nestbox_id}), 400

        # Read recording info
        with open(recording_flag, 'r') as f:
            lines = f.read().strip().split('\n')
            pid = int(lines[0])
            file_path = Path(lines[1])
            relative_path = lines[3]

        # Stop ffmpeg gracefully
        import subprocess
        import signal
        import os

        try:
            os.kill(pid, signal.SIGINT)
            # Wait a moment for file to be finalized
            import time
            time.sleep(2)
        except ProcessLookupError:
            pass  # Process already ended

        # Remove flag
        recording_flag.unlink()

        # Check file exists and get info
        if not file_path.exists():
            return jsonify({'error': 'Recording file not found'}), 500

        file_size = file_path.stat().st_size

        # Get duration using ffprobe
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                str(file_path)
            ], capture_output=True, timeout=10)
            duration = int(float(result.stdout.decode().strip()))
        except:
            duration = None

        # Save to database
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            INSERT INTO nestbox_media
            (nestbox_id, media_type, capture_type, file_path, file_name, file_size_bytes, duration_seconds, captured_at)
            VALUES (%s, 'video', 'manual', %s, %s, %s, %s, NOW())
            RETURNING id
        """, (nestbox_id, relative_path, file_path.name, file_size, duration))

        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'id': result['id'],
            'file_path': relative_path,
            'file_size_bytes': file_size,
            'duration_seconds': duration,
            'url': f"/api/nestbox/media/file/{result['id']}"
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/capture/video/status')
def video_recording_status():
    """Check if any nestbox is currently recording"""
    try:
        status = {}
        for nestbox_id in ['voor', 'midden', 'achter']:
            flag = Path(f"/tmp/nestbox_recording_{nestbox_id}.pid")
            status[nestbox_id] = flag.exists()

        return jsonify({'recording': status})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# === TIMELAPSE API ===

TIMELAPSE_DIR = Path("/mnt/nas-birdnet-archive/gegenereerde_beelden/nestkasten")
TIMELAPSE_SCRIPT = Path("/home/ronny/emsn2/scripts/nestbox/nestbox_timelapse.py")
timelapse_jobs = {}  # Track running timelapse jobs

@app.route('/api/nestbox/timelapse/list')
def list_timelapses():
    """List available timelapses for a nestbox"""
    try:
        nestbox_id = request.args.get('nestbox_id')

        timelapses = []
        search_dir = TIMELAPSE_DIR / nestbox_id if nestbox_id else TIMELAPSE_DIR

        if search_dir.exists():
            for mp4_file in search_dir.glob('**/*.mp4'):
                stat = mp4_file.stat()
                # Parse filename: midden_20251223-20260105_30fps.mp4
                name = mp4_file.stem
                parts = name.split('_')
                nestbox = parts[0] if parts else 'unknown'

                timelapses.append({
                    'filename': mp4_file.name,
                    'nestbox_id': nestbox,
                    'path': str(mp4_file.relative_to(TIMELAPSE_DIR)),
                    'size_mb': round(stat.st_size / 1024 / 1024, 1),
                    'created': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        # Sort by creation date, newest first
        timelapses.sort(key=lambda x: x['created'], reverse=True)

        return jsonify({'timelapses': timelapses})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/timelapse/file/<path:filename>')
def serve_timelapse(filename):
    """Serve timelapse video file"""
    try:
        file_path = TIMELAPSE_DIR / filename
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        return send_file(file_path, mimetype='video/mp4')

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/timelapse/info')
def timelapse_info():
    """Get info about available screenshots for timelapse generation"""
    try:
        nestbox_id = request.args.get('nestbox_id', 'midden')
        start_date = request.args.get('start')
        end_date = request.args.get('end')

        # Run script with --list to get screenshot count
        cmd = [VENV_PYTHON, str(TIMELAPSE_SCRIPT), '-n', nestbox_id, '--list']

        if start_date:
            cmd.extend(['--start', start_date])
        if end_date:
            cmd.extend(['--end', end_date])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        # Parse output for screenshot count
        output = result.stdout + result.stderr
        count = 0
        date_range = {'start': None, 'end': None}

        for line in output.split('\n'):
            if 'screenshots gevonden' in line.lower():
                try:
                    count = int(line.split()[0])
                except:
                    pass
            if 'Beschikbare periode:' in line:
                # Parse: "Beschikbare periode: 2025-12-23 tot 2026-01-05"
                try:
                    parts = line.split(':')[1].strip().split(' tot ')
                    date_range['start'] = parts[0].strip()
                    date_range['end'] = parts[1].strip()
                except:
                    pass

        return jsonify({
            'nestbox_id': nestbox_id,
            'screenshot_count': count,
            'date_range': date_range
        })

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout getting info'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/timelapse/generate', methods=['POST'])
def generate_timelapse():
    """Generate a new timelapse video"""
    try:
        data = request.get_json() or {}

        nestbox_id = data.get('nestbox_id', 'midden')
        start_date = data.get('start')
        end_date = data.get('end')
        days = data.get('days')
        duration = data.get('duration', 30)  # Target video duration in seconds
        fps = data.get('fps')
        day_night = data.get('day_night', 'all')  # all, day, night

        if nestbox_id not in ['voor', 'midden', 'achter']:
            return jsonify({'error': 'Invalid nestbox_id'}), 400

        # Build command
        cmd = [VENV_PYTHON, str(TIMELAPSE_SCRIPT), '-n', nestbox_id]

        if start_date:
            cmd.extend(['--start', start_date])
        if end_date:
            cmd.extend(['--end', end_date])
        if days:
            cmd.extend(['-d', str(days)])
        if duration:
            cmd.extend(['--duration', str(duration)])
        if fps:
            cmd.extend(['--fps', str(fps)])
        if day_night and day_night != 'all':
            cmd.extend(['--filter', day_night])

        # Generate unique job ID
        job_id = f"{nestbox_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Run in background thread
        def run_timelapse():
            try:
                timelapse_jobs[job_id] = {'status': 'running', 'started': datetime.now().isoformat()}
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

                if result.returncode == 0:
                    # Find output file path in output
                    output_file = None
                    for line in result.stdout.split('\n'):
                        if 'Timelapse opgeslagen:' in line or 'Saved:' in line:
                            output_file = line.split(':')[-1].strip()
                            break

                    timelapse_jobs[job_id] = {
                        'status': 'completed',
                        'output_file': output_file,
                        'completed': datetime.now().isoformat()
                    }
                else:
                    timelapse_jobs[job_id] = {
                        'status': 'failed',
                        'error': result.stderr,
                        'completed': datetime.now().isoformat()
                    }
            except subprocess.TimeoutExpired:
                timelapse_jobs[job_id] = {'status': 'failed', 'error': 'Timeout after 10 minutes'}
            except Exception as e:
                timelapse_jobs[job_id] = {'status': 'failed', 'error': str(e)}

        thread = threading.Thread(target=run_timelapse)
        thread.start()

        return jsonify({
            'job_id': job_id,
            'status': 'started',
            'message': f'Timelapse generation started for {nestbox_id}'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nestbox/timelapse/status/<job_id>')
def timelapse_status(job_id):
    """Check status of timelapse generation job"""
    try:
        if job_id not in timelapse_jobs:
            return jsonify({'error': 'Job not found'}), 404

        return jsonify({'job_id': job_id, **timelapse_jobs[job_id]})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Run development server
    app.run(host='0.0.0.0', port=8081, debug=False)
