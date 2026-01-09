#!/usr/bin/env python3
"""
EMSN Weather Forecast Module
Fetches weather forecast from Open-Meteo API (free, no API key required)
For Nijverdal, Overijssel (52.36°N, 6.46°E)
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional


# Nijverdal coordinates
LATITUDE = 52.36
LONGITUDE = 6.46

# Open-Meteo API endpoint
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def get_weather_forecast(days: int = 7) -> Optional[Dict]:
    """
    Get weather forecast for the coming days.

    Args:
        days: Number of days to forecast (1-16)

    Returns:
        Dict with forecast data or None on error
    """
    try:
        params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "weather_code",
                "sunrise",
                "sunset"
            ],
            "timezone": "Europe/Amsterdam",
            "forecast_days": min(days, 16)  # API supports up to 16 days
        }

        response = requests.get(FORECAST_URL, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Parse daily data
        daily = data.get("daily", {})

        forecast_days = []
        dates = daily.get("time", [])

        for i, date_str in enumerate(dates):
            day_data = {
                "date": date_str,
                "date_formatted": _format_date(date_str),
                "temp_max": daily.get("temperature_2m_max", [])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
                "temp_min": daily.get("temperature_2m_min", [])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
                "precipitation": daily.get("precipitation_sum", [])[i] if i < len(daily.get("precipitation_sum", [])) else None,
                "precipitation_probability": daily.get("precipitation_probability_max", [])[i] if i < len(daily.get("precipitation_probability_max", [])) else None,
                "wind_speed_max": daily.get("wind_speed_10m_max", [])[i] if i < len(daily.get("wind_speed_10m_max", [])) else None,
                "weather_code": daily.get("weather_code", [])[i] if i < len(daily.get("weather_code", [])) else None,
                "sunrise": daily.get("sunrise", [])[i] if i < len(daily.get("sunrise", [])) else None,
                "sunset": daily.get("sunset", [])[i] if i < len(daily.get("sunset", [])) else None,
            }

            # Add weather description
            day_data["weather_description"] = _weather_code_to_description(day_data["weather_code"])
            day_data["weather_icon"] = _weather_code_to_icon(day_data["weather_code"])

            forecast_days.append(day_data)

        # Calculate summary statistics
        if forecast_days:
            temps_max = [d["temp_max"] for d in forecast_days if d["temp_max"] is not None]
            temps_min = [d["temp_min"] for d in forecast_days if d["temp_min"] is not None]
            precip = [d["precipitation"] for d in forecast_days if d["precipitation"] is not None]
            precip_prob = [d["precipitation_probability"] for d in forecast_days if d["precipitation_probability"] is not None]

            summary = {
                "avg_temp_max": round(sum(temps_max) / len(temps_max), 1) if temps_max else None,
                "avg_temp_min": round(sum(temps_min) / len(temps_min), 1) if temps_min else None,
                "highest_temp": max(temps_max) if temps_max else None,
                "lowest_temp": min(temps_min) if temps_min else None,
                "total_precipitation": round(sum(precip), 1) if precip else 0,
                "rainy_days": sum(1 for p in precip if p and p > 0.5),
                "avg_precipitation_chance": round(sum(precip_prob) / len(precip_prob)) if precip_prob else None,
            }

            # Determine overall forecast
            if summary["rainy_days"] >= 4:
                summary["overall"] = "nat"
            elif summary["rainy_days"] >= 2:
                summary["overall"] = "wisselvallig"
            else:
                summary["overall"] = "droog"

            # Temperature trend
            if temps_max and len(temps_max) >= 3:
                first_half = sum(temps_max[:len(temps_max)//2]) / (len(temps_max)//2)
                second_half = sum(temps_max[len(temps_max)//2:]) / (len(temps_max) - len(temps_max)//2)
                if second_half - first_half > 2:
                    summary["temp_trend"] = "stijgend"
                elif first_half - second_half > 2:
                    summary["temp_trend"] = "dalend"
                else:
                    summary["temp_trend"] = "stabiel"
            else:
                summary["temp_trend"] = "onbekend"

        else:
            summary = {}

        return {
            "location": "Nijverdal, Overijssel",
            "coordinates": {"lat": LATITUDE, "lon": LONGITUDE},
            "generated": datetime.now().isoformat(),
            "days": forecast_days,
            "summary": summary
        }

    except requests.exceptions.RequestException as e:
        print(f"Weather forecast API error: {e}")
        return None
    except Exception as e:
        print(f"Weather forecast error: {e}")
        return None


def _format_date(date_str: str) -> str:
    """Format date string to Dutch readable format."""
    try:
        dt = datetime.fromisoformat(date_str)
        day_names = ['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag']
        month_names = ['januari', 'februari', 'maart', 'april', 'mei', 'juni',
                       'juli', 'augustus', 'september', 'oktober', 'november', 'december']
        return f"{day_names[dt.weekday()]} {dt.day} {month_names[dt.month - 1]}"
    except (ValueError, IndexError):
        return date_str


def _weather_code_to_description(code: Optional[int]) -> str:
    """Convert WMO weather code to Dutch description."""
    if code is None:
        return "onbekend"

    weather_codes = {
        0: "helder",
        1: "overwegend helder",
        2: "half bewolkt",
        3: "bewolkt",
        45: "mist",
        48: "rijpmist",
        51: "lichte motregen",
        53: "motregen",
        55: "dichte motregen",
        56: "lichte ijzel",
        57: "ijzel",
        61: "lichte regen",
        63: "regen",
        65: "zware regen",
        66: "lichte ijsregen",
        67: "ijsregen",
        71: "lichte sneeuw",
        73: "sneeuw",
        75: "zware sneeuw",
        77: "sneeuwkorrels",
        80: "lichte buien",
        81: "buien",
        82: "zware buien",
        85: "lichte sneeuwbuien",
        86: "sneeuwbuien",
        95: "onweer",
        96: "onweer met hagel",
        99: "zwaar onweer met hagel",
    }
    return weather_codes.get(code, "onbekend")


def _weather_code_to_icon(code: Optional[int]) -> str:
    """Convert WMO weather code to text description."""
    if code is None:
        return "onbekend"

    if code == 0:
        return "zonnig"
    elif code in [1, 2]:
        return "licht bewolkt"
    elif code == 3:
        return "bewolkt"
    elif code in [45, 48]:
        return "mist"
    elif code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]:
        return "regen"
    elif code in [71, 73, 75, 77, 85, 86]:
        return "sneeuw"
    elif code in [95, 96, 99]:
        return "onweer"
    else:
        return "wisselend"


def format_forecast_for_report(forecast: Dict) -> str:
    """
    Format forecast data as markdown text for inclusion in reports.

    Args:
        forecast: Forecast data from get_weather_forecast()

    Returns:
        Markdown formatted forecast section
    """
    if not forecast or not forecast.get("days"):
        return "*Weersverwachting kon niet worden opgehaald.*"

    days = forecast["days"]
    summary = forecast.get("summary", {})

    markdown = "### Weersverwachting Komende Week\n\n"

    # Summary line
    if summary:
        markdown += f"**Vooruitzicht:** {summary.get('overall', 'onbekend').capitalize()}"
        if summary.get("temp_trend"):
            markdown += f" met {summary['temp_trend']}e temperaturen"
        markdown += ".\n\n"

        if summary.get("avg_temp_max") and summary.get("avg_temp_min"):
            markdown += f"- **Temperatuur:** gemiddeld {summary['avg_temp_min']}°C tot {summary['avg_temp_max']}°C\n"
        if summary.get("highest_temp") and summary.get("lowest_temp"):
            markdown += f"- **Extremen:** {summary['lowest_temp']}°C tot {summary['highest_temp']}°C\n"
        if summary.get("total_precipitation") is not None:
            markdown += f"- **Neerslag:** {summary['total_precipitation']}mm totaal ({summary.get('rainy_days', 0)} regendag{'en' if summary.get('rainy_days', 0) != 1 else ''})\n"
        markdown += "\n"

    # Daily forecast table
    markdown += "| Dag | Weer | Temp | Neerslag | Wind |\n"
    markdown += "|-----|------|------|----------|------|\n"

    for day in days[:7]:  # Max 7 days
        date_parts = day['date_formatted'].split(' ')
        day_name = date_parts[0][:2].capitalize()  # ma, di, wo, etc.

        icon = day.get('weather_icon', '')
        desc = day.get('weather_description', '')

        temp_min = day.get('temp_min')
        temp_max = day.get('temp_max')
        temp_str = f"{temp_min:.0f}°/{temp_max:.0f}°" if temp_min is not None and temp_max is not None else "?"

        precip = day.get('precipitation', 0) or 0
        precip_prob = day.get('precipitation_probability', 0) or 0
        precip_str = f"{precip:.1f}mm ({precip_prob}%)" if precip > 0.1 else "droog"

        wind = day.get('wind_speed_max', 0) or 0
        wind_str = f"{wind:.0f} km/u" if wind else "?"

        markdown += f"| {day_name} | {icon} {desc} | {temp_str} | {precip_str} | {wind_str} |\n"

    markdown += "\n*Bron: Open-Meteo.com*\n"

    return markdown


def get_forecast_for_report() -> str:
    """
    Convenience function to get formatted forecast for direct inclusion in reports.

    Returns:
        Markdown formatted forecast section
    """
    forecast = get_weather_forecast(days=7)
    return format_forecast_for_report(forecast)


if __name__ == "__main__":
    # Test the forecast
    print("Testing weather forecast...")
    forecast = get_weather_forecast(7)

    if forecast:
        print(f"\nForecast for {forecast['location']}")
        print(f"Generated: {forecast['generated']}")
        print(f"\nSummary: {forecast['summary']}")
        print(f"\nDaily forecast:")
        for day in forecast['days']:
            print(f"  {day['date_formatted']}: {day['weather_icon']} {day['weather_description']}, "
                  f"{day['temp_min']:.0f}°C - {day['temp_max']:.0f}°C, "
                  f"wind {day['wind_speed_max']:.0f} km/u")

        print("\n" + "="*60)
        print("\nFormatted for report:")
        print(format_forecast_for_report(forecast))
    else:
        print("Failed to get forecast")
