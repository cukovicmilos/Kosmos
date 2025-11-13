---
id: task-004
title: 'Phase 5: List and delete reminders'
status: In Progress
assignee: []
created_date: '2025-11-12 21:28'
updated_date: '2025-11-13 18:40'
labels:
  - phase-5
  - list-reminders
  - delete-reminders
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement reminder listing functionality with the ability to view all upcoming reminders and delete individual reminders using inline keyboard buttons.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Implement handlers/list.py with /list command
- [ ] #2 Fetch all future reminders from database sorted by scheduled_time
- [ ] #3 Format message showing each reminder with date, time, and [Delete] button
- [ ] #4 Implement callback handler for delete action
- [ ] #5 Update reminder status to 'cancelled' in database when deleted
- [ ] #6 Show confirmation message: 'Podsetnik obrisan ✓' / 'Reminder deleted ✓'
- [ ] #7 Auto-refresh list after deletion
- [ ] #8 Test listing and deletion flow
<!-- AC:END -->
