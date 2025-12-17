# Sessie Samenvatting: 17 december 2025

## Homer Dashboard, PDF Rapporten en BirdNET-Pi Aanpassingen

### Overzicht
Deze sessie omvatte drie hoofdonderwerpen:
1. Homer dashboard customization
2. PDF rapport verbeteringen
3. BirdNET-Pi authenticatie uitschakelen

---

## 1. Homer Dashboard Aanpassingen

### Bestanden gewijzigd
- `/mnt/nas-docker/homer/config.yml` - Dashboard configuratie
- `/mnt/nas-docker/homer/assets/custom.css` - Custom styling
- `/mnt/nas-docker/docker-compose.yml` - Volume mounts toegevoegd

### Wijzigingen

**Donkergroene header (#1B5E3B - EMSN groen)**
```yaml
colors:
  light:
    highlight-primary: "#1B5E3B"
    highlight-secondary: "#2E7D4E"
    highlight-hover: "#3D9960"
  dark:
    highlight-primary: "#1B5E3B"
    highlight-secondary: "#2E7D4E"
    highlight-hover: "#3D9960"
```

**EMSN logo voor vogelstations**
- Beide stations (Zolder en Berging) gebruiken nu `assets/icons/emsn-station.png`
- Logo gekopieerd van `/home/ronny/emsn2/assets/logo-pdf.png` (400x400, transparant)

**Favicons toegevoegd**
- Gekopieerd van `/home/ronny/emsn2/assets/` naar `/mnt/nas-docker/homer/assets/icons/`
- favicon.ico, favicon-32x32.png, favicon-192x192.png, favicon-180x180.png

**Custom CSS voor watermerk en twee kolommen**
```css
/* Subtiel watermerk logo op achtergrond */
#app::before {
    background-image: url("/assets/icons/emsn-logo.png");
    opacity: 0.04;
}

/* Twee kolommen voor Monitoring sectie */
@media (min-width: 1200px) {
    .service-list {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
    }
}
```

**Docker-compose volume mounts**
```yaml
volumes:
  - ./homer/config.yml:/www/assets/config.yml:ro
  - ./homer/assets/icons:/www/assets/icons:ro
  - ./homer/assets/custom.css:/www/assets/custom.css:ro
  - ./homer/assets/emsn-logo.png:/www/assets/icons/emsn-logo.png:ro
```

### Homer herstarten
```bash
ssh ronny@192.168.1.25
cd /volume1/docker && sudo docker-compose restart homer
```

---

## 2. PDF Rapport Verbeteringen

### Bestanden gewijzigd
- `/home/ronny/emsn2/reports-web/emsn-template.tex` - LaTeX template

### Wijzigingen

**Watermerk alleen vanaf pagina 2**
```latex
\AddToShipoutPictureBG{%
    \ifnum\value{page}>1
        \AtPageCenter{%
            \begin{tikzpicture}[remember picture,overlay]
                \node[opacity=0.04] at (0,0) {\includegraphics[height=28cm]{$logo-path$}};
            \end{tikzpicture}%
        }%
    \fi
}
```

**Disclaimer tekst aangepast**
```latex
Dit rapport is automatisch gegenereerd op basis van geluidsopnames die zijn geanalyseerd
met BirdNET, een AI-systeem voor het herkennen van vogelzang en vogelgeluiden. Hoewel
BirdNET een hoge nauwkeurigheid heeft, kunnen er fouten voorkomen bij de soortdeterminatie.
Zeldzame en opvallende soorten worden altijd getoetst door de gebruiker.

De gegevens zijn afkomstig van het Ecologisch Monitoring Systeem Nijverdal (EMSN), een
citizen science project van Ronny Hullegie.
```

**Emoji verwijderd uit rapporten**
- `weekly_report.py` - Alle emoji uit sectiekoppen verwijderd
- `monthly_report.py` - Alle emoji uit sectiekoppen verwijderd
- `weather_forecast.py` - Emoji weer-iconen vervangen door tekst

---

## 3. BirdNET-Pi Authenticatie Uitgeschakeld

### BELANGRIJK: Core file wijziging!
Deze wijziging wordt mogelijk overschreven bij een BirdNET-Pi update.

### Bestanden gewijzigd
- `/home/ronny/BirdNET-Pi/scripts/common.php` (Zolder - 192.168.1.178)
- `/home/ronny/BirdNET-Pi/scripts/common.php` (Berging - 192.168.1.87)

### Wijziging
De `is_authenticated()` functie is aangepast om authenticatie over te slaan als `CADDY_PWD` leeg is:

```php
function is_authenticated() {
  // Skip auth if CADDY_PWD is empty
  $config = get_config();
  if (empty($config['CADDY_PWD'])) {
    return true;
  }
  $ret = false;
  if (isset($_SERVER['PHP_AUTH_USER'])) {
    $config = get_config();
    $ret = ($_SERVER['PHP_AUTH_PW'] == $config['CADDY_PWD'] && $_SERVER['PHP_AUTH_USER'] == 'birdnet');
  }
  return $ret;
}
```

### Reden
De gebruiker moest telkens een gebruikersnaam (birdnet) invoeren om bij de BirdNET-Pi settings te komen, ondanks dat `CADDY_PWD` leeg was in `birdnet.conf`.

### Na BirdNET-Pi update
Als BirdNET-Pi wordt bijgewerkt, moet deze patch opnieuw worden toegepast:

```bash
# Op Zolder (192.168.1.178)
sudo sed -i 's/function is_authenticated() {/function is_authenticated() {\n  \/\/ Skip auth if CADDY_PWD is empty\n  $config = get_config();\n  if (empty($config['\''CADDY_PWD'\''])) {\n    return true;\n  }/' /home/ronny/BirdNET-Pi/scripts/common.php

# Op Berging (192.168.1.87)
ssh ronny@192.168.1.87 "sudo sed -i 's/function is_authenticated() {/function is_authenticated() {\n  \/\/ Skip auth if CADDY_PWD is empty\n  \$config = get_config();\n  if (empty(\$config['\''CADDY_PWD'\''])) {\n    return true;\n  }/' /home/ronny/BirdNET-Pi/scripts/common.php"
```

---

## 4. BirdNET-Pi Logo

### Eerder deze sessie
EMSN logo toegevoegd aan BirdNET-Pi webinterface op beide stations:
- Gekopieerd naar `/home/ronny/emsn-logo.png` op beide Pi's
- Pad ingesteld via BirdNET-Pi webui Settings
- Logo verschijnt onderaan de Overview pagina

---

## Geleerde Lessen en Technische Details

### Homer Dashboard
- **Custom CSS laden:** Homer laadt stylesheets via de `stylesheet:` array in config.yml
- **Volume mounts:** CSS moet expliciet gemount worden in docker-compose, niet alleen de icons folder
- **Watermerk via CSS:** `::before` pseudo-element op `#app` met lage opacity (0.04) en `pointer-events: none`
- **Twee kolommen:** CSS Grid met `grid-template-columns: repeat(2, 1fr)` in media query
- **Logo's voor items:** Gebruik `logo:` voor lokale/externe afbeeldingen, `icon:` voor FontAwesome icons

### LaTeX/PDF Generatie
- **Watermerk met TikZ:** De `transparent` package werkt niet goed met XeLaTeX; gebruik `\node[opacity=0.04]` in TikZ
- **Conditionele pagina's:** `\ifnum\value{page}>1` om watermerk alleen op pagina 2+ te tonen
- **eso-pic package:** `\AddToShipoutPictureBG` voor achtergrond op elke pagina
- **Afbeelding formaat:** `height=28cm` voor volledige A4 pagina hoogte

### BirdNET-Pi Architectuur
- **Authenticatie:** PHP functie `is_authenticated()` in `/scripts/common.php`
- **Config bestand:** `CADDY_PWD` in `/home/ronny/BirdNET-Pi/birdnet.conf`
- **Caddy webserver:** Caddyfile in `/etc/caddy/Caddyfile`
- **Custom logo:** Pad in te stellen via webui Settings, logo verschijnt onderaan Overview

### NAS/Docker
- **Homer poort:** 8181 (extern) -> 8080 (intern)
- **Docker-compose locatie:** `/volume1/docker/` op NAS
- **Herstarten:** `docker-compose restart homer` of via Synology DSM Container Manager

---

## Samenvatting bestanden

| Locatie | Bestand | Wijziging |
|---------|---------|-----------|
| NAS | `/mnt/nas-docker/homer/config.yml` | Kleuren, logo's, stylesheet |
| NAS | `/mnt/nas-docker/homer/assets/custom.css` | Watermerk, 2 kolommen |
| NAS | `/mnt/nas-docker/docker-compose.yml` | Volume mounts |
| NAS | `/mnt/nas-docker/homer/assets/icons/` | Favicons, station logo |
| Zolder | `/home/ronny/emsn2/reports-web/emsn-template.tex` | Watermerk, disclaimer |
| Zolder | `/home/ronny/emsn2/scripts/reports/weekly_report.py` | Emoji verwijderd |
| Zolder | `/home/ronny/emsn2/scripts/reports/monthly_report.py` | Emoji verwijderd |
| Zolder | `/home/ronny/emsn2/scripts/reports/weather_forecast.py` | Emoji vervangen door tekst |
| Zolder | `/home/ronny/BirdNET-Pi/scripts/common.php` | Auth bypass |
| Berging | `/home/ronny/BirdNET-Pi/scripts/common.php` | Auth bypass |

---

## Handige Commando's

```bash
# Homer herstarten
ssh ronny@192.168.1.25 "cd /volume1/docker && sudo docker-compose restart homer"

# Berging Pi SSH
ssh ronny@192.168.1.87

# BirdNET-Pi auth patch na update (Zolder)
sudo sed -i 's/function is_authenticated() {/function is_authenticated() {\n  \/\/ Skip auth if CADDY_PWD is empty\n  $config = get_config();\n  if (empty($config['\''CADDY_PWD'\''])) {\n    return true;\n  }/' /home/ronny/BirdNET-Pi/scripts/common.php

# Controleer auth functie
sed -n '69,85p' /home/ronny/BirdNET-Pi/scripts/common.php
```

---

## Open Punten
- Homer watermerk werkt nog niet (CSS wordt mogelijk niet correct geladen door container)
- Na Homer restart controleren of watermerk en twee kolommen werken
