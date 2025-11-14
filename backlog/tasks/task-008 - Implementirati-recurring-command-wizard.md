---
id: task-008
title: Implementirati /recurring command wizard
status: To Do
assignee: []
created_date: '2025-11-14 21:40'
labels:
  - handler
  - recurring
  - conversation
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Kreirati ConversationHandler za /recurring komandu sa koracima:
1. Unos poruke podsetnika
2. Izbor tipa ponavljanja (Daily/Every X days/Weekly/Monthly) - inline buttons
3. Konfiguracija specifična za tip:
   - Every X days: unos broja
   - Weekly: multi-select dani u nedelji
   - Monthly: izbor dana u mesecu (1-31)
4. Unos vremena (HH:MM)
5. Potvrda i kreiranje u bazi

Kreirati novi fajl: handlers/recurring.py
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ConversationHandler implementiran sa svim koracima
- [ ] #2 Svi tipovi ponavljanja podržani (daily, interval, weekly, monthly)
- [ ] #3 Validacija inputa (broj dana, vreme, dani)
- [ ] #4 Potvrda sa pregledom pre kreiranja
- [ ] #5 Registrovan handler u main.py
<!-- AC:END -->
