#!/usr/bin/env python3
"""
EMSN 2.0 - Ulanzi TC001 Notificatie Configuratie
"""

import sys
from pathlib import Path

# Import secrets voor credentials
sys.path.insert(0, str(Path(__file__).parent))
try:
    from emsn_secrets import get_postgres_config, get_mqtt_config
    _pg = get_postgres_config()
    _mqtt = get_mqtt_config()
except ImportError:
    import os
    _pg = {'password': os.environ.get('EMSN_DB_PASSWORD', '')}
    _mqtt = {'password': os.environ.get('EMSN_MQTT_PASSWORD', '')}

# Ulanzi/AWTRIX Configuration
ULANZI = {
    'ip': '192.168.1.11',
    'api_base': 'http://192.168.1.11/api',
    'notify_endpoint': '/notify',
    'rtttl_endpoint': '/rtttl',
}

# MQTT Configuration (credentials uit secrets)
MQTT = {
    'broker': '192.168.1.178',
    'port': 1883,
    'username': _mqtt.get('username', 'ecomonitor'),
    'password': _mqtt.get('password', ''),
    'topics': {
        # Nieuwe JSON topics van birdnet_mqtt_publisher (met vocalization)
        'zolder_detection': 'birdnet/zolder/detection',
        'berging_detection': 'birdnet/berging/detection',
        'dual_detection': 'emsn2/dual/detection/new',
        'ulanzi_notify': 'emsn2/ulanzi/notify',
        'presence': 'emsn2/presence/home',
    }
}

# PostgreSQL Configuration (credentials uit secrets)
PG_CONFIG = {
    'host': _pg.get('host', '192.168.1.25'),
    'port': _pg.get('port', 5433),
    'database': _pg.get('database', 'emsn'),
    'user': _pg.get('user', 'birdpi_zolder'),
    'password': _pg.get('password', '')
}

# RTTTL Sounds - staan al op Ulanzi in MELODIES map
RTTTL_SOUNDS = {
    'dual': 'emsn_dual:d=4,o=5,b=180:8g,8c6',
    'green': 'emsn_green:d=4,o=5,b=200:8c6',      # 90%+ confidence
    'yellow': 'emsn_yellow:d=4,o=5,b=200:8g',     # 85-89%
    'orange': 'emsn_orange:d=4,o=5,b=200:8e',     # 75-84%
    'red': 'emsn_red:d=4,o=5,b=200:8c',           # 65-74%
    'milestone': 'emsn_milestone:d=4,o=5,b=180:8g,8g,8a,4g',
    'new': 'emsn_new:d=4,o=5,b=200:8c,8e,8g,4c6',  # Nieuwe soort dit jaar
}

# Rarity Tiers - gebaseerd op detecties in laatste 30 dagen
# Sounds zijn confidence-based, display duur is tier-based
RARITY_TIERS = {
    'legendary': {
        'min_count': 0,
        'max_count': 0,
        'cooldown_seconds': 0,      # Geen cooldown
        'display_duration_sec': 45,
        'play_sound': True,
    },
    'rare': {
        'min_count': 1,
        'max_count': 19,
        'cooldown_seconds': 300,    # 5 minuten
        'display_duration_sec': 35,
        'play_sound': True,
    },
    'uncommon': {
        'min_count': 20,
        'max_count': 99,
        'cooldown_seconds': 900,    # 15 minuten
        'display_duration_sec': 25,
        'play_sound': True,
    },
    'common': {
        'min_count': 100,
        'max_count': 499,
        'cooldown_seconds': 3600,   # 1 uur
        'display_duration_sec': 15,
        'play_sound': True,
    },
    'abundant': {
        'min_count': 500,
        'max_count': float('inf'),
        'cooldown_seconds': 7200,   # 2 uur
        'display_duration_sec': 10,
        'play_sound': False,
    }
}

# Confidence Kleuren (hex)
CONFIDENCE_COLORS = {
    'dual': '#00FFFF',      # Cyaan - dual detection
    'excellent': '#00FF00', # Groen - 90-100%
    'good': '#FFFF00',      # Geel - 85-89%
    'medium': '#FFA500',    # Oranje - 75-84%
    'low': '#FF0000',       # Rood - 65-74%
}

# Confidence Thresholds
CONFIDENCE_THRESHOLDS = {
    'min_display': 0.65,    # Onder 65% niet tonen
    'excellent': 0.90,
    'good': 0.85,
    'medium': 0.75,
    'low': 0.65,
}

# Display Settings
DISPLAY = {
    'scroll_speed': 80,  # Lager = langzamer scrollen (default AWTRIX is 100)
    'base_duration_ms': 10000,  # 10 seconden basis
    'per_char_duration_ms': 500,  # +0.5 sec per karakter
    'max_duration_ms': 30000,  # Max 30 seconden
}

# Special Events - negeren cooldown
SPECIAL_EVENTS = {
    'first_of_year': True,      # Eerste detectie dit jaar
    'dual_detection': True,     # Beide stations
    'milestone': True,          # Milestone bereikt
}

# Milestone thresholds
MILESTONES = {
    'detection_milestones': [1000, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000],
    'species_milestones': [50, 75, 100, 125, 150, 175, 200],
}

# Lookback period voor rarity berekening
RARITY_LOOKBACK_DAYS = 30

# Log directory
LOG_DIR = '/mnt/usb/logs'

# Smart Cooldown Settings
# Multipliers for cooldown based on time of day and season
SMART_COOLDOWN = {
    # Tijd van de dag multipliers (lagere multiplier = kortere cooldown = meer notificaties)
    'time_multipliers': {
        'dawn': 0.5,      # 05:00-08:00 - Ochtendkoor, halve cooldown
        'morning': 0.75,  # 08:00-12:00 - Actieve ochtend
        'afternoon': 1.0, # 12:00-17:00 - Normale middag
        'evening': 0.75,  # 17:00-20:00 - Avondactiviteit
        'night': 1.5,     # 20:00-05:00 - Nacht, langere cooldown (uilen etc.)
    },
    # Seizoen multipliers (lagere = kortere cooldown)
    'season_multipliers': {
        'spring': 0.7,    # Maart-Mei: Veel activiteit, broedseizoen, trek
        'summer': 0.9,    # Juni-Aug: Redelijk actief
        'autumn': 0.7,    # Sept-Nov: Herfsttrek
        'winter': 1.2,    # Dec-Feb: Minder activiteit
    },
    # Weekend/vakantie multiplier (meer tijd om te kijken)
    'weekend_multiplier': 0.8,  # Weekenden: kortere cooldown

    # Minimum en maximum cooldown (in seconden)
    'min_cooldown_seconds': 60,    # Nooit korter dan 1 minuut
    'max_cooldown_seconds': 14400, # Nooit langer dan 4 uur
}
