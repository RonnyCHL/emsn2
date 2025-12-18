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

        # TODO: Insert custom text into markdown if present
        # TODO: Regenerate PDF with custom text
        # TODO: Trigger email sending

        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f"Rapport '{report['report_title']}' goedgekeurd. Verzending gestart."
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


if __name__ == '__main__':
    # Run development server
    app.run(host='0.0.0.0', port=8081, debug=False)
