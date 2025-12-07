# Edit Reminder - Implementation Plan

## Overview
Pristup 2: Reply-based edit sa minimalnim UI/UX kompleksnošću.

## User Flow

```
User: /list

Bot:
📝 *Your reminders:*

1. 🔁 Kafa (every day)
   08.12.2024. at 14:00

2. Meeting
   09.12.2024. at 10:00

[🗑️ Delete #1] [✏️ Edit #1]
[🗑️ Delete #2] [✏️ Edit #2]

User klikne: [✏️ Edit #1]

Bot (sa ForceReply):
✏️ *Editing:* Kafa

Reply with new text and/or time:
• `New text 15:00` - change both
• `New text` - change only text  
• `15:00` - change only time

User reply: "Čaj sa mlekom 15:30"

Bot: ✓ Čaj sa mlekom > 15:30
```

---

## Implementation Checklist

### 1. Database (`database.py`)
- [x] Nova funkcija `update_reminder(reminder_id, message_text, scheduled_time)`
- Omogućava update teksta, vremena, ili oba
- ~20 linija koda

### 2. Lokalizacija

#### `locales/en.po`
- [x] `edit_button` - "Edit"
- [x] `edit_prompt` - Prompt za edit sa instrukcijama
- [x] `edit_cancelled` - "Edit cancelled"
- [x] `reminder_updated` - "Reminder updated ✓"
- [x] `edit_parse_error` - Error poruka za nevažeći input
- [x] `edit_not_found` - Reminder nije pronađen

#### `locales/sr-lat.po`
- [x] Isti stringovi na srpskom

### 3. List Handler (`handlers/list.py`)

- [x] **Edit button u keyboard** - Dodaj `✏️ Edit #N` dugme pored Delete
- [x] **`edit_callback()`** - Handler za klik na Edit dugme
  - Prikazuje edit prompt sa ForceReply
  - Čuva `editing_reminder_id` u `context.user_data`
- [x] **`edit_message_handler()`** - Handler za user reply
  - Parsira input (tekst, vreme, ili oba)
  - Poziva `update_reminder()`
  - Šalje confirmation
- [x] **Registracija handlera** u `register_handlers()`

---

## Files Changed

| File | Changes | Lines |
|------|---------|-------|
| `database.py` | +`update_reminder()` | ~20 |
| `handlers/list.py` | +Edit button, +2 handlers | ~120 |
| `locales/en.po` | +6 strings | ~12 |
| `locales/sr-lat.po` | +6 strings | ~12 |
| **TOTAL** | | **~165** |

---

## Edge Cases Handled

1. **User reply-uje ali nije u edit modu** → Ignorisati (proveri `context.user_data`)
2. **Reminder obrisan pre nego što user reply-uje** → Prikaži "not found" poruku
3. **Recurring reminder** → Radi isto kao za regular (menja master reminder)
4. **Nevažeće vreme (u prošlosti)** → Time parser već to handluje
5. **User šalje command umesto reply-a** → Edit se otkazuje automatski

---

## Notes

- Recurring reminders se edituju direktno (menja se master reminder)
- Nema potrebe za ConversationHandler - koristi se ForceReply + user_data
- Edit timeout nije implementiran (user može reply-ovati bilo kada)

---

## Implementation Complete

**Date:** 2024-12-07

All checklist items have been implemented:

1. **database.py** - Added `update_reminder()` function (~55 lines)
2. **locales/en.po** - Added 6 translation strings
3. **locales/sr-lat.po** - Added 6 translation strings  
4. **handlers/list.py** - Added:
   - Edit button next to Delete button in keyboard
   - `edit_callback()` - handles edit button click, shows ForceReply prompt
   - `edit_message_handler()` - parses user reply and updates reminder
   - Registered both handlers in `register_handlers()`

**Total lines added:** ~175 lines

**Ready for testing!**
