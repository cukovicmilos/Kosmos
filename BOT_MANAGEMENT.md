# Bot Management Guide

## ⚠️ VAŽNO: Kako pravilno upravljati botom

Bot je konfigurisan kao **systemd service** i automatski se startuje.

### ✅ PRAVILNO - Koristi systemd komande:

```bash
# Restart bota (nakon izmena koda)
sudo systemctl restart kosmos-bot.service

# Provera statusa
sudo systemctl status kosmos-bot.service

# Zaustavljanje bota
sudo systemctl stop kosmos-bot.service

# Pokretanje bota
sudo systemctl start kosmos-bot.service

# Provera logova (real-time)
sudo journalctl -u kosmos-bot.service -f

# Provera poslednjih 50 linija loga
sudo journalctl -u kosmos-bot.service -n 50

# Disable auto-start (ako ne želiš da se startuje pri boot-u)
sudo systemctl disable kosmos-bot.service

# Enable auto-start
sudo systemctl enable kosmos-bot.service
```

### ❌ POGREŠNO - NE koristi ručno pokretanje:

```bash
# ❌ Ovo će kreirati DUPLIKAT proces!
nohup venv/bin/python main.py &
python main.py &
venv/bin/python main.py
```

## 🔧 Systemd Service Konfiguracija

**Lokacija:** `/etc/systemd/system/kosmos-bot.service`

```ini
[Unit]
Description=Kosmos Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=chule
WorkingDirectory=/var/www/html/kosmos
Environment="PATH=/var/www/html/kosmos/venv/bin:/usr/bin"
ExecStart=/var/www/html/kosmos/venv/bin/python /var/www/html/kosmos/main.py
Restart=always         # Automatski restart ako crashuje
RestartSec=10         # Čeka 10s pre restart-a
StandardOutput=append:/var/www/html/kosmos/log/bot.log
StandardError=append:/var/www/html/kosmos/log/bot.log

[Install]
WantedBy=multi-user.target
```

## 🐛 Troubleshooting Duplikacije Procesa

### Problem: "Conflict: terminated by other getUpdates request"

**Uzrok:** Dva bot procesa pokušavaju da poll-uju Telegram API istovremeno.

**Dijagnoza:**
```bash
# Proveri sve Python procese
ps aux | grep -E "[p]ython.*main.py"

# Ako vidiš 2+ procesa → DUPLIKACIJA!
```

**Rešenje:**
```bash
# 1. Zaustavi sve ručno pokrenute procese
pkill -f "python.*main.py"

# 2. Restart preko systemd
sudo systemctl restart kosmos-bot.service

# 3. Verifikuj da je samo jedan proces
ps aux | grep -E "[p]ython.*main.py"
# Trebao bi biti samo jedan (user: chule)
```

## 📋 Logovanje

Bot piše logove na dva mesta:

1. **Systemd journal:**
   ```bash
   sudo journalctl -u kosmos-bot.service -f
   ```

2. **Application log:**
   ```bash
   tail -f /var/www/html/kosmos/log/app.log
   ```

## 🔄 Izmene Koda - Workflow

Nakon izmena u kodu:

```bash
# 1. Proveri syntax (opciono)
cd /var/www/html/kosmos
source venv/bin/activate
python -m py_compile main.py

# 2. Restart service
sudo systemctl restart kosmos-bot.service

# 3. Proveri da je startovao ok
sudo systemctl status kosmos-bot.service

# 4. Prati log
tail -f log/app.log
```

## 🔄 Ažuriranje Bot Menija (Commands)

Ako si dodao/izmenio bot komande u `main.py` (npr. `/netstats`), moraš prisilno ažurirati meni:

```bash
cd /var/www/html/kosmos
source venv/bin/activate
python update_bot_commands.py
```

**Šta radi skripta:**
- Briše stare komande sa Telegram servera (čisti keš)
- Postavlja nove komande
- Prikazuje listu trenutnih komandi

**VAŽNO - Kako videti nove komande u Telegram aplikaciji:**

Telegram kešira komande na klijentskoj strani! Nakon pokretanja skripte:

1. **Zatvori Telegram aplikaciju potpuno** (ne samo bot chat, već celu aplikaciju)
2. **Ponovo otvori Telegram**
3. **Otvori bot chat**
4. **Klikni na Menu dugme** (⋮ ili ☰ ikonica pored text input polja)
5. Sada bi trebalo da vidiš **sve nove komande** uključujući `/netstats`

**Alternativa (bez zatvaranja aplikacije):**
- Obrisi chat sa botom i započni novi chat (ali je sigurnije restartovati aplikaciju)

## 🚀 Deployment Checklist

✅ Izmeni kod  
✅ Test syntax: `python -m py_compile <file.py>`  
✅ Restart: `sudo systemctl restart kosmos-bot.service`  
✅ Proveri status: `sudo systemctl status kosmos-bot.service`  
✅ Proveri log: `tail -f log/app.log`  
✅ Test funkcionalnost u Telegram-u

## 📊 Monitoring

```bash
# Provera da li je bot aktivan
systemctl is-active kosmos-bot.service

# Provera da li je enabled (auto-start)
systemctl is-enabled kosmos-bot.service

# Provera memory/CPU usage
systemctl status kosmos-bot.service

# Puni status sa logovima
sudo systemctl status kosmos-bot.service -l --no-pager
```

## 🔐 Permissions

Service radi pod user-om: **chule**

Fajlovi trebaju biti:
- Owner: chule
- Readable/executable: venv i main.py

```bash
# Provera permissions
ls -la /var/www/html/kosmos/
ls -la /var/www/html/kosmos/venv/bin/python
```

---

**Zaključak:** UVEK koristi `systemctl` komande za upravljanje botom. Nikad ne pokreći ručno sa `python main.py` ili `nohup`.
