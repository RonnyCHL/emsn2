# EMSN Reports Web Interface - Setup Instructies

## ✅ Voltooid

- ✅ HTML interface gecreëerd
- ✅ Flask API server draait op port 8081
- ✅ PDF conversie met pandoc
- ✅ Automatische index generatie bij nieuwe rapporten

## 🔧 Nginx Configuratie op NAS

Om de rapporten via Homer toegankelijk te maken, moet je nginx op je NAS configureren om requests door te sturen naar de API op de Raspberry Pi.

### 1. Nginx Config Toevoegen

Maak een nieuwe config file aan op je NAS:

```bash
# SSH naar je NAS
ssh gebruiker@192.168.1.25

# Maak nginx config aan
sudo nano /etc/nginx/sites-available/emsn-reports

# Voeg de volgende configuratie toe:
```

```nginx
server {
    listen 80;
    server_name rapporten.emsn.local;  # Of gebruik je NAS IP

    location / {
        proxy_pass http://192.168.1.YOUR_PI_IP:8081;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. Config Activeren

```bash
# Symlink maken
sudo ln -s /etc/nginx/sites-available/emsn-reports /etc/nginx/sites-enabled/

# Test config
sudo nginx -t

# Herstart nginx
sudo systemctl reload nginx
```

### 3. Alternatief: Subdirectory

Als je de rapporten onder een subdirectory wil (bijv. `http://nas.local/rapporten/`):

```nginx
location /rapporten/ {
    proxy_pass http://192.168.1.YOUR_PI_IP:8081/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    rewrite ^/rapporten/(.*)$ /$1 break;
}
```

## 🏠 Homer Dashboard Integratie

### Homer Config Toevoegen

Edit je Homer config (meestal `/opt/homer/config.yml` of `/var/www/html/homer/config.yml`):

```yaml
services:
  - name: "EMSN"
    icon: "fas fa-dove"
    items:
      - name: "Vogelrapporten"
        subtitle: "Wekelijkse en maandelijkse rapporten"
        logo: "assets/icons/bird.png"
        url: "http://nas.local/rapporten/"  # Of http://rapporten.emsn.local
        target: "_blank"
```

## 📱 Directe Toegang (Zonder Nginx)

Als je geen nginx wil configureren, kun je ook direct naar de API op de Pi gaan:

```
http://192.168.1.YOUR_PI_IP:8081
```

Je moet dan wel zeker zijn dat de firewall op de Pi port 8081 toelaat.

## 🔒 Firewall (Optioneel)

Als je ufw gebruikt op de Pi:

```bash
sudo ufw allow 8081/tcp
sudo ufw reload
```

## 🧪 Testen

Test of alles werkt:

```bash
# Vanaf je NAS of andere machine:
curl http://192.168.1.YOUR_PI_IP:8081/reports.json

# Via nginx (als geconfigureerd):
curl http://nas.local/rapporten/reports.json
```

## 📄 PDF Generatie

De "Download PDF" knop gebruikt pandoc om de markdown rapporten naar PDF te converteren. Dit gebeurt automatisch via de API endpoint:

```
GET /api/pdf?file=2025-W50-Weekrapport.md
```

## 🔄 Automatische Updates

De index wordt automatisch bijgewerkt telkens wanneer:
- Een nieuw weekrapport wordt gegenereerd (maandag 07:00)
- Een nieuw maandrapport wordt gegenereerd (1e van de maand 08:00)

## 🐛 Troubleshooting

### API draait niet

```bash
sudo systemctl status emsn-reports-api.service
sudo journalctl -u emsn-reports-api.service -f
```

### Port 8081 niet toegankelijk

```bash
# Check of de API luistert
sudo ss -tlnp | grep 8081

# Test lokaal
curl http://localhost:8081
```

### PDF generatie faalt

```bash
# Check of pandoc werkt
which pandoc
pandoc --version

# Check logs
tail -f /mnt/usb/logs/emsn-reports-api.error.log
```

### Nginx errors

```bash
# Check nginx config
sudo nginx -t

# Check nginx logs
sudo tail -f /var/log/nginx/error.log
```

## 📊 Status Check

Alle services checken:

```bash
# Op de Pi:
sudo systemctl status emsn-reports-api.service
sudo systemctl status emsn-weekly-report.timer
sudo systemctl status emsn-monthly-report.timer
systemctl list-timers | grep emsn

# Check laatste rapporten
ls -lh /home/ronny/emsn2/reports/

# Check web index
cat /home/ronny/emsn2/reports-web/reports.json | jq '.'
```

## 🎉 Klaar!

Als alles werkt, kun je:
- Rapporten bekijken via je browser
- PDFs downloaden
- Automatisch nieuwe rapporten ontvangen elke week/maand
- Toegang via Homer dashboard
