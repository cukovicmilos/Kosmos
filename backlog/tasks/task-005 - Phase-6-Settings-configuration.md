---
id: task-005
title: 'Phase 6: Settings configuration'
status: In Progress
assignee: []
created_date: '2025-11-12 21:28'
updated_date: '2025-11-13 19:00'
labels:
  - phase-6
  - settings
  - i18n
  - timezone
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement comprehensive settings system allowing users to configure language (Serbian/English), time format (12h/24h), and timezone preferences.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Implement handlers/settings.py with /settings command and main menu
- [ ] #2 Create inline keyboard for Language, Time format, and Timezone options
- [ ] #3 Implement language setting: Srpski (sr-lat) / English (en)
- [ ] #4 Implement time format setting: AM/PM / 24h
- [ ] #5 Implement timezone setting with selector list of popular timezones
- [ ] #6 Add optional timezone search functionality
- [ ] #7 Update user preferences in database for all settings
- [ ] #8 Test all settings changes persist correctly
<!-- AC:END -->
