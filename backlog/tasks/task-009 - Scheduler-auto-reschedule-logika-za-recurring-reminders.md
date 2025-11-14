---
id: task-009
title: Scheduler auto-reschedule logika za recurring reminders
status: To Do
assignee: []
created_date: '2025-11-14 21:41'
labels:
  - scheduler
  - recurring
  - core-logic
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ažurirati scheduler.py da automatski reschedule-uje recurring remindere nakon slanja.

Umesto status='sent', izračunati sledeći occurrence i ažurirati scheduled_time:
- Daily: +1 dan
- Interval: +N dana
- Weekly: sledeći dan iz liste (npr. ako je pon/sre/pet, posle pon ide sre)
- Monthly: sledeći mesec, isti dan

Status ostaje 'pending' za recurring, tako da se ponovo trigggeruje.

Fajl: scheduler.py
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Funkcija calculate_next_occurrence() implementirana
- [ ] #2 Scheduler proverava is_recurring flag
- [ ] #3 Recurring reminders se reschedule-uju umesto marking sent
- [ ] #4 One-time reminders i dalje rade normalno (status=sent)
- [ ] #5 Testiran svaki tip ponavljanja
<!-- AC:END -->
