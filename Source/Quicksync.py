"""!b quicksync: the owner's fallback for syncing slash commands when /owner isn't there yet."""
import logging
import os

import discord
from discord.ext import commands

log = logging.getLogger(__name__)


class QuickSync(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="quicksync", hidden=True)
    @commands.is_owner()
    async def quicksync(self, ctx: commands.Context) -> None:
        if ctx.guild is None:
            await ctx.send("Run this in one of the allowed servers.")
            return
        # Same parsing as OwnerCommands, so a stray entry is skipped instead of crashing.
        allowed = [int(g.strip()) for g in os.getenv("ALLOWED_GUILDS", "").split(",") if g.strip().isdigit()]
        if not allowed:
            await ctx.send("No allowed servers are set in ALLOWED_GUILDS.")
            return
        if ctx.guild.id not in allowed:
            await ctx.send("Quicksync can't be used in this server.")
            return

        await ctx.send(f"Syncing slash commands to {len(allowed)} allowed server(s).")
        try:
            for guild_id in allowed:
                await self.bot.tree.sync(guild=discord.Object(id=guild_id))
        except Exception:
            log.exception("Quicksync failed")
            await ctx.send("Sync failed. The error is in the log.")
            return
        await ctx.send("Synced commands to all allowed servers.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(QuickSync(bot))
