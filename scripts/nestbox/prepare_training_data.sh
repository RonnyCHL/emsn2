#!/bin/bash
#
# Bereidt nestkast screenshots voor ML training
# Maakt een zip bestand met de juiste structuur voor Colab
#

OUTPUT_DIR="/tmp/nestbox_training"
ZIP_FILE="/tmp/nestbox_data.zip"

echo "=== Nestkast Training Data Voorbereiding ==="

# Opruimen
rm -rf "$OUTPUT_DIR" "$ZIP_FILE"
mkdir -p "$OUTPUT_DIR/nestbox_data/bezet"
mkdir -p "$OUTPUT_DIR/nestbox_data/leeg"

# Midden = bezet (Koolmees slaapt daar)
echo "Kopieer 'bezet' screenshots (midden)..."
find /mnt/nas-birdnet-archive/nestbox/midden -name "*.jpg" -exec cp {} "$OUTPUT_DIR/nestbox_data/bezet/" \;
BEZET_COUNT=$(ls "$OUTPUT_DIR/nestbox_data/bezet/"*.jpg 2>/dev/null | wc -l)
echo "  $BEZET_COUNT bestanden gekopieerd"

# Voor + Achter = leeg
echo "Kopieer 'leeg' screenshots (voor + achter)..."
find /mnt/nas-birdnet-archive/nestbox/voor -name "*.jpg" -exec cp {} "$OUTPUT_DIR/nestbox_data/leeg/" \;
find /mnt/nas-birdnet-archive/nestbox/achter -name "*.jpg" -exec cp {} "$OUTPUT_DIR/nestbox_data/leeg/" \;
LEEG_COUNT=$(ls "$OUTPUT_DIR/nestbox_data/leeg/"*.jpg 2>/dev/null | wc -l)
echo "  $LEEG_COUNT bestanden gekopieerd"

# Maak zip
echo ""
echo "Maak zip bestand..."
cd "$OUTPUT_DIR"
zip -r "$ZIP_FILE" nestbox_data -q

# Resultaat
ZIP_SIZE=$(du -h "$ZIP_FILE" | cut -f1)
echo ""
echo "=== Klaar ==="
echo "Zip bestand: $ZIP_FILE"
echo "Grootte: $ZIP_SIZE"
echo ""
echo "Totaal: $((BEZET_COUNT + LEEG_COUNT)) afbeeldingen"
echo "  - Bezet: $BEZET_COUNT"
echo "  - Leeg: $LEEG_COUNT"
echo ""
echo "Upload dit bestand naar Colab en voer de notebook uit!"
