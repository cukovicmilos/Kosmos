---
id: task-012
title: Delete confirmation za recurring reminders
status: To Do
assignee: []
created_date: '2025-11-14 21:41'
labels:
  - delete
  - ui
  - recurring
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Dodati potvrdu prilikom brisanja recurring reminder-a.

Kada korisnik klikne delete na recurring reminder:
1. Prikazati: "Ovo je ponavljajući podsetnik. Želiš li da ga trajno obrišeš?"
2. Buttons: [Obriši zauvek] [Otkaži]
3. Ako potvrdi: status='cancelled'

Fajlovi: handlers/list.py (i možda novi callback)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Confirmation dialog za recurring reminders
- [ ] #2 One-time reminders se brišu direktno kao pre
- [ ] #3 Cancel dugme funkcioniše
- [ ] #4 Status se postavlja na 'cancelled'
<!-- AC:END -->
