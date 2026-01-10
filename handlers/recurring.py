"""
Recurring reminder handler for Kosmos Telegram Bot.
Handles /recurring command with conversation flow for creating recurring reminders.
"""

import json
import logging
from datetime import datetime, time
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from database import create_reminder, get_user
from i18n import get_text
from parsers.time_parser import parse_time

logger = logging.getLogger(__name__)

# Conversation states
(
    MESSAGE,
    RECURRENCE_TYPE,
    INTERVAL_DAYS,
    WEEKLY_DAYS,
    MONTHLY_DAY,
    TIME_INPUT,
    CONFIRM
) = range(7)


async def recurring_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start the recurring reminder creation conversation.
    """
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("Molim te prvo pokreni bota sa /start")
        return ConversationHandler.END

    user_lang = user.get('language', 'en')

    # Initialize conversation data
    context.user_data['recurring'] = {}

    await update.message.reply_text(
        "📋 *Kreiranje ponavljajućeg podsetnika*\n\n"
        "Unesi tekst podsetnika:",
        parse_mode="Markdown"
    )

    return MESSAGE


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle reminder message text input.
    """
    message_text = update.message.text.strip()

    if not message_text:
        await update.message.reply_text("Poruka ne može biti prazna. Pokušaj ponovo:")
        return MESSAGE

    # Save message to context
    context.user_data['recurring']['message'] = message_text

    # Show recurrence type options
    keyboard = [
        [
            InlineKeyboardButton("📅 Svaki dan", callback_data="rec_type_daily"),
            InlineKeyboardButton("🔢 Svaki X dan", callback_data="rec_type_interval"),
        ],
        [
            InlineKeyboardButton("📆 Dani u nedelji", callback_data="rec_type_weekly"),
            InlineKeyboardButton("📌 Mesečno", callback_data="rec_type_monthly"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ Podsetnik: *{message_text}*\n\n"
        "Izaberi tip ponavljanja:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    return RECURRENCE_TYPE


async def handle_recurrence_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle recurrence type selection.
    """
    query = update.callback_query
    await query.answer()

    rec_type = query.data.replace("rec_type_", "")
    context.user_data['recurring']['type'] = rec_type

    if rec_type == "daily":
        # Go directly to time input
        await query.edit_message_text(
            "✅ Tip: *Svaki dan*\n\n"
            "Unesi vreme (npr. 09:00, 14:30):",
            parse_mode="Markdown"
        )
        return TIME_INPUT

    elif rec_type == "interval":
        # Ask for number of days
        await query.edit_message_text(
            "✅ Tip: *Svaki X dan*\n\n"
            "Unesi broj dana (npr. 3 za svaka 3 dana):",
            parse_mode="Markdown"
        )
        return INTERVAL_DAYS

    elif rec_type == "weekly":
        # Show day selection
        context.user_data['recurring']['selected_days'] = []
        keyboard = create_weekday_keyboard([])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "✅ Tip: *Dani u nedelji*\n\n"
            "Izaberi dane (možeš više):",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return WEEKLY_DAYS

    elif rec_type == "monthly":
        # Ask for day of month
        await query.edit_message_text(
            "✅ Tip: *Mesečno*\n\n"
            "Unesi dan u mesecu (1-31):",
            parse_mode="Markdown"
        )
        return MONTHLY_DAY


def create_weekday_keyboard(selected_days):
    """
    Create inline keyboard for weekday selection with checkmarks.
    """
    days = [
        ("Pon", "monday"),
        ("Uto", "tuesday"),
        ("Sre", "wednesday"),
        ("Čet", "thursday"),
        ("Pet", "friday"),
        ("Sub", "saturday"),
        ("Ned", "sunday")
    ]

    keyboard = []
    row = []

    for label, day in days:
        checkmark = "✓ " if day in selected_days else ""
        button = InlineKeyboardButton(
            f"{checkmark}{label}",
            callback_data=f"weekday_{day}"
        )
        row.append(button)

        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    # Add "Done" button
    keyboard.append([InlineKeyboardButton("✅ Gotovo", callback_data="weekday_done")])

    return keyboard


async def handle_weekday_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle weekday toggle selection.
    """
    query = update.callback_query
    await query.answer()

    if query.data == "weekday_done":
        selected_days = context.user_data['recurring'].get('selected_days', [])

        if not selected_days:
            await query.answer("Molim te izaberi bar jedan dan!", show_alert=True)
            return WEEKLY_DAYS

        # Save and proceed to time input
        await query.edit_message_text(
            f"✅ Dani: *{', '.join([d.capitalize() for d in selected_days])}*\n\n"
            "Unesi vreme (npr. 09:00, 14:30):",
            parse_mode="Markdown"
        )
        return TIME_INPUT

    # Toggle day selection
    day = query.data.replace("weekday_", "")
    selected_days = context.user_data['recurring'].get('selected_days', [])

    if day in selected_days:
        selected_days.remove(day)
    else:
        selected_days.append(day)

    context.user_data['recurring']['selected_days'] = selected_days

    # Update keyboard
    keyboard = create_weekday_keyboard(selected_days)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_reply_markup(reply_markup=reply_markup)

    return WEEKLY_DAYS


async def handle_interval_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle interval days input.
    """
    try:
        days = int(update.message.text.strip())

        if days < 1 or days > 365:
            await update.message.reply_text(
                "Broj dana mora biti između 1 i 365. Pokušaj ponovo:"
            )
            return INTERVAL_DAYS

        context.user_data['recurring']['interval'] = days

        await update.message.reply_text(
            f"✅ Interval: *Svaka {days} dana*\n\n"
            "Unesi vreme (npr. 09:00, 14:30):",
            parse_mode="Markdown"
        )
        return TIME_INPUT

    except ValueError:
        await update.message.reply_text(
            "Molim te unesi validan broj. Pokušaj ponovo:"
        )
        return INTERVAL_DAYS


async def handle_monthly_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle monthly day input.
    """
    try:
        day = int(update.message.text.strip())

        if day < 1 or day > 31:
            await update.message.reply_text(
                "Dan mora biti između 1 i 31. Pokušaj ponovo:"
            )
            return MONTHLY_DAY

        context.user_data['recurring']['day_of_month'] = day

        await update.message.reply_text(
            f"✅ Dan u mesecu: *{day}.*\n\n"
            "Unesi vreme (npr. 09:00, 14:30):",
            parse_mode="Markdown"
        )
        return TIME_INPUT

    except ValueError:
        await update.message.reply_text(
            "Molim te unesi validan broj. Pokušaj ponovo:"
        )
        return MONTHLY_DAY


async def handle_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle time input and show confirmation.
    """
    time_str = update.message.text.strip()
    user_id = update.effective_user.id
    user = get_user(user_id)

    # Parse time
    parsed_time = parse_time(time_str)

    if not parsed_time:
        await update.message.reply_text(
            "❌ Neispravan format vremena. Pokušaj ponovo (npr. 09:00, 14:30):"
        )
        return TIME_INPUT

    context.user_data['recurring']['time'] = parsed_time

    # Build summary
    rec_data = context.user_data['recurring']
    rec_type = rec_data['type']

    summary_lines = [
        "📋 *Pregled ponavljajućeg podsetnika*\n",
        f"💬 Poruka: {rec_data['message']}",
        f"🕐 Vreme: {parsed_time.strftime('%H:%M')}",
    ]

    if rec_type == "daily":
        summary_lines.append("🔁 Ponavljanje: Svaki dan")

    elif rec_type == "interval":
        days = rec_data['interval']
        summary_lines.append(f"🔁 Ponavljanje: Svaka {days} dana")

    elif rec_type == "weekly":
        days_str = ', '.join([d.capitalize() for d in rec_data['selected_days']])
        summary_lines.append(f"🔁 Ponavljanje: {days_str}")

    elif rec_type == "monthly":
        day = rec_data['day_of_month']
        summary_lines.append(f"🔁 Ponavljanje: Svakog {day}. u mesecu")

    summary = '\n'.join(summary_lines)

    # Confirmation buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Potvrdi", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Otkaži", callback_data="confirm_no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    return CONFIRM


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle confirmation and create the recurring reminder.
    """
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_no":
        await query.edit_message_text("❌ Otkazano. Koristi /recurring da počneš ponovo.")
        context.user_data.pop('recurring', None)
        return ConversationHandler.END

    # Create recurring reminder
    user_id = update.effective_user.id
    user = get_user(user_id)
    user_tz = user.get('timezone', 'Europe/Belgrade')

    rec_data = context.user_data['recurring']
    rec_type = rec_data['type']
    message = rec_data['message']
    reminder_time = rec_data['time']

    # Calculate first occurrence (using user's timezone)
    from datetime import timedelta
    try:
        tz = pytz.timezone(user_tz)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone("Europe/Belgrade")
    now = datetime.now(tz).replace(tzinfo=None)  # Naive datetime in user's timezone

    # For interval type, first occurrence is X days from now
    if rec_type == "interval":
        interval = rec_data['interval']
        # Check if today's time is still valid, otherwise add interval days
        base_time = datetime.combine(now.date(), reminder_time)
        if base_time <= now:
            # Today's time has passed, schedule for interval days from tomorrow
            scheduled_datetime = base_time + timedelta(days=interval)
        else:
            # Today's time is still valid, but for interval we start from interval days
            scheduled_datetime = base_time + timedelta(days=interval)
    else:
        # For other types: today or tomorrow based on time
        scheduled_datetime = datetime.combine(now.date(), reminder_time)
        # If time has passed today, schedule for tomorrow
        if scheduled_datetime <= now:
            scheduled_datetime += timedelta(days=1)

    # Prepare recurrence parameters
    recurrence_interval = None
    recurrence_days = None
    recurrence_day_of_month = None

    if rec_type == "interval":
        recurrence_interval = rec_data['interval']
    elif rec_type == "weekly":
        recurrence_days = json.dumps(rec_data['selected_days'])
    elif rec_type == "monthly":
        recurrence_day_of_month = rec_data['day_of_month']

    # Create reminder
    reminder_id = create_reminder(
        user_id=user_id,
        message_text=message,
        scheduled_time=scheduled_datetime,
        is_recurring=True,
        recurrence_type=rec_type,
        recurrence_interval=recurrence_interval,
        recurrence_days=recurrence_days,
        recurrence_day_of_month=recurrence_day_of_month
    )

    if reminder_id:
        next_time_str = scheduled_datetime.strftime('%d.%m.%Y u %H:%M')
        await query.edit_message_text(
            f"✅ *Ponavljajući podsetnik kreiran!*\n\n"
            f"Sledeći podsetnik: {next_time_str}",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            "❌ Greška prilikom kreiranja podsetnika. Pokušaj ponovo."
        )

    # Clean up
    context.user_data.pop('recurring', None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cancel the conversation.
    """
    await update.message.reply_text(
        "❌ Otkazano. Koristi /recurring da počneš ponovo."
    )
    context.user_data.pop('recurring', None)
    return ConversationHandler.END


def register_handlers(application):
    """
    Register recurring reminder handlers.
    """
    from telegram.ext import CommandHandler, MessageHandler, filters

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("recurring", recurring_command),
            MessageHandler(filters.Regex("^(🔁 Recurring|🔁 Ponavljajući)$"), recurring_command)
        ],
        states={
            MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            RECURRENCE_TYPE: [CallbackQueryHandler(handle_recurrence_type, pattern="^rec_type_")],
            INTERVAL_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_interval_days)],
            WEEKLY_DAYS: [CallbackQueryHandler(handle_weekday_selection, pattern="^weekday_")],
            MONTHLY_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_monthly_day)],
            TIME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time_input)],
            CONFIRM: [CallbackQueryHandler(handle_confirmation, pattern="^confirm_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
