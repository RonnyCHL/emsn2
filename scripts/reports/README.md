# EMSN AI Rapporten

Automatisch gegenereerde, verhalende rapporten over vogelactiviteit met Claude AI.

## 🎯 Features

- **Wekelijkse rapporten**: Elke maandag om 07:00
- **Maandelijkse rapporten**: Elke 1e van de maand om 08:00
- **Verhalende stijl**: Niet alleen cijfers, maar een verhaal
- **Nederlands**: Warme, persoonlijke taal
- **Markdown output**: Opgeslagen in Obsidian vault
- **Uitgebreide data**: Top soorten, zeldzaamheden, patronen, trends

## 📋 Vereisten

### Python packages

```bash
pip3 install anthropic psycopg2-binary
```

### Claude API Key

1. Ga naar https://console.anthropic.com/
2. Maak een API key aan
3. Sla op als environment variable:

```bash
# In ~/.bashrc of systemd service file
export ANTHROPIC_API_KEY="sk-ant-..."
```

**BELANGRIJK:** Update `/home/ronny/emsn2/systemd/emsn-weekly-report.service` met je API key!

### Obsidian Directory

```bash
# Maak rapporten directory aan
mkdir -p /mnt/nas/obsidian/EMSN/Rapporten

# Check permissions
ls -la /mnt/nas/obsidian/EMSN/
```

## 🚀 Installatie

### 1. Dependencies installeren

```bash
pip3 install anthropic psycopg2-binary
```

### 2. API Key configureren

Edit `/home/ronny/emsn2/systemd/emsn-weekly-report.service` en voeg je API key toe:

```ini
Environment="ANTHROPIC_API_KEY=sk-ant-jouw-key-hier"
```

### 3. Systemd timers installeren

```bash
# Copy systemd files (weekly + monthly)
sudo cp /home/ronny/emsn2/systemd/emsn-weekly-report.service /etc/systemd/system/
sudo cp /home/ronny/emsn2/systemd/emsn-weekly-report.timer /etc/systemd/system/
sudo cp /home/ronny/emsn2/systemd/emsn-monthly-report.service /etc/systemd/system/
sudo cp /home/ronny/emsn2/systemd/emsn-monthly-report.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start timers
sudo systemctl enable emsn-weekly-report.timer emsn-monthly-report.timer
sudo systemctl start emsn-weekly-report.timer emsn-monthly-report.timer

# Check status
sudo systemctl status emsn-weekly-report.timer emsn-monthly-report.timer
systemctl list-timers | grep emsn
```

## 🧪 Handmatig Testen

### Test rapport generatie

```bash
cd /home/ronny/emsn2/scripts/reports

# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."
export EMSN_DB_PASSWORD="REDACTED_DB_PASS"

# Run weekly report
python3 weekly_report.py

# Run monthly report
python3 monthly_report.py
```

### Test systemd services

```bash
# Run services manually
sudo systemctl start emsn-weekly-report.service
sudo systemctl start emsn-monthly-report.service

# Check logs
tail -f /mnt/usb/logs/emsn-weekly-report.log
tail -f /mnt/usb/logs/emsn-monthly-report.log
```

## 📂 Output

Rapporten worden opgeslagen als:

```
/mnt/nas/obsidian/EMSN/Rapporten/
├── 2025-W50-Weekrapport.md
├── 2025-W51-Weekrapport.md
├── 2025-W52-Weekrapport.md
├── 2025-12-Maandrapport.md
└── 2026-01-Maandrapport.md
```

### Markdown structuur

```markdown
---
type: weekrapport
week: 50
year: 2025
period: 2025-12-09 tot 2025-12-15
total_detections: 1245
unique_species: 34
generated: 2025-12-16 07:00:15
---

# Week 50 - Vogelactiviteit

**Periode:** 2025-12-09 tot 2025-12-15
**Detecties:** 1,245
**Soorten:** 34

---

[Claude's verhalende tekst hier]

---

## 📊 Statistieken
[Top 10 soorten, zeldzame waarnemingen, etc.]
```

## 💰 Kosten

- **Per weekrapport:** ~$0.01
- **Per maandrapport:** ~$0.02
- **Per jaar:** ~$0.76 (52 weken + 12 maanden)

Zeer laag dankzij efficiënte prompts en Sonnet model.

## 🔧 Troubleshooting

### "ANTHROPIC_API_KEY environment variable not set"

API key niet geconfigureerd. Check:
1. Environment variable in systemd service file
2. `.bashrc` als je handmatig test

### "Database connection failed"

PostgreSQL niet bereikbaar. Check:
1. Database draait: `systemctl status postgresql`
2. Firewall: `sudo ufw status`
3. Password klopt

### "Permission denied" op Obsidian directory

```bash
# Check eigenaar
ls -la /mnt/nas/obsidian/EMSN/

# Fix permissions
sudo chown -R ronny:ronny /mnt/nas/obsidian/EMSN/
```

### Timer triggert niet

```bash
# Check timer status
systemctl status emsn-weekly-report.timer

# Check volgende trigger tijd
systemctl list-timers | grep emsn-weekly

# Force trigger now
sudo systemctl start emsn-weekly-report.service
```

## 📝 Logs

Logs worden geschreven naar:
- **Stdout:** `/mnt/usb/logs/emsn-weekly-report.log`
- **Stderr:** `/mnt/usb/logs/emsn-weekly-report.error.log`

```bash
# Bekijk logs
tail -f /mnt/usb/logs/emsn-weekly-report.log

# Bekijk fouten
tail -f /mnt/usb/logs/emsn-weekly-report.error.log
```

## 🔮 Toekomstige Features

- [x] Maandelijkse rapporten
- [ ] HTML export voor website
- [ ] Email notificaties
- [ ] Engelse vertalingen
- [ ] Foto's embedden
- [ ] Audio samples linken

## 📚 Zie ook

- [Fase 13 Planning](../../planning/Fase-13-AI-Rapporten.md)
- [Claude API Docs](https://docs.anthropic.com/)
- [EMSN Database Schema](../../docs/database-schema.md)
