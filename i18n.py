"""
Internationalization (i18n) module for Kosmos Telegram Bot.
Handles loading and translation of text strings.
"""

import logging
from pathlib import Path
from typing import Dict, Optional
import polib

from config import ROOT_DIR, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)

# Global translations dictionary
# Structure: {language: {msgid: msgstr}}
_translations: Dict[str, Dict[str, str]] = {}


def load_translations():
    """
    Load all translation files from locales directory.
    """
    locales_dir = ROOT_DIR / "locales"

    if not locales_dir.exists():
        logger.warning(f"Locales directory not found: {locales_dir}")
        return

    for lang in SUPPORTED_LANGUAGES:
        po_file = locales_dir / f"{lang}.po"

        if not po_file.exists():
            logger.warning(f"Translation file not found: {po_file}")
            continue

        try:
            po = polib.pofile(str(po_file))
            translations = {}

            for entry in po:
                if entry.msgstr:  # Only add if translation exists
                    translations[entry.msgid] = entry.msgstr

            _translations[lang] = translations
            logger.info(f"Loaded {len(translations)} translations for '{lang}'")

        except Exception as e:
            logger.error(f"Error loading translations for '{lang}': {e}")


def get_text(msgid: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """
    Get translated text for a given message ID.

    Args:
        msgid: Message ID (key in .po file)
        language: Language code (en, sr-lat)
        **kwargs: Format arguments for string formatting

    Returns:
        Translated string or msgid if translation not found
    """
    # Fallback to default language if requested language not found
    if language not in _translations:
        language = DEFAULT_LANGUAGE

    # Get translation or fallback to msgid
    text = _translations.get(language, {}).get(msgid, msgid)

    # Format string with kwargs if provided
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing format key in translation '{msgid}': {e}")

    return text


def _(msgid: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """
    Shorthand alias for get_text().

    Args:
        msgid: Message ID
        language: Language code
        **kwargs: Format arguments

    Returns:
        Translated string
    """
    return get_text(msgid, language, **kwargs)


class UserTranslator:
    """
    Translator class that remembers user's language.
    """

    def __init__(self, language: str = DEFAULT_LANGUAGE):
        self.language = language

    def _(self, msgid: str, **kwargs) -> str:
        """Get translated text in user's language."""
        return get_text(msgid, self.language, **kwargs)

    def set_language(self, language: str):
        """Change user's language."""
        if language in SUPPORTED_LANGUAGES:
            self.language = language
        else:
            logger.warning(f"Unsupported language: {language}")


# Load translations on module import
load_translations()


if __name__ == "__main__":
    # Test translations
    print("Testing i18n module...")
    print(f"Supported languages: {SUPPORTED_LANGUAGES}")
    print(f"Loaded translations: {list(_translations.keys())}")

    # Test English
    print("\nEnglish:")
    print(_("welcome_message", "en"))

    # Test Serbian
    print("\nSrpski:")
    print(_("welcome_message", "sr-lat"))
