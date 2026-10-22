import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# Members: color roles and the player counts in the status need the member list.
# Message content: the owner's `!b quicksync` prefix command. Presences aren't used.
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{')
# Rotated so discord.log can't fill the host's disk.
file_handler = RotatingFileHandler(filename='discord.log', encoding='utf-8', maxBytes=5 * 1024 * 1024, backupCount=3)
console_handler = logging.StreamHandler(sys.stdout)
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
        super().__init__(
            command_prefix='!b ',
            intents=intents,
            # Players may be pinged; roles and @everyone never are.
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True, replied_user=False),
        )

    async def setup_hook(self) -> None:
        for ext in core_extensions:
            try:
                await self.load_extension(ext)
                logging.info('Loaded core extension: %s', ext)
            except Exception as e:
                logging.error("Failed to load extension %s", ext, exc_info=e)

        # Every package or module in Source/Cogs is an extension; helpers live inside a package.
        cogs_dir = 'Source/Cogs'
        if os.path.exists(cogs_dir):
            for item in os.listdir(cogs_dir):
                item_path = os.path.join(cogs_dir, item)
                if os.path.isdir(item_path) and item != '__pycache__':
                    if os.path.isfile(os.path.join(item_path, '__init__.py')):
                        name = f'Source.Cogs.{item}'
                    else:
                        continue
                elif os.path.isfile(item_path) and item.endswith('.py') and item != '__init__.py':
                    name = f'Source.Cogs.{item[:-3]}'
                else:
                    continue
                try:
                    await self.load_extension(name)
                    logging.info('Loaded extension: %s', name)
                except Exception as e:
                    logging.error("Failed to load extension %s", name, exc_info=e)


TOKEN = os.getenv('API_TOKEN')
if not TOKEN:
    logging.critical("API_TOKEN is missing from .env, so Sentiment can't log in.")
    sys.exit(1)

bot = MyBot()
bot.run(TOKEN, log_handler=None)
