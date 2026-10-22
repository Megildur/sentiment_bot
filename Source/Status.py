"""Rotates Sentiment's presence every hour."""
import logging
import random

import discord
from discord.ext import commands, tasks

log = logging.getLogger(__name__)

PLAYING, WATCHING, LISTENING, COMPETING = (
    discord.ActivityType.playing, discord.ActivityType.watching, discord.ActivityType.listening, discord.ActivityType.competing,
)

# {servers} and {players} are filled in each time.
PRESENCES = [
    (PLAYING, "with your emotions"),
    (PLAYING, "a chord of Dissonance"),
    (PLAYING, "with forgotten Memories"),
    (PLAYING, "the chords of Resonance"),
    (PLAYING, "a game of hearts and minds"),
    (WATCHING, "Memories unfold"),
    (WATCHING, "the Bonds of {players} players"),
    (WATCHING, "Bonds forge and shatter"),
    (WATCHING, "the narrative unravel"),
    (WATCHING, "emotions run high"),
    (WATCHING, "the collective unconscious"),
    (WATCHING, "over {servers} campaigns"),
    (LISTENING, "shifting Sentiments"),
    (LISTENING, "the Resonance in {servers} servers"),
    (LISTENING, "the echoes of past sessions"),
    (LISTENING, "quiet confessions"),
    (LISTENING, "the hum of Dissonance"),
    (LISTENING, "the stories of {players} players"),
    (COMPETING, "a battle for emotional control"),
    (COMPETING, "a clash of Sentiments"),
    (COMPETING, "the struggle against fading Memories"),
]

STATUSES = [discord.Status.online, discord.Status.idle, discord.Status.do_not_disturb]


class Status(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.cycle.start()

    async def cog_unload(self) -> None:
        self.cycle.cancel()

    @tasks.loop(hours=1.0)
    async def cycle(self) -> None:
        kind, text = random.choice(PRESENCES)
        activity = discord.Activity(type=kind, name=text.format(servers=len(self.bot.guilds), players=len(self.bot.users)))
        status = random.choice(STATUSES)
        try:
            await self.bot.change_presence(activity=activity, status=status)
        except Exception:
            log.exception("Could not change the presence")
            return
        log.info("Presence: [%s] %s %s", status, kind.name, activity.name)

    @cycle.before_loop
    async def before_cycle(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.info("Logged in as %s (ID: %s)", self.bot.user.name, self.bot.user.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Status(bot))
