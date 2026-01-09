#!/bin/bash
# Cleanup script voor NAS vocalization data
# Voer dit uit op de NAS met: sudo bash cleanup_nas_vocalization.sh

VOCALIZATION_DIR="/volume1/docker/emsn-vocalization"

echo "=== NAS Vocalization Cleanup ==="
echo ""

# 1. Stop en verwijder Docker containers
echo "1. Docker containers stoppen en verwijderen..."
docker stop emsn-vocalization-pytorch 2>/dev/null && echo "   Container gestopt"
docker rm emsn-vocalization-pytorch 2>/dev/null && echo "   Container verwijderd"

# 2. Verwijder Docker images
echo ""
echo "2. Docker images verwijderen..."
docker images | grep -E "emsn-vocalization|vocalization" | awk '{print $3}' | xargs -r docker rmi 2>/dev/null
echo "   Images opgeruimd"

# 3. Toon huidige disk usage
echo ""
echo "3. Huidige disk usage:"
du -sh $VOCALIZATION_DIR/data/* 2>/dev/null

# 4. Verwijder raw audio (29GB)
echo ""
echo "4. Raw audio verwijderen (29GB)..."
rm -rf $VOCALIZATION_DIR/data/raw/*
echo "   Raw audio verwijderd"

# 5. Verwijder spectrograms (41GB)
echo ""
echo "5. Spectrograms verwijderen (41GB)..."
rm -rf $VOCALIZATION_DIR/data/spectrograms-*
echo "   Spectrograms verwijderd"

# 6. Verwijder SQLite copy
echo ""
echo "6. SQLite kopie verwijderen..."
rm -f $VOCALIZATION_DIR/data/birds.db
echo "   birds.db verwijderd"

# 7. Cleanup logs (optioneel - bewaar laatste)
echo ""
echo "7. Oude logs opruimen..."
find $VOCALIZATION_DIR/logs -name "*.log" -mtime +7 -delete 2>/dev/null
find $VOCALIZATION_DIR/logs -name "*.png" -mtime +7 -delete 2>/dev/null
echo "   Oude logs verwijderd"

# 8. Toon wat overblijft
echo ""
echo "=== Resultaat ==="
echo "Overgebleven (te behouden):"
du -sh $VOCALIZATION_DIR/data/models 2>/dev/null
echo ""
echo "Totale vocalization folder:"
du -sh $VOCALIZATION_DIR 2>/dev/null

echo ""
echo "=== Cleanup voltooid ==="
echo ""
echo "De 168 getrainde modellen (4.7GB) zijn behouden in:"
echo "  $VOCALIZATION_DIR/data/models/"
echo ""
echo "Deze modellen worden gebruikt door de vocalization-enricher"
echo "service op de Pi voor classificatie van vogelgeluiden."
