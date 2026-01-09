#!/bin/bash
#
# Setup Nestkast Cameras in Homer
# Voegt de nestkast camera sectie toe aan Homer config
#

HOMER_CONFIG="/mnt/nas-docker/homer/config.yml"
BACKUP="${HOMER_CONFIG}.bak.$(date +%Y%m%d%H%M%S)"

echo "=== EMSN Nestkast Cameras Setup ==="

# Backup
cp "$HOMER_CONFIG" "$BACKUP"
echo "Backup gemaakt: $BACKUP"

# Check of nestkast cameras al bestaan
if grep -q "Nestkast Cameras" "$HOMER_CONFIG"; then
    echo "Nestkast Cameras sectie bestaat al!"
    exit 0
fi

# Maak tijdelijk bestand met nieuwe config
cat > /tmp/nestcam_section.txt << 'EOF'

  - name: "Nestkast Cameras"
    icon: "fas fa-video"
    items:
      - name: "go2rtc Streams"
        logo: "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/go2rtc.png"
        subtitle: "Video + Audio (WebRTC)"
        url: "http://192.168.1.25:1984"
        target: "_blank"

      - name: "Nestkast Voor"
        icon: "fas fa-home"
        subtitle: "Voortuin - video+audio"
        url: "http://192.168.1.25:1984/stream.html?src=nestkast_voor"
        target: "_blank"

      - name: "Nestkast Midden"
        icon: "fas fa-home"
        subtitle: "Midden - video+audio"
        url: "http://192.168.1.25:1984/stream.html?src=nestkast_midden"
        target: "_blank"

      - name: "Nestkast Achter"
        icon: "fas fa-home"
        subtitle: "Achtertuin - video+audio"
        url: "http://192.168.1.25:1984/stream.html?src=nestkast_achter"
        target: "_blank"

      - name: "UniFi Protect"
        logo: "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/unifi-protect.png"
        subtitle: "Opnames & beheer"
        url: "https://192.168.1.1/protect/devices"
        target: "_blank"

EOF

# Voeg sectie toe na "AtmosBird Sky" blok
# We zoeken de regel met "# === KOLOM 2:" en voegen ervoor in
sed -i "/# === KOLOM 2: SYSTEEM & WEER ===/r /tmp/nestcam_section.txt" "$HOMER_CONFIG"

# Verplaats de ingevoegde sectie naar de juiste plek (na AtmosBird, voor KOLOM 2 comment)
# De sed hierboven voegt toe NA de match, dus we moeten de comment weer bovenaan zetten

rm /tmp/nestcam_section.txt

echo "Nestkast Cameras sectie toegevoegd aan Homer!"
echo ""
echo "Homer herlaadt automatisch. Check: http://192.168.1.25:8181"
