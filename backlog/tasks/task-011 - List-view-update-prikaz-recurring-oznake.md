---
id: task-011
title: List view update - prikaz recurring oznake
status: Done
assignee: []
created_date: '2025-11-14 21:41'
updated_date: '2025-11-15 19:03'
labels:
  - list
  - ui
  - recurring
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ažurirati handlers/list.py da prikazuje recurring remindere sa 🔁 oznakom i opisom ponavljanja.

Format:
- 🔁 Sastanak sa timom (svaki ponedeljak u 10:00)
- 🔁 Vežbanje (svaki dan u 07:00)
- 🔁 Plaćanje (svakog 15. u mesecu u 12:00)

Prikazati i sledeći scheduled occurrence.

Fajl: handlers/list.py
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Recurring reminders imaju 🔁 oznaku
- [x] #2 Prikazan opis ponavljanja na srpskom i engleskom
- [x] #3 Prikazan sledeći occurrence
- [x] #4 One-time reminders prikazani normalno
<!-- AC:END -->
