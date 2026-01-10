# Kosmos Telegram Bot State Machines

This document describes the state machines for the main components of the Kosmos Telegram Bot system.

## 1. Main Application State Machine

```mermaid
stateDiagram-v2
    [*] --> Initialization
    Initialization --> DatabaseInit: Start main()
    DatabaseInit --> HandlerRegistration: init_database()
    HandlerRegistration --> PostInit: register_handlers()
    PostInit --> BotCommandsSet: post_init()
    BotCommandsSet --> SchedulerStarted: start_scheduler()
    SchedulerStarted --> PollingStarted: application.run_polling()
    PollingStarted --> Running: Bot active
    Running --> Error: Exception
    Error --> [*]: Shutdown
    Running --> [*]: Shutdown
```

**States:**
- **Initialization**: Bot startup process begins
- **DatabaseInit**: Database connection and schema setup
- **HandlerRegistration**: Registering command and message handlers
- **PostInit**: Setting bot commands and updating descriptions
- **BotCommandsSet**: Telegram UI commands configured
- **SchedulerStarted**: Background reminder scheduler running
- **PollingStarted**: Telegram update polling active
- **Running**: Bot fully operational
- **Error**: Critical error state

## 2. Reminder Creation State Machine

```mermaid
stateDiagram-v2
    [*] --> ReceiveMessage
    ReceiveMessage --> ValidateUser: Check user exists
    ValidateUser --> ParseMessage: parse_reminder()
    ParseMessage --> ValidateTime: Check not in past
    ValidateTime --> CreateReminder: create_reminder()
    CreateReminder --> SendConfirmation: Success
    SendConfirmation --> [*]: Confirmation sent

    ValidateUser --> Error: User not found
    ParseMessage --> SendError: Parse failed
    ValidateTime --> SendError: Time in past
    CreateReminder --> SendError: DB error
    SendConfirmation --> QueueConfirmation: Network error
    QueueConfirmation --> [*]: Queued for retry

    Error --> [*]
    SendError --> [*]
```

**States:**
- **ReceiveMessage**: Text message received from user
- **ValidateUser**: Verify user exists in database
- **ParseMessage**: Extract reminder text and time using time parser
- **ValidateTime**: Ensure scheduled time is in the future
- **CreateReminder**: Store reminder in database
- **SendConfirmation**: Send success message to user
- **QueueConfirmation**: Queue confirmation for retry on network error

## 3. Recurring Reminder Creation State Machine

```mermaid
stateDiagram-v2
    [*] --> MESSAGE
    MESSAGE --> RECURRENCE_TYPE: Valid message text
    RECURRENCE_TYPE --> TIME_INPUT: Daily selected
    RECURRENCE_TYPE --> INTERVAL_DAYS: Interval selected
    RECURRENCE_TYPE --> WEEKLY_DAYS: Weekly selected
    RECURRENCE_TYPE --> MONTHLY_DAY: Monthly selected

    INTERVAL_DAYS --> TIME_INPUT: Valid interval (1-365)
    MONTHLY_DAY --> TIME_INPUT: Valid day (1-31)

    WEEKLY_DAYS --> SelectDays: Initial display
    SelectDays --> SelectDays: Day toggle
    SelectDays --> TIME_INPUT: Done clicked + days selected

    TIME_INPUT --> CONFIRM: Valid time parsed
    CONFIRM --> [*]: Yes - create reminder
    CONFIRM --> [*]: No - cancel

    MESSAGE --> MESSAGE: Invalid message
    INTERVAL_DAYS --> INTERVAL_DAYS: Invalid interval
    MONTHLY_DAY --> MONTHLY_DAY: Invalid day
    TIME_INPUT --> TIME_INPUT: Invalid time
    SelectDays --> SelectDays: Done with no days
    WEEKLY_DAYS --> [*]: Cancel command
```

**States:**
- **MESSAGE**: Waiting for reminder text input
- **RECURRENCE_TYPE**: Selecting recurrence pattern (daily/interval/weekly/monthly)
- **INTERVAL_DAYS**: Input number of days for interval recurrence
- **WEEKLY_DAYS**: Select which days of week for recurrence
- **MONTHLY_DAY**: Input day of month for monthly recurrence
- **TIME_INPUT**: Input time for the recurring reminder
- **CONFIRM**: Show summary and confirm creation

**Transitions:**
- Each input state loops back on invalid input
- Cancel command can be issued from any state
- Confirmation state allows final yes/no decision

## 4. Settings Configuration State Machine

```mermaid
stateDiagram-v2
    [*] --> MainMenu
    MainMenu --> LanguageMenu: Language button
    MainMenu --> TimeFormatMenu: Time Format button
    MainMenu --> TimezoneMenu: Timezone button

    LanguageMenu --> SetLanguage: Language selected
    TimeFormatMenu --> SetTimeFormat: Format selected
    TimezoneMenu --> SetTimezone: Timezone selected

    SetLanguage --> MainMenu: Success
    SetTimeFormat --> MainMenu: Success
    SetTimezone --> MainMenu: Success

    MainMenu --> [*]: Back/Cancel
    LanguageMenu --> MainMenu: Back
    TimeFormatMenu --> MainMenu: Back
    TimezoneMenu --> MainMenu: Back

    SetLanguage --> Error: DB error
    SetTimeFormat --> Error: DB error
    SetTimezone --> Error: DB error
    Error --> MainMenu: Retry
```

**States:**
- **MainMenu**: Settings overview with current preferences
- **LanguageMenu**: Language selection (English/Serbian)
- **TimeFormatMenu**: Time format selection (12h/24h)
- **TimezoneMenu**: Timezone selection from predefined list
- **SetLanguage/TimeFormat/Timezone**: Database update operations
- **Error**: Database operation failure

## 5. List/Delete/Edit Operations State Machine

```mermaid
stateDiagram-v2
    [*] --> ListReminders
    ListReminders --> DeleteConfirm: Delete clicked
    ListReminders --> EditPrompt: Edit clicked (AWAITING_EDIT_INPUT)

    DeleteConfirm --> DeleteOneTime: One-time reminder
    DeleteConfirm --> DeleteRecurring: Recurring reminder

    DeleteOneTime --> ListUpdated: Delete from DB
    DeleteRecurring --> ConfirmDialog: Show confirmation
    ConfirmDialog --> DeleteRecurring: Yes
    ConfirmDialog --> ListReminders: No/Cancel

    EditPrompt --> ParseEditInput: User replies
    EditPrompt --> [*]: /cancel command
    ParseEditInput --> UpdateReminder: Parse successful
    UpdateReminder --> SendEditConfirm: DB update success

    ListUpdated --> ListReminders: Refresh display
    SendEditConfirm --> [*]: Edit complete (ConversationHandler.END)

    DeleteConfirm --> Error: Reminder not found
    EditPrompt --> Error: Reminder not found
    ParseEditInput --> ParseEditInput: Invalid time input (stay in AWAITING_EDIT_INPUT)
    UpdateReminder --> Error: DB error

    Error --> ListReminders: Show error
```

**States:**
- **ListReminders**: Display all pending reminders with action buttons
- **DeleteConfirm**: Initial delete action, check if recurring
- **DeleteOneTime**: Immediate deletion of one-time reminder
- **DeleteRecurring**: Show confirmation dialog for recurring reminders
- **ConfirmDialog**: User confirms/cancels recurring reminder deletion
- **EditPrompt**: Show edit prompt with ForceReply
- **ParseEditInput**: Parse user's edit input (text/time/both)
- **UpdateReminder**: Update reminder in database
- **ListUpdated**: Refresh the reminder list display

**Edit Flow Implementation Details:**
The edit operation uses ConversationHandler with the following state:
- `AWAITING_EDIT_INPUT` (0): Waiting for user's new text/time input

Context data stored during edit:
- `editing_reminder_id`: ID of reminder being edited
- `edit_prompt_message_id`: Message ID of the ForceReply prompt
- `edit_prompt_chat_id`: Chat ID where prompt was sent

Helper function `_cleanup_edit_state()` handles cleanup of context data and deletion of the ForceReply prompt message.

Parse strategies:
1. Time-only input (e.g., "15:00", "tue 10:00") → Updates only time
2. Text + time (e.g., "New text 15:00") → Updates both
3. Text-only (no recognizable time) → Updates only text

Fallback: User can cancel edit with /cancel command

## 6. Reminder Execution State Machine (Scheduler)

```mermaid
stateDiagram-v2
    [*] --> CheckPending
    CheckPending --> SendReminder: Reminders found
    CheckPending --> [*]: No reminders

    SendReminder --> NetworkSuccess: Message sent
    SendReminder --> NetworkError: Timeout/Failure

    NetworkSuccess --> CheckRecurring: Reminder sent
    NetworkError --> [*]: Retry next cycle

    CheckRecurring --> RescheduleRecurring: Is recurring
    CheckRecurring --> MarkSent: One-time reminder

    RescheduleRecurring --> CalculateNext: Use recurrence rules
    CalculateNext --> UpdateTime: Next occurrence calculated
    UpdateTime --> [*]: Reminder rescheduled

    MarkSent --> [*]: Status updated to 'sent'
```

**States:**
- **CheckPending**: Query database for due reminders (every minute)
- **SendReminder**: Send notification to user with postpone options
- **NetworkSuccess**: Message delivered successfully
- **NetworkError**: Network timeout or delivery failure
- **CheckRecurring**: Determine if reminder is recurring or one-time
- **RescheduleRecurring**: Handle recurring reminder rescheduling
- **CalculateNext**: Compute next occurrence based on recurrence pattern
- **UpdateTime**: Update reminder's scheduled time in database
- **MarkSent**: Mark one-time reminder as completed

**Recurrence Types:**
- **Daily**: Add 1 day to current time
- **Interval**: Add N days (configurable interval)
- **Weekly**: Find next occurrence from selected weekdays
- **Monthly**: Same day number next month (with overflow handling)

**Timezone Handling:**
Reminders are stored as naive datetime in the user's local timezone. When checking for due reminders:
1. Fetch all pending reminders with user's timezone (via JOIN)
2. For each reminder, get current time in user's timezone
3. Compare scheduled_time with current time in user's timezone
4. Only include reminders where scheduled_time <= now (in user's TZ)

This ensures reminders fire at the correct time regardless of server timezone.

## 7. Postpone Reminder State Machine

```mermaid
stateDiagram-v2
    [*] --> PostponeClicked
    PostponeClicked --> CalculateDelay: Parse button data
    CalculateDelay --> UpdateTime: Add delay to current time
    UpdateTime --> [*]: Reminder rescheduled

    PostponeClicked --> CustomTimePrompt: "Drugo vreme" clicked
    CustomTimePrompt --> ParseCustomTime: User input received
    ParseCustomTime --> UpdateTime: Valid time parsed
    ParseCustomTime --> CustomTimePrompt: Invalid time

    UpdateTime --> [*]
```

**States:**
- **PostponeClicked**: User clicks postpone button in reminder notification
- **CalculateDelay**: Parse button callback data (15m, 30m, 1h, 3h, 1d)
- **UpdateTime**: Update reminder's scheduled time in database
- **CustomTimePrompt**: Show input field for custom postpone time
- **ParseCustomTime**: Parse user's custom time input

## 8. Message Queue State Machine

```mermaid
stateDiagram-v2
    [*] --> QueueMessage
    QueueMessage --> StoreInDB: Network error occurred
    StoreInDB --> [*]: Message queued

    [*] --> ProcessPending: Every 30 seconds
    ProcessPending --> SendQueuedMessage: Messages found
    SendQueuedMessage --> NetworkRetry: Attempt send
    NetworkRetry --> RemoveFromQueue: Success
    NetworkRetry --> KeepInQueue: Failed - retry later

    RemoveFromQueue --> [*]: Message sent
    KeepInQueue --> [*]: Will retry later

    [*] --> CleanupOld: Daily cleanup
    CleanupOld --> DeleteExpired: Messages older than 7 days
    DeleteExpired --> [*]: Old messages removed
```

**States:**
- **QueueMessage**: Original send operation failed due to network error
- **StoreInDB**: Store failed message in message_queue table
- **ProcessPending**: Background job checks for queued messages (every 30 seconds)
- **SendQueuedMessage**: Attempt to send queued message
- **NetworkRetry**: Retry sending over network
- **RemoveFromQueue**: Delete successfully sent message
- **KeepInQueue**: Keep failed message for next retry attempt
- **CleanupOld**: Remove messages older than retention period (max 5 retries)

**Exponential Backoff:**
Messages are retried with increasing delays to prevent API hammering:
- Retry 0: 30 seconds
- Retry 1: 60 seconds (1 minute)
- Retry 2: 120 seconds (2 minutes)
- Retry 3: 300 seconds (5 minutes)
- Retry 4: 600 seconds (10 minutes)

After 5 failed retries, messages are cleaned up during daily cleanup.

## 9. Network Monitoring State Machine

```mermaid
stateDiagram-v2
    [*] --> NetworkOperation
    NetworkOperation --> Success: Operation completed
    NetworkOperation --> Timeout: Operation timed out

    Success --> RecordSuccess: Update success counter
    Timeout --> RecordTimeout: Log timeout event

    RecordSuccess --> [*]: Stats updated
    RecordTimeout --> [*]: Error logged

    [*] --> GenerateReport: On /netstats command
    GenerateReport --> DisplayStats: Show network statistics
    DisplayStats --> [*]: Report shown
```

**States:**
- **NetworkOperation**: Any network-dependent operation (send message, etc.)
- **Success**: Operation completed without error
- **Timeout**: Operation failed due to timeout
- **RecordSuccess**: Increment success counter in database
- **RecordTimeout**: Log timeout details for analysis
- **GenerateReport**: User requests network statistics
- **DisplayStats**: Show success/failure rates and recent issues

## 10. Bot Statistics State Machine

```mermaid
stateDiagram-v2
    [*] --> UpdateShortDesc: Every 6 hours
    [*] --> UpdateFullDesc: Daily

    UpdateShortDesc --> QueryActiveUsers: Get user count
    UpdateFullDesc --> QueryStats: Get comprehensive stats

    QueryActiveUsers --> UpdateBotProfile: Set short description
    QueryStats --> UpdateBotProfile: Set full description

    UpdateBotProfile --> [*]: Profile updated

    UpdateShortDesc --> Error: API failure
    UpdateFullDesc --> Error: API failure
    QueryActiveUsers --> Error: DB failure
    QueryStats --> Error: DB failure

    Error --> [*]: Log error, skip update
```

**States:**
- **UpdateShortDesc**: Periodic update of bot's short description
- **UpdateFullDesc**: Daily update of bot's full description
- **QueryActiveUsers**: Count active users from database
- **QueryStats**: Gather comprehensive bot usage statistics
- **UpdateBotProfile**: Call Telegram API to update bot profile
- **Error**: Handle API or database failures gracefully</content>
<parameter name="filePath">/var/www/html/kosmos/State_Machine.md