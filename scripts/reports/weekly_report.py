#!/usr/bin/env python3
"""
EMSN Weekly Bird Activity Report Generator
Generates narrative reports using Claude API
"""

import sys
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
import psycopg2

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from report_base import ReportBase, REPORTS_PATH
from report_charts import ReportCharts
from report_highlights import ReportHighlights
from report_spectrograms import ReportSpectrograms
from weather_forecast import get_forecast_for_report


class WeeklyReportGenerator(ReportBase):
    """Generate weekly narrative bird activity reports"""

    def __init__(self, style=None, report_format='uitgebreid', include_spectrograms=False,
                 pending_mode=False):
        super().__init__()
        self.get_style(style)
        self.report_format = report_format  # 'kort' or 'uitgebreid'
        self.include_spectrograms = include_spectrograms
        self.pending_mode = pending_mode  # If True, add to review queue instead of sending

    def create_pending_report(self, report_type, report_title, report_filename,
                              markdown_path, pdf_path=None, expires_hours=24,
                              report_data=None):
        """
        Create a pending report in the review queue.
        Sends notification to Ulanzi display and email.
        """
        import json
        import requests

        try:
            # Insert into database
            cur = self.conn.cursor()

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
            self.conn.commit()

            # Send Ulanzi notification
            self._send_ulanzi_notification(report_type, report_title)

            # Send email notification
            self._send_pending_email_notification(report_type, report_title)

            # Update notification status
            cur.execute("""
                UPDATE pending_reports
                SET notification_sent = TRUE, notification_sent_at = NOW()
                WHERE id = %s
            """, (report_id,))
            self.conn.commit()

            return report_id

        except Exception as e:
            print(f"ERROR creating pending report: {e}")
            return None

    def _send_ulanzi_notification(self, report_type, report_title):
        """Send notification to Ulanzi TC001 display"""
        import requests

        try:
            type_labels = {
                'weekly': 'Weekrapport',
                'monthly': 'Maandrapport',
                'seasonal': 'Seizoen',
                'yearly': 'Jaarrapport'
            }
            type_label = type_labels.get(report_type, 'Rapport')

            payload = {
                "text": f"Nieuw {type_label} wacht op review",
                "color": "#FFAA00",
                "duration": 300,  # 30 seconds in deciseconds
                "scrollSpeed": 80,
                "stack": True,
            }

            response = requests.post(
                "http://192.168.1.11/api/notify",
                json=payload,
                timeout=5
            )
            return response.status_code == 200

        except Exception as e:
            print(f"   WARNING: Ulanzi notification failed: {e}")
            return False

    def _send_pending_email_notification(self, report_type, report_title):
        """Send email notification about pending report"""
        import smtplib
        import yaml
        from email.mime.text import MIMEText

        try:
            config_path = Path(__file__).parent.parent.parent / 'config' / 'email.yaml'
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            smtp_password = os.environ.get('EMSN_SMTP_PASSWORD')
            if not smtp_password:
                print("   WARNING: SMTP password not set, skipping email notification")
                return False

            smtp_config = config.get('smtp', {})
            email_config = config.get('email', {})
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
http://192.168.1.25/rapporten/#review

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
            print(f"   WARNING: Email notification failed: {e}")
            return False

    def get_week_dates(self):
        """Get start and end dates for last week"""
        today = datetime.now()
        # Last Monday
        days_since_monday = (today.weekday() - 0) % 7
        if days_since_monday == 0:
            days_since_monday = 7
        last_monday = today - timedelta(days=days_since_monday)
        last_monday = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)

        # Last Sunday
        last_sunday = last_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

        return last_monday, last_sunday

    def collect_data(self, start_date, end_date):
        """Collect all statistics for the report period"""
        cur = self.conn.cursor()

        data = {
            "period": f"{start_date.strftime('%Y-%m-%d')} tot {end_date.strftime('%Y-%m-%d')}",
            "week_number": start_date.isocalendar()[1],
            "year": start_date.year
        }

        # Total detections
        cur.execute("""
            SELECT COUNT(*)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
        """, (start_date, end_date))
        data["total_detections"] = cur.fetchone()[0]

        # Unique species
        cur.execute("""
            SELECT COUNT(DISTINCT species)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
        """, (start_date, end_date))
        data["unique_species"] = cur.fetchone()[0]

        # Top species (Dutch common_name + scientific species name)
        cur.execute("""
            SELECT common_name, species, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY common_name, species
            ORDER BY count DESC
            LIMIT 10
        """, (start_date, end_date))
        data["top_species"] = [
            {
                "name": row[0] or row[1],  # Dutch name, fallback to scientific
                "scientific_name": row[1],
                "count": row[2]
            }
            for row in cur.fetchall()
        ]

        # Rare sightings (species with < 5 detections in the week)
        cur.execute("""
            SELECT common_name, species, detection_timestamp, confidence, station
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            AND species IN (
                SELECT species
                FROM bird_detections
                WHERE detection_timestamp BETWEEN %s AND %s
                GROUP BY species
                HAVING COUNT(*) <= 5
            )
            ORDER BY confidence DESC
            LIMIT 5
        """, (start_date, end_date, start_date, end_date))
        data["rare_sightings"] = [
            {
                "species": row[0] or row[1],  # Dutch name, fallback to scientific
                "scientific_name": row[1],
                "time": row[2].strftime('%Y-%m-%d %H:%M'),
                "confidence": float(row[3]),
                "station": row[4]
            }
            for row in cur.fetchall()
        ]

        # Dual detections (same species detected on both stations within 5 seconds)
        cur.execute("""
            SELECT COUNT(DISTINCT d1.id)
            FROM bird_detections d1
            INNER JOIN bird_detections d2
                ON d1.species = d2.species
                AND d1.station != d2.station
                AND ABS(EXTRACT(EPOCH FROM (d1.detection_timestamp - d2.detection_timestamp))) <= 5
            WHERE d1.detection_timestamp BETWEEN %s AND %s
        """, (start_date, end_date))
        data["dual_detections"] = cur.fetchone()[0]

        # Busiest hour
        cur.execute("""
            SELECT EXTRACT(HOUR FROM detection_timestamp) as hour, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 1
        """, (start_date, end_date))
        result = cur.fetchone()
        if result:
            hour = int(result[0])
            data["busiest_hour"] = f"{hour:02d}:00-{hour+1:02d}:00"
            data["busiest_hour_count"] = result[1]

        # Quietest hour (only daylight hours 6-20)
        cur.execute("""
            SELECT EXTRACT(HOUR FROM detection_timestamp) as hour, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            AND EXTRACT(HOUR FROM detection_timestamp) BETWEEN 6 AND 20
            GROUP BY hour
            ORDER BY count ASC
            LIMIT 1
        """, (start_date, end_date))
        result = cur.fetchone()
        if result:
            hour = int(result[0])
            data["quietest_hour"] = f"{hour:02d}:00-{hour+1:02d}:00"
            data["quietest_hour_count"] = result[1]

        # Hourly activity (for charts)
        cur.execute("""
            SELECT EXTRACT(HOUR FROM detection_timestamp) as hour, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY hour
            ORDER BY hour
        """, (start_date, end_date))
        data["hourly_activity"] = {int(row[0]): row[1] for row in cur.fetchall()}

        # Daily activity (for charts)
        cur.execute("""
            SELECT DATE(detection_timestamp) as day, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY day
            ORDER BY day
        """, (start_date, end_date))
        data["daily_activity"] = [
            {"date": row[0].strftime('%Y-%m-%d'), "count": row[1]}
            for row in cur.fetchall()
        ]

        # Daily activity with temperature (for charts)
        cur.execute("""
            SELECT
                DATE(d.detection_timestamp) as day,
                COUNT(d.id) as detections,
                AVG(w.temp_outdoor) as avg_temp
            FROM bird_detections d
            LEFT JOIN weather_data w
                ON DATE(d.detection_timestamp) = DATE(w.measurement_timestamp)
            WHERE d.detection_timestamp BETWEEN %s AND %s
            GROUP BY day
            ORDER BY day
        """, (start_date, end_date))
        data["daily_temp_activity"] = [
            {
                "date": row[0].strftime('%Y-%m-%d'),
                "detections": row[1],
                "temp_avg": round(float(row[2]), 1) if row[2] else None
            }
            for row in cur.fetchall()
        ]

        # Weather correlation (if weather data available)
        cur.execute("""
            SELECT
                CASE WHEN w.rain_rate > 0 THEN 'rainy' ELSE 'dry' END as weather,
                COUNT(DISTINCT d.id) as detections
            FROM bird_detections d
            LEFT JOIN weather_data w
                ON DATE_TRUNC('hour', d.detection_timestamp) = DATE_TRUNC('hour', w.measurement_timestamp)
            WHERE d.detection_timestamp BETWEEN %s AND %s
            AND w.rain_rate IS NOT NULL
            GROUP BY weather
        """, (start_date, end_date))
        weather_data = dict(cur.fetchall())
        data["weather_correlation"] = {
            "rainy_days_detections": weather_data.get('rainy', 0),
            "dry_days_detections": weather_data.get('dry', 0)
        }

        # Extended weather analysis

        # 1. Temperature statistics (this week vs previous week)
        cur.execute("""
            SELECT
                MIN(temp_outdoor) as min_temp,
                MAX(temp_outdoor) as max_temp,
                AVG(temp_outdoor) as avg_temp,
                DATE(measurement_timestamp) as day
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND temp_outdoor IS NOT NULL
            GROUP BY day
            ORDER BY day
        """, (start_date, end_date))

        daily_temps = []
        for row in cur.fetchall():
            daily_temps.append({
                "day": row[3].strftime('%Y-%m-%d'),
                "min": float(row[0]) if row[0] else None,
                "max": float(row[1]) if row[1] else None,
                "avg": float(row[2]) if row[2] else None
            })

        # Overall week stats
        if daily_temps:
            week_min = min(d["min"] for d in daily_temps if d["min"] is not None)
            week_max = max(d["max"] for d in daily_temps if d["max"] is not None)
            week_avg = sum(d["avg"] for d in daily_temps if d["avg"] is not None) / len([d for d in daily_temps if d["avg"] is not None])

            # Find warmest and coldest day
            warmest_day = max(daily_temps, key=lambda x: x["max"] if x["max"] else -999)
            coldest_day = min(daily_temps, key=lambda x: x["min"] if x["min"] else 999)
        else:
            week_min = week_max = week_avg = None
            warmest_day = coldest_day = None

        # Previous week temperature for comparison
        prev_start = start_date - timedelta(days=7)
        prev_end = end_date - timedelta(days=7)
        cur.execute("""
            SELECT AVG(temp_outdoor)
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND temp_outdoor IS NOT NULL
        """, (prev_start, prev_end))
        prev_week_avg_temp = cur.fetchone()[0]

        temp_comparison = None
        if week_avg and prev_week_avg_temp:
            temp_diff = week_avg - float(prev_week_avg_temp)
            temp_comparison = f"{'kouder' if temp_diff < 0 else 'warmer'}"
            temp_comparison_value = abs(temp_diff)

        data["temperature_stats"] = {
            "week_min": round(week_min, 1) if week_min else None,
            "week_max": round(week_max, 1) if week_max else None,
            "week_avg": round(week_avg, 1) if week_avg else None,
            "warmest_day": warmest_day["day"] if warmest_day else None,
            "warmest_temp": warmest_day["max"] if warmest_day else None,
            "coldest_day": coldest_day["day"] if coldest_day else None,
            "coldest_temp": coldest_day["min"] if coldest_day else None,
            "comparison_prev_week": temp_comparison,
            "temp_diff": round(temp_comparison_value, 1) if temp_comparison else None,
            "daily_temps": daily_temps
        }

        # 2. Optimal conditions analysis - bird activity by temperature
        cur.execute("""
            SELECT
                CASE
                    WHEN w.temp_outdoor < 0 THEN '<0°C'
                    WHEN w.temp_outdoor >= 0 AND w.temp_outdoor < 5 THEN '0-5°C'
                    WHEN w.temp_outdoor >= 5 AND w.temp_outdoor < 10 THEN '5-10°C'
                    WHEN w.temp_outdoor >= 10 AND w.temp_outdoor < 15 THEN '10-15°C'
                    WHEN w.temp_outdoor >= 15 AND w.temp_outdoor < 20 THEN '15-20°C'
                    WHEN w.temp_outdoor >= 20 THEN '≥20°C'
                END as temp_bracket,
                COUNT(DISTINCT d.id) as detections,
                AVG(w.temp_outdoor) as avg_temp_in_bracket
            FROM bird_detections d
            LEFT JOIN weather_data w
                ON DATE_TRUNC('hour', d.detection_timestamp) = DATE_TRUNC('hour', w.measurement_timestamp)
            WHERE d.detection_timestamp BETWEEN %s AND %s
            AND w.temp_outdoor IS NOT NULL
            GROUP BY temp_bracket
            ORDER BY detections DESC
        """, (start_date, end_date))

        temp_activity = []
        for row in cur.fetchall():
            temp_activity.append({
                "bracket": row[0],
                "detections": row[1],
                "avg_temp": round(float(row[2]), 1) if row[2] else None
            })

        optimal_temp_bracket = temp_activity[0] if temp_activity else None

        data["optimal_conditions"] = {
            "by_temperature": temp_activity,
            "optimal_bracket": optimal_temp_bracket["bracket"] if optimal_temp_bracket else None,
            "optimal_detections": optimal_temp_bracket["detections"] if optimal_temp_bracket else None
        }

        # 3. Wind analysis
        cur.execute("""
            SELECT
                AVG(wind_speed) as avg_wind,
                MAX(wind_gust_speed) as max_gust
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND wind_speed IS NOT NULL
        """, (start_date, end_date))
        result = cur.fetchone()
        avg_wind = float(result[0]) if result[0] else None
        max_gust = float(result[1]) if result[1] else None

        # Bird activity on calm vs windy days
        cur.execute("""
            SELECT
                CASE
                    WHEN w.wind_speed < 2 THEN 'windstil'
                    WHEN w.wind_speed >= 2 AND w.wind_speed < 5 THEN 'lichte wind'
                    WHEN w.wind_speed >= 5 AND w.wind_speed < 10 THEN 'matige wind'
                    WHEN w.wind_speed >= 10 THEN 'harde wind'
                END as wind_category,
                COUNT(DISTINCT d.id) as detections
            FROM bird_detections d
            LEFT JOIN weather_data w
                ON DATE_TRUNC('hour', d.detection_timestamp) = DATE_TRUNC('hour', w.measurement_timestamp)
            WHERE d.detection_timestamp BETWEEN %s AND %s
            AND w.wind_speed IS NOT NULL
            GROUP BY wind_category
            ORDER BY detections DESC
        """, (start_date, end_date))

        wind_activity = []
        for row in cur.fetchall():
            wind_activity.append({
                "category": row[0],
                "detections": row[1]
            })

        data["wind_analysis"] = {
            "avg_speed": round(avg_wind, 1) if avg_wind else None,
            "max_gust": round(max_gust, 1) if max_gust else None,
            "activity_by_wind": wind_activity
        }

        # 4. Humidity & Pressure
        cur.execute("""
            SELECT
                AVG(humidity_outdoor) as avg_humidity,
                AVG(barometer) as avg_pressure,
                MIN(barometer) as min_pressure,
                MAX(barometer) as max_pressure
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND humidity_outdoor IS NOT NULL
            AND barometer IS NOT NULL
        """, (start_date, end_date))
        result = cur.fetchone()

        data["humidity_pressure"] = {
            "avg_humidity": int(result[0]) if result[0] else None,
            "avg_pressure": round(float(result[1]), 1) if result[1] else None,
            "min_pressure": round(float(result[2]), 1) if result[2] else None,
            "max_pressure": round(float(result[3]), 1) if result[3] else None
        }

        # Bird activity by pressure (low vs high)
        cur.execute("""
            WITH pressure_avg AS (
                SELECT AVG(barometer) as avg_p
                FROM weather_data
                WHERE measurement_timestamp BETWEEN %s AND %s
                AND barometer IS NOT NULL
            )
            SELECT
                CASE
                    WHEN w.barometer < (SELECT avg_p FROM pressure_avg) THEN 'lage druk'
                    ELSE 'hoge druk'
                END as pressure_category,
                COUNT(DISTINCT d.id) as detections
            FROM bird_detections d
            LEFT JOIN weather_data w
                ON DATE_TRUNC('hour', d.detection_timestamp) = DATE_TRUNC('hour', w.measurement_timestamp)
            WHERE d.detection_timestamp BETWEEN %s AND %s
            AND w.barometer IS NOT NULL
            GROUP BY pressure_category
        """, (start_date, end_date, start_date, end_date))

        pressure_activity = {}
        for row in cur.fetchall():
            pressure_activity[row[0]] = row[1]

        data["humidity_pressure"]["activity_by_pressure"] = pressure_activity

        # 5. Day/Night temperature difference
        cur.execute("""
            SELECT
                AVG(CASE WHEN EXTRACT(HOUR FROM measurement_timestamp) BETWEEN 6 AND 20
                    THEN temp_outdoor END) as day_temp,
                AVG(CASE WHEN EXTRACT(HOUR FROM measurement_timestamp) NOT BETWEEN 6 AND 20
                    THEN temp_outdoor END) as night_temp
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND temp_outdoor IS NOT NULL
        """, (start_date, end_date))
        result = cur.fetchone()

        day_temp = float(result[0]) if result[0] else None
        night_temp = float(result[1]) if result[1] else None

        data["day_night_temp"] = {
            "day_avg": round(day_temp, 1) if day_temp else None,
            "night_avg": round(night_temp, 1) if night_temp else None,
            "difference": round(day_temp - night_temp, 1) if (day_temp and night_temp) else None
        }

        # Comparison with previous week
        prev_start = start_date - timedelta(days=7)
        prev_end = end_date - timedelta(days=7)

        cur.execute("""
            SELECT COUNT(*), COUNT(DISTINCT species)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
        """, (prev_start, prev_end))
        prev_detections, prev_species = cur.fetchone()

        if prev_detections > 0:
            detection_change = ((data["total_detections"] - prev_detections) / prev_detections) * 100
            data["comparison_last_week"] = {
                "detections_change": f"{detection_change:+.0f}%",
                "species_change": f"{data['unique_species'] - prev_species:+d}",
                "prev_detections": prev_detections,
                "prev_species": prev_species,
                "prev_week_number": prev_start.isocalendar()[1]
            }
        else:
            data["comparison_last_week"] = {
                "detections_change": "N/A",
                "species_change": "N/A",
                "prev_detections": 0,
                "prev_species": 0,
                "prev_week_number": prev_start.isocalendar()[1]
            }

        # Check for milestones
        cur.execute("""
            SELECT COUNT(*)
            FROM bird_detections
            WHERE detection_timestamp <= %s
        """, (end_date,))
        total_all_time = cur.fetchone()[0]

        milestones = []
        for milestone in [1000, 5000, 10000, 25000, 50000, 75000, 100000]:
            if total_all_time >= milestone and total_all_time - data["total_detections"] < milestone:
                milestones.append(f"{milestone:,} detecties bereikt deze week!")

        data["milestones"] = milestones
        data["total_all_time"] = total_all_time

        # New species this year
        cur.execute("""
            SELECT DISTINCT common_name, species
            FROM bird_detections
            WHERE EXTRACT(YEAR FROM detection_timestamp) = %s
            AND detection_timestamp BETWEEN %s AND %s
            AND species NOT IN (
                SELECT DISTINCT species
                FROM bird_detections
                WHERE detection_timestamp < %s
            )
        """, (start_date.year, start_date, end_date, start_date))
        data["new_species_this_week"] = [
            {"name": row[0] or row[1], "scientific_name": row[1]}
            for row in cur.fetchall()
        ]

        cur.close()
        return data

    def generate_report(self, data):
        """Use Claude API to generate narrative report"""

        style_prompt = self.get_style_prompt()

        # Different prompts for short vs extended format
        if self.report_format == 'kort':
            prompt = f"""{style_prompt}

Je schrijft een BEKNOPT weekrapport voor het EMSN vogelmonitoringsproject in Nijverdal, Overijssel.

DATA:
{json.dumps(data, indent=2, ensure_ascii=False)}

STRUCTUUR (kort en bondig):
1. Korte samenvatting van de week (weer + vogelactiviteit in 2-3 zinnen)
2. Top 3 waarnemingen of hoogtepunten
3. Vergelijking met vorige week (1 zin)

LENGTE: 150-200 woorden MAXIMUM
Wees beknopt, alleen de essentie. Geen uitgebreide beschrijvingen.
"""
            max_tokens = 800
        else:  # uitgebreid (default)
            prompt = f"""{style_prompt}

Je schrijft een weekrapport voor het EMSN vogelmonitoringsproject in Nijverdal, Overijssel.

DATA:
{json.dumps(data, indent=2, ensure_ascii=False)}

STRUCTUUR:
1. Opening (weerbeeld, seizoen, gevoel van de week)
2. Weer & Vogels: Bespreek de weersomstandigheden en hoe deze de vogelactiviteit beïnvloedden
   - Temperatuurverloop (min/max/gemiddeld, vergelijking met vorige week)
   - Bij welke temperaturen waren vogels het actiefst?
   - Invloed van wind, regen, luchtvochtigheid en luchtdruk
   - Warmste vs koudste dag
3. Hoogtepunten van de week (top soorten, opmerkelijke momenten)
4. Interessante patronen (busiest/quietest hours, dual detections)
5. Zeldzame waarnemingen
6. Vergelijking met vorige week (zowel vogels als weer)
7. Vooruitblik

LENGTE: 400-600 woorden
Gebruik geen bullet points, schrijf vloeiende paragrafen.
"""
            max_tokens = 2000

        return self.generate_with_claude(prompt, max_tokens=max_tokens)

    def save_report(self, report_text, data, start_date=None, end_date=None):
        """Save report as markdown file with charts and optionally spectrograms"""

        # Create reports directory if it doesn't exist
        REPORTS_PATH.mkdir(parents=True, exist_ok=True)

        # Filename based on format
        format_suffix = "-kort" if self.report_format == 'kort' else ""
        filename = f"{data['year']}-W{data['week_number']:02d}-Weekrapport{format_suffix}.md"
        filepath = REPORTS_PATH / filename

        # Generate charts (fewer for short format)
        print("Genereren grafieken...")
        charts = ReportCharts(REPORTS_PATH)

        # Generate spectrograms
        # - If --spectrograms flag: include full set (top species + highlights)
        # - For uitgebreid format: automatically include highlights spectrograms (max 3)
        spectrograms_markdown = ""
        if start_date and end_date:
            spec_generator = ReportSpectrograms(REPORTS_PATH, self.conn)
            top_species_names = [s['name'] for s in data.get('top_species', [])[:5]]
            highlights = data.get('highlights', {})

            if self.include_spectrograms:
                # Full spectrogram mode: top species + highlights
                print("Zoeken spectrogrammen (volledig)...")
                prepared_specs = spec_generator.prepare_for_report(
                    start_date, end_date,
                    top_species=top_species_names,
                    highlights=highlights,
                    max_total=6 if self.report_format == 'uitgebreid' else 3
                )
            elif self.report_format == 'uitgebreid' and highlights:
                # Auto-include spectrograms for interesting highlights only
                print("Zoeken spectrogrammen (highlights)...")
                prepared_specs = spec_generator.prepare_for_report(
                    start_date, end_date,
                    top_species=None,  # Skip top species
                    highlights=highlights,
                    max_total=3  # Max 3 for auto-include
                )
            else:
                prepared_specs = []

            if prepared_specs:
                spectrograms_markdown = spec_generator.generate_markdown_section(prepared_specs)
                print(f"   - {len(prepared_specs)} spectrogrammen toegevoegd")

        # Always generate top species chart
        chart_top_species = charts.top_species_bar(
            data['top_species'],
            title=f"Top 10 Soorten - Week {data['week_number']}"
        )

        # Extended format gets all charts, short format only gets essentials
        chart_hourly = None
        chart_daily = None
        chart_temp = None
        chart_pie = None
        chart_weather = None
        chart_comparison = None

        if self.report_format == 'uitgebreid':
            chart_hourly = charts.hourly_activity(
                data.get('hourly_activity', {}),
                title=f"Activiteit per Uur - Week {data['week_number']}"
            )

            chart_daily = charts.daily_activity(
                data.get('daily_activity', []),
                title=f"Activiteit per Dag - Week {data['week_number']}"
            )

            chart_temp = charts.temperature_vs_activity(
                data.get('daily_temp_activity', []),
                title=f"Temperatuur vs Vogelactiviteit - Week {data['week_number']}"
            )

            chart_pie = charts.species_pie(
                data['top_species'],
                title=f"Verdeling Soorten - Week {data['week_number']}"
            )

            # Prepare weather data for chart
            weather_chart_data = {
                'wind': data.get('wind_analysis', {}).get('activity_by_wind', []),
                'temperature': data.get('optimal_conditions', {}).get('by_temperature', []),
                'precipitation': {
                    'Droog': data.get('weather_correlation', {}).get('dry_days_detections', 0),
                    'Regen': data.get('weather_correlation', {}).get('rainy_days_detections', 0)
                }
            }
            chart_weather = charts.weather_conditions(
                weather_chart_data,
                title=f"Activiteit per Weersomstandigheid - Week {data['week_number']}"
            )

        # Comparison chart for both formats
        comparison = data.get('comparison_last_week', {})
        if comparison.get('prev_detections', 0) > 0:
            current_data = {
                'label': f'Week {data["week_number"]}',
                'detections': data['total_detections'],
                'species': data['unique_species']
            }
            previous_data = {
                'label': f'Week {comparison["prev_week_number"]}',
                'detections': comparison['prev_detections'],
                'species': comparison['prev_species']
            }
            chart_comparison = charts.comparison_chart(
                current_data, previous_data,
                title=f"Week {data['week_number']} vs Week {comparison['prev_week_number']}"
            )

        print(f"   - {len(charts.generated_charts)} grafieken gegenereerd")

        # Create markdown with frontmatter
        markdown = f"""---
type: weekrapport
week: {data['week_number']}
year: {data['year']}
period: {data['period']}
total_detections: {data['total_detections']}
unique_species: {data['unique_species']}
generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

![EMSN Logo](logo.png)

# Week {data['week_number']} - Vogelactiviteit

**Periode:** {data['period']}
**Detecties:** {data['total_detections']:,}
**Soorten:** {data['unique_species']}

---

{report_text}

---

## Grafieken

"""

        # Add charts to markdown
        if chart_top_species:
            markdown += f"### Top Soorten\n\n![Top 10 Soorten]({chart_top_species.name})\n\n"

        if chart_hourly:
            markdown += f"### Activiteit per Uur\n\n![Activiteit per Uur]({chart_hourly.name})\n\n"

        if chart_daily:
            markdown += f"### Activiteit per Dag\n\n![Activiteit per Dag]({chart_daily.name})\n\n"

        if chart_temp:
            markdown += f"### Temperatuur vs Activiteit\n\n![Temperatuur vs Activiteit]({chart_temp.name})\n\n"

        if chart_pie:
            markdown += f"### Verdeling Soorten\n\n![Verdeling Soorten]({chart_pie.name})\n\n"

        if chart_weather:
            markdown += f"### Weersomstandigheden\n\n![Weersomstandigheden]({chart_weather.name})\n\n"

        if chart_comparison:
            markdown += f"### Vergelijking Vorige Week\n\n![Vergelijking]({chart_comparison.name})\n\n"

        # Add spectrograms section if available
        if spectrograms_markdown:
            markdown += spectrograms_markdown

        # Add highlights section
        highlights = data.get('highlights', {})
        if any(highlights.values()):
            markdown += "---\n\n## Highlights\n\n"

            # New species (most important)
            if highlights.get('new_species'):
                markdown += "### Nieuwe Soorten\n\n"
                for h in highlights['new_species'][:5]:  # Top 5
                    markdown += f"- **{h['common_name']}** (*{h['scientific_name']}*) - eerste detectie ooit! ({h['count']} detecties)\n"
                markdown += "\n"

            # Milestones
            if highlights.get('milestones'):
                markdown += "### Mijlpalen\n\n"
                for h in highlights['milestones']:
                    markdown += f"- {h['message']}\n"
                markdown += "\n"

            # Records
            if highlights.get('records'):
                markdown += "### Records\n\n"
                for h in highlights['records'][:3]:  # Top 3
                    markdown += f"- {h['message']}\n"
                markdown += "\n"

            # Rare species
            if highlights.get('rare_species'):
                markdown += "### Zeldzame Soorten\n\n"
                for h in highlights['rare_species'][:5]:  # Top 5
                    markdown += f"- **{h['species']}** ({h['confidence']:.0%} zekerheid) - totaal {h['total_ever']} detecties ooit\n"
                markdown += "\n"

            # Unusual times
            if highlights.get('unusual_times'):
                markdown += "### Ongewone Waarnemingstijden\n\n"
                for h in highlights['unusual_times'][:3]:  # Top 3
                    markdown += f"- {h['message']}\n"
                markdown += "\n"

        markdown += """---

## Statistieken

### Top 10 Soorten
"""

        for i, species in enumerate(data['top_species'], 1):
            name = species['name']
            scientific = species.get('scientific_name', '')
            if scientific and scientific != name:
                markdown += f"{i}. **{name}** (*{scientific}*): {species['count']:,} detecties\n"
            else:
                markdown += f"{i}. **{name}**: {species['count']:,} detecties\n"

        if data['rare_sightings']:
            markdown += "\n### Zeldzame Waarnemingen\n\n"
            for sighting in data['rare_sightings']:
                name = sighting['species']
                scientific = sighting.get('scientific_name', '')
                if scientific and scientific != name:
                    species_str = f"**{name}** (*{scientific}*)"
                else:
                    species_str = f"**{name}**"
                markdown += f"- {species_str} op {sighting['time']} ({sighting['confidence']:.1%} zekerheid, station {sighting['station']})\n"

        if data['milestones']:
            markdown += "\n### Mijlpalen\n\n"
            for milestone in data['milestones']:
                markdown += f"- {milestone}\n"

        markdown += f"\n### Overige Gegevens\n\n"
        markdown += f"- **Dual detections:** {data['dual_detections']:,}\n"
        markdown += f"- **Drukste uur:** {data['busiest_hour']} ({data.get('busiest_hour_count', 0):,} detecties)\n"
        markdown += f"- **Rustigste uur:** {data['quietest_hour']} ({data.get('quietest_hour_count', 0):,} detecties)\n"
        markdown += f"- **Totaal t/m deze week:** {data['total_all_time']:,} detecties\n"

        if data['comparison_last_week']['detections_change'] != 'N/A':
            markdown += f"\n### Vergelijking met vorige week\n\n"
            markdown += f"- **Detecties:** {data['comparison_last_week']['detections_change']}\n"
            markdown += f"- **Nieuwe soorten:** {data['comparison_last_week']['species_change']}\n"

        # Weather statistics section
        markdown += f"\n### Weerdata\n\n"

        temp_stats = data.get('temperature_stats', {})
        if temp_stats.get('week_avg'):
            markdown += f"**Temperatuur:**\n"
            markdown += f"- Gemiddeld: {temp_stats['week_avg']}°C\n"
            markdown += f"- Min/Max: {temp_stats['week_min']}°C / {temp_stats['week_max']}°C\n"
            if temp_stats.get('warmest_day'):
                markdown += f"- Warmste dag: {temp_stats['warmest_day']} ({temp_stats['warmest_temp']}°C)\n"
            if temp_stats.get('coldest_day'):
                markdown += f"- Koudste dag: {temp_stats['coldest_day']} ({temp_stats['coldest_temp']}°C)\n"
            if temp_stats.get('comparison_prev_week'):
                markdown += f"- T.o.v. vorige week: {temp_stats['temp_diff']}°C {temp_stats['comparison_prev_week']}\n"
            markdown += f"\n"

        day_night = data.get('day_night_temp', {})
        if day_night.get('day_avg'):
            markdown += f"**Dag/Nacht:**\n"
            markdown += f"- Overdag (6-20u): {day_night['day_avg']}°C\n"
            markdown += f"- 's Nachts: {day_night['night_avg']}°C\n"
            markdown += f"- Verschil: {day_night['difference']}°C\n\n"

        optimal = data.get('optimal_conditions', {})
        if optimal.get('optimal_bracket'):
            markdown += f"**Optimale Temperatuur voor Vogels:**\n"
            markdown += f"- Meeste activiteit: {optimal['optimal_bracket']} ({optimal['optimal_detections']:,} detecties)\n"
            if optimal.get('by_temperature'):
                markdown += f"- Alle temperatuur brackets:\n"
                for temp_data in optimal['by_temperature']:
                    markdown += f"  - {temp_data['bracket']}: {temp_data['detections']:,} detecties\n"
            markdown += f"\n"

        wind = data.get('wind_analysis', {})
        if wind.get('avg_speed') is not None:
            markdown += f"**Wind:**\n"
            markdown += f"- Gemiddelde snelheid: {wind['avg_speed']} m/s\n"
            markdown += f"- Maximale windstoot: {wind['max_gust']} m/s\n"
            if wind.get('activity_by_wind'):
                markdown += f"- Activiteit per windsterkte:\n"
                for wind_data in wind['activity_by_wind']:
                    markdown += f"  - {wind_data['category'].capitalize()}: {wind_data['detections']:,} detecties\n"
            markdown += f"\n"

        humidity = data.get('humidity_pressure', {})
        if humidity.get('avg_humidity'):
            markdown += f"**Luchtvochtigheid & Druk:**\n"
            markdown += f"- Gemiddelde luchtvochtigheid: {humidity['avg_humidity']}%\n"
            markdown += f"- Gemiddelde luchtdruk: {humidity['avg_pressure']} hPa\n"
            markdown += f"- Druk range: {humidity['min_pressure']} - {humidity['max_pressure']} hPa\n"
            if humidity.get('activity_by_pressure'):
                markdown += f"- Activiteit bij lage druk: {humidity['activity_by_pressure'].get('lage druk', 0):,} detecties\n"
                markdown += f"- Activiteit bij hoge druk: {humidity['activity_by_pressure'].get('hoge druk', 0):,} detecties\n"

        # Add weather forecast for coming week (only for extended format)
        if self.report_format == 'uitgebreid':
            markdown += "\n"
            try:
                weather_forecast = get_forecast_for_report()
                markdown += weather_forecast
                markdown += "\n"
            except Exception as e:
                print(f"   WARNING: Kon weersverwachting niet ophalen: {e}")
                markdown += "\n*Weersverwachting niet beschikbaar.*\n"

        markdown += f"""
---

*Geschreven door Ecologisch Monitoring Systeem Nijverdal - Ronny Hullegie*
*Meetlocatie: Nijverdal, Overijssel (52.36°N, 6.46°E)*

**Contact:** emsn@ronnyhullegie.nl | **Website:** www.ronnyhullegie.nl

© {data['year']} Ronny Hullegie. Alle rechten voorbehouden.
Licentie: CC BY-NC 4.0 (gebruik toegestaan met bronvermelding, niet commercieel)
"""

        # Write file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"Rapport opgeslagen: {filepath}")
        return filepath

    def run(self):
        """Main execution"""
        print("EMSN Weekly Report Generator")
        print("=" * 60)

        # Get week dates
        start_date, end_date = self.get_week_dates()
        print(f"Periode: {start_date.strftime('%Y-%m-%d')} tot {end_date.strftime('%Y-%m-%d')}")

        # Connect to database
        if not self.connect_db():
            return False

        print("Verzamelen data...")
        data = self.collect_data(start_date, end_date)
        print(f"   - {data['total_detections']:,} detecties")
        print(f"   - {data['unique_species']} soorten")
        print(f"   - {data['dual_detections']:,} dual detections")

        # Generate highlights
        print("Detecteren highlights...")
        highlights_detector = ReportHighlights(self.conn)
        data['highlights'] = highlights_detector.get_all_highlights(start_date, end_date)
        highlight_count = sum(len(v) for v in data['highlights'].values())
        print(f"   - {highlight_count} highlights gedetecteerd")

        # Generate report with Claude
        print("Genereren rapport met Claude AI...")
        report = self.generate_report(data)

        if not report:
            print("ERROR: Rapport generatie mislukt")
            return False

        print(f"   - {len(report)} karakters gegenereerd")

        # Save report
        print("Opslaan rapport...")
        filepath = self.save_report(report, data, start_date, end_date)

        # Update web index
        print("Bijwerken web index...")
        self.update_web_index()

        # Pending mode: add to review queue instead of sending
        if self.pending_mode:
            print("Toevoegen aan review queue...")
            report_id = self.create_pending_report(
                report_type='weekly',
                report_title=f"Weekrapport Week {data['week_number']} - {data['year']}",
                report_filename=filepath.name,
                markdown_path=filepath,
                report_data={
                    'total_detections': data['total_detections'],
                    'unique_species': data['unique_species'],
                    'week_number': data['week_number'],
                    'year': data['year'],
                    'period': data['period']
                }
            )
            if report_id:
                print(f"   - Rapport toegevoegd aan review queue (ID: {report_id})")
                print("   - Notificatie verzonden naar Ulanzi & email")
            else:
                print("   WARNING: Kon rapport niet toevoegen aan review queue")

            print(f"\nWeekrapport succesvol gegenereerd en wacht op review")
            print(f"Bestand: {filepath}")

        else:
            # Original behavior: send emails per style preference
            print("Versturen emails per stijlvoorkeur...")
            subject = f"EMSN Weekrapport Week {data['week_number']} - {data['year']}"

            # Get recipients grouped by their preferred style
            recipients_by_style = self.get_recipients_by_style(report_type="weekly")

            if not recipients_by_style:
                print("   - Geen ontvangers voor automatische verzending")
            else:
                # Track which styles we need to generate
                generated_reports = {}  # style_name -> report_text

                # Always have the primary style available
                generated_reports[self.style_name] = report

                for style_name, recipients in recipients_by_style.items():
                    print(f"   - Stijl '{style_name}': {len(recipients)} ontvanger(s)")

                    # Generate report for this style if not already done
                    if style_name not in generated_reports:
                        print(f"     Genereren rapport in stijl '{style_name}'...")
                        # Temporarily switch style
                        original_style = self.style
                        original_style_name = self.style_name
                        self.get_style(style_name)

                        style_report = self.generate_report(data)
                        if style_report:
                            generated_reports[style_name] = style_report
                            print(f"     - {len(style_report)} karakters gegenereerd")
                        else:
                            print(f"     WARNING: Kon rapport niet genereren, gebruik default")
                            generated_reports[style_name] = report

                        # Restore original style
                        self.style = original_style
                        self.style_name = original_style_name

                    # Create personalized email body with the style-specific content
                    style_report_text = generated_reports.get(style_name, report)
                    email_body = self._create_email_body(data, style_report_text, style_name)

                    # Send to recipients of this style
                    self.send_email_to_recipients(subject, email_body, recipients)

            print(f"\nWeekrapport succesvol gegenereerd")
            print(f"Bestand: {filepath}")

        self.close_db()
        return True

    def _create_email_body(self, data, report_text, style_name):
        """Create email body with report content"""
        style_labels = {
            'wetenschappelijk': 'Wetenschappelijk',
            'populair': 'Populair',
            'kinderen': 'Kinderen',
            'technisch': 'Technisch'
        }
        style_label = style_labels.get(style_name, style_name.capitalize())

        email_body = f"""Weekrapport Week {data['week_number']} ({data['period']})
Stijl: {style_label}

Samenvatting:
- {data['total_detections']:,} detecties
- {data['unique_species']} soorten
- {data['dual_detections']:,} dual detections

Top 3 soorten:
"""
        for i, species in enumerate(data['top_species'][:3], 1):
            name = species['name']
            scientific = species.get('scientific_name', '')
            if scientific and scientific != name:
                email_body += f"{i}. {name} ({scientific}): {species['count']:,} detecties\n"
            else:
                email_body += f"{i}. {name}: {species['count']:,} detecties\n"

        email_body += f"""
--- Rapport Tekst ({style_label}) ---

{report_text}

---

Bekijk het volledige rapport met grafieken op:
http://192.168.1.25/rapporten/

---
EMSN Vogelmonitoring Nijverdal
"""
        return email_body


def main():
    import argparse
    from report_base import get_available_styles

    parser = argparse.ArgumentParser(description='Generate EMSN weekly bird report')
    parser.add_argument('--style', type=str, default=None,
                        help='Writing style (default: wetenschappelijk)')
    parser.add_argument('--format', type=str, default='uitgebreid',
                        choices=['kort', 'uitgebreid'],
                        help='Report format: kort (150-200 woorden, 2 grafieken) or uitgebreid (400-600 woorden, alle grafieken)')
    parser.add_argument('--spectrograms', action='store_true',
                        help='Include spectrograms from BirdNET-Pi recordings')
    parser.add_argument('--pending', action='store_true',
                        help='Add report to review queue instead of sending directly')
    parser.add_argument('--list-styles', action='store_true',
                        help='List available writing styles and exit')

    args = parser.parse_args()

    if args.list_styles:
        styles = get_available_styles()
        print("Beschikbare schrijfstijlen:")
        for name, info in styles.items():
            print(f"  {name}: {info['description']}")
        sys.exit(0)

    generator = WeeklyReportGenerator(
        style=args.style,
        report_format=args.format,
        include_spectrograms=args.spectrograms,
        pending_mode=args.pending
    )
    success = generator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
