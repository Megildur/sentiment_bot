"""The last resort when a slash command or view fails: a plain-language private notice, details in the log."""
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands

from Source.Utils import Theme
from Source.Utils.Notice import notice_view, send_ephemeral

log = logging.getLogger(__name__)

SUPPORT_SERVER = os.getenv("BOT_SERVER", "")


def _error_view(title: str, body: str) -> discord.ui.LayoutView:
    footer = f"If this keeps happening, ask in the [support server]({SUPPORT_SERVER})." if SUPPORT_SERVER else None
    return notice_view(title, body, Theme.ERROR, footer)


async def global_view_error(view: discord.ui.LayoutView, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
    log.error("Unhandled exception in view %s", type(view).__name__, exc_info=error)
    await send_ephemeral(interaction, _error_view("Something went wrong", "That didn't go through. Try again in a moment."))


class ErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self._old_tree_error = self.bot.tree.on_error
        self.bot.tree.on_error = self.tree_on_error
        self._old_view_error = discord.ui.LayoutView.on_error
        discord.ui.LayoutView.on_error = global_view_error

    async def cog_unload(self) -> None:
        self.bot.tree.on_error = self._old_tree_error
        discord.ui.LayoutView.on_error = self._old_view_error

    async def tree_on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        original = getattr(error, "original", error)
        command = getattr(interaction.command, "qualified_name", "unknown command")

        if isinstance(error, app_commands.MissingPermissions):
            missing = ", ".join(p.replace("_", " ").title() for p in error.missing_permissions)
            view = _error_view("Permission needed", f"You need **{missing}** to use this command.")
        elif isinstance(error, app_commands.NoPrivateMessage):
            view = _error_view("Server only", "This command only works in a server.")
        elif isinstance(original, discord.Forbidden):
            log.warning("Discord refused /%s: %s", command, original)
            view = _error_view("Discord refused", "Sentiment is missing a permission for that, or the member's role is above Sentiment's.")
        elif isinstance(original, discord.HTTPException) and original.status >= 500:
            log.warning("Discord had an error during /%s: %s", command, original)
            view = _error_view("Discord is having trouble", "Discord's servers had a problem. Try again in a moment.")
        else:
            log.error("Unhandled exception in /%s", command, exc_info=original)
            view = _error_view("Something went wrong", "That command didn't go through. Try again in a moment.")
        await send_ephemeral(interaction, view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ErrorHandler(bot))
