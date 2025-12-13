#!/usr/bin/env python3
"""
EMSN Email Sender
Sends reports via email
"""

import os
import sys
import smtplib
import yaml
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path


CONFIG_PATH = Path("/home/ronny/emsn2/config/email.yaml")


def load_config():
    """Load email configuration"""
    if not CONFIG_PATH.exists():
        print(f"ERROR: Config file not found: {CONFIG_PATH}")
        return None

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def send_report(report_path, subject=None, body=None, recipients=None):
    """
    Send a report via email

    Args:
        report_path: Path to the markdown report file
        subject: Email subject (optional, will generate from filename)
        body: Email body text (optional, will use intro from report)
        recipients: List of email addresses (optional, uses config)
    """
    config = load_config()
    if not config:
        return False

    # Get SMTP credentials from environment
    smtp_user = os.getenv('EMSN_SMTP_USER')
    smtp_pass = os.getenv('EMSN_SMTP_PASSWORD')
    from_address = os.getenv('EMSN_EMAIL_FROM', smtp_user)

    if not smtp_user or not smtp_pass:
        print("ERROR: SMTP credentials not set")
        print("Set EMSN_SMTP_USER and EMSN_SMTP_PASSWORD environment variables")
        return False

    # Get recipients
    if recipients is None:
        recipients = config.get('recipients', [])

    if not recipients:
        print("ERROR: No recipients configured")
        return False

    # Read report
    report_file = Path(report_path)
    if not report_file.exists():
        print(f"ERROR: Report file not found: {report_path}")
        return False

    with open(report_file, 'r', encoding='utf-8') as f:
        report_content = f.read()

    # Generate subject from filename if not provided
    if subject is None:
        subject = f"EMSN Rapport: {report_file.stem}"

    # Generate body if not provided
    if body is None:
        # Extract first paragraph after frontmatter
        lines = report_content.split('\n')
        in_frontmatter = False
        body_lines = []
        for line in lines:
            if line.strip() == '---':
                in_frontmatter = not in_frontmatter
                continue
            if not in_frontmatter and line.strip():
                if line.startswith('#'):
                    body_lines.append(line.lstrip('#').strip())
                else:
                    body_lines.append(line)
                if len(body_lines) > 5:
                    break
        body = '\n'.join(body_lines[:5])
        body += "\n\nHet volledige rapport is bijgevoegd als PDF (indien beschikbaar) en tekst."

    # Create message
    msg = MIMEMultipart()
    msg['From'] = f"{config['email']['from_name']} <{from_address}>"
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject

    # Add body
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    # Attach report as text
    attachment = MIMEText(report_content, 'plain', 'utf-8')
    attachment.add_header('Content-Disposition', 'attachment',
                         filename=report_file.name)
    msg.attach(attachment)

    # Send email
    try:
        smtp_config = config['smtp']
        with smtplib.SMTP(smtp_config['host'], smtp_config['port']) as server:
            if smtp_config.get('use_tls', True):
                server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        print(f"Email verzonden naar: {', '.join(recipients)}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("ERROR: SMTP authentication failed")
        print("Check EMSN_SMTP_USER and EMSN_SMTP_PASSWORD")
        return False
    except Exception as e:
        print(f"ERROR: Failed to send email: {e}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Send EMSN report via email')
    parser.add_argument('report', type=str, help='Path to report file')
    parser.add_argument('--subject', type=str, help='Email subject')
    parser.add_argument('--to', type=str, nargs='+', help='Recipient email addresses')

    args = parser.parse_args()

    success = send_report(
        args.report,
        subject=args.subject,
        recipients=args.to
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
