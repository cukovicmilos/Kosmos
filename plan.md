# Kosmos - Telegram Reminder Bot

## 📋 O projektu

**Kosmos** je Telegram bot čiji je osnovni zadatak da bude podsetnik. Korisnik može da napiše poruku i vreme kada ta poruka treba da stigne kao podsetnik u samom botu.

**Jezici:** Srpski (latinica) i Engleski (default: Engleski)

---

## 🎯 Funkcionalne specifikacije

### 1. Kreiranje podsetnika

#### User flow
Korisnik šalje poruku u formatu:
```
[Tekst podsetnika] [vremenska odrednica]
```

**Primer:**
```
Ponesi pecaljku na jezero sutra 16:00
```

- **"Ponesi pecaljku na jezero"** = tekst podsetnika
- **"sutra 16:00"** = vremenska odrednica

Bot odgovara sa potvrdom: **"Zabeleženo ✓"**

#### Vremenske odrednice

##### Dani

| Srpski | Engleski | Opis |
|--------|----------|------|
| sutra | tomorrow | Sledeći dan |
| prekosutra | dat | Dan posle sutra |
| pon, uto, sre, cet, pet, sub, ned | mon, tue, wed, thu, fri, sat, sun | Dani u nedelji (skraćeno) |
| *(prazan)* | *(prazan)* | Današnji dan (default) |

**Pravilo za dane u nedelji:**
- Ako korisnik unese dan u nedelji (npr. "pon"), **uvek** se odnosi na **sledeći** ponedeljak
- Primer: Ako je danas ponedeljak i korisnik napiše "pon 10:00", odnosi se na sledeći ponedeljak

##### Vreme

Podržani formati:
- `21:00` - sati i minuti sa dvema tačkama
- `21:30` - sati i minuti
- `8` - samo sat (pun sat: 08:00)
- `17` - samo sat (17:00)
- `7am` - AM/PM format (malo slovo)
- `6AM` - AM/PM format (veliko slovo)
- `2100` - military time (4 cifre)
- `6 AM` - sa razmakom
- `06 AM` - sa vodećom nulom i razmakom
- `0700` - military time sa vodećom nulom

**Pravila:**
- Vreme **mora biti na kraju poruke** (nakon teksta podsetnika i dana)
- Ako je uneseno vreme koje je već prošlo (bez specificiranja dana), automatski se pretpostavlja **sutra**

#### Validacija i error handling

Ako parsing ne uspe, bot prikazuje **jednostavnu poruku** sa primerima:

```
Nisam razumeo vreme. Pokušaj ponovo sa formatom:

[Poruka] [dan] [vreme]

Primeri:
- Ponesi pecaljku sutra 16:00
- Sastanak pon 10:00
- Kafa 14:30
```

---

### 2. Listanje podsetnika

#### Komanda: `/list` ili bot menu dugme "List"

Prikazuje sve buduće podsetnike korisnika sa **Telegram inline keyboard** dugmadima.

**Format:**
```
📝 Tvoji podsetnici:

1. Ponesi pecaljku na jezero
   📅 12.11.2025. u 16:00
   [Delete]

2. Sastanak sa timom
   📅 14.11.2025. u 10:00
   [Delete]

3. Kafa sa Markom
   📅 15.11.2025. u 14:30
   [Delete]
```

- Svaki podsetnik ima svoje **[Delete]** inline dugme
- Klikom na Delete, podsetnik se briše iz baze

---

### 3. Brisanje podsetnika

Korisnik briše podsetnike klikom na **[Delete]** inline dugme pored podsetnika u listi.

**Potvrda:**
```
Podsetnik obrisan ✓
```

Lista se automatski ažurira.

---

### 4. Slanje podsetnika

Kada dođe vreme za podsetnik, bot šalje poruku sa:

**Format:**
```
🔔 Podsetnik:

Ponesi pecaljku na jezero
```

Ispod poruke se prikazuju **inline dugmad za odlaganje (postpone)**:

```
[15m] [30m] [1h] [3h] [1d] [Custom time]
```

#### Postpone opcije:

| Opcija | Opis |
|--------|------|
| 15m | Odloži za 15 minuta |
| 30m | Odloži za 30 minuta |
| 1h | Odloži za 1 sat |
| 3h | Odloži za 3 sata |
| 1d | Odloži za 1 dan |
| Custom time | Korisnik ručno određuje vreme |

#### Custom time flow:

1. Korisnik klikne **[Custom time]**
2. Bot odgovara: `Unesi novo vreme:`
3. Korisnik šalje **samo vremensku odrednicu** (jer tekst podsetnika već postoji)
   - Može uneti samo vreme: `19:00` (danas u 19:00 ili sutra ako je vreme prošlo)
   - Ili dan + vreme: `uto 19:00` (utorak u 19:00)
4. Bot potvrđuje: `Podsetnik odložen ✓`

---

### 5. Podešavanja (Settings)

#### Komanda: `/settings`

Omogućava korisniku da podesi:

1. **Jezik** (Language)
   - Srpski (sr-lat)
   - English (en)

2. **Format vremena** (Time format)
   - AM/PM (12-sat format)
   - 24:00 (military time, 24-sat format)

3. **Vremenska zona** (Timezone)
   - Automatski preuzeta iz Telegram naloga (ako je dostupna)
   - Ako nije dostupna, korisnik bira pri `/start` iz liste

**Navigacija:** Inline keyboard sa dugmadima za svaku opciju.

---

### 6. Komande

| Komanda | Opis |
|---------|------|
| `/start` | Inicijalizacija bota, kreiranje korisničkog naloga |
| `/settings` | Podešavanja (jezik, vreme, timezone) |
| `/list` | Listanje svih budućih podsetnika |
| `/help` | Pomoć - kratak helper tekst sa osnovnim podacima i primeri |

---

### 7. Bot Menu (Persistent Menu)

Dugmad u Telegram bot meniju (ispod input fielda):

- **List** - Prikaz liste podsetnika (isto kao `/list`)
- **New Reminder** - Pokretanje flow-a za kreiranje novog podsetnika sa uputstvima

---

### 8. Timezone handling

- **Automatsko preuzimanje:** Bot pokušava da preuzme timezone iz Telegram naloga korisnika
- **Ako nije dostupan:** Pri `/start` komandi, bot prikazuje **selector listu** gde korisnik bira svoju vremensku zonu
- **Izmena:** Korisnik može da promeni timezone u `/settings`

**Format slanja poruke:**
- Korisnik dobija podsetnik u **svojoj** vremenskoj zoni

---

### 9. Organizacija korisnika u bazi

Bot čuva podatke o svim korisnicima koji koriste bot:

- **Telegram ID** (jedinstveni identifikator)
- **Username/Handle** (korisničko ime)
- **Jezik** (sr-lat ili en)
- **Time format** (AM/PM ili 24h)
- **Timezone** (npr. Europe/Belgrade, America/New_York)
- **Datum kreiranja naloga**

> **Napomena:** Ovo su predradnje za buduću monetizaciju, ali u prvoj verziji nema dodatnih funkcionalnosti vezanih za to.

---

## 🛠️ Tehnička arhitektura

### Backend framework
- **python-telegram-bot** (v20+)
  - GitHub: https://github.com/python-telegram-bot/python-telegram-bot
  - Dokumentacija: https://docs.python-telegram-bot.org/

### Baza podataka
- **SQLite** - lightweight, file-based database

#### Database šema

**Tabela: `users`**
| Polje | Tip | Opis |
|-------|-----|------|
| telegram_id | INTEGER PRIMARY KEY | Telegram user ID |
| username | TEXT | Telegram username/handle |
| language | TEXT | Jezik (en, sr-lat) |
| time_format | TEXT | Format vremena (12h, 24h) |
| timezone | TEXT | Timezone (pytz format) |
| created_at | TIMESTAMP | Datum kreiranja naloga |

**Tabela: `reminders`**
| Polje | Tip | Opis |
|-------|-----|------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Jedinstveni ID podsetnika |
| user_id | INTEGER | Foreign key -> users.telegram_id |
| message_text | TEXT | Tekst podsetnika |
| scheduled_time | TIMESTAMP | Vreme slanja (UTC) |
| created_at | TIMESTAMP | Datum kreiranja podsetnika |
| status | TEXT | Status (pending, sent, cancelled) |

### Internationalization (i18n)

Dva fajla za jezike:
- **en.po** - Engleski tekstovi
- **sr-lat.po** - Srpski (latinica) tekstovi

Svi tekstovi u kodu se referenciraju preko i18n helper funkcije koja automatski bira jezik na osnovu korisničkih podešavanja.

**Primer:**
```python
# Kod
message = _("reminder_created")

# en.po
msgid "reminder_created"
msgstr "Reminder created ✓"

# sr-lat.po
msgid "reminder_created"
msgstr "Zabeleženo ✓"
```

### Logging sistem

- **Log level:** INFO, DEBUG, WARNING, ERROR
- **Log fajl:** `log/app.log`
- **Rotacija:** Automatska rotacija po veličini (max 10MB, keep 5 backups)

**Log format:**
```
[2025-11-12 14:30:45] [INFO] [user:123456789] Reminder created: "Ponesi pecaljku" at 2025-11-13 16:00
```

---

## 📁 Project struktura

```
kosmos/
├── main.py                     # Entry point, bot startup
├── config.py                   # Konfiguracija i environment variables
├── database.py                 # SQLite helper funkcije, ORM
├── scheduler.py                # Background scheduler za proveru i slanje podsetnika
├── i18n.py                     # Internationalization helper (PO file loading)
│
├── handlers/                   # Telegram bot handlers
│   ├── __init__.py
│   ├── start.py                # /start komanda, inicijalizacija korisnika
│   ├── reminder.py             # Kreiranje podsetnika, parsing user input
│   ├── list.py                 # /list komanda, prikaz i brisanje podsetnika
│   ├── settings.py             # /settings komanda, podešavanja
│   ├── postpone.py             # Odlaganje podsetnika (callback handlers)
│   └── help.py                 # /help komanda
│
├── parsers/                    # Parsing logika
│   ├── __init__.py
│   └── time_parser.py          # Parsing vremenskih odrednica (dan, vreme)
│
├── locales/                    # Internationalization fajlovi
│   ├── en.po                   # Engleski tekstovi
│   └── sr-lat.po               # Srpski (latinica) tekstovi
│
├── log/                        # Log fajlovi (git ignored)
│   └── app.log
│
├── requirements.txt            # Python dependencies
├── .env.example                # Primer environment variables
├── .gitignore                  # Git ignore rules
├── README.md                   # Dokumentacija projekta
└── plan.md                     # Ovaj fajl - plan projekta
```

---

## 📦 Dependencies (requirements.txt)

```
python-telegram-bot>=20.0
pytz>=2023.3
APScheduler>=3.10.0
python-dotenv>=1.0.0
polib>=1.2.0
```

---

## 🔧 Konfiguracija (Environment variables)

Fajl: `.env`

```bash
# Telegram Bot Token (dobija se od BotFather)
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# Database path
DB_PATH=kosmos.db

# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Default timezone (ako nije dostupan iz Telegrama)
DEFAULT_TIMEZONE=Europe/Belgrade
```

---

## 🚀 Implementation plan

### **Faza 1: Osnovna infrastruktura i setup**
- [x] Kreirati projektnu strukturu (`kosmos/` direktorijum)
- [x] Kreirati `config.py` - učitavanje environment variables
- [x] Kreirati `.env.example` fajl
- [x] Kreirati `database.py` - SQLite konekcija i helper funkcije
- [x] Kreirati database šemu (users, reminders tabele)
- [x] Kreirati `i18n.py` - internationalization helper
- [x] Kreirati `en.po` i `sr-lat.po` fajlove (osnovni tekstovi)
- [x] Kreirati `logging` sistem u `config.py`

**Očekivano vreme:** 3-4 sata

---

### **Faza 2: Bot inicijalizacija i osnove**
- [x] Kreirati `main.py` - bot startup, handler registration
- [x] Implementirati `handlers/start.py`:
  - Kreiranje korisnika u bazi
  - Timezone selector (ako nije dostupan)
  - Welcome poruka
- [x] Implementirati `handlers/help.py`:
  - Kratak helper tekst
  - Primeri korišćenja
- [x] Postaviti bot menu (List, New Reminder dugmad)

**Očekivano vreme:** 2-3 sata

---

### **Faza 3: Parsing vremena i kreiranje podsetnika**
- [x] Implementirati `parsers/time_parser.py`:
  - Parsing dana (sutra/tomorrow, prekosutra/dat, pon-ned/mon-sun)
  - Parsing vremena (svi navedeni formati)
  - **Pravilo:** Vreme uvek na kraju poruke
  - **Pravilo:** Ako je vreme prošlo, pretpostavi sutra
  - **Pravilo:** Dani u nedelji = uvek sledeći
  - Validacija i error handling
- [x] Implementirati `handlers/reminder.py`:
  - Obrada user input poruke
  - Poziv time_parser-a
  - Čuvanje podsetnika u bazu
  - Potvrda: "Zabeleženo ✓"
- [x] Implementirati error handling sa jednostavnim porukama

**Očekivano vreme:** 5-6 sati

---

### **Faza 4: Scheduler i slanje podsetnika**
- [x] Implementirati `scheduler.py`:
  - APScheduler konfiguracija
  - Background task za proveru podsetnika
  - Slanje podsetnika u pravo vreme
- [x] Format poslate poruke:
  - Emoji 🔔
  - Tekst podsetnika
  - Inline keyboard sa postpone opcijama
- [x] Implementirati `handlers/postpone.py`:
  - Callback handlers za 15m, 30m, 1h, 3h, 1d
  - Custom time flow (prihvata vreme ili dan+vreme)
  - Update podsetnika u bazi

**Očekivano vreme:** 4-5 sati

---

### **Faza 5: Lista i brisanje podsetnika**
- [x] Implementirati `handlers/list.py`:
  - `/list` komanda
  - Fetch svih budućih podsetnika iz baze (sorted by scheduled_time)
  - Formatiranje poruke sa inline keyboard
  - [Delete] dugmad za svaki podsetnik
- [x] Implementirati callback handler za brisanje:
  - Update status u bazi (cancelled)
  - Potvrda: "Podsetnik obrisan ✓"
  - Refresh liste

**Očekivano vreme:** 3-4 sata

---

### **Faza 6: Podešavanja (Settings)**
- [x] Implementirati `handlers/settings.py`:
  - `/settings` komanda - glavni meni
  - Inline keyboard za opcije (Language, Time format, Timezone)
- [x] **Language setting:**
  - Izbor: Srpski (sr-lat) / English (en)
  - Update u bazi
- [x] **Time format setting:**
  - Izbor: AM/PM / 24h
  - Update u bazi
- [x] **Timezone setting:**
  - Selector lista sa popularnim timezone-ovima
  - Pretraga timezone-a (opciono)
  - Update u bazi

**Očekivano vreme:** 4-5 sati

---

### **Faza 7: Finalizacija i testiranje**
- [x] Database inicijalizacija skript
- [x] Kreirati `requirements.txt` sa svim dependencies
- [x] Kreirati `README.md`:
  - Instrukcije za setup (BotFather, .env, instalacija)
  - Instrukcije za pokretanje
  - Troubleshooting sekcija
- [x] **Testiranje:**
  - Kreiranje podsetnika (svi formati vremena)
  - Slanje podsetnika u pravo vreme
  - Postpone opcije
  - Lista i brisanje
  - Settings (jezik, time format, timezone)
  - Error handling
- [x] Bug fixing
- [x] Code review i refactoring

**Očekivano vreme:** 3-4 sata

---

**UKUPNO OČEKIVANO VREME:** ~24-31 sat (3-4 radna dana)

---

## 🏁 Setup i pokretanje

### 1. Kreiranje bota na Telegramu

1. Otvori Telegram i potraži **@BotFather**
2. Pošalji `/newbot`
3. Prati instrukcije:
   - Ime bota: `Kosmos Reminder`
   - Username: `kosmos_reminder_bot` (mora biti jedinstveno)
4. BotFather će ti dati **BOT_TOKEN** - sačuvaj ga!

### 2. Instalacija i pokretanje

```bash
# 1. Clone projekta (ili preuzmi fajlove)
cd kosmos/

# 2. Kreiranje virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ili
venv\Scripts\activate  # Windows

# 3. Instalacija dependencies
pip install -r requirements.txt

# 4. Kreiranje .env fajla
cp .env.example .env
# Edituj .env i dodaj svoj BOT_TOKEN

# 5. Inicijalizacija baze podataka
python database.py

# 6. Pokretanje bota
python main.py
```

Bot je sada pokrenut! Otvori Telegram i potraži svoj bot.

---

## 📝 Napomene

### Timezone handling
- Bot pokušava da automatski preuzme timezone iz Telegram naloga
- Ako nije dostupan, prikazuje selector listu pri `/start`
- Svi podsetnici se čuvaju u **UTC** u bazi
- Pri slanju, vreme se konvertuje u korisničku timezone

### Recurring reminders
- **Nije implementirano u v1**
- Planirano za v2 (opcija "Svaki dan", "Svaki ponedeljak", itd.)

### Monetizacija
- Database struktura već podržava tracking korisnika
- U v1 nema ograničenja ili premium feature-a
- Planirano za kasnije verzije

### Sigurnost
- BOT_TOKEN se čuva u `.env` fajlu (nikad u git-u!)
- SQLite baza ima write permissions samo za bot proces
- Input validacija protiv SQL injection (koristi parameterized queries)

---

## 📞 Podrška

Prijavi bugove ili predloži nove feature-e na GitHub-u!

---

**Kosmos v1.0** - Telegram Reminder Bot
Kreirano: Novembar 2025
