#!/usr/bin/env python3
"""
EMSN 2.0 - Ulanzi TC001 Notificatie Configuratie
"""

# Ulanzi/AWTRIX Configuration
ULANZI = {
    'ip': '192.168.1.11',
    'api_base': 'http://192.168.1.11/api',
    'notify_endpoint': '/notify',
    'rtttl_endpoint': '/rtttl',
}

# MQTT Configuration
MQTT = {
    'broker': '192.168.1.178',
    'port': 1883,
    'username': 'ecomonitor',
    'password': 'REDACTED_DB_PASS',
    'topics': {
        'zolder_detection': 'emsn2/zolder/detection/new',
        'berging_detection': 'emsn2/berging/detection/new',
        'ulanzi_notify': 'emsn2/ulanzi/notify',
        'presence': 'emsn2/presence/home',
    }
}

# PostgreSQL Configuration
PG_CONFIG = {
    'host': '192.168.1.25',
    'port': 5433,
    'database': 'emsn',
    'user': 'birdpi_zolder',
    'password': 'REDACTED_DB_PASS'
}

# Rarity Tiers - gebaseerd op detecties in laatste 30 dagen
RARITY_TIERS = {
    'rare': {
        'min_count': 0,
        'max_count': 19,
        'cooldown_seconds': 0,  # Altijd tonen
        'sound': 'emsn_rare',
        'play_sound': True,
    },
    'uncommon': {
        'min_count': 20,
        'max_count': 99,
        'cooldown_seconds': 120,  # 2 minuten
        'sound': 'emsn_uncommon',
        'play_sound': True,
    },
    'common': {
        'min_count': 100,
        'max_count': 499,
        'cooldown_seconds': 300,  # 5 minuten
        'sound': 'emsn_common',
        'play_sound': True,
    },
    'very_common': {
        'min_count': 500,
        'max_count': float('inf'),
        'cooldown_seconds': 600,  # 10 minuten
        'sound': None,
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
    'scroll_speed': 130,
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

# RTTTL Sounds (voor later uploaden naar Ulanzi)
RTTTL_SOUNDS = {
    'emsn_rare': 'emsn_rare:d=4,o=5,b=140:e6,8p,e6,8p,8e6,8p,c6,e6,g6,p,g',
    'emsn_uncommon': 'emsn_uncommon:d=4,o=5,b=180:e6,e6,e6',
    'emsn_common': 'emsn_common:d=4,o=5,b=200:e6',
    'emsn_dual': 'emsn_dual:d=4,o=5,b=140:c6,e6,g6,c7',
    'emsn_milestone': 'emsn_milestone:d=4,o=5,b=120:c6,e6,g6,c7,8p,c7,g6,e6,c6',
}

# Lookback period voor rarity berekening
RARITY_LOOKBACK_DAYS = 30

# Log directory
LOG_DIR = '/mnt/usb/logs'
