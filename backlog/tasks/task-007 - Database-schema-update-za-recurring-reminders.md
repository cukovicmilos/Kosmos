---
id: task-007
title: Database schema update za recurring reminders
status: Done
assignee: []
created_date: '2025-11-14 21:40'
updated_date: '2025-11-15 18:38'
labels:
  - database
  - schema
  - recurring
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Dodati nove kolone u reminders tabelu za podršku recurring functionality.

Nove kolone:
- is_recurring BOOLEAN DEFAULT 0
- recurrence_type TEXT (NULL, 'daily', 'interval', 'weekly', 'monthly')
- recurrence_interval INTEGER (za "svaki X dan")
- recurrence_days TEXT (JSON array za dane: ["monday", "wednesday"])
- recurrence_day_of_month INTEGER (za mesečno: 1-31)

Fajl: database.py
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Nove kolone dodate u CREATE TABLE statement
- [x] #2 Migration funkcija kreira kolone ako ne postoje
- [x] #3 Testirana migracija na postojećoj bazi
<!-- AC:END -->
