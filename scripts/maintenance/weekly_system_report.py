#!/usr/bin/env python3
"""
EMSN Weekly System Report

Wekelijkse uitgebreide systeemcheck met email rapportage.
Controleert zolder, berging en database, en stuurt samenvatting naar rapporten@ronnyhullegie.nl

Checks per station:
- Disk space (/, /mnt/usb)
- Memory en swap usage
- Failed systemd services
- Log file sizes
- Recent detection counts

Database checks:
- Connection status
- Table sizes
- Dead tuples
- Idle connections

Draait via systemd timer (wekelijks zondag 08:00)
"""

import os
import sys
import json
import subprocess
import smtplib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add core modules path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psutil
    import psycopg2
    import yaml
    from core.config import get_postgres_config
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Logging
LOG_DIR = Path("/mnt/usb/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "weekly_system_report.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
STATIONS = {
    'zolder': {'host': 'localhost', 'name': 'Pi Zolder'},
    'berging': {'host': 'emsn2-berging', 'name': 'Pi Berging'}
}

EMAIL_CONFIG_PATH = Path("/home/ronny/emsn2/config/email.yaml")
SECRETS_PATH = Path("/home/ronny/emsn2/.secrets")

# Thresholds
DISK_WARNING = 70
DISK_CRITICAL = 85
LOG_SIZE_WARNING_MB = 100


def load_secrets():
    """Load credentials from .secrets file"""
    secrets = {}
    if SECRETS_PATH.exists():
        with open(SECRETS_PATH) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    secrets[key.strip()] = value.strip().strip('"').strip("'")
    return secrets


def run_remote_command(host, command):
    """Run command on remote host via SSH"""
    if host == 'localhost':
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
    else:
        result = subprocess.run(
            f"ssh {host} '{command}'",
            shell=True, capture_output=True, text=True, timeout=30
        )
    return result.stdout.strip(), result.returncode


def get_disk_usage(host):
    """Get disk usage for a station"""
    disks = {}
    for mount in ['/', '/mnt/usb']:
        cmd = f"df -h {mount} 2>/dev/null | tail -1 | awk '{{print $5}}'"
        output, _ = run_remote_command(host, cmd)
        if output:
            try:
                disks[mount] = int(output.replace('%', ''))
            except ValueError:
                disks[mount] = None
    return disks


def get_memory_usage(host):
    """Get memory usage for a station"""
    cmd = "free | grep Mem | awk '{print int($3/$2 * 100)}'"
    output, _ = run_remote_command(host, cmd)
    try:
        return int(output) if output else None
    except ValueError:
        return None


def get_swap_usage(host):
    """Get swap usage for a station"""
    cmd = "free | grep Swap | awk '{if($2>0) print int($3/$2 * 100); else print 0}'"
    output, _ = run_remote_command(host, cmd)
    try:
        return int(output) if output else None
    except ValueError:
        return None


def get_failed_services(host):
    """Get list of failed systemd services"""
    cmd = "systemctl --failed --no-legend --plain 2>/dev/null | awk '{print $1}'"
    output, _ = run_remote_command(host, cmd)
    if output:
        return [s for s in output.split('\n') if s]
    return []


def get_log_sizes(host):
    """Get sizes of log files over warning threshold"""
    cmd = f"find /mnt/usb/logs -type f -size +{LOG_SIZE_WARNING_MB}M -exec ls -lh {{}} \\; 2>/dev/null"
    output, _ = run_remote_command(host, cmd)
    large_logs = []
    if output:
        for line in output.split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 9:
                    size = parts[4]
                    name = parts[-1].split('/')[-1]
                    large_logs.append(f"{name} ({size})")
    return large_logs


def get_total_log_size(host):
    """Get total log directory size"""
    cmd = "du -sh /mnt/usb/logs 2>/dev/null | awk '{print $1}'"
    output, _ = run_remote_command(host, cmd)
    return output if output else "Unknown"


def get_uptime(host):
    """Get system uptime"""
    cmd = "uptime -p 2>/dev/null || uptime"
    output, _ = run_remote_command(host, cmd)
    return output if output else "Unknown"


def get_database_stats():
    """Get database statistics"""
    stats = {
        'connection': False,
        'tables': [],
        'dead_tuples': [],
        'connections': 0,
        'idle_in_transaction': 0,
        'detections_week': {}
    }

    try:
        config = get_postgres_config()
        conn = psycopg2.connect(
            host=config['host'],
            port=config['port'],
            database=config['database'],
            user=config['user'],
            password=config['password'],
            connect_timeout=10
        )
        stats['connection'] = True
        cursor = conn.cursor()

        # Table sizes
        cursor.execute("""
            SELECT tablename, pg_size_pretty(pg_total_relation_size('public.' || tablename))
            FROM pg_tables WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size('public.' || tablename) DESC LIMIT 10
        """)
        stats['tables'] = cursor.fetchall()

        # Dead tuples (tables with significant bloat)
        cursor.execute("""
            SELECT relname, n_dead_tup, n_live_tup
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 1000
            ORDER BY n_dead_tup DESC LIMIT 5
        """)
        stats['dead_tuples'] = cursor.fetchall()

        # Connection counts
        cursor.execute("SELECT COUNT(*) FROM pg_stat_activity")
        stats['connections'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'idle in transaction'")
        stats['idle_in_transaction'] = cursor.fetchone()[0]

        # Detections per station last 7 days
        cursor.execute("""
            SELECT station, COUNT(*)
            FROM bird_detections
            WHERE date >= CURRENT_DATE - 7
            GROUP BY station
        """)
        for row in cursor.fetchall():
            stats['detections_week'][row[0]] = row[1]

        # Total species count
        cursor.execute("SELECT COUNT(DISTINCT common_name) FROM bird_detections WHERE date >= CURRENT_DATE - 7")
        stats['species_week'] = cursor.fetchone()[0]

        conn.close()

    except Exception as e:
        logger.error(f"Database check failed: {e}")
        stats['error'] = str(e)

    return stats


def check_station(station_id, station_config):
    """Perform all checks for a station"""
    host = station_config['host']
    name = station_config['name']

    logger.info(f"Checking station: {name}")

    result = {
        'name': name,
        'status': 'healthy',
        'issues': [],
        'warnings': [],
        'disk': get_disk_usage(host),
        'memory': get_memory_usage(host),
        'swap': get_swap_usage(host),
        'failed_services': get_failed_services(host),
        'large_logs': get_log_sizes(host),
        'total_log_size': get_total_log_size(host),
        'uptime': get_uptime(host)
    }

    # Evaluate disk
    for mount, usage in result['disk'].items():
        if usage is None:
            result['issues'].append(f"Disk {mount} niet bereikbaar")
        elif usage >= DISK_CRITICAL:
            result['issues'].append(f"Disk {mount}: {usage}% (KRITIEK)")
            result['status'] = 'critical'
        elif usage >= DISK_WARNING:
            result['warnings'].append(f"Disk {mount}: {usage}%")
            if result['status'] == 'healthy':
                result['status'] = 'warning'

    # Evaluate failed services
    if result['failed_services']:
        result['issues'].append(f"Failed services: {', '.join(result['failed_services'])}")
        result['status'] = 'critical'

    # Evaluate large logs
    if result['large_logs']:
        result['warnings'].append(f"Grote log bestanden: {', '.join(result['large_logs'])}")
        if result['status'] == 'healthy':
            result['status'] = 'warning'

    return result


def generate_report(station_results, db_stats):
    """Generate markdown report"""
    now = datetime.now()
    week_number = now.isocalendar()[1]

    lines = [
        f"# EMSN Wekelijks Systeemrapport",
        f"",
        f"**Datum:** {now.strftime('%d %B %Y')}",
        f"**Week:** {week_number}",
        f"**Gegenereerd:** {now.strftime('%H:%M')}",
        f"",
        f"---",
        f"",
        f"## Samenvatting",
        f"",
    ]

    # Overall status
    all_healthy = all(s['status'] == 'healthy' for s in station_results.values())
    any_critical = any(s['status'] == 'critical' for s in station_results.values())

    if all_healthy and db_stats['connection'] and db_stats.get('idle_in_transaction', 0) == 0:
        lines.append("✅ **Alle systemen operationeel**")
    elif any_critical:
        lines.append("🔴 **Kritieke problemen gedetecteerd!**")
    else:
        lines.append("⚠️ **Waarschuwingen aanwezig**")

    lines.append("")

    # Station summaries
    lines.append("| Station | Status | Disk / | Disk USB | Memory | Issues |")
    lines.append("|---------|--------|--------|----------|--------|--------|")

    for station_id, result in station_results.items():
        status_icon = "✅" if result['status'] == 'healthy' else ("🔴" if result['status'] == 'critical' else "⚠️")
        disk_root = f"{result['disk'].get('/', 'N/A')}%" if result['disk'].get('/') else "N/A"
        disk_usb = f"{result['disk'].get('/mnt/usb', 'N/A')}%" if result['disk'].get('/mnt/usb') else "N/A"
        memory = f"{result['memory']}%" if result['memory'] else "N/A"
        issues = len(result['issues']) + len(result['warnings'])

        lines.append(f"| {result['name']} | {status_icon} | {disk_root} | {disk_usb} | {memory} | {issues} |")

    lines.append("")

    # Database summary
    lines.append("## Database Status")
    lines.append("")

    if db_stats['connection']:
        lines.append(f"✅ **Connectie:** OK")
        lines.append(f"- Actieve connecties: {db_stats['connections']}")
        lines.append(f"- Idle in transaction: {db_stats['idle_in_transaction']}")

        if db_stats.get('detections_week'):
            total_detections = sum(db_stats['detections_week'].values())
            lines.append(f"- Detecties deze week: {total_detections:,}")
            lines.append(f"- Soorten deze week: {db_stats.get('species_week', 'N/A')}")
    else:
        lines.append(f"🔴 **Connectie mislukt:** {db_stats.get('error', 'Onbekend')}")

    lines.append("")

    # Detailed station info
    lines.append("---")
    lines.append("")
    lines.append("## Details per Station")

    for station_id, result in station_results.items():
        lines.append("")
        lines.append(f"### {result['name']}")
        lines.append("")
        lines.append(f"**Uptime:** {result['uptime']}")
        lines.append(f"**Log directory:** {result['total_log_size']}")
        lines.append("")

        if result['issues']:
            lines.append("**Problemen:**")
            for issue in result['issues']:
                lines.append(f"- 🔴 {issue}")
            lines.append("")

        if result['warnings']:
            lines.append("**Waarschuwingen:**")
            for warning in result['warnings']:
                lines.append(f"- ⚠️ {warning}")
            lines.append("")

        if not result['issues'] and not result['warnings']:
            lines.append("✅ Geen problemen gedetecteerd")
            lines.append("")

    # Database tables
    if db_stats['tables']:
        lines.append("---")
        lines.append("")
        lines.append("## Database Tabellen (top 10)")
        lines.append("")
        lines.append("| Tabel | Grootte |")
        lines.append("|-------|---------|")
        for table, size in db_stats['tables']:
            lines.append(f"| {table} | {size} |")
        lines.append("")

    # Dead tuples warning
    if db_stats['dead_tuples']:
        lines.append("## Database Onderhoud")
        lines.append("")
        lines.append("Tabellen met veel dead tuples (mogelijk VACUUM nodig):")
        lines.append("")
        for table, dead, live in db_stats['dead_tuples']:
            pct = round(100 * dead / (live + dead), 1) if (live + dead) > 0 else 0
            lines.append(f"- {table}: {dead:,} dead tuples ({pct}%)")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Dit rapport is automatisch gegenereerd door EMSN Weekly System Report*")

    return '\n'.join(lines)


def send_email_report(report_content, has_issues):
    """Send report via email"""
    try:
        # Load email config
        if not EMAIL_CONFIG_PATH.exists():
            logger.error(f"Email config not found: {EMAIL_CONFIG_PATH}")
            return False

        with open(EMAIL_CONFIG_PATH) as f:
            email_config = yaml.safe_load(f)

        # Load SMTP credentials from secrets
        secrets = load_secrets()
        smtp_password = secrets.get('SMTP_PASS') or secrets.get('SMTP_PASSWORD') or secrets.get('EMSN_SMTP_PASSWORD')

        if not smtp_password:
            # Try environment variable
            smtp_password = os.getenv('EMSN_SMTP_PASSWORD') or os.getenv('SMTP_PASS')

        if not smtp_password:
            logger.error("SMTP password not found in .secrets or environment")
            return False

        smtp_config = email_config['smtp']
        smtp_user = smtp_config['username']
        from_address = email_config['email']['from_address']
        from_name = email_config['email']['from_name']

        # Determine subject
        now = datetime.now()
        week = now.isocalendar()[1]
        status = "⚠️ ISSUES" if has_issues else "✅ OK"
        subject = f"EMSN Systeemrapport Week {week} - {status}"

        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{from_name} <{from_address}>"
        msg['To'] = 'rapporten@ronnyhullegie.nl'
        msg['Subject'] = subject

        # Plain text version
        msg.attach(MIMEText(report_content, 'plain', 'utf-8'))

        # Send
        with smtplib.SMTP(smtp_config['host'], smtp_config['port']) as server:
            if smtp_config.get('use_tls', True):
                server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info(f"Report email sent to rapporten@ronnyhullegie.nl")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("EMSN Weekly System Report - Starting")
    logger.info("=" * 60)

    # Check all stations
    station_results = {}
    for station_id, station_config in STATIONS.items():
        try:
            station_results[station_id] = check_station(station_id, station_config)
        except Exception as e:
            logger.error(f"Failed to check station {station_id}: {e}")
            station_results[station_id] = {
                'name': station_config['name'],
                'status': 'critical',
                'issues': [f"Station check failed: {e}"],
                'warnings': [],
                'disk': {},
                'memory': None,
                'swap': None,
                'failed_services': [],
                'large_logs': [],
                'total_log_size': 'Unknown',
                'uptime': 'Unknown'
            }

    # Check database
    db_stats = get_database_stats()

    # Generate report
    report = generate_report(station_results, db_stats)

    # Save report locally
    report_file = LOG_DIR / f"weekly_report_{datetime.now().strftime('%Y%m%d')}.md"
    with open(report_file, 'w') as f:
        f.write(report)
    logger.info(f"Report saved to: {report_file}")

    # Determine if there are issues
    has_issues = any(
        s['status'] != 'healthy' for s in station_results.values()
    ) or not db_stats['connection'] or db_stats.get('idle_in_transaction', 0) > 0

    # Send email
    if send_email_report(report, has_issues):
        logger.info("Email sent successfully")
    else:
        logger.error("Failed to send email")

    logger.info("=" * 60)
    logger.info("EMSN Weekly System Report - Completed")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
