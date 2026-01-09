#!/usr/bin/env python3
"""
EMSN 2.0 - Ulanzi Bridge Service

Luistert naar MQTT detectie berichten en stuurt notificaties naar de Ulanzi TC001.
Voert anti-spam filtering uit gebaseerd op rarity tiers.
"""

import json
import re
import sys
import time
import requests
import psycopg2
from datetime import datetime, timedelta
from pathlib import Path
import paho.mqtt.client as mqtt

# Add config path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
from ulanzi_config import (
    ULANZI, MQTT as MQTT_CONFIG, PG_CONFIG,
    RARITY_TIERS, CONFIDENCE_COLORS, CONFIDENCE_THRESHOLDS,
    DISPLAY, SPECIAL_EVENTS, LOG_DIR, RTTTL_SOUNDS, MILESTONES,
    SMART_COOLDOWN
)


class UlanziLogger:
    """Simple logger"""

    def __init__(self):
        self.log_dir = Path(LOG_DIR)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"ulanzi_bridge_{datetime.now().strftime('%Y%m%d')}.log"

    def log(self, level, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"[{timestamp}] [{level}] {message}"
        print(entry)
        with open(self.log_file, 'a') as f:
            f.write(entry + '\n')

    def info(self, msg): self.log('INFO', msg)
    def error(self, msg): self.log('ERROR', msg)
    def warning(self, msg): self.log('WARNING', msg)
    def success(self, msg): self.log('SUCCESS', msg)


class SpeciesNameCache:
    """Cache voor wetenschappelijke naam → Nederlandse naam mapping"""

    def __init__(self, logger):
        self.logger = logger
        self.cache = {}  # scientific_name -> dutch_name
        self.fallback = {}  # Externe lookup tabel
        self.pg_conn = None
        self._load_fallback()

    def _load_fallback(self):
        """Load fallback Dutch names from JSON file"""
        fallback_file = Path(__file__).parent.parent.parent / 'config' / 'dutch_bird_names.json'
        try:
            if fallback_file.exists():
                with open(fallback_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Normalize keys to lowercase
                    self.fallback = {k.lower(): v for k, v in data.items()}
                self.logger.info(f"Fallback names loaded: {len(self.fallback)} species")
        except Exception as e:
            self.logger.warning(f"Could not load fallback names: {e}")

    def connect(self, pg_conn):
        """Use existing connection"""
        self.pg_conn = pg_conn

    def refresh(self):
        """Load species name mappings from database"""
        if not self.pg_conn:
            return False

        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("""
                SELECT DISTINCT species, common_name
                FROM bird_detections
                WHERE species IS NOT NULL AND common_name IS NOT NULL
            """)

            self.cache = {}
            for row in cursor.fetchall():
                scientific_name, dutch_name = row
                self.cache[scientific_name.lower()] = dutch_name

            self.logger.info(f"Species name cache loaded: {len(self.cache)} mappings")
            return True

        except Exception as e:
            self.logger.error(f"Error loading species names: {e}")
            return False

    def get_dutch_name(self, scientific_name):
        """Get Dutch name from scientific name (DB first, then fallback)"""
        if not scientific_name:
            return None
        key = scientific_name.lower()
        # Try database cache first, then fallback
        return self.cache.get(key) or self.fallback.get(key)


class FirstOfYearCache:
    """Cache voor tracking eerste detectie dit jaar per soort"""

    def __init__(self, logger):
        self.logger = logger
        self.seen_this_year = set()  # Dutch names already detected this year
        self.pg_conn = None

    def connect(self, pg_conn):
        """Use existing connection"""
        self.pg_conn = pg_conn

    def refresh(self):
        """Load species already detected this year"""
        if not self.pg_conn:
            return False

        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("""
                SELECT DISTINCT common_name
                FROM bird_detections
                WHERE EXTRACT(YEAR FROM detection_timestamp) = EXTRACT(YEAR FROM NOW())
            """)

            self.seen_this_year = {row[0] for row in cursor.fetchall()}
            self.logger.info(f"First-of-year cache: {len(self.seen_this_year)} species seen in {datetime.now().year}")
            return True

        except Exception as e:
            self.logger.error(f"Error loading first-of-year cache: {e}")
            return False

    def is_first_of_year(self, dutch_name):
        """Check if this is the first detection of this species this year"""
        return dutch_name not in self.seen_this_year

    def mark_seen(self, dutch_name):
        """Mark species as seen this year"""
        self.seen_this_year.add(dutch_name)


class MilestoneTracker:
    """Track detection and species milestones"""

    def __init__(self, logger):
        self.logger = logger
        self.pg_conn = None
        self.total_detections = 0
        self.total_species = 0
        self.achieved_detection_milestones = set()
        self.achieved_species_milestones = set()

    def connect(self, pg_conn):
        """Use existing connection"""
        self.pg_conn = pg_conn

    def refresh(self):
        """Load current counts and achieved milestones"""
        if not self.pg_conn:
            return False

        try:
            cursor = self.pg_conn.cursor()

            # Get total detection count
            cursor.execute("SELECT COUNT(*) FROM bird_detections")
            self.total_detections = cursor.fetchone()[0]

            # Get total unique species count
            cursor.execute("SELECT COUNT(DISTINCT species) FROM bird_detections")
            self.total_species = cursor.fetchone()[0]

            # Determine which milestones have already been achieved
            for m in MILESTONES['detection_milestones']:
                if self.total_detections >= m:
                    self.achieved_detection_milestones.add(m)

            for m in MILESTONES['species_milestones']:
                if self.total_species >= m:
                    self.achieved_species_milestones.add(m)

            self.logger.info(f"Milestones: {self.total_detections} detections, {self.total_species} species")
            return True

        except Exception as e:
            self.logger.error(f"Error loading milestone data: {e}")
            return False

    def check_detection_milestone(self):
        """Check if a new detection milestone was reached. Returns milestone number or None."""
        self.total_detections += 1

        for m in MILESTONES['detection_milestones']:
            if self.total_detections == m and m not in self.achieved_detection_milestones:
                self.achieved_detection_milestones.add(m)
                return m
        return None

    def check_species_milestone(self, is_new_species):
        """Check if a new species milestone was reached. Returns milestone number or None."""
        if not is_new_species:
            return None

        self.total_species += 1

        for m in MILESTONES['species_milestones']:
            if self.total_species == m and m not in self.achieved_species_milestones:
                self.achieved_species_milestones.add(m)
                return m
        return None


class RarityCache:
    """Cache voor species rarity tiers"""

    def __init__(self, logger):
        self.logger = logger
        self.cache = {}
        self.last_refresh = None
        self.pg_conn = None

    def connect(self):
        """Connect to PostgreSQL"""
        try:
            self.pg_conn = psycopg2.connect(**PG_CONFIG)
            return True
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return False

    def refresh(self):
        """Refresh rarity cache from database"""
        if not self.pg_conn:
            if not self.connect():
                return False

        try:
            cursor = self.pg_conn.cursor()

            # Get detection counts per species in last 30 days
            cursor.execute("""
                SELECT
                    common_name,
                    species,
                    COUNT(*) as detection_count
                FROM bird_detections
                WHERE detection_timestamp >= NOW() - INTERVAL '30 days'
                GROUP BY common_name, species
            """)

            self.cache = {}
            for row in cursor.fetchall():
                common_name, species, count = row
                tier = self._get_tier(count)
                self.cache[common_name] = {
                    'species': species,
                    'count': count,
                    'tier': tier,
                    'tier_config': RARITY_TIERS[tier]
                }

            self.last_refresh = datetime.now()
            self.logger.info(f"Rarity cache refreshed: {len(self.cache)} species")
            return True

        except Exception as e:
            self.logger.error(f"Error refreshing rarity cache: {e}")
            return False

    def _get_tier(self, count):
        """Determine rarity tier based on count"""
        for tier_name, tier_config in RARITY_TIERS.items():
            if tier_config['min_count'] <= count <= tier_config['max_count']:
                return tier_name
        return 'abundant'

    def get_species_info(self, common_name):
        """Get species info including rarity tier"""
        # Refresh if cache is older than 1 hour
        if not self.last_refresh or (datetime.now() - self.last_refresh).seconds > 3600:
            self.refresh()

        if common_name in self.cache:
            return self.cache[common_name]

        # Unknown species = legendary (never seen before in 30 days)
        return {
            'species': None,
            'count': 0,
            'tier': 'legendary',
            'tier_config': RARITY_TIERS['legendary']
        }


class CooldownManager:
    """Manages notification cooldowns per species with smart time/season adjustments"""

    def __init__(self, logger=None):
        self.logger = logger
        self.last_notification = {}
        self.anti_spam_seconds = 30  # Minimum 30 seconds between identical species (burst protection)
        self.burst_detection_seconds = 5  # Detect bursts within 5 seconds
        self.last_received = {}  # Track when detection was received (not shown)
        self.species_tiers = {}  # species -> tier info for remaining time calculation
        self.pg_conn = None
        self.smart_cooldown_enabled = True  # Can be disabled if needed

    def connect(self, pg_conn):
        """Use existing database connection for cooldown persistence"""
        self.pg_conn = pg_conn

    def get_time_of_day(self):
        """Determine current time period"""
        hour = datetime.now().hour
        if 5 <= hour < 8:
            return 'dawn'
        elif 8 <= hour < 12:
            return 'morning'
        elif 12 <= hour < 17:
            return 'afternoon'
        elif 17 <= hour < 20:
            return 'evening'
        else:
            return 'night'

    def get_season(self):
        """Determine current season based on month"""
        month = datetime.now().month
        if month in (3, 4, 5):
            return 'spring'
        elif month in (6, 7, 8):
            return 'summer'
        elif month in (9, 10, 11):
            return 'autumn'
        else:
            return 'winter'

    def is_weekend(self):
        """Check if today is a weekend"""
        return datetime.now().weekday() >= 5  # 5=Saturday, 6=Sunday

    def calculate_smart_cooldown(self, base_cooldown_seconds):
        """Apply smart multipliers to base cooldown"""
        if not self.smart_cooldown_enabled or base_cooldown_seconds == 0:
            return base_cooldown_seconds

        # Get multipliers
        time_period = self.get_time_of_day()
        season = self.get_season()

        time_mult = SMART_COOLDOWN['time_multipliers'].get(time_period, 1.0)
        season_mult = SMART_COOLDOWN['season_multipliers'].get(season, 1.0)

        # Apply weekend multiplier if applicable
        weekend_mult = SMART_COOLDOWN['weekend_multiplier'] if self.is_weekend() else 1.0

        # Calculate final cooldown
        adjusted = base_cooldown_seconds * time_mult * season_mult * weekend_mult

        # Clamp to min/max
        min_cd = SMART_COOLDOWN.get('min_cooldown_seconds', 60)
        max_cd = SMART_COOLDOWN.get('max_cooldown_seconds', 14400)

        final_cooldown = int(max(min_cd, min(max_cd, adjusted)))

        if self.logger and final_cooldown != base_cooldown_seconds:
            self.logger.info(
                f"Smart cooldown: {base_cooldown_seconds}s -> {final_cooldown}s "
                f"(time={time_period}:{time_mult}, season={season}:{season_mult}, "
                f"weekend={self.is_weekend()}:{weekend_mult})"
            )

        return final_cooldown

    def is_burst_detection(self, common_name):
        """Check if this is a burst detection (same species within 5 seconds)"""
        last_received = self.last_received.get(common_name)
        if not last_received:
            return False

        elapsed = (datetime.now() - last_received).total_seconds()
        return elapsed < self.burst_detection_seconds

    def record_received(self, common_name):
        """Record that a detection was received (not necessarily shown)"""
        self.last_received[common_name] = datetime.now()

    def can_notify(self, common_name, tier_config, is_special=False):
        """Check if notification is allowed based on smart cooldown"""
        if is_special:
            return True

        last_time = self.last_notification.get(common_name)
        if not last_time:
            return True

        elapsed = (datetime.now() - last_time).total_seconds()

        # First check anti-spam filter (burst protection)
        if elapsed < self.anti_spam_seconds:
            return False

        # Get base cooldown and apply smart adjustments
        base_cooldown = tier_config['cooldown_seconds']
        if base_cooldown == 0:
            return True

        smart_cooldown = self.calculate_smart_cooldown(base_cooldown)
        return elapsed >= smart_cooldown

    def record_notification(self, common_name, tier=None, tier_config=None):
        """Record that a notification was sent"""
        now = datetime.now()
        self.last_notification[common_name] = now

        # Store tier info for remaining time calculation
        if tier and tier_config:
            self.species_tiers[common_name] = {
                'tier': tier,
                'cooldown_seconds': tier_config.get('cooldown_seconds', 3600)
            }

        # Persist to database
        self.update_cooldown_db(common_name, tier, tier_config)

    def update_cooldown_db(self, species_nl, tier=None, tier_config=None):
        """Update cooldown status in database with smart cooldown"""
        if not self.pg_conn:
            return

        try:
            now = datetime.now()
            base_cooldown = tier_config.get('cooldown_seconds', 3600) if tier_config else 3600
            # Apply smart cooldown for database persistence
            cooldown_sec = self.calculate_smart_cooldown(base_cooldown)
            expires_at = now + timedelta(seconds=cooldown_sec)

            cursor = self.pg_conn.cursor()
            cursor.execute("""
                INSERT INTO ulanzi_cooldown_status
                (species_nl, rarity_tier, cooldown_seconds, last_notified, expires_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (species_nl) DO UPDATE SET
                    rarity_tier = EXCLUDED.rarity_tier,
                    cooldown_seconds = EXCLUDED.cooldown_seconds,
                    last_notified = EXCLUDED.last_notified,
                    expires_at = EXCLUDED.expires_at,
                    updated_at = EXCLUDED.updated_at
            """, (species_nl, tier, cooldown_sec, now, expires_at, now))
            self.pg_conn.commit()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to update cooldown DB: {e}")
            try:
                self.pg_conn.rollback()
            except (Exception, OSError):
                pass  # Rollback is non-critical

    def cleanup_expired_cooldowns(self):
        """Remove expired cooldowns from database"""
        if not self.pg_conn:
            return

        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("DELETE FROM ulanzi_cooldown_status WHERE expires_at < NOW()")
            self.pg_conn.commit()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to cleanup cooldowns: {e}")

    def get_cooldowns(self):
        """Get all active cooldowns with remaining time"""
        now = datetime.now()
        cooldowns = []

        for species, last_time in self.last_notification.items():
            elapsed = (now - last_time).total_seconds()
            # Only show cooldowns that are still active (within 2 hours max)
            if elapsed < 7200:  # 2 hours = max cooldown for 'abundant' tier
                cooldowns.append({
                    'species': species,
                    'elapsed_seconds': int(elapsed),
                    'notified_at': last_time
                })

        # Sort by most recent first
        cooldowns.sort(key=lambda x: x['elapsed_seconds'])
        return cooldowns


class UlanziNotifier:
    """Sends notifications to Ulanzi TC001"""

    def __init__(self, logger):
        self.logger = logger
        self.api_base = ULANZI['api_base']

    def get_color(self, confidence, is_dual=False):
        """Get color based on confidence level"""
        if is_dual:
            return CONFIDENCE_COLORS['dual']

        if confidence >= CONFIDENCE_THRESHOLDS['excellent']:
            return CONFIDENCE_COLORS['excellent']
        elif confidence >= CONFIDENCE_THRESHOLDS['good']:
            return CONFIDENCE_COLORS['good']
        elif confidence >= CONFIDENCE_THRESHOLDS['medium']:
            return CONFIDENCE_COLORS['medium']
        else:
            return CONFIDENCE_COLORS['low']

    def get_sound(self, confidence, is_dual=False, is_new_species=False):
        """Get RTTTL sound based on confidence level"""
        if is_new_species:
            return RTTTL_SOUNDS['new']
        if is_dual:
            return RTTTL_SOUNDS['dual']

        if confidence >= CONFIDENCE_THRESHOLDS['excellent']:
            return RTTTL_SOUNDS['green']      # 90%+
        elif confidence >= CONFIDENCE_THRESHOLDS['good']:
            return RTTTL_SOUNDS['yellow']     # 85-89%
        elif confidence >= CONFIDENCE_THRESHOLDS['medium']:
            return RTTTL_SOUNDS['orange']     # 75-84%
        else:
            return RTTTL_SOUNDS['red']        # 65-74%

    def format_message(self, station, common_name, confidence, is_dual=False, is_new_species=False, vocalization_type=None):
        """Format notification message"""
        conf_pct = int(confidence * 100)

        # Voeg vocalisatie type toe als beschikbaar
        name_with_voc = common_name
        if vocalization_type:
            name_with_voc = f"{common_name} {vocalization_type}"

        if is_new_species:
            return f"{station}-***NIEUW 2025***-{name_with_voc}-{conf_pct}%"
        elif is_dual:
            return f"Dubbel-{name_with_voc}-{conf_pct}%"
        else:
            return f"{station}-{name_with_voc}-{conf_pct}%"

    def calculate_duration(self, message, tier_duration_sec=None):
        """
        Calculate display duration based on message length and tier.
        Uses dynamic calculation: base + (characters × 0.5) seconds
        But respects tier minimum duration.
        """
        # Dynamic calculation: 10 + (len × 0.5) seconds
        base_sec = DISPLAY['base_duration_ms'] / 1000
        per_char_sec = DISPLAY['per_char_duration_ms'] / 1000
        dynamic_duration = base_sec + (len(message) * per_char_sec)

        # Use tier duration as minimum, dynamic as maximum
        if tier_duration_sec:
            duration_sec = max(tier_duration_sec, dynamic_duration)
        else:
            duration_sec = dynamic_duration

        # Cap at max duration
        max_sec = DISPLAY['max_duration_ms'] / 1000
        return int(min(duration_sec, max_sec))

    def send_notification(self, message, color, sound=None, duration_sec=None):
        """Send notification to Ulanzi via HTTP API"""
        if duration_sec is None:
            duration_sec = self.calculate_duration(message)

        # Convert hex color to RGB list
        color_hex = color.lstrip('#')
        color_rgb = [int(color_hex[i:i+2], 16) for i in (0, 2, 4)]

        payload = {
            'text': message,
            'color': color_rgb,
            'duration': duration_sec,  # AWTRIX uses seconds
            'scrollSpeed': DISPLAY['scroll_speed'],
            'repeat': 1,  # Toon tekst maar 1x (niet herhalen)
        }

        if sound:
            payload['rtttl'] = sound  # AWTRIX uses rtttl for custom sounds

        try:
            url = f"{self.api_base}/notify"
            response = requests.post(url, json=payload, timeout=5)

            if response.status_code == 200:
                self.logger.success(f"Notification sent: {message}")
                return True
            else:
                self.logger.error(f"Ulanzi API error: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
            return False


class UlanziBridge:
    """Main bridge service"""

    def __init__(self):
        self.logger = UlanziLogger()
        self.rarity_cache = RarityCache(self.logger)
        self.species_names = SpeciesNameCache(self.logger)
        self.first_of_year = FirstOfYearCache(self.logger)
        self.milestones = MilestoneTracker(self.logger)
        self.cooldown = CooldownManager(self.logger)
        self.notifier = UlanziNotifier(self.logger)
        self.mqtt_client = None
        self.running = False
        self.presence_home = True  # Default: assume home

        # Track last dual detection to prevent burst duplicates
        self.last_dual_detection = {}  # species -> (timestamp, confidence)
        self.dual_burst_window = 10  # 10 seconds window for dual detection bursts

        # Last notification ID for screenshot linking
        self.last_notification_id = None

        # Vocalization classifier (lazy loaded)
        self.vocalization_classifier = None
        self.vocalization_enabled = True  # Set to False to disable

    def _get_vocalization_type(self, dutch_name: str, audio_file: str = None) -> str | None:
        """Get vocalization type (zang/roep/alarm) for a detection."""
        if not self.vocalization_enabled:
            return None

        try:
            # Lazy load classifier
            if self.vocalization_classifier is None:
                try:
                    # Add vocalization path to sys.path for import
                    import sys
                    voc_path = str(Path(__file__).parent.parent / 'vocalization')
                    if voc_path not in sys.path:
                        sys.path.insert(0, voc_path)
                    from vocalization_classifier import VocalizationClassifier
                    self.vocalization_classifier = VocalizationClassifier()
                    self.logger.info("Vocalization classifier loaded")
                except ImportError as e:
                    self.logger.warning(f"Vocalization classifier not available: {e}")
                    self.vocalization_enabled = False
                    return None

            # Check if we have a model for this species
            if not self.vocalization_classifier.has_model(dutch_name):
                return None

            # Find audio file (by file path or by searching for most recent)
            audio_path = self._find_audio_file(file_name=audio_file, dutch_name=dutch_name)
            if not audio_path:
                self.logger.info(f"No audio file found for {dutch_name}")
                return None

            # Classify
            result = self.vocalization_classifier.classify(dutch_name, audio_path)
            if result and result['confidence'] >= 0.4:  # Threshold 40% (was 50%)
                self.logger.info(f"Vocalization: {dutch_name} = {result['type_nl']} ({result['confidence']:.0%})")
                return result['type_nl']

        except Exception as e:
            self.logger.warning(f"Vocalization classification failed: {e}")

        return None

    def _find_audio_file(self, file_name: str = None, dutch_name: str = None):
        """Find audio file from BirdNET detection."""
        from pathlib import Path

        # BirdNET audio directories (correct path without /BirdNET-Pi/)
        birdnet_audio = Path("/home/ronny/BirdSongs")

        # If we have a file name, try that first
        if file_name:
            if Path(file_name).exists():
                return Path(file_name)

            direct = birdnet_audio / file_name
            if direct.exists():
                return direct

            for path in birdnet_audio.rglob(Path(file_name).name):
                return path

        # If no file name, try to find the most recent file for this species
        if dutch_name:
            # Look in Extracted/By_Date/YYYY-MM-DD/Species/
            today = datetime.now().strftime("%Y-%m-%d")
            species_dir = birdnet_audio / "Extracted" / "By_Date" / today / dutch_name

            if species_dir.exists():
                # Get most recent audio file (mp3 or wav)
                audio_files = sorted(
                    [f for f in species_dir.glob("*") if f.suffix in ('.mp3', '.wav')],
                    key=lambda p: p.stat().st_mtime, reverse=True
                )
                if audio_files:
                    return audio_files[0]

            # Also check yesterday (for detections around midnight)
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            species_dir = birdnet_audio / "Extracted" / "By_Date" / yesterday / dutch_name

            if species_dir.exists():
                audio_files = sorted(
                    [f for f in species_dir.glob("*") if f.suffix in ('.mp3', '.wav')],
                    key=lambda p: p.stat().st_mtime, reverse=True
                )
                if audio_files:
                    # Only use if less than 5 minutes old
                    if (datetime.now().timestamp() - audio_files[0].stat().st_mtime) < 300:
                        return audio_files[0]

        return None

    def parse_detection_message(self, payload):
        """Parse detection message - supports both JSON (new) and Apprise (legacy) formats"""
        try:
            text = payload.decode('utf-8') if isinstance(payload, bytes) else payload

            # Try JSON format first (from birdnet_mqtt_publisher)
            try:
                data = json.loads(text)
                return {
                    'common_name': data.get('species', 'Unknown'),
                    'scientific_name': data.get('scientific_name', ''),
                    'confidence': data.get('confidence', 0),
                    'file': data.get('file', ''),
                    'vocalization': data.get('vocalization'),
                    'vocalization_nl': data.get('vocalization_nl'),
                    'vocalization_confidence': data.get('vocalization_confidence'),
                    'station': data.get('station', ''),
                    'raw': text
                }
            except json.JSONDecodeError:
                pass

            # Fallback: Apprise format (legacy)
            # Example: "A Eurasian Magpie (Pica pica) was just detected with a confidence of 0.87 (detection)"
            pattern = r"A (.+?) \((.+?)\)\s+was just detected with a confidence of ([\d.]+)"
            match = re.search(pattern, text, re.DOTALL)

            if match:
                common_name = match.group(1).strip()
                scientific_name = match.group(2).strip()
                confidence = float(match.group(3))

                return {
                    'common_name': common_name,
                    'scientific_name': scientific_name,
                    'confidence': confidence,
                    'vocalization': None,
                    'vocalization_nl': None,
                    'raw': text
                }

            self.logger.warning(f"Could not parse message: {text[:100]}")
            return None

        except Exception as e:
            self.logger.error(f"Error parsing message: {e}")
            return None

    def on_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        """MQTT connection callback"""
        if reason_code == 0:
            self.logger.success("Connected to MQTT broker")

            # Subscribe to detection topics
            topics = [
                (MQTT_CONFIG['topics']['zolder_detection'], 1),
                (MQTT_CONFIG['topics']['berging_detection'], 1),
                (MQTT_CONFIG['topics']['dual_detection'], 1),
                (MQTT_CONFIG['topics']['presence'], 1),
            ]
            client.subscribe(topics)
            self.logger.info(f"Subscribed to {len(topics)} topics")
        else:
            self.logger.error(f"MQTT connection failed: {reason_code}")

    def on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback"""
        topic = msg.topic

        # Handle presence updates
        if 'presence' in topic:
            try:
                self.presence_home = msg.payload.decode().lower() in ('true', '1', 'home')
                self.logger.info(f"Presence updated: {'home' if self.presence_home else 'away'}")
            except (UnicodeDecodeError, AttributeError):
                pass  # Invalid payload is non-critical
            return

        # Handle dual detection messages (JSON format from dual_detection_sync)
        # Dual detections always show regardless of presence (special event)
        if 'dual' in topic:
            self.handle_dual_detection(msg.payload)
            return

        # Determine station from topic
        if 'zolder' in topic:
            station = 'Zolder'
        elif 'berging' in topic:
            station = 'Berging'
        else:
            station = 'Unknown'

        # Parse the detection message (JSON or Apprise format)
        detection = self.parse_detection_message(msg.payload)
        if not detection:
            return

        # Override station if provided in JSON message
        if detection.get('station'):
            station = detection['station'].capitalize()

        # Check confidence threshold
        if detection['confidence'] < CONFIDENCE_THRESHOLDS['min_display']:
            self.logger.info(f"Skipping low confidence: {detection['common_name']} ({detection['confidence']:.0%})")
            return

        # Get Dutch name - JSON format already has Dutch name in 'species' field
        # For Apprise format, try to translate from scientific name
        if detection.get('station'):
            # JSON format from publisher - species is already Dutch
            dutch_name = detection['common_name']
        else:
            # Apprise format - need to translate
            dutch_name = self.species_names.get_dutch_name(detection['scientific_name'])
            if not dutch_name:
                dutch_name = detection['common_name']
                self.logger.warning(f"No Dutch name for {detection['scientific_name']}, using: {dutch_name}")

        # Check for burst detection (duplicate within 5 seconds)
        if self.cooldown.is_burst_detection(dutch_name):
            self.logger.info(f"Skipping (burst detection): {dutch_name} - duplicate within 5 seconds")
            self.log_notification(dutch_name, detection['confidence'], station, 'burst', False, 'burst_duplicate')
            return

        # Record that we received this detection
        self.cooldown.record_received(dutch_name)

        # Check if this is the first detection of this species this year
        is_first_of_year = self.first_of_year.is_first_of_year(dutch_name)

        # Get species rarity info (using Dutch name for cache lookup)
        species_info = self.rarity_cache.get_species_info(dutch_name)
        tier_config = species_info['tier_config']
        tier = species_info['tier']

        # Check presence - if not home, only show special events
        if not self.presence_home:
            is_special = is_first_of_year or tier == 'rare'
            if not is_special:
                self.logger.info(f"Skipping (not home, not special): {dutch_name}")
                return

        # Check cooldown (skip for first-of-year - special event)
        if not is_first_of_year and not self.cooldown.can_notify(dutch_name, tier_config):
            last_time = self.cooldown.last_notification.get(dutch_name)
            if last_time:
                elapsed = (datetime.now() - last_time).total_seconds()
                if elapsed < self.cooldown.anti_spam_seconds:
                    self.logger.info(f"Skipping (anti-spam): {dutch_name} (within {int(elapsed)}s)")
                    self.log_notification(dutch_name, detection['confidence'], station, tier, False, 'anti_spam')
                else:
                    self.logger.info(f"Skipping (cooldown): {dutch_name} (within {int(elapsed)}s)")
                    self.log_notification(dutch_name, detection['confidence'], station, tier, False, 'cooldown')
            return

        # Get vocalization type - prefer from MQTT message (already classified by publisher)
        vocalization_type = detection.get('vocalization_nl')
        if not vocalization_type:
            # Fallback: classify locally (for legacy Apprise messages)
            vocalization_type = self._get_vocalization_type(dutch_name, detection.get('file'))

        # Format and send notification with Dutch name
        message = self.notifier.format_message(
            station=station,
            common_name=dutch_name,
            confidence=detection['confidence'],
            is_new_species=is_first_of_year,
            vocalization_type=vocalization_type
        )

        # First-of-year gets special sound, otherwise confidence-based
        if is_first_of_year:
            color = self.notifier.get_color(detection['confidence'])
            sound = self.notifier.get_sound(detection['confidence'], is_new_species=True)
            notification_type = 'first_of_year'
        else:
            color = self.notifier.get_color(detection['confidence'])
            sound = self.notifier.get_sound(detection['confidence']) if tier_config['play_sound'] else None
            notification_type = 'standard'

        # Calculate duration based on tier and message length
        tier_duration = tier_config.get('display_duration_sec', 15)
        duration_sec = self.notifier.calculate_duration(message, tier_duration)

        if self.notifier.send_notification(message, color, sound, duration_sec):
            self.cooldown.record_notification(dutch_name, tier=tier, tier_config=tier_config)

            # Mark as seen this year
            if is_first_of_year:
                self.first_of_year.mark_seen(dutch_name)
                self.logger.success(f"FIRST OF YEAR: {dutch_name}")

            # Log to database (with Dutch name)
            self.log_notification(dutch_name, detection['confidence'], station, tier, True, notification_type=notification_type)

            # Check for milestones
            self.check_and_notify_milestones(dutch_name, detection['confidence'], is_first_of_year)
        else:
            self.log_notification(dutch_name, detection['confidence'], station, species_info['tier'], False, 'send_failed', notification_type=notification_type)

    def check_and_notify_milestones(self, dutch_name, confidence, is_first_of_year):
        """Check and send milestone notifications"""
        # Check detection milestone
        detection_milestone = self.milestones.check_detection_milestone()
        if detection_milestone:
            self.send_milestone_notification('detection', detection_milestone, dutch_name, confidence)

        # Check species milestone (only if this was a new species)
        species_milestone = self.milestones.check_species_milestone(is_first_of_year)
        if species_milestone:
            self.send_milestone_notification('species', species_milestone, dutch_name, confidence)

    def send_milestone_notification(self, milestone_type, milestone_value, dutch_name, confidence):
        """Send a milestone notification to Ulanzi"""
        conf_pct = int(confidence * 100)

        if milestone_type == 'detection':
            # Format: "VOGEL 10000: Ekster-87%"
            message = f"VOGEL {milestone_value}: {dutch_name}-{conf_pct}%"
        else:
            # Format: "SOORT 100: Ekster-87%"
            message = f"SOORT {milestone_value}: {dutch_name}-{conf_pct}%"

        # Milestones use gold color and milestone sound
        color = '#FFD700'  # Gold
        sound = RTTTL_SOUNDS['milestone']

        # Give milestones a long duration (45 sec like legendary)
        duration_sec = self.notifier.calculate_duration(message, 45)

        if self.notifier.send_notification(message, color, sound, duration_sec):
            self.logger.success(f"MILESTONE: {milestone_type} #{milestone_value} reached with {dutch_name}")
            self.log_notification(dutch_name, confidence, 'milestone', 'special', True, notification_type=f'milestone_{milestone_type}')

    def handle_dual_detection(self, payload):
        """Handle dual detection messages from dual_detection_sync"""
        try:
            data = json.loads(payload.decode('utf-8') if isinstance(payload, bytes) else payload)

            species = data.get('species')
            common_name = data.get('common_name')  # This is already Dutch from the database
            avg_confidence = data.get('avg_confidence', 0)
            verification_score = data.get('verification_score', 0)

            if not common_name:
                self.logger.warning("Dual detection missing common_name")
                return

            # Check confidence threshold
            if avg_confidence < CONFIDENCE_THRESHOLDS['min_display']:
                self.logger.info(f"Skipping dual (low confidence): {common_name} ({avg_confidence:.0%})")
                return

            # Check for burst detection - same species within 10 seconds
            # Only show the FIRST detection, skip all others in the burst window
            now = datetime.now()
            if common_name in self.last_dual_detection:
                last_time, last_confidence = self.last_dual_detection[common_name]
                elapsed = (now - last_time).total_seconds()

                if elapsed < self.dual_burst_window:
                    # Within burst window - skip ALL duplicates (don't show any after first)
                    self.logger.info(f"Skipping dual burst: {common_name} ({avg_confidence:.0%}) within {int(elapsed)}s of first detection")
                    self.log_notification(common_name, avg_confidence, 'dual', 'special', False, 'dual_burst_duplicate', notification_type='dual')
                    return

            # Record this as the FIRST dual detection of this species (start of burst window)
            self.last_dual_detection[common_name] = (now, avg_confidence)

            # Dual detections always show (ignore cooldown) - special event
            # Get vocalization type
            vocalization_type = self._get_vocalization_type(common_name)

            # Format message for dual detection
            message = self.notifier.format_message(
                station='Dubbel',
                common_name=common_name,
                confidence=avg_confidence,
                is_dual=True,
                vocalization_type=vocalization_type
            )

            # Dual detection uses cyan color and dual sound
            color = self.notifier.get_color(avg_confidence, is_dual=True)
            sound = self.notifier.get_sound(avg_confidence, is_dual=True)

            # Dual detections get special long duration (45 sec like legendary)
            duration_sec = self.notifier.calculate_duration(message, 45)

            if self.notifier.send_notification(message, color, sound, duration_sec):
                # Log to database
                self.log_notification(common_name, avg_confidence, 'dual', 'special', True, notification_type='dual')
                self.logger.success(f"Dual detection: {common_name} (score: {verification_score:.2f})")

                # Check for milestones (dual counts as detection, but not as new species)
                self.check_and_notify_milestones(common_name, avg_confidence, False)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse dual detection JSON: {e}")
        except Exception as e:
            self.logger.error(f"Error handling dual detection: {e}")

    def log_notification(self, dutch_name, confidence, station, tier, was_shown, skip_reason=None, notification_type='standard'):
        """Log notification to database and return the ID"""
        notification_id = None
        try:
            if not self.rarity_cache.pg_conn:
                self.rarity_cache.connect()

            cursor = self.rarity_cache.pg_conn.cursor()
            cursor.execute("""
                INSERT INTO ulanzi_notification_log
                (species_nl, station, confidence, rarity_tier, was_shown, skip_reason, notification_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                dutch_name,
                station.lower(),
                confidence,
                tier,
                was_shown,
                skip_reason,
                notification_type
            ))
            notification_id = cursor.fetchone()[0]
            self.rarity_cache.pg_conn.commit()

            # If notification was shown, trigger screenshot
            if was_shown and self.mqtt_client:
                self.trigger_screenshot(dutch_name, notification_id)

        except Exception as e:
            self.logger.error(f"Error logging notification: {e}")

        return notification_id

    def trigger_screenshot(self, species_nl, detection_id):
        """Trigger screenshot service via MQTT"""
        try:
            payload = json.dumps({
                'species_nl': species_nl,
                'detection_id': detection_id,
                'timestamp': datetime.now().isoformat()
            })
            self.mqtt_client.publish('emsn2/ulanzi/screenshot/trigger', payload)
            self.logger.info(f"Screenshot triggered for {species_nl}")
        except Exception as e:
            self.logger.error(f"Failed to trigger screenshot: {e}")

    def start(self):
        """Start the bridge service"""
        self.logger.info("=" * 60)
        self.logger.info("EMSN Ulanzi Bridge Service Starting")
        self.logger.info("=" * 60)

        # Initialize rarity cache
        self.rarity_cache.refresh()

        # Initialize species name cache (uses same connection)
        self.species_names.connect(self.rarity_cache.pg_conn)
        self.species_names.refresh()

        # Initialize first-of-year cache
        self.first_of_year.connect(self.rarity_cache.pg_conn)
        self.first_of_year.refresh()

        # Initialize milestone tracker
        self.milestones.connect(self.rarity_cache.pg_conn)
        self.milestones.refresh()

        # Initialize cooldown manager with DB connection
        self.cooldown.connect(self.rarity_cache.pg_conn)
        self.cooldown.cleanup_expired_cooldowns()

        # Setup MQTT client
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.username_pw_set(
            MQTT_CONFIG['username'],
            MQTT_CONFIG['password']
        )
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message

        try:
            self.mqtt_client.connect(
                MQTT_CONFIG['broker'],
                MQTT_CONFIG['port'],
                60
            )

            self.running = True
            self.logger.success("Bridge service started")

            # Run forever
            self.mqtt_client.loop_forever()

        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
        except Exception as e:
            self.logger.error(f"Error: {e}")
        finally:
            self.running = False
            if self.mqtt_client:
                self.mqtt_client.disconnect()


def main():
    bridge = UlanziBridge()
    bridge.start()


if __name__ == "__main__":
    main()
