from .Dice import Dice

async def setup(bot) -> None:
    await bot.add_cog(Dice(bot))