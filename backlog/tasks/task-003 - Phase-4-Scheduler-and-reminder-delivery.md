---
id: task-003
title: 'Phase 4: Scheduler and reminder delivery'
status: To Do
assignee: []
created_date: '2025-11-12 21:28'
labels:
  - phase-4
  - scheduler
  - postpone
  - apscheduler
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement background scheduler using APScheduler to check and send reminders at the correct time. Include postpone functionality with predefined and custom time options.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Implement scheduler.py with APScheduler configuration
- [ ] #2 Create background task to check and send pending reminders
- [ ] #3 Format reminder messages with 🔔 emoji and reminder text
- [ ] #4 Add inline keyboard with postpone options: 15m, 30m, 1h, 3h, 1d, Custom time
- [ ] #5 Implement handlers/postpone.py with callback handlers for all postpone options
- [ ] #6 Implement custom time flow where user enters new time after clicking Custom time
- [ ] #7 Update reminder status in database after sending
- [ ] #8 Test scheduler runs correctly and sends reminders on time
<!-- AC:END -->
