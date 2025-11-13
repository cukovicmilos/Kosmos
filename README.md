# Kosmos - Telegram Reminder Bot

**Kosmos** is a Telegram bot designed to help you remember important tasks by sending you reminders at specified times.

## Features

- Create reminders with natural language time expressions
- Multiple language support (English, Serbian)
- Postpone reminders with quick actions (15m, 30m, 1h, 3h, 1d) or custom time
- List and manage all your upcoming reminders
- Persistent keyboard buttons for quick access (List, Settings)
- Smart reminder confirmations showing scheduled time
- Timezone support with accurate local time handling
- Customizable time format (12h/24h)

## Quick Start

### 1. Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` command
3. Follow the instructions to set up your bot
4. Copy the **BOT_TOKEN** provided by BotFather

### 2. Installation

```bash
# Clone the repository
git clone git@github.com:cukovicmilos/Kosmos.git
cd Kosmos/kosmos

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# or
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your BOT_TOKEN
nano .env  # or use your preferred editor
```

### 4. Run the Bot

```bash
python main.py
```

## Usage Examples

### Creating a Reminder

Simply send a message with your reminder text and time:

```
Take fishing rod to the lake tomorrow 16:00
Meeting mon 10:00
Coffee 14:30
```

You'll receive a confirmation showing when the reminder is scheduled:
```
✓ Coffee > 14:30
✓ Meeting > 15.11.2025. 10:00
```

### Quick Access Buttons

After running `/start`, you'll see persistent buttons at the bottom of your chat:
- **📋 List** - Quickly view all your reminders
- **⚙️ Settings** - Access settings menu

### Postponing Reminders

When a reminder arrives, you can postpone it with:
- Quick actions: 15 min, 30 min, 1h, 3h, 1 day
- Custom time: Choose "Drugo vreme" / "Custom time" and enter specific time (e.g., `19:00` or `tue 14:00`)

After postponing, you'll see:
```
⏰ Coffee > 15:30  (if today)
⏰ Meeting > 16.11.2025. 10:00  (if another day)
```

### Commands

- `/start` - Initialize the bot and show keyboard buttons
- `/list` - View all upcoming reminders
- `/settings` - Configure language, time format, and timezone
- `/help` - Get help and usage examples

## Supported Time Formats

### Days
- `tomorrow` / `sutra`
- `dat` / `prekosutra` (day after tomorrow)
- Day of week: `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`

### Time
- `21:00` - hours and minutes
- `8` - hour only (08:00)
- `7am` / `7AM` / `7 AM` - AM/PM format
- `2100` - military time

## Project Structure

See [plan.md](../plan.md) for detailed project documentation and implementation plan.

## Development Status

✅ **Completed** - Version 1.0

All major features implemented:
- ✅ Bot initialization with timezone selection
- ✅ Natural language time parsing (SR/EN)
- ✅ Scheduler and reminder delivery with accurate timezone handling
- ✅ Postpone functionality (quick actions + custom time)
- ✅ List and delete reminders (with sequential numbering)
- ✅ Settings configuration (language, time format, timezone)
- ✅ Persistent keyboard buttons for quick access
- ✅ Smart reminder confirmations with scheduled time display

## Troubleshooting

### Bot doesn't start
- Check that `BOT_TOKEN` is set correctly in `.env`
- Ensure virtual environment is activated
- Verify all dependencies are installed: `pip install -r requirements.txt`

### Reminders not sending
- Check that scheduler is running (you'll see "Reminder scheduler started" in logs)
- Verify database has pending reminders: `sqlite3 kosmos.db "SELECT * FROM reminders WHERE status='pending';"`
- Check logs in `log/app.log` for errors

### Time parsing issues
- Time must be at the end of the message
- If time has passed today (and no day specified), bot assumes tomorrow
- Weekdays always mean next occurrence

### Keyboard buttons not showing
- Send `/start` command to initialize persistent keyboard
- Restart Telegram app if buttons don't appear
- Make sure you have the latest version of Telegram

### Postpone custom time not working
- Make sure to enter time in correct format: `19:00` or `tue 14:00`
- Time must be valid (0-23 hours, 0-59 minutes)
- If entering a day, use supported day names (mon, tue, tomorrow, etc.)

### Database issues
- Delete `kosmos.db` and restart bot to recreate database
- Check file permissions on database file

## License

MIT License

## Author

Milos Cukovic (@cukovicmilos)
