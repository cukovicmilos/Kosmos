"""
Shared inline keyboard builders for Kosmos Telegram Bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from i18n import get_text


def build_notification_keyboard(
    reminder_id: int,
    is_recurring: bool = False,
    language: str = "en"
) -> InlineKeyboardMarkup:
    """
    Build the inline keyboard for a reminder notification with postpone options.

    Args:
        reminder_id: Reminder ID embedded in callback data
        is_recurring: Whether to add the 'delete recurrence' button
        language: User's language for button labels

    Returns:
        InlineKeyboardMarkup with postpone (and optional delete) buttons
    """
    keyboard = [
        [
            InlineKeyboardButton(
                get_text("postpone_15m", language),
                callback_data=f"postpone_{reminder_id}_15m"
            ),
            InlineKeyboardButton(
                get_text("postpone_30m", language),
                callback_data=f"postpone_{reminder_id}_30m"
            ),
            InlineKeyboardButton(
                get_text("postpone_1h", language),
                callback_data=f"postpone_{reminder_id}_1h"
            ),
        ],
        [
            InlineKeyboardButton(
                get_text("postpone_3h", language),
                callback_data=f"postpone_{reminder_id}_3h"
            ),
            InlineKeyboardButton(
                get_text("postpone_1d", language),
                callback_data=f"postpone_{reminder_id}_1d"
            ),
            InlineKeyboardButton(
                get_text("postpone_custom", language),
                callback_data=f"postpone_{reminder_id}_custom"
            ),
        ],
    ]

    if is_recurring:
        keyboard.append([
            InlineKeyboardButton(
                get_text("stop_recurring_button", language),
                callback_data=f"stop_recurring_{reminder_id}"
            )
        ])

    return InlineKeyboardMarkup(keyboard)


def build_challenge_notification_keyboard(
    reminder_id: int,
    language: str = "en"
) -> InlineKeyboardMarkup:
    """
    Build the inline keyboard for a challenge notification.
    Challenges only have a delete button (no postpone - postponing a daily
    challenge message makes no sense).

    Args:
        reminder_id: Reminder ID embedded in callback data
        language: User's language for button labels

    Returns:
        InlineKeyboardMarkup with a single 'delete challenge' button
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                get_text("challenge_delete_button", language),
                callback_data=f"stop_recurring_{reminder_id}"
            ),
        ]
    ])


def build_delete_recurring_confirm_keyboard(
    reminder_id: int,
    language: str = "en",
    confirm_callback: str = None,
    cancel_callback: str = None
) -> InlineKeyboardMarkup:
    """
    Build the confirmation keyboard for deleting a recurring reminder.

    Args:
        reminder_id: Reminder ID embedded in callback data
        language: User's language for button labels
        confirm_callback: Callback data for confirm (default: delete_confirm_{id})
        cancel_callback: Callback data for cancel (default: delete_cancel_{id})

    Returns:
        InlineKeyboardMarkup with confirm and cancel buttons
    """
    confirm_data = confirm_callback or f"delete_confirm_{reminder_id}"
    cancel_data = cancel_callback or f"delete_cancel_{reminder_id}"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                get_text("delete_forever_button", language),
                callback_data=confirm_data
            ),
            InlineKeyboardButton(
                get_text("cancel_button", language),
                callback_data=cancel_data
            ),
        ]
    ])
