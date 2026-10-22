"""Sentiment's slash commands. Command, group and option names are fixed: renaming one breaks it for every server."""
import logging
import random
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

from Source.Utils import Theme
from Source.Utils.Background import Background
from Source.Utils.Notice import notice_view, send_ephemeral
from Source.Utils.Permissions import server_of
from . import Characters, ColorRolesPanel, GM, HelpPages, Rolls
from .Characters import (
    ATTRIBUTES, CARD, CREATE, MAX_HP, active_character, attribute_panel, character_card, create_character_view,
    hp_result_view, max_hp_panel, refresh_later,
)
from .ColorRoles import remove_swing_color_roles, sync_member_swing_color_role
from .Common import send_tracked
from .Constants import swing_accent
from .Database import CharacterState, DiceDatabase
from .DieStates import DieStateModal, SupportDieModal
from .RollText import VIEW_TYPES, Die

log = logging.getLogger(__name__)

# Every button and menu on Sentiment's messages; see Source/Utils/Views.py.
LASTING_ITEMS = Characters.ITEMS + Rolls.ITEMS + GM.ITEMS + HelpPages.ITEMS + ColorRolesPanel.ITEMS

NO_MENTIONS = discord.AllowedMentions.none()


class Dice(commands.Cog):
    hp = app_commands.Group(name="hp", description="Manage your active character's HP: heal, damage and Max HP")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = DiceDatabase()
        self.background = Background()

    async def cog_load(self) -> None:
        await self.db.connect()
        self.bot.add_dynamic_items(*LASTING_ITEMS)

    async def cog_unload(self) -> None:
        self.bot.remove_dynamic_items(*LASTING_ITEMS)
        self.background.cancel_all()
        await self.db.close()

    async def _state(self, interaction: discord.Interaction) -> Optional[CharacterState]:
        """The player's active character, or None after telling them they have none.

        Called before any defer, so the notice stays private.
        """
        char_name = await active_character(interaction, interaction.user.id)
        if not char_name:
            await send_ephemeral(interaction, notice_view("No character", "You don't have a character yet. Create one with `/set_attributes`.", Theme.ACCENT))
            return None
        return await self.db.get_character_state(interaction.user.id, char_name)

    async def _refuse(self, interaction: discord.Interaction, title: str, body: str, state: Optional[CharacterState] = None) -> None:
        await send_ephemeral(interaction, notice_view(title, body, swing_accent(state.swing) if state else Theme.ACCENT))

    # Rolls

    @app_commands.command(name="roll_to_dye", description="Roll every available Attribute die to defend or react")
    async def roll_to_dye(self, interaction: discord.Interaction) -> None:
        state = await self._state(interaction)
        if state is None:
            return
        if not state.attributes:
            await self._refuse(interaction, "No Attributes", f"**{state.display_name}** has no Attributes. Add some with `/set_attributes`.", state)
            return
        usable = state.usable()
        if not usable:
            await self._refuse(interaction, "No dice to roll", f"All of **{state.display_name}**'s dice are Wounded, Locked or sent to an ally as Support.", state)
            return

        await interaction.response.defer()
        swing = state.swing
        dice = [
            # The swing die keeps its saved value instead of being rolled again.
            Die(c, state.name(c), swing[1], b, True) if swing and c == swing[0] else Die(c, state.name(c), random.randint(1, 6), b)
            for c, b in usable
        ]
        waiting = await self.db.get_pending_support_dice(interaction.user.id, state.char_name)
        view = Rolls.dye_view(state.display_name, dice, [], bool(waiting))
        await send_tracked(interaction, view, VIEW_TYPES["dye"], interaction.user.id, state.char_name)

    @app_commands.command(name="roll_to_do", description="Roll a d20 plus your Swing, or a Wild 1d6, to act on the world")
    async def roll_to_do(self, interaction: discord.Interaction) -> None:
        state = await self._state(interaction)
        if state is None:
            return
        await interaction.response.defer()
        d20 = random.randint(1, 20)
        if state.swing:
            color, value = state.swing
            swing, wild = (color, state.name(color), value, state.bonus(color)), 0
        else:
            swing, wild = None, random.randint(1, 6)
        waiting = await self.db.get_pending_support_dice(interaction.user.id, state.char_name)
        view = Rolls.do_view(state.display_name, d20, wild, swing, [], bool(waiting))
        await send_tracked(interaction, view, VIEW_TYPES["do"], interaction.user.id, state.char_name)

    @app_commands.command(name="roll_to_recover", description="Unlock all dice and roll your Unwounded dice to regain HP")
    async def roll_to_recover(self, interaction: discord.Interaction) -> None:
        user_id = interaction.user.id
        char_name = await active_character(interaction, user_id)
        if not char_name:
            await self._state(interaction)
            return
        await interaction.response.defer()
        await self.db.unlock_all_dice(user_id, char_name)
        state = await self.db.get_character_state(user_id, char_name)
        swing_color = state.swing[0] if state.swing else None
        dice = [Die(c, state.name(c), random.randint(1, 6), b, c == swing_color) for c, b in state.usable(locked=False, shared_out=False)]
        total = sum(d.roll + d.bonus for d in dice)
        hp = await self.db.recover_hp(user_id, char_name, total, has_unwounded_dice=bool(dice))
        view = Rolls.recover_view(state.display_name, dice, hp)
        await send_tracked(interaction, view, VIEW_TYPES["recover"], user_id, char_name)
        refresh_later(interaction, user_id, char_name)

    @app_commands.command(name="roll_wild", description="Roll a single 1d6")
    async def roll_wild(self, interaction: discord.Interaction) -> None:
        roll = random.randint(1, 6)
        char_name = await self.db.get_selected_char(interaction.user.id)
        display_name = await self.db.get_char_display_name(char_name) if char_name else "no character"
        swing = await self.db.get_swing(interaction.user.id, char_name) if char_name else None
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(f"## 🎲 1d6 rolled\n*{interaction.user.display_name}* rolled **{roll}** for *{display_name}*."),
            accent_colour=swing_accent(swing),
        ))
        await interaction.response.send_message(view=view)

    # Characters

    @app_commands.command(name="set_attributes", description="Create a character, or set up your active character's Attributes")
    async def set_attributes_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        user_id = interaction.user.id
        char_name = await active_character(interaction, user_id)
        if char_name:
            view = await attribute_panel(self.bot, self.db, user_id, char_name)
            await send_tracked(interaction, view, ATTRIBUTES, user_id, char_name)
        else:
            await send_tracked(interaction, create_character_view(), CREATE, user_id, "")

    async def characters_autocomplete(self, interaction: discord.Interaction, current: str) -> list:
        chars = await self.db.get_all_characters(interaction.user.id)
        return [app_commands.Choice(name=c, value=c) for c in chars if current.lower() in c.lower()][:25]

    @app_commands.command(name="change_active_character", description="Switch your active character")
    @app_commands.autocomplete(characters=characters_autocomplete)
    async def change_active_character(self, interaction: discord.Interaction, characters: str) -> None:
        user_id = interaction.user.id
        if characters not in await self.db.get_all_characters(user_id):
            await self._refuse(interaction, "Character not found", f"You don't have a character named **{characters}**.")
            return
        await interaction.response.defer(ephemeral=True)
        await self.db.set_selected_char(user_id, characters)
        guild = server_of(interaction)
        if guild is not None:
            await sync_member_swing_color_role(guild, user_id, self.db)
        swing = await self.db.get_swing(user_id, characters)
        await send_ephemeral(interaction, notice_view("Active character changed", f"You're now playing **{characters}**.", swing_accent(swing) or Theme.BRAND))
        refresh_later(interaction, user_id, characters)

    @app_commands.command(name="character_card", description="Show your active character's card")
    async def character_card(self, interaction: discord.Interaction) -> None:
        user_id = interaction.user.id
        char_name = await active_character(interaction, user_id)
        if not char_name:
            await self._state(interaction)
            return
        await interaction.response.defer()
        view = await character_card(self.db, user_id, char_name)
        await send_tracked(interaction, view, CARD, user_id, char_name, allowed_mentions=NO_MENTIONS)

    # Dice states

    async def _die_form(self, interaction: discord.Interaction, action: str) -> None:
        state = await self._state(interaction)
        if state is None:
            return
        if action in ("wound", "lock") and not state.attributes:
            await self._refuse(interaction, "No Attributes", f"**{state.display_name}** has no Attributes. Add some with `/set_attributes`.", state)
            return
        colors = {
            "wound": [c for c, _ in state.usable(locked=False, shared_out=False)],
            "unwound": state.wounded,
            "lock": [c for c, _ in state.usable(shared_out=False)],
            "unlock": state.locked,
        }[action]
        if not colors:
            body = {
                "wound": f"Every Attribute of **{state.display_name}** is already Wounded.",
                "unwound": f"None of **{state.display_name}**'s dice are Wounded.",
                "lock": f"Every die of **{state.display_name}** is already Locked or Wounded.",
                "unlock": f"None of **{state.display_name}**'s dice are Locked. Use `/lock_die` to Lock one.",
            }[action]
            await self._refuse(interaction, "Nothing to change", body, state)
            return
        await interaction.response.send_modal(DieStateModal(action, state, colors))

    @app_commands.command(name="wound_die", description="Wound one of your Attributes")
    async def wound_die(self, interaction: discord.Interaction) -> None:
        await self._die_form(interaction, "wound")

    @app_commands.command(name="unwound_die", description="Heal a Wounded Attribute die")
    async def unwound_die(self, interaction: discord.Interaction) -> None:
        await self._die_form(interaction, "unwound")

    @app_commands.command(name="lock_die", description="Lock an Attribute die, to Sprint, Tag a Prop or Ignite your Swing")
    async def lock_die(self, interaction: discord.Interaction) -> None:
        await self._die_form(interaction, "lock")

    @app_commands.command(name="unlock_die", description="Unlock a Locked Attribute die")
    async def unlock_die(self, interaction: discord.Interaction) -> None:
        await self._die_form(interaction, "unlock")

    @app_commands.command(name="drop_swing", description="Drop your active character's Swing and become colorless")
    async def drop_swing(self, interaction: discord.Interaction) -> None:
        state = await self._state(interaction)
        if state is None:
            return
        if not state.swing:
            await self._refuse(interaction, "No Swing", f"**{state.display_name}** has no Swing to drop.")
            return
        await interaction.response.defer()
        user_id = interaction.user.id
        await self.db.drop_swing(user_id, state.char_name)
        guild = server_of(interaction)
        if guild is not None:
            await remove_swing_color_roles(guild, user_id, self.db)
        view = notice_view("Swing dropped", f"**{state.display_name}** dropped their Swing and is colorless now.", None)
        await interaction.followup.send(view=view)
        refresh_later(interaction, user_id, state.char_name)

    @app_commands.command(name="support", description="Send an Attribute die to Support an ally's next roll")
    @app_commands.describe(user="The ally to Support")
    async def support(self, interaction: discord.Interaction, user: Union[discord.User, discord.Member]) -> None:
        state = await self._state(interaction)
        if state is None:
            return
        if user.id == interaction.user.id:
            await self._refuse(interaction, "Pick an ally", "You can't Support yourself.", state)
            return
        target_char = await self.db.get_selected_char(user.id)
        if not target_char:
            await self._refuse(interaction, "Ally has no character", f"<@{user.id}> has no active character.", state)
            return
        colors = [c for c, _ in state.usable()]
        if not colors:
            await self._refuse(interaction, "No dice to send", f"All of **{state.display_name}**'s dice are Wounded, Locked or already Supporting an ally.", state)
            return
        await interaction.response.send_modal(SupportDieModal(state, user, target_char, colors))

    # HP

    @hp.command(name="heal", description="Restore HP to your active character, up to Max HP")
    @app_commands.describe(amount="How much HP to restore")
    async def hp_heal(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1]) -> None:
        state = await self._state(interaction)
        if state is None:
            return
        await interaction.response.defer()
        old_hp, new_hp, max_hp = await self.db.heal_hp(interaction.user.id, state.char_name, amount)
        await interaction.followup.send(view=hp_result_view(state.display_name, "heal", amount, old_hp, new_hp, max_hp, swing=state.swing))
        refresh_later(interaction, interaction.user.id, state.char_name)

    @hp.command(name="damage", description="Take damage on your active character's HP")
    @app_commands.describe(amount="How much damage was taken")
    async def hp_damage(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1]) -> None:
        state = await self._state(interaction)
        if state is None:
            return
        await interaction.response.defer()
        old_hp, new_hp, max_hp = await self.db.damage_hp(interaction.user.id, state.char_name, amount)
        view = hp_result_view(
            state.display_name, "damage", amount, old_hp, new_hp, max_hp,
            total_attrs=len(state.attributes), wounded_count=len(state.wounded), swing=state.swing,
        )
        await interaction.followup.send(view=view)
        refresh_later(interaction, interaction.user.id, state.char_name)

    @hp.command(name="max", description="Raise or lower Max HP: spend Potential, or set it yourself")
    async def hp_max(self, interaction: discord.Interaction) -> None:
        user_id = interaction.user.id
        char_name = await active_character(interaction, user_id)
        if not char_name:
            await self._state(interaction)
            return
        await interaction.response.defer()
        view = await max_hp_panel(self.db, user_id, char_name)
        await send_tracked(interaction, view, MAX_HP, user_id, char_name)

    # Server and help

    @app_commands.command(name="set_gm", description="Choose who is the game's GM")
    @app_commands.describe(user="The member to make GM")
    async def set_gm_c(self, interaction: discord.Interaction, user: Union[discord.User, discord.Member]) -> None:
        await GM.set_gm(interaction, user)

    @app_commands.command(name="color_roles", description="Set up the roles that color players' names by their Swing")
    @app_commands.guild_only()
    async def color_roles(self, interaction: discord.Interaction) -> None:
        guild = server_of(interaction)
        if guild is None:
            await self._refuse(interaction, "Server only", "Color roles work in a server Sentiment is in.")
            return
        await interaction.response.defer()
        await interaction.followup.send(view=await ColorRolesPanel.color_roles_panel(guild, self.db), allowed_mentions=NO_MENTIONS)

    @app_commands.command(name="help", description="Guide to Sentiment's commands and rules")
    async def help_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(view=HelpPages.help_view())
