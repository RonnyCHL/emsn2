#!/bin/bash
#
# Homer Dashboard Stats Updater
# Update de message banner in Homer met live statistieken uit de database.
# Draait via systemd timer (bijv. elke 15 minuten).
#

HOMER_CONFIG="/mnt/nas-docker/homer/config.yml"
LOG_FILE="/var/log/homer-stats.log"

# Database credentials
PGPASSWORD="IwnadBon2iN"
DB_HOST="192.168.1.25"
DB_PORT="5433"
DB_NAME="emsn"
DB_USER="postgres"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE" 2>/dev/null || echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Haal archief stats
get_archive_stats() {
    PGPASSWORD=$PGPASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -A -c "
        SELECT
            COUNT(*),
            COUNT(DISTINCT species),
            ROUND(COALESCE(SUM(file_size_bytes), 0)::numeric / 1073741824, 1)
        FROM media_archive
    " 2>/dev/null
}

# Haal vandaag detecties
get_today_detections() {
    PGPASSWORD=$PGPASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -A -c "
        SELECT COUNT(*) FROM bird_detections
        WHERE detection_timestamp >= CURRENT_DATE
    " 2>/dev/null
}

# Haal top soort vandaag (Nederlandse naam)
get_top_species() {
    PGPASSWORD=$PGPASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -A -c "
        SELECT COALESCE(common_name, species) FROM bird_detections
        WHERE detection_timestamp >= CURRENT_DATE
        GROUP BY COALESCE(common_name, species)
        ORDER BY COUNT(*) DESC
        LIMIT 1
    " 2>/dev/null
}

# Check stations online (laatste 15 min)
get_stations_online() {
    PGPASSWORD=$PGPASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -A -c "
        SELECT COUNT(DISTINCT station)
        FROM bird_detections
        WHERE detection_timestamp >= NOW() - INTERVAL '15 minutes'
    " 2>/dev/null
}

# Format grote nummers
format_number() {
    local n=$1
    if [ "$n" -ge 1000000 ]; then
        echo "$(echo "scale=1; $n/1000000" | bc)M"
    elif [ "$n" -ge 1000 ]; then
        echo "$(echo "scale=0; $n/1000" | bc)k"
    else
        echo "$n"
    fi
}

main() {
    log "Homer stats update gestart"

    # Haal alle stats
    ARCHIVE_STATS=$(get_archive_stats)
    if [ -z "$ARCHIVE_STATS" ]; then
        log "ERROR: Kan archief stats niet ophalen"
        exit 1
    fi

    ARCHIVE_TOTAL=$(echo "$ARCHIVE_STATS" | cut -d'|' -f1)
    ARCHIVE_SPECIES=$(echo "$ARCHIVE_STATS" | cut -d'|' -f2)
    ARCHIVE_GB=$(echo "$ARCHIVE_STATS" | cut -d'|' -f3)

    TODAY_DETECTIONS=$(get_today_detections)
    TOP_SPECIES=$(get_top_species)
    STATIONS_ONLINE=$(get_stations_online)

    log "Stats: archief=$ARCHIVE_TOTAL, soorten=$ARCHIVE_SPECIES, GB=$ARCHIVE_GB, vandaag=$TODAY_DETECTIONS, top=$TOP_SPECIES, stations=$STATIONS_ONLINE"

    # Bepaal style en title
    if [ "$STATIONS_ONLINE" -eq 0 ]; then
        STYLE="is-warning"
        TITLE="Geen Recente Detecties (15 min)"
        ICON="fas fa-exclamation-triangle"
    elif [ "$STATIONS_ONLINE" -eq 1 ]; then
        STYLE="is-info"
        TITLE="1 Station Actief"
        ICON="fas fa-dove"
    else
        STYLE="is-success"
        TITLE="Beide Stations Actief"
        ICON="fas fa-dove"
    fi

    # Build content string
    FORMATTED_TOTAL=$(format_number "$ARCHIVE_TOTAL")
    CONTENT="${FORMATTED_TOTAL}+ opnames | ${ARCHIVE_SPECIES} soorten | ${ARCHIVE_GB} GB"

    if [ "$TODAY_DETECTIONS" -gt 0 ]; then
        CONTENT="$CONTENT | Vandaag: $TODAY_DETECTIONS"
    fi

    if [ -n "$TOP_SPECIES" ]; then
        # Kort de soortnaam af tot eerste woord
        SHORT_NAME=$(echo "$TOP_SPECIES" | cut -d' ' -f1)
        CONTENT="$CONTENT | Top: $SHORT_NAME"
    fi

    log "Content: $CONTENT"

    # Check of Homer config bestaat
    if [ ! -f "$HOMER_CONFIG" ]; then
        log "ERROR: Homer config niet gevonden: $HOMER_CONFIG"
        exit 1
    fi

    # Backup maken
    cp "$HOMER_CONFIG" "${HOMER_CONFIG}.bak"

    # Update message sectie in YAML
    # We gebruiken een tijdelijk bestand
    TMP_FILE=$(mktemp)

    # Lees bestand en vervang message sectie
    awk -v style="$STYLE" -v title="$TITLE" -v icon="$ICON" -v content="$CONTENT" '
    BEGIN { in_message = 0; printed_message = 0 }
    /^message:/ {
        in_message = 1
        print "message:"
        print "  style: \"" style "\""
        print "  title: \"" title "\""
        print "  icon: \"" icon "\""
        print "  content: \"" content "\""
        printed_message = 1
        next
    }
    in_message && /^[^ ]/ && !/^message:/ {
        in_message = 0
    }
    !in_message { print }
    ' "$HOMER_CONFIG" > "$TMP_FILE"

    # Kopieer terug
    cat "$TMP_FILE" > "$HOMER_CONFIG"
    rm "$TMP_FILE"

    log "Homer config succesvol bijgewerkt"
}

main "$@"
