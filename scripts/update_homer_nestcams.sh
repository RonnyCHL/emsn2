#!/bin/bash
#
# Voeg nestkast cameras toe aan Homer config
# Eenmalig uitvoeren met: sudo bash /home/ronny/emsn2/scripts/update_homer_nestcams.sh
#

HOMER_CONFIG="/mnt/nas-docker/homer/config.yml"

# Backup maken
cp "$HOMER_CONFIG" "${HOMER_CONFIG}.bak.$(date +%Y%m%d%H%M%S)"

# Check of nestkast cameras al bestaan
if grep -q "Nestkast Cameras" "$HOMER_CONFIG"; then
    echo "Nestkast Cameras sectie bestaat al in Homer config"
    exit 0
fi

# Voeg nestkast cameras sectie toe na AtmosBird Sky
sed -i '/AtmosBird Sky/,/target: "_blank"/{
    /target: "_blank"/a\
\
  - name: "Nestkast Cameras"\
    icon: "fas fa-video"\
    items:\
      - name: "UniFi Protect"\
        logo: "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/unifi-protect.png"\
        subtitle: "Video - alle cameras"\
        url: "https://192.168.1.1/protect/devices"\
        target: "_blank"\
\
      - name: "Tuya Smart (Audio)"\
        icon: "fas fa-volume-up"\
        subtitle: "Audio - via app"\
        url: "https://smartlife.tuya.com/"\
        target: "_blank"\
\
      - name: "Nestkast Voor"\
        icon: "fas fa-home"\
        subtitle: "Voortuin nestkast"\
        url: "https://192.168.1.1/protect/devices"\
        target: "_blank"\
\
      - name: "Nestkast Midden"\
        icon: "fas fa-home"\
        subtitle: "Midden nestkast"\
        url: "https://192.168.1.1/protect/devices"\
        target: "_blank"\
\
      - name: "Nestkast Achter"\
        icon: "fas fa-home"\
        subtitle: "Achtertuin nestkast"\
        url: "https://192.168.1.1/protect/devices"\
        target: "_blank"
}' "$HOMER_CONFIG"

echo "Nestkast Cameras toegevoegd aan Homer config!"
echo "Homer herlaadt automatisch de config."
