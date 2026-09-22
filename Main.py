import discord
from discord.ext import commands
from discord import app_commands
import dotenv
from dotenv import load_dotenv
import os
import logging
import random
import asyncio
import traceback

load_dotenv()

intents = discord.Intents.all()

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

class MyBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix='!b ', intents=intents)
        self.db_pool = None

    async def setup_hook(self) -> None:
        for ext in core_extensions:
            try:
                await self.load_extension(ext)
                print(f'Loaded core extension: {ext}')
            except Exception as e:
                print(f"Failed to load extension {ext}: {e}")
                traceback.print_exc()

        cogs_dir = 'Source/Cogs'
        if os.path.exists(cogs_dir):
            for item in os.listdir(cogs_dir):
                item_path = os.path.join(cogs_dir, item)

                if os.path.isdir(item_path) and item != '__pycache__':
                    if os.path.isfile(os.path.join(item_path, '__init__.py')):
                        try:
                            await bot.load_extension(f'Source.Cogs.{item}')
                            print(f'Loaded package: {item}')
                        except Exception as e:
                            print(f"Failed to load package {item}: {e}")
                            traceback.print_exc()

                elif os.path.isfile(item_path) and item.endswith('.py') and item != '__init__.py':
                    cog_name = item[:-3]
                    try:
                        await bot.load_extension(f'Source.Cogs.{cog_name}')
                        print(f'Loaded module: {cog_name}')
                    except Exception as e:
                        print(f"Failed to load module {cog_name}: {e}")
                        traceback.print_exc()
      
bot = MyBot()

TOKEN = str(os.getenv('API_TOKEN'))

bot.run(TOKEN, log_handler=handler, log_level=logging.ERROR)