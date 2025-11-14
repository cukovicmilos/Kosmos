---
id: task-010
title: Postpone handling - kreiranje one-time instance
status: To Do
assignee: []
created_date: '2025-11-14 21:41'
labels:
  - postpone
  - recurring
  - handler
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ažurirati postpone.py da kreira novu one-time instancu kada korisnik postpone-uje recurring reminder.

Logika:
- Proveriti da li je reminder recurring (is_recurring=1)
- Ako jeste: kreirati NOVU one-time instancu (is_recurring=0) sa postponed vremenom
- Originalni recurring reminder ostaje nepromenjen i nastavlja po rasporedu
- Ako nije recurring: postojeća logika (update scheduled_time)

Fajl: handlers/postpone.py
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Postpone za recurring kreira novu instancu
- [ ] #2 Originalni recurring nastavlja normalno
- [ ] #3 Postpone za one-time radi kao pre
- [ ] #4 Poruka korisniku jasno pokazuje šta se desilo
<!-- AC:END -->
