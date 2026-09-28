import discord
from discord.ext import commands
from discord import app_commands
import dotenv
from dotenv import load_dotenv
import os
import sys
import logging
import random
import asyncio
import traceback

load_dotenv()

intents = discord.Intents.all()

file_handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='a')
console_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_uncaught_exception

core_extensions = [
    'Source.Errors',
    'Source.OwnerCommands',
    'Source.Quicksync',
    'Source.Status',
]

class MyBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix='!b ', intents=intents)
        self.db_pool = None

    async def setup_hook(self) -> None:
        for ext in core_extensions:
            try:
                await self.load_extension(ext)
                logging.info(f'Loaded core extension: {ext}')
            except Exception as e:
                logging.error(f"Failed to load extension {ext}", exc_info=e)

        cogs_dir = 'Source/Cogs'
        if os.path.exists(cogs_dir):
            for item in os.listdir(cogs_dir):
                item_path = os.path.join(cogs_dir, item)

                if os.path.isdir(item_path) and item != '__pycache__':
                    if os.path.isfile(os.path.join(item_path, '__init__.py')):
                        try:
                            await self.load_extension(f'Source.Cogs.{item}')
                            logging.info(f'Loaded package: {item}')
                        except Exception as e:
                            logging.error(f"Failed to load package {item}", exc_info=e)

                elif os.path.isfile(item_path) and item.endswith('.py') and item != '__init__.py':
                    cog_name = item[:-3]
                    try:
                        await self.load_extension(f'Source.Cogs.{cog_name}')
                        logging.info(f'Loaded module: {cog_name}')
                    except Exception as e:
                        logging.error(f"Failed to load module {cog_name}", exc_info=e)
      
bot = MyBot()

TOKEN = str(os.getenv('API_TOKEN'))

bot.run(TOKEN, log_handler=None)