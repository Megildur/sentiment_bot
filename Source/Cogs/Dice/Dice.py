import asyncio
import discord
import random
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
from typing import Optional, Literal, Any
from .Database import DiceDatabase
from .Views import (
    SetValuesModal,
    CreateCharButton,
    AttributeSetView,
    NoticeView,
    CharacterCardView,
    ManageMaxHPView,
    HPActionResultView,
    WoundDieModal,
    UnwoundDieModal,
    LockDieModal,
    UnlockDieModal,
    SupportDieModal,
    RollToDyeView,
    RollToDoView,
    RollToRecoverView,
    get_swing_accent_color,
    ColorRolesConfigView,
    NoCharactersLeftView,
    get_persistent_views,
    update_user_active_character_views,
)
from .ColorRoles import remove_swing_color_roles, sync_member_swing_color_role
from Source.Utils.Paginator import ButtonPaginator
from .HelpPages import get_help_pages

class Dice(commands.Cog):
    hp = app_commands.Group(name="hp", description="Manage your active character's HP (heal, damage, max HP)")

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.db_manager = DiceDatabase(self.bot)

    async def cog_load(self) -> None:
        await self.db_manager.connect()
        for pview in get_persistent_views(self.bot, self.db_manager):
            self.bot.add_view(pview)

    async def cog_unload(self) -> None:
        await self.db_manager.close()

    async def _get_char_color(self, user_id: int, char_name: Optional[str] = None) -> discord.Color:
        if not char_name:
            return discord.Color.random()
        swing = await self.db_manager.get_swing(user_id, char_name)
        return get_swing_accent_color(swing)

    async def _ensure_active_char(self, interaction: discord.Interaction) -> Optional[str]:
        active_char = await self.db_manager.get_selected_char(interaction.user.id)
        all_chars = await self.db_manager.get_all_characters(interaction.user.id)
        if not all_chars:
            if active_char:
                await self.db_manager.completely_delete_character(interaction.user.id, active_char)
            view = NoticeView(
                title="⚠️ No Active Character",
                body="You do not have any characters created.\n\nUse `/set_attributes` to create a character first!"
            )
            if interaction.response.is_done():
                await interaction.followup.send(view=view, ephemeral=True)
            else:
                await interaction.response.send_message(view=view, ephemeral=True)
            return None

        if not active_char or active_char not in all_chars:
            active_char = all_chars[0]
            await self.db_manager.set_selected_char(interaction.user.id, active_char)
            asyncio.create_task(update_user_active_character_views(self.bot, self.db_manager, interaction.user.id, active_char))

        return active_char

    @app_commands.command(name="roll_to_dye", description="Roll all available attribute dice to defend or react")
    async def roll_to_dye(self, interaction: discord.Interaction):
        await interaction.response.defer()
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        char_color = await self._get_char_color(interaction.user.id, active_char)
        all_attrs = await self.db_manager.get_character_attributes(interaction.user.id, active_char)
        if not all_attrs:
            view = NoticeView("⚠️ No Attributes", f"**{active_char}** does not have any attributes set. Use `/set_attributes` to configure them.", color=char_color)
            await interaction.followup.send(view=view)
            return

        wounded = await self.db_manager.get_wounded(interaction.user.id, active_char)
        locked = await self.db_manager.get_locked(interaction.user.id, active_char)
        shared_out = await self.db_manager.get_active_shared_out_dice(interaction.user.id, active_char)
        available = [a for a in all_attrs if a[0] not in wounded and a[0] not in locked and a[0] not in shared_out]
        display_name = await self.db_manager.get_char_display_name(active_char)

        if not available:
            view = NoticeView("⚠️ No Dice Available", f"No attribute dice are available for **{display_name}** to Roll to Dye.\n\nAll dice are wounded, locked, or currently lent out to allies.", color=char_color)
            await interaction.followup.send(view=view)
            return

        attr_names = await self.db_manager.get_attribute_names(interaction.user.id, active_char)
        swing = await self.db_manager.get_swing(interaction.user.id, active_char)
        swing_color = swing[0] if swing else None
        swing_val = swing[1] if swing else None

        rolled_dice = []
        for color, bonus in available:
            custom_name = attr_names.get(color, "None")
            if swing and color == swing_color:
                rolled_dice.append({
                    "color": color,
                    "name": custom_name,
                    "roll": swing_val,
                    "bonus": bonus,
                    "is_swing": True
                })
            else:
                rolled_dice.append({
                    "color": color,
                    "name": custom_name,
                    "roll": random.randint(1, 6),
                    "bonus": bonus,
                    "is_swing": False
                })

        swing_bonus = next((b for c, b in available if c == swing_color), 0) if swing_color else 0
        swing_info = (swing_color, swing_val, swing_bonus) if swing_color and any(c == swing_color for c, _ in available) else None
        pending_support = await self.db_manager.get_pending_support_dice(interaction.user.id, active_char)

        view = RollToDyeView(self.bot, interaction.user.id, active_char, display_name, rolled_dice, swing_info, pending_support, self.db_manager)
        await interaction.followup.send(view=view)

    @app_commands.command(name="roll_to_do", description="Roll a d20 with your Swing or 1d6 Wild die to affect the world")
    async def roll_to_do(self, interaction: discord.Interaction):
        await interaction.response.defer()
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        display_name = await self.db_manager.get_char_display_name(active_char)
        swing = await self.db_manager.get_swing(interaction.user.id, active_char)
        attr_names = await self.db_manager.get_attribute_names(interaction.user.id, active_char)
        all_attrs = await self.db_manager.get_character_attributes(interaction.user.id, active_char)

        d20_roll = random.randint(1, 20)
        if swing:
            color, val = swing
            bonus = next((b for c, b in all_attrs if c == color), 0)
            custom_name = attr_names.get(color, "None")
            swing_info = (color, custom_name, val, bonus)
            d6_wild = 0
        else:
            swing_info = None
            d6_wild = random.randint(1, 6)

        pending_support = await self.db_manager.get_pending_support_dice(interaction.user.id, active_char)
        view = RollToDoView(self.bot, interaction.user.id, active_char, display_name, swing_info, d20_roll, d6_wild, pending_support, self.db_manager)
        await interaction.followup.send(view=view)

    @app_commands.command(name="roll_to_recover", description="Unlock all locked dice and roll unwounded dice to regain HP")
    async def roll_to_recover(self, interaction: discord.Interaction):
        await interaction.response.defer()
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        await self.db_manager.unlock_all_dice(interaction.user.id, active_char)
        display_name = await self.db_manager.get_char_display_name(active_char)
        all_attrs = await self.db_manager.get_character_attributes(interaction.user.id, active_char)
        wounded = await self.db_manager.get_wounded(interaction.user.id, active_char)
        unwounded = [a for a in all_attrs if a[0] not in wounded]
        attr_names = await self.db_manager.get_attribute_names(interaction.user.id, active_char)

        rolled_dice = []
        total_roll = 0
        for color, bonus in unwounded:
            custom_name = attr_names.get(color, "None")
            die_roll = random.randint(1, 6)
            total_roll += die_roll + bonus
            rolled_dice.append({
                "color": color,
                "name": custom_name,
                "roll": die_roll,
                "bonus": bonus
            })

        old_hp, new_hp, max_hp = await self.db_manager.recover_hp(
            interaction.user.id,
            active_char,
            total_roll,
            has_unwounded_dice=bool(rolled_dice)
        )

        swing = await self.db_manager.get_swing(interaction.user.id, active_char)
        swing_info = (swing[0], swing[1], next((b for c, b in all_attrs if c == swing[0]), 0)) if swing else None

        view = RollToRecoverView(
            self.bot,
            interaction.user.id,
            active_char,
            display_name,
            rolled_dice,
            swing_info,
            self.db_manager,
            old_hp=old_hp,
            new_hp=new_hp,
            max_hp=max_hp
        )
        await interaction.followup.send(view=view)
        asyncio.create_task(update_user_active_character_views(self.bot, self.db_manager, interaction.user.id, active_char))

    @app_commands.command(name="set_gm", description="choose who is the game gm")
    @app_commands.describe(user="user to set as gm")
    async def set_gm_c(self, interaction: discord.Interaction, user: discord.User | discord.Member):
        await self.db_manager.set_gm_check(interaction, user.id)

    @app_commands.command(name="set_attributes", description="View or set your character attributes")
    async def set_attributes_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        active_char = await self.db_manager.get_selected_char(interaction.user.id)
        all_chars = await self.db_manager.get_all_characters(interaction.user.id)
        
        if all_chars:
            if not active_char or active_char not in all_chars:
                active_char = all_chars[0]
                await self.db_manager.set_selected_char(interaction.user.id, active_char)
            view = await AttributeSetView.build(self.bot, interaction, self.db_manager, char_name=active_char)
            msg = await interaction.followup.send(view=view)
            ch_id = msg.channel.id if getattr(msg, "channel", None) else interaction.channel_id
            await self.db_manager.track_active_view(interaction.user.id, ch_id, msg.id, "AttributeSetView")
        else:
            if active_char:
                await self.db_manager.completely_delete_character(interaction.user.id, active_char)
            view = NoCharactersLeftView(self.bot, self.db_manager, user_id=interaction.user.id)
            msg = await interaction.followup.send(view=view)
            ch_id = msg.channel.id if getattr(msg, "channel", None) else interaction.channel_id
            await self.db_manager.track_active_view(interaction.user.id, ch_id, msg.id, "NoCharactersLeftView")

    async def characters_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        chars = await self.db_manager.get_all_characters(interaction.user.id)
        
        return [
            app_commands.Choice(name=char, value=char)
            for char in chars if current.lower() in char.lower()
        ][:25]
    
    @app_commands.command(name="change_active_character", description="Switch your active character")
    @app_commands.autocomplete(characters=characters_autocomplete)
    async def change_active_character(self, interaction: discord.Interaction, characters: str):
        await interaction.response.defer(ephemeral=True)
        all_chars = await self.db_manager.get_all_characters(interaction.user.id)
        
        if characters not in all_chars:
            view = NoticeView("❌ Character Not Found", f"You do not own a character named **{characters}**.")
            await interaction.followup.send(view=view, ephemeral=True)
            return
            
        await self.db_manager.set_selected_char(interaction.user.id, characters)
        guild = interaction.guild or (self.bot.get_guild(interaction.guild_id) if (self.bot and interaction.guild_id) else None)
        if guild:
            await sync_member_swing_color_role(self.bot, guild, interaction.user.id, self.db_manager)
        char_color = await self._get_char_color(interaction.user.id, characters)
        view = NoticeView("✅ Active Character Changed", f"Your active character has been changed to **{characters}**.", color=char_color)
        await interaction.followup.send(view=view, ephemeral=True)
        asyncio.create_task(update_user_active_character_views(self.bot, self.db_manager, interaction.user.id, characters))

    @app_commands.command(name="roll_wild", description="Roll a standalone 1d6")
    async def roll_wild(self, interaction: discord.Interaction):
        roll = random.randint(1, 6)
        view = discord.ui.LayoutView()
        active_char = await self.db_manager.get_selected_char(interaction.user.id)
        display_name = await self.db_manager.get_char_display_name(active_char) if active_char else "No Character"

        container = discord.ui.Container(
            discord.ui.TextDisplay(content="## 🎲 1d6 Rolled!"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=f"*{interaction.user.display_name}* rolled **{roll}** for *{display_name}*"),
            accent_color=discord.Color.random()
        )
        view.add_item(container)
        await interaction.response.send_message(view=view)
    
    @app_commands.command(name="character_card", description="Display your character card and active status")
    async def character_card(self, interaction: discord.Interaction):
        await interaction.response.defer()
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        view = await CharacterCardView.build(self.bot, interaction, self.db_manager, char_name=active_char)
        msg = await interaction.followup.send(view=view)
        ch_id = msg.channel.id if getattr(msg, "channel", None) else interaction.channel_id
        await self.db_manager.track_active_view(interaction.user.id, ch_id, msg.id, "CharacterCardView")

    @app_commands.command(name="wound_die", description="Wound an attribute die")
    async def wound_die(self, interaction: discord.Interaction):
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        char_color = await self._get_char_color(interaction.user.id, active_char)
        all_attrs = await self.db_manager.get_character_attributes(interaction.user.id, active_char)
        if not all_attrs:
            view = NoticeView("⚠️ No Attributes", f"**{active_char}** has no attributes set. Use `/set_attributes` to create them.", color=char_color)
            await interaction.response.send_message(view=view, ephemeral=True)
            return

        wounded = await self.db_manager.get_wounded(interaction.user.id, active_char)
        available = [a for a in all_attrs if a[0] not in wounded]
        display_name = await self.db_manager.get_char_display_name(active_char)

        if not available:
            view = NoticeView("⚠️ All Dice Wounded", f"All attribute dice for **{display_name}** are already wounded. No more dice can be wounded.", color=char_color)
            await interaction.response.send_message(view=view)
            return

        attr_names = await self.db_manager.get_attribute_names(interaction.user.id, active_char)
        modal = WoundDieModal(self.bot, self.db_manager, active_char, available, attr_names)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="unwound_die", description="Heal / unwound a wounded attribute die")
    async def unwound_die(self, interaction: discord.Interaction):
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        char_color = await self._get_char_color(interaction.user.id, active_char)
        wounded = await self.db_manager.get_wounded(interaction.user.id, active_char)
        display_name = await self.db_manager.get_char_display_name(active_char)

        if not wounded:
            view = NoticeView("ℹ️ No Wounded Dice", f"None of the dice for **{display_name}** are currently wounded.\n\nUse `/wound_die` if you need to wound one.", color=char_color)
            await interaction.response.send_message(view=view, ephemeral=True)
            return

        attr_names = await self.db_manager.get_attribute_names(interaction.user.id, active_char)
        modal = UnwoundDieModal(self.bot, self.db_manager, active_char, wounded, attr_names)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="lock_die", description="Lock an attribute die (e.g. for sprinting or igniting)")
    async def lock_die(self, interaction: discord.Interaction):
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        char_color = await self._get_char_color(interaction.user.id, active_char)
        all_attrs = await self.db_manager.get_character_attributes(interaction.user.id, active_char)
        if not all_attrs:
            view = NoticeView("⚠️ No Attributes", f"**{active_char}** has no attributes set. Use `/set_attributes` to create them.", color=char_color)
            await interaction.response.send_message(view=view, ephemeral=True)
            return

        wounded = await self.db_manager.get_wounded(interaction.user.id, active_char)
        locked = await self.db_manager.get_locked(interaction.user.id, active_char)
        available = [a for a in all_attrs if a[0] not in wounded and a[0] not in locked]
        display_name = await self.db_manager.get_char_display_name(active_char)

        if not available:
            view = NoticeView("⚠️ No Lockable Dice", f"No dice are available to lock for **{display_name}**.\n\nAll dice are either already locked or wounded.", color=char_color)
            await interaction.response.send_message(view=view)
            return

        attr_names = await self.db_manager.get_attribute_names(interaction.user.id, active_char)
        modal = LockDieModal(self.bot, self.db_manager, active_char, available, attr_names)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="unlock_die", description="Unlock a locked attribute die")
    async def unlock_die(self, interaction: discord.Interaction):
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        char_color = await self._get_char_color(interaction.user.id, active_char)
        locked = await self.db_manager.get_locked(interaction.user.id, active_char)
        display_name = await self.db_manager.get_char_display_name(active_char)

        if not locked:
            view = NoticeView("ℹ️ No Locked Dice", f"There are no locked dice for **{display_name}**.\n\nUse `/lock_die` to lock one if needed.", color=char_color)
            await interaction.response.send_message(view=view, ephemeral=True)
            return

        attr_names = await self.db_manager.get_attribute_names(interaction.user.id, active_char)
        modal = UnlockDieModal(self.bot, self.db_manager, active_char, locked, attr_names)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="drop_swing", description="Drop your character's current active swing die")
    async def drop_swing(self, interaction: discord.Interaction):
        await interaction.response.defer()
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        display_name = await self.db_manager.get_char_display_name(active_char)
        swing = await self.db_manager.get_swing(interaction.user.id, active_char)

        if not swing:
            view = NoticeView("ℹ️ No Swing Set", f"**{display_name}** does not currently have an active swing set.", color=discord.Color.random())
            await interaction.followup.send(view=view, ephemeral=True)
            return

        await self.db_manager.drop_swing(interaction.user.id, active_char)
        guild = interaction.guild or (self.bot.get_guild(interaction.guild_id) if (self.bot and interaction.guild_id) else None)
        if guild:
            await remove_swing_color_roles(self.bot, guild, interaction.user.id, self.db_manager)
        view = NoticeView("✅ Swing Dropped", f"Dropped active swing for **{display_name}**.\n\nYour character is now colorless with no active swing.", color=discord.Color.random())
        await interaction.followup.send(view=view)
        asyncio.create_task(update_user_active_character_views(self.bot, self.db_manager, interaction.user.id, active_char))

    @app_commands.command(name="support", description="Share an attribute die to support an ally's roll")
    @app_commands.describe(user="The ally you want to support with a die")
    async def support(self, interaction: discord.Interaction, user: discord.User | discord.Member):
        sender_char = await self._ensure_active_char(interaction)
        if not sender_char:
            return

        char_color = await self._get_char_color(interaction.user.id, sender_char)

        if user.id == interaction.user.id:
            view = NoticeView("❌ Invalid Ally", "You cannot send a support die to yourself!", color=char_color)
            await interaction.response.send_message(view=view, ephemeral=True)
            return

        target_char = await self.db_manager.get_selected_char(user.id)
        if not target_char:
            view = NoticeView("⚠️ Ally Has No Character", f"<@{user.id}> does not have an active character selected.", color=char_color)
            await interaction.response.send_message(view=view, ephemeral=True)
            return

        all_attrs = await self.db_manager.get_character_attributes(interaction.user.id, sender_char)
        wounded = await self.db_manager.get_wounded(interaction.user.id, sender_char)
        locked = await self.db_manager.get_locked(interaction.user.id, sender_char)
        shared_out = await self.db_manager.get_active_shared_out_dice(interaction.user.id, sender_char)
        available = [a for a in all_attrs if a[0] not in wounded and a[0] not in locked and a[0] not in shared_out]
        sender_display = await self.db_manager.get_char_display_name(sender_char)

        if not available:
            view = NoticeView("⚠️ No Available Dice", f"You have no available dice to send as support for **{sender_display}**.\n\nAll dice are wounded, locked, or already supporting an ally.", color=char_color)
            await interaction.response.send_message(view=view, ephemeral=True)
            return

        attr_names = await self.db_manager.get_attribute_names(interaction.user.id, sender_char)
        modal = SupportDieModal(self.bot, self.db_manager, sender_char, user, target_char, available, attr_names)
        await interaction.response.send_modal(modal)

    @hp.command(name="heal", description="Restore current HP for your active character (cannot exceed Max HP)")
    @app_commands.describe(amount="Amount of HP to restore")
    async def hp_heal(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1]):
        await interaction.response.defer()
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        display_name = await self.db_manager.get_char_display_name(active_char)
        old_hp, new_hp, max_hp = await self.db_manager.heal_hp(interaction.user.id, active_char, amount)
        swing = await self.db_manager.get_swing(interaction.user.id, active_char)
        view = HPActionResultView(display_name, "heal", amount, old_hp, new_hp, max_hp, swing=swing)
        await interaction.followup.send(view=view)
        asyncio.create_task(update_user_active_character_views(self.bot, self.db_manager, interaction.user.id, active_char))

    @hp.command(name="damage", description="Deal damage to your active character's current HP")
    @app_commands.describe(amount="Amount of damage taken")
    async def hp_damage(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1]):
        await interaction.response.defer()
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        display_name = await self.db_manager.get_char_display_name(active_char)
        old_hp, new_hp, max_hp = await self.db_manager.damage_hp(interaction.user.id, active_char, amount)
        all_attrs = await self.db_manager.get_character_attributes(interaction.user.id, active_char)
        wounded = await self.db_manager.get_wounded(interaction.user.id, active_char)
        swing = await self.db_manager.get_swing(interaction.user.id, active_char)
        view = HPActionResultView(
            display_name,
            "damage",
            amount,
            old_hp,
            new_hp,
            max_hp,
            total_attrs=len(all_attrs),
            wounded_count=len(wounded),
            swing=swing
        )
        await interaction.followup.send(view=view)
        asyncio.create_task(update_user_active_character_views(self.bot, self.db_manager, interaction.user.id, active_char))

    @hp.command(name="max", description="Open the Manage Max HP submenu (Level Up Potential brackets or custom adjust)")
    async def hp_max(self, interaction: discord.Interaction):
        await interaction.response.defer()
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        view = await ManageMaxHPView.build(self.bot, interaction, self.db_manager, active_char)
        msg = await interaction.followup.send(view=view)
        ch_id = msg.channel.id if getattr(msg, "channel", None) else interaction.channel_id
        await self.db_manager.track_active_view(interaction.user.id, ch_id, msg.id, "ManageMaxHPView")

    @app_commands.command(name="color_roles", description="Manage and configure swing color roles that change user name color in chat")
    @app_commands.guild_only()
    async def color_roles(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view = await ColorRolesConfigView.build(self.bot, interaction.guild, self.db_manager)
        await interaction.followup.send(view=view)

    @app_commands.command(name="help", description="Guide and reference for Sentiment TTRPG commands and mechanics")
    async def help_command(self, interaction: discord.Interaction):
        pages = get_help_pages()
        paginator = ButtonPaginator.create_standard_paginator(
            pages,
            author_id=None,
            timeout=None
        )
        await paginator.start(interaction)