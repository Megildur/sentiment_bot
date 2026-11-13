"""The Sentiment cog: slash commands, rolls, character panels and the database behind them.

Dice.py holds the commands and Database.py every read and write; the other modules are the panels, roll messages and helpers the commands share. Only `setup` is loaded as an extension; the rest are imported by it.
"""
from .Dice import Dice

async def setup(bot) -> None:
    await bot.add_cog(Dice(bot))