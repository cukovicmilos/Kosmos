#!/usr/bin/env python3
import asyncio
from telegram import Bot
from config import BOT_TOKEN

async def check_description():
    bot = Bot(token=BOT_TOKEN)
    
    # Get bot info
    me = await bot.get_me()
    print(f"Bot Username: @{me.username}")
    print(f"Bot Name: {me.first_name}")
    print()
    
    # Get short description
    short_desc = await bot.get_my_short_description()
    print(f"Short Description:")
    print(f"  {short_desc.short_description}")
    print()
    
    # Get full description
    full_desc = await bot.get_my_description()
    print(f"Full Description:")
    print(full_desc.description)

if __name__ == "__main__":
    asyncio.run(check_description())
