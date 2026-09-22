import discord
import random
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
from typing import Optional, Literal, Any
from .Database import DiceDatabase
from .Views import SetValuesModal, CreateCharButton, AttributeSetView

class Dice(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.db_manager = DiceDatabase(self.bot)

    async def cog_load(self) -> None:
        await self.db_manager.connect()

    async def cog_unload(self) -> None:
        await self.db_manager.close()

    @app_commands.command(name="roll_to_dye")
    async def roll_to_dye(self, interaction: discord.Interaction):
        pass

    @app_commands.command(name="roll_to_do")
    async def roll_to_do(self, interaction: discord.Interaction):
        pass

    @app_commands.command(name="set_gm", description="choose who is the game gm")
    @app_commands.describe(user="user to set as gm")
    async def set_gm_c(self, interaction: discord.Interaction, user: discord.User | discord.Member):
        await self.db_manager.set_gm_check(interaction, user.id)

    @app_commands.command(name="set_attributes", description="View or set your character attributes")
    async def set_attributes_command(self, interaction: discord.Interaction):
        active_char = await self.db_manager.get_selected_char(interaction.user.id)
        
        if active_char:
            view = await AttributeSetView.build(self.bot, interaction, self.db_manager, char_name=active_char)
            await interaction.response.send_message(view=view)
        else:
            view=discord.ui.LayoutView()
            container=discord.ui.Container(
                discord.ui.TextDisplay(content="## **Create New Character!**"),
                discord.ui.Separator(),
                discord.ui.TextDisplay(content=
                    "You have no characters made.\n\n"
                    "To create a new character please press the button below.\n\n"
                    "When the menu comes up start by entering your character's name.\n"
                    "Then select up to three colors, and select a bonus for each.\n"
                    "Select bonuses in the same order as your colors from top to bottom in the checklist.\n\n"
                    "**NOTE:** Only select the same number of bonuses as selected colors!\n"
                ),
                discord.ui.ActionRow(CreateCharButton(self.bot, self.db_manager))
            )
            view.add_item(container)
            await interaction.response.send_message(view=view, ephemeral=True)

    async def characters_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        chars = await self.db_manager.get_all_characters(interaction.user.id)
        
        return [
            app_commands.Choice(name=char, value=char)
            for char in chars if current.lower() in char.lower()
        ][:25]
    
    @app_commands.command(name="change_active_character", description="Switch your active character")
    @app_commands.autocomplete(characters=characters_autocomplete)
    async def change_active_character(self, interaction: discord.Interaction, characters: str):
        all_chars = await self.db_manager.get_all_characters(interaction.user.id)
        
        if characters not in all_chars:
            await interaction.response.send_message(
                f"❌ You do not own a character named **{characters}**.", 
                ephemeral=True
            )
            return
            
        await self.db_manager.set_selected_char(interaction.user.id, characters)
        
        await interaction.response.send_message(
            f"✅ Your active character has been changed to **{characters}**.", 
            ephemeral=True
        )

    @app_commands.command(name="roll_wild")
    async def roll_wild(self, interaction: discord.Interaction):
        roll = random.randint(1, 6)
        view = discord.ui.LayoutView()
        active_char = await self.db_manager.get_selected_char(interaction.user.id)

        container = discord.ui.Container(
            discord.ui.TextDisplay(content="1d6 rolled!"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=f"*{interaction.user.display_name}* rolled **{roll}** for *{active_char}*")
        )
        view.add_item(container)
        await interaction.response.send_message(view=view)
    
    @app_commands.command(name="wound_die")
    async def wound_die(self, interaction: discord.Interaction):
        pass

    @app_commands.command(name="unwound_die")
    async def unwound_die(self, interaction: discord.Interaction):
        pass   

    @app_commands.command(name="character_card")
    async def character_card(self, interaction: discord.Interaction):
        pass   

    @app_commands.command(name="drop_swing")
    async def drop_swing(self, interaction: discord.Interaction):
        pass   

    @app_commands.command(name="lock_die")
    async def lock_die(self, interaction: discord.Interaction):
        pass 

    @app_commands.command(name="unlock_die")
    async def unlock_die(self, interaction: discord.Interaction):
        pass   