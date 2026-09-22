import random
import discord
from discord.ext import commands, tasks

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cycle.start()

    def cog_unload(self):
        self.cycle.cancel()

    @tasks.loop(hours=1.0)
    async def cycle(self):
        try:
            server_count = len(self.bot.guilds)
            user_count = len(self.bot.users)

            presences = [
                discord.Activity(type=discord.ActivityType.playing, name="with your emotions"),
                discord.Activity(type=discord.ActivityType.playing, name="a chord of Dissonance"),
                discord.Activity(type=discord.ActivityType.playing, name="with forgotten Memories"),
                discord.Activity(type=discord.ActivityType.playing, name="the chords of Resonance"),
                discord.Activity(type=discord.ActivityType.playing, name="a game of hearts and minds"),
                discord.Activity(type=discord.ActivityType.watching, name="Memories unfold"),
                discord.Activity(type=discord.ActivityType.watching, name=f"the Bonds of {user_count} players"),
                discord.Activity(type=discord.ActivityType.watching, name="Bonds forge and shatter"),
                discord.Activity(type=discord.ActivityType.watching, name="the narrative unravel"),
                discord.Activity(type=discord.ActivityType.watching, name="emotions run high"),
                discord.Activity(type=discord.ActivityType.watching, name="the collective unconscious"),
                discord.Activity(type=discord.ActivityType.watching, name=f"over {server_count} campaigns"),
                discord.Activity(type=discord.ActivityType.listening, name="shifting Sentiments"),
                discord.Activity(type=discord.ActivityType.listening, name=f"the Resonance in {server_count} servers"),
                discord.Activity(type=discord.ActivityType.listening, name="the echoes of past sessions"),
                discord.Activity(type=discord.ActivityType.listening, name="quiet confessions"),
                discord.Activity(type=discord.ActivityType.listening, name="the hum of Dissonance"),
                discord.Activity(type=discord.ActivityType.listening, name=f"the stories of {user_count} players"),
                discord.Activity(type=discord.ActivityType.competing, name="a battle for emotional control"),
                discord.Activity(type=discord.ActivityType.competing, name="a clash of Sentiments"),
                discord.Activity(type=discord.ActivityType.competing, name="the struggle against fading Memories")
            ]
            
            statuses = [discord.Status.online, discord.Status.idle, discord.Status.do_not_disturb]
            
            chosen_activity = random.choice(presences)
            chosen_status = random.choice(statuses)
            
            await self.bot.change_presence(activity=chosen_activity, status=chosen_status)
            print(f"Changed status to: [{chosen_status}] {chosen_activity.type.name.capitalize()} {chosen_activity.name}")
            
        except Exception as e:
            print(f'Error updating status: {e}')

    @cycle.before_loop
    async def before_cycle(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        print(f'Logged in as {self.bot.user.name} (ID: {self.bot.user.id})')

async def setup(bot):
   await bot.add_cog(Status(bot))