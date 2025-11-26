# Bot Statistics - Dinamički Short Description

## Pregled

Implementirana je funkcionalnost za automatsko ažuriranje Telegram bot-a sa statistikama aktivnih korisnika kroz `setMyShortDescription` API.

## Šta je dodato

### 1. Database funkcije (`database.py`)

Tri nove funkcije za statistiku:

- **`get_monthly_active_users()`** - Vraća broj korisnika koji su kreirali bar jedan reminder u poslednjih 30 dana
- **`get_peak_monthly_users()`** - Vraća najviši broj korisnika u jednom mesecu (istorijski rekord)
- **`get_total_users()`** - Vraća ukupan broj registrovanih korisnika

### 2. Bot Stats modul (`bot_stats.py`)

Novi modul sa dve async funkcije:

- **`update_bot_short_description(bot)`** - Ažurira kratak opis bota sa statistikama
  - Prikazuje mesečne aktivne korisnike (prioritet)
  - Fallback na peak korisnike, pa total korisnike
  - Default poruka ako nema podataka
  
- **`update_bot_description(bot)`** - Ažurira puni opis bota sa detaljnom statistikom
  - Uključuje mesečne aktivne i ukupne korisnike
  - Prikazuje sve komande

### 3. Scheduler Jobs (`scheduler.py`)

Dodati su automatski zadaci:

- **Svaka 6 sati** - Ažuriranje kratkog opisa (`update_bot_short_description`)
- **Jednom dnevno** - Ažuriranje punog opisa (`update_bot_description`)

### 4. Startup Hook (`main.py`)

Pri pokretanju bota, u `post_init` funkciji:
- Odmah se ažuriraju oba opisa sa trenutnim statistikama
- Omogućava da bot ima svež opis čim krene

## Kako radi

1. **Pri startu bota**: Short description se odmah postavi sa trenutnom statistikom
2. **Tokom rada**: Scheduler automatski osvežava opis svaka 6 sati
3. **Što više korisnika koristi bot**: Short description prikazuje broj aktivnih korisnika
4. **Prioritet prikaza**:
   - Ako ima aktivnih korisnika u poslednjih 30 dana → prikazuje se to
   - Inače, prikazuje se najviši mesečni rekord
   - Ako ni to nije dostupno → ukupan broj korisnika
   - Ako nema korisnika → generički opis

## Format Short Description-a

```
🤖 Aktivno korisnika (30 dana): 42
```

ili

```
🤖 Rekordni broj korisnika: 100
```

ili

```
🤖 Ukupno korisnika: 250
```

## Testiranje

Pre pokretanja bota, možete testirati statistike sa:

```bash
python3 test_bot_stats.py
```

Ovo će:
- Inicijalizovati bazu
- Prikazati trenutne statistike
- Generisati primer short/full description-a
- **Neće** poslati API poziv ka Telegram-u (za to treba pun bot)

## Pokretanje u produkciji

1. Instalirajte dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Pokrenite bota normalno:
   ```bash
   python3 main.py
   ```

3. Bot će automatski:
   - Postaviti short description pri startu
   - Osvežavati ga svaka 6 sati
   - Osvežavati puni opis jednom dnevno

## Logovanje

Sve operacije se loguju:
- `Bot short description updated: ...` - Uspešno ažuriranje
- `Stats - Monthly: X, Peak: Y, Total: Z` - Debug info sa statistikama
- Errori ako API pozivi ne uspeju

## Napomene

- API pozivi za setMyShortDescription ne troše rate limit značajno
- Statistike se računaju u realnom vremenu iz baze podataka
- Nema dodatnih tabela - koriste se postojeće `users` i `reminders` tabele
- Compatible sa postojećom arhitekturom bota
