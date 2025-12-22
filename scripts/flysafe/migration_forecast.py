#!/usr/bin/env python3
"""
FlySafe Migration Forecast
==========================

Predicts bird migration activity based on:
- Historical radar patterns
- Weather conditions (wind, temperature, pressure)
- Seasonal timing
- Recent detection trends

Author: EMSN Team
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import math

# Import secrets
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
try:
    from emsn_secrets import get_postgres_config
    _pg = get_postgres_config()
except ImportError:
    _pg = {'host': '192.168.1.25', 'port': 5433, 'database': 'emsn',
           'user': 'birdpi_zolder', 'password': os.getenv('EMSN_DB_PASSWORD', '')}

# Configuration (from secrets)
DB_CONFIG = {
    'host': _pg.get('host', '192.168.1.25'),
    'port': _pg.get('port', 5433),
    'database': _pg.get('database', 'emsn'),
    'user': _pg.get('user', 'birdpi_zolder'),
    'password': _pg.get('password', '') or os.getenv('EMSN_DB_PASSWORD', '')
}

LOGS_DIR = Path("/mnt/usb/logs")

# Migration season parameters (Netherlands)
SPRING_MIGRATION = {'start': (3, 1), 'peak': (4, 15), 'end': (5, 31)}  # March-May
AUTUMN_MIGRATION = {'start': (8, 15), 'peak': (10, 15), 'end': (11, 30)}  # Aug-Nov

# Ideal weather conditions for migration
IDEAL_CONDITIONS = {
    'wind_speed_max': 8.0,  # m/s - birds prefer calm to moderate winds
    'wind_direction_favorable': ['N', 'NE', 'E', 'S', 'SW'],  # Tailwinds for NL
    'temp_range': (5, 15),  # Celsius - moderate temps
    'pressure_rising': True,  # High pressure = good visibility
    'no_precipitation': True
}

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "migration-forecast.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MigrationForecaster:
    """Predicts bird migration activity"""

    def __init__(self):
        pass

    def get_db_connection(self):
        """Create database connection"""
        return psycopg2.connect(**DB_CONFIG)

    def get_seasonal_factor(self, date=None):
        """
        Calculate seasonal migration factor (0-1)
        Higher during peak migration periods
        """
        if date is None:
            date = datetime.now()

        month = date.month
        day = date.day
        day_of_year = date.timetuple().tm_yday

        # Spring migration: March-May
        spring_start = datetime(date.year, *SPRING_MIGRATION['start']).timetuple().tm_yday
        spring_peak = datetime(date.year, *SPRING_MIGRATION['peak']).timetuple().tm_yday
        spring_end = datetime(date.year, *SPRING_MIGRATION['end']).timetuple().tm_yday

        # Autumn migration: August-November
        autumn_start = datetime(date.year, *AUTUMN_MIGRATION['start']).timetuple().tm_yday
        autumn_peak = datetime(date.year, *AUTUMN_MIGRATION['peak']).timetuple().tm_yday
        autumn_end = datetime(date.year, *AUTUMN_MIGRATION['end']).timetuple().tm_yday

        factor = 0.1  # Base factor outside migration season

        # Spring migration
        if spring_start <= day_of_year <= spring_end:
            if day_of_year <= spring_peak:
                # Rising to peak
                progress = (day_of_year - spring_start) / (spring_peak - spring_start)
            else:
                # Declining from peak
                progress = 1 - (day_of_year - spring_peak) / (spring_end - spring_peak)
            factor = 0.3 + (0.7 * progress)

        # Autumn migration (typically stronger in NL)
        elif autumn_start <= day_of_year <= autumn_end:
            if day_of_year <= autumn_peak:
                progress = (day_of_year - autumn_start) / (autumn_peak - autumn_start)
            else:
                progress = 1 - (day_of_year - autumn_peak) / (autumn_end - autumn_peak)
            factor = 0.4 + (0.6 * progress)  # Autumn slightly stronger

        return round(factor, 2)

    def get_weather_factor(self, weather_data=None):
        """
        Calculate weather favorability factor (0-1)
        Based on current weather conditions
        """
        if weather_data is None:
            weather_data = self.get_latest_weather()

        if not weather_data:
            return 0.5  # Neutral if no data

        factor = 0.5

        # Wind speed (lower is better for migration)
        wind_speed = float(weather_data.get('wind_speed') or 0)
        if wind_speed < 3:
            factor += 0.15
        elif wind_speed < 6:
            factor += 0.1
        elif wind_speed > 10:
            factor -= 0.2

        # Temperature
        temp = float(weather_data.get('temperature') or 10)
        if 5 <= temp <= 15:
            factor += 0.1
        elif temp < 0 or temp > 25:
            factor -= 0.15

        # Pressure trend (rising = good)
        pressure = float(weather_data.get('pressure') or 1013)
        if pressure > 1020:
            factor += 0.1
        elif pressure < 1000:
            factor -= 0.1

        # Rain (no rain is better)
        rain = weather_data.get('rain') or 0
        if rain == 0:
            factor += 0.1
        elif rain > 1:
            factor -= 0.2

        # Cloud cover (clear nights better for nocturnal migration)
        hour = datetime.now().hour
        if 20 <= hour or hour <= 6:  # Night
            cloud = weather_data.get('cloud_cover', 50)
            if cloud < 30:
                factor += 0.1

        return round(max(0, min(1, factor)), 2)

    def get_latest_weather(self):
        """Get latest weather data from database"""
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT
                    temp_outdoor as temperature,
                    wind_speed,
                    barometer as pressure,
                    rain_rate as rain
                FROM weather_data
                ORDER BY measurement_timestamp DESC
                LIMIT 1
            """)

            result = cur.fetchone()
            conn.close()

            if result:
                return dict(result)
            return None

        except Exception as e:
            logger.warning(f"Could not get weather data: {e}")
            return None

    def get_historical_factor(self, days=7):
        """
        Calculate factor based on recent radar history
        Trending migration activity
        """
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT
                    AVG(intensity_level) as avg_intensity,
                    MAX(intensity_level) as max_intensity,
                    COUNT(*) as observations
                FROM radar_observations
                WHERE observation_date >= CURRENT_DATE - INTERVAL '%s days'
            """, (days,))

            result = cur.fetchone()
            conn.close()

            if result and result['avg_intensity']:
                # Normalize to 0-1 (convert Decimal to float)
                return round(float(result['avg_intensity']) / 100, 2)
            return 0.1

        except Exception as e:
            logger.warning(f"Could not get historical data: {e}")
            return 0.1

    def get_time_of_day_factor(self, hour=None):
        """
        Factor based on time of day
        Nocturnal migration is strongest 2-4 hours after sunset
        """
        if hour is None:
            hour = datetime.now().hour

        # Peak nocturnal migration: 22:00 - 04:00
        # Secondary peak: Dawn (06:00 - 08:00)
        if 22 <= hour or hour <= 4:
            return 0.9
        elif 4 < hour <= 8:
            return 0.7
        elif 18 <= hour < 22:
            return 0.6
        else:
            return 0.3

    def get_detection_trend_factor(self, hours=24):
        """
        Factor based on recent BirdNET detection trends
        """
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT
                    COUNT(*) as recent_count
                FROM bird_detections
                WHERE detection_timestamp >= NOW() - INTERVAL '%s hours'
                  AND confidence >= 0.7
            """, (hours,))

            result = cur.fetchone()
            conn.close()

            if result:
                count = result['recent_count']
                # Normalize: 100+ detections/day = high activity
                return round(min(1.0, count / 100), 2)
            return 0.1

        except Exception as e:
            logger.warning(f"Could not get detection trend: {e}")
            return 0.1

    def generate_forecast(self, target_date=None):
        """
        Generate migration forecast
        Returns prediction with confidence and reasoning
        """
        if target_date is None:
            target_date = datetime.now()

        # Calculate all factors
        seasonal = self.get_seasonal_factor(target_date)
        weather = self.get_weather_factor()
        historical = self.get_historical_factor()
        time_factor = self.get_time_of_day_factor(target_date.hour)
        detection_trend = self.get_detection_trend_factor()

        # Weighted combination
        weights = {
            'seasonal': 0.30,
            'weather': 0.25,
            'historical': 0.15,
            'time_of_day': 0.15,
            'detection_trend': 0.15
        }

        prediction_score = (
            seasonal * weights['seasonal'] +
            weather * weights['weather'] +
            historical * weights['historical'] +
            time_factor * weights['time_of_day'] +
            detection_trend * weights['detection_trend']
        )

        # Determine category
        if prediction_score >= 0.7:
            category = 'HOOG'
            emoji = '🔴'
        elif prediction_score >= 0.5:
            category = 'GEMIDDELD'
            emoji = '🟡'
        elif prediction_score >= 0.3:
            category = 'LAAG'
            emoji = '🟢'
        else:
            category = 'MINIMAAL'
            emoji = '⚪'

        # Confidence based on data availability
        confidence = 0.5
        if historical > 0.1:
            confidence += 0.2
        if weather != 0.5:
            confidence += 0.2
        if detection_trend > 0.1:
            confidence += 0.1

        forecast = {
            'timestamp': datetime.now().isoformat(),
            'target_date': target_date.isoformat(),
            'prediction': {
                'score': round(prediction_score * 100, 1),
                'category': category,
                'emoji': emoji
            },
            'confidence': round(confidence * 100, 1),
            'factors': {
                'seasonal': {'value': seasonal, 'weight': weights['seasonal'], 'contribution': round(seasonal * weights['seasonal'] * 100, 1)},
                'weather': {'value': weather, 'weight': weights['weather'], 'contribution': round(weather * weights['weather'] * 100, 1)},
                'historical': {'value': historical, 'weight': weights['historical'], 'contribution': round(historical * weights['historical'] * 100, 1)},
                'time_of_day': {'value': time_factor, 'weight': weights['time_of_day'], 'contribution': round(time_factor * weights['time_of_day'] * 100, 1)},
                'detection_trend': {'value': detection_trend, 'weight': weights['detection_trend'], 'contribution': round(detection_trend * weights['detection_trend'] * 100, 1)}
            },
            'reasoning': self._generate_reasoning(seasonal, weather, historical, time_factor, detection_trend)
        }

        return forecast

    def _generate_reasoning(self, seasonal, weather, historical, time_factor, detection_trend):
        """Generate human-readable reasoning"""
        reasons = []

        # Seasonal
        if seasonal >= 0.7:
            reasons.append("We zitten in piek migratieseizoen")
        elif seasonal >= 0.4:
            reasons.append("Actief migratieseizoen")
        elif seasonal < 0.2:
            reasons.append("Buiten normaal migratieseizoen")

        # Weather
        if weather >= 0.6:
            reasons.append("Weersomstandigheden gunstig voor trek")
        elif weather <= 0.3:
            reasons.append("Weer ongunstig (wind/regen)")

        # Historical
        if historical >= 0.5:
            reasons.append("Recente radar toont hoge activiteit")
        elif historical <= 0.2:
            reasons.append("Radar activiteit afgelopen week laag")

        # Time
        if time_factor >= 0.8:
            reasons.append("Optimaal tijdstip voor nachtelijke trek")
        elif time_factor <= 0.4:
            reasons.append("Overdag minder trekactiviteit verwacht")

        # Detection trend
        if detection_trend >= 0.5:
            reasons.append("BirdNET toont verhoogde activiteit")

        return "; ".join(reasons) if reasons else "Normale condities"

    def forecast_next_24h(self):
        """Generate forecasts for next 24 hours"""
        forecasts = []
        now = datetime.now()

        for hours_ahead in [0, 6, 12, 18, 24]:
            target = now + timedelta(hours=hours_ahead)
            forecast = self.generate_forecast(target)
            forecast['hours_ahead'] = hours_ahead
            forecasts.append(forecast)

        return forecasts

    def print_forecast(self, forecast):
        """Print forecast in readable format"""
        pred = forecast['prediction']

        print(f"\n{pred['emoji']} Vogeltrek Voorspelling: {pred['category']}")
        print(f"   Score: {pred['score']}%")
        print(f"   Vertrouwen: {forecast['confidence']}%")
        print(f"\n📊 Factor Bijdragen:")

        for name, data in forecast['factors'].items():
            bar_len = int(data['contribution'] / 2)
            bar = '█' * bar_len + '░' * (15 - bar_len)
            print(f"   {name:15} [{bar}] {data['contribution']}%")

        print(f"\n💡 {forecast['reasoning']}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='FlySafe Migration Forecast')
    parser.add_argument('--json', action='store_true', help='Output raw JSON')
    parser.add_argument('--24h', action='store_true', dest='full_day', help='Forecast next 24 hours')

    args = parser.parse_args()

    forecaster = MigrationForecaster()

    if args.full_day:
        forecasts = forecaster.forecast_next_24h()
        if args.json:
            print(json.dumps(forecasts, indent=2))
        else:
            print("\n" + "="*60)
            print("  VOGELTREK VOORSPELLING - KOMENDE 24 UUR")
            print("="*60)
            for f in forecasts:
                hours = f['hours_ahead']
                target = datetime.fromisoformat(f['target_date'])
                print(f"\n⏰ +{hours}h ({target.strftime('%H:%M')})")
                forecaster.print_forecast(f)
            print("="*60)
    else:
        forecast = forecaster.generate_forecast()
        if args.json:
            print(json.dumps(forecast, indent=2))
        else:
            print("\n" + "="*60)
            print("  VOGELTREK VOORSPELLING - NU")
            print("="*60)
            forecaster.print_forecast(forecast)
            print("="*60 + "\n")


if __name__ == '__main__':
    main()
