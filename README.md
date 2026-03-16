# Kosmos - Telegram Reminder Bot

**Kosmos** is a Telegram bot that helps you remember important tasks by sending reminders at specified times. Supports natural language, recurring reminders, multiple languages, and timezones.

## Features

- Create reminders with natural language time expressions
- **🔁 Recurring reminders** - Daily, every X days, weekly (specific days), or monthly with optional duration
- Multiple language support (English, Serbian)
- Postpone reminders with quick actions (15m, 30m, 1h, 3h, 1d) or custom time
- List and manage all your upcoming reminders
- Persistent keyboard buttons for quick access (List, Recurring, Quick)
- Timezone support with accurate local time handling
- Customizable time format (12h/24h)

## Getting Started

### Option 1: Use Kosmos Directly

The fastest way - no setup required:

1. Open Telegram and search for **@kosmos_reminder_bot** or click [this link](https://t.me/kosmos_reminder_bot)
2. Press **Start**
3. Select your timezone
4. Start sending reminders! Just type something like: `Meeting tomorrow 10:00`

### Option 2: Self-Hosted

Want to run your own instance? See the [Self-Hosted Installation](#self-hosted-installation) section below.

## Usage

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
✓ Meeting > Mon 15.11.2025. 10:00
```

### Quick Access Buttons

After running `/start`, you'll see persistent buttons at the bottom of your chat:
- **📋 List** - View all your reminders
- **🔁 Recurring** - Create a recurring reminder
- **⚡ Quick** - Create a reminder from your most used texts

### Postponing Reminders

When a reminder arrives, you can postpone it with:
- Quick actions: 15 min, 30 min, 1h, 3h, 1 day
- Custom time: Choose "Drugo vreme" / "Custom time" and enter specific time (e.g., `19:00` or `tue 14:00`)

### Commands

- `/start` - Initialize the bot and show keyboard buttons
- `/list` - View all upcoming reminders
- `/recurring` - Create a recurring reminder (daily, weekly, monthly, etc.)
- `/quick` - Create a reminder from your most used texts
- `/settings` - Configure language, time format, and timezone
- `/help` - Get help and usage examples

### Recurring Reminders

Use `/recurring` command to create reminders that repeat automatically:

1. **Daily** - Every day at the same time
2. **Every X Days** - Repeat every N days
3. **Weekly (Specific Days)** - Repeat on selected weekdays
4. **Monthly** - Repeat on specific day of the month

**Duration:** Choose how long the reminder should repeat (7, 14, 30 days, custom, or forever). It automatically stops after the chosen period.

**Deleting from Notification:** When a recurring reminder fires, you can delete it directly from the notification using the delete button.

**Postponing:** When you postpone a recurring reminder, a new one-time reminder is created while the original continues on its schedule.

## Supported Time Formats

### Days
- `tomorrow` / `sutra`
- `dat` / `prekosutra` (day after tomorrow)
- Day of week: `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`
- Next week: `sl pon`, `sl uto`, `next mon`, `next tue`

### Time
- `21:00` - hours and minutes
- `8` - hour only (08:00)
- `7am` / `7AM` / `7 AM` - AM/PM format
- `2100` - military time

## Self-Hosted Installation

### 1. Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` command
3. Follow the instructions to set up your bot
4. Copy the **BOT_TOKEN** provided by BotFather

### 2. Clone and Install

```bash
git clone git@github.com:cukovicmilos/Kosmos.git
cd Kosmos

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
nano .env  # Add your BOT_TOKEN
```

### 4. Run

**Quick start:**
```bash
python main.py
```

**Production (systemd service):**

Create `/etc/systemd/system/kosmos-bot.service`:
```ini
[Unit]
Description=Kosmos Telegram Bot
After=network-online.target

[Service]
User=your-user
WorkingDirectory=/path/to/Kosmos
ExecStart=/path/to/Kosmos/venv/bin/python /path/to/Kosmos/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable kosmos-bot
sudo systemctl start kosmos-bot
```

## Troubleshooting

### Bot doesn't start
- Check that `BOT_TOKEN` is set correctly in `.env`
- Ensure virtual environment is activated
- Verify all dependencies are installed: `pip install -r requirements.txt`

### Reminders not sending
- Check that scheduler is running (you'll see "Reminder scheduler started" in logs)
- Check logs in `log/bot.log` for errors

### Time parsing issues
- Time must be at the end of the message
- If time has passed today (and no day specified), bot assumes tomorrow
- Weekdays always mean next occurrence

### Keyboard buttons not showing
- Send `/start` command to initialize persistent keyboard
- Restart Telegram app if buttons don't appear

## License

MIT License

## Author

Milos Cukovic ([@cukovicmilos](https://github.com/cukovicmilos))
