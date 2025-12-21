# EMSN2 Patches

Patches voor aanpassingen die na een BirdNET-Pi update opnieuw toegepast moeten worden.

## birdnet-disable-auth

**Doel:** Schakelt de WebUI login uit voor BirdNET-Pi

**Locatie:** `/home/ronny/emsn2/scripts/patches/birdnet-disable-auth.patch`

**Toepassen op Zolder:**
```bash
bash /home/ronny/emsn2/scripts/patches/birdnet-disable-auth.patch
```

**Toepassen op Berging:**
```bash
scp /home/ronny/emsn2/scripts/patches/birdnet-disable-auth.patch ronny@192.168.1.87:/tmp/
ssh ronny@192.168.1.87 "bash /tmp/birdnet-disable-auth.patch"
```

**Wanneer:** Na elke BirdNET-Pi update
