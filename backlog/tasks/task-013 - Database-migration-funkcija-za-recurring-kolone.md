---
id: task-013
title: Database migration funkcija za recurring kolone
status: Done
assignee: []
created_date: '2025-11-14 21:41'
updated_date: '2025-11-15 18:38'
labels:
  - database
  - migration
  - recurring
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implementirati SQLite migration logiku koja automatski dodaje nove kolone ako ne postoje.

Provera i dodavanje:
- Proveri da li kolone postoje (PRAGMA table_info)
- Ako ne postoje, ALTER TABLE ADD COLUMN za svaku
- Pozvati migration na startup (init_database)

Fajl: database.py
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Migration funkcija proverava postojanje kolona
- [x] #2 ALTER TABLE komande dodaju kolone
- [x] #3 Migracija se izvršava automatski pri startu
- [x] #4 Ne crashuje ako kolone već postoje
- [x] #5 Testirana na production bazi
<!-- AC:END -->
