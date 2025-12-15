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
EMAIL_CONFIG_FILE = CONFIG_DIR / "email.yaml"
VENV_PYTHON = "/home/ronny/emsn2/venv/bin/python3"

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

@app.route('/api/pdf')
def generate_pdf():
    """Generate PDF from markdown report"""
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
        # Use pandoc to convert markdown to PDF
        # Strip YAML frontmatter first
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Remove frontmatter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                content = parts[2].strip()

        # Write cleaned content to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp_md:
            tmp_md.write(content)
            tmp_md_path = Path(tmp_md.name)

        # Convert to PDF with pandoc using XeLaTeX for better Unicode support
        result = subprocess.run([
            'pandoc',
            str(tmp_md_path),
            '-o', str(pdf_path),
            '--pdf-engine=xelatex',
            '-V', 'geometry:margin=2cm',
            '--metadata', 'title=EMSN Rapport'
        ], check=True, capture_output=True, text=True)

        # Clean up temp markdown
        tmp_md_path.unlink()

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

    except subprocess.CalledProcessError as e:
        if pdf_path.exists():
            pdf_path.unlink()
        error_msg = f'PDF generation failed: {str(e)}'
        if e.stderr:
            error_msg += f'\nStderr: {e.stderr}'
        return jsonify({'error': error_msg}), 500
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

        # Email body
        body = f"""Beste vogelliefhebber,

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
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Generate PDF from markdown using pandoc
        pdf_filename = report_file.replace('.md', '.pdf')
        pdf_path = REPORTS_DIR / pdf_filename

        try:
            # Create PDF with pandoc
            import subprocess
            result = subprocess.run([
                'pandoc',
                str(report_path),
                '-o', str(pdf_path),
                '--pdf-engine=xelatex',
                '-V', 'geometry:margin=2.5cm',
                '-V', 'fontsize=11pt',
                '--resource-path', str(REPORTS_DIR)
            ], capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                return jsonify({'error': f'PDF generatie mislukt: {result.stderr}'}), 500

            # Read PDF and attach
            with open(pdf_path, 'rb') as pdf_file:
                attachment = MIMEApplication(pdf_file.read(), _subtype='pdf')
                attachment['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
                msg.attach(attachment)

        except subprocess.TimeoutExpired:
            return jsonify({'error': 'PDF generatie timeout'}), 500
        except FileNotFoundError:
            return jsonify({'error': 'pandoc niet geïnstalleerd'}), 500

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

        return jsonify({
            'success': True,
            'message': f'Rapport verstuurd naar {len(recipient_emails)} ontvanger(s)'
        })

    except smtplib.SMTPAuthenticationError:
        return jsonify({'error': 'SMTP authenticatie mislukt'}), 500
    except Exception as e:
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


if __name__ == '__main__':
    # Run development server
    app.run(host='0.0.0.0', port=8081, debug=False)
