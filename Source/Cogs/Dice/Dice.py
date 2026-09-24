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
)
from Source.Utils.Paginator import ButtonPaginator

class Dice(commands.Cog):
    hp = app_commands.Group(name="hp", description="Manage your active character's HP (heal, damage, max HP)")

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.db_manager = DiceDatabase(self.bot)

    async def cog_load(self) -> None:
        await self.db_manager.connect()

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

        return active_char

    @app_commands.command(name="roll_to_dye", description="Roll all available attribute dice to defend or react")
    async def roll_to_dye(self, interaction: discord.Interaction):
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        char_color = await self._get_char_color(interaction.user.id, active_char)
        all_attrs = await self.db_manager.get_character_attributes(interaction.user.id, active_char)
        if not all_attrs:
            view = NoticeView("⚠️ No Attributes", f"**{active_char}** does not have any attributes set. Use `/set_attributes` to configure them.", color=char_color)
            await interaction.response.send_message(view=view, ephemeral=True)
            return

        wounded = await self.db_manager.get_wounded(interaction.user.id, active_char)
        locked = await self.db_manager.get_locked(interaction.user.id, active_char)
        shared_out = await self.db_manager.get_active_shared_out_dice(interaction.user.id, active_char)
        available = [a for a in all_attrs if a[0] not in wounded and a[0] not in locked and a[0] not in shared_out]
        display_name = await self.db_manager.get_char_display_name(active_char)

        if not available:
            view = NoticeView("⚠️ No Dice Available", f"No attribute dice are available for **{display_name}** to Roll to Dye.\n\nAll dice are wounded, locked, or currently lent out to allies.", color=char_color)
            await interaction.response.send_message(view=view)
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
        await interaction.response.send_message(view=view)

    @app_commands.command(name="roll_to_do", description="Roll a d20 with your Swing or 1d6 Wild die to affect the world")
    async def roll_to_do(self, interaction: discord.Interaction):
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
        await interaction.response.send_message(view=view)

    @app_commands.command(name="roll_to_recover", description="Unlock all locked dice and roll unwounded dice to regain HP")
    async def roll_to_recover(self, interaction: discord.Interaction):
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
        await interaction.response.send_message(view=view)

    @app_commands.command(name="set_gm", description="choose who is the game gm")
    @app_commands.describe(user="user to set as gm")
    async def set_gm_c(self, interaction: discord.Interaction, user: discord.User | discord.Member):
        await self.db_manager.set_gm_check(interaction, user.id)

    @app_commands.command(name="set_attributes", description="View or set your character attributes")
    async def set_attributes_command(self, interaction: discord.Interaction):
        active_char = await self.db_manager.get_selected_char(interaction.user.id)
        all_chars = await self.db_manager.get_all_characters(interaction.user.id)
        
        if all_chars:
            if not active_char or active_char not in all_chars:
                active_char = all_chars[0]
                await self.db_manager.set_selected_char(interaction.user.id, active_char)
            view = await AttributeSetView.build(self.bot, interaction, self.db_manager, char_name=active_char)
            await interaction.response.send_message(view=view)
        else:
            if active_char:
                await self.db_manager.completely_delete_character(interaction.user.id, active_char)
            view = discord.ui.LayoutView()
            container = discord.ui.Container(
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
            view = NoticeView("❌ Character Not Found", f"You do not own a character named **{characters}**.")
            await interaction.response.send_message(view=view, ephemeral=True)
            return
            
        await self.db_manager.set_selected_char(interaction.user.id, characters)
        char_color = await self._get_char_color(interaction.user.id, characters)
        view = NoticeView("✅ Active Character Changed", f"Your active character has been changed to **{characters}**.", color=char_color)
        await interaction.response.send_message(view=view, ephemeral=True)

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
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        view = await CharacterCardView.build(self.bot, interaction, self.db_manager, char_name=active_char)
        await interaction.response.send_message(view=view)

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
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        display_name = await self.db_manager.get_char_display_name(active_char)
        swing = await self.db_manager.get_swing(interaction.user.id, active_char)

        if not swing:
            view = NoticeView("ℹ️ No Swing Set", f"**{display_name}** does not currently have an active swing set.", color=discord.Color.random())
            await interaction.response.send_message(view=view, ephemeral=True)
            return

        await self.db_manager.drop_swing(interaction.user.id, active_char)
        view = NoticeView("✅ Swing Dropped", f"Dropped active swing for **{display_name}**.\n\nYour character is now colorless with no active swing.", color=discord.Color.random())
        await interaction.response.send_message(view=view)

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
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        display_name = await self.db_manager.get_char_display_name(active_char)
        old_hp, new_hp, max_hp = await self.db_manager.heal_hp(interaction.user.id, active_char, amount)
        swing = await self.db_manager.get_swing(interaction.user.id, active_char)
        view = HPActionResultView(display_name, "heal", amount, old_hp, new_hp, max_hp, swing=swing)
        await interaction.response.send_message(view=view)

    @hp.command(name="damage", description="Deal damage to your active character's current HP")
    @app_commands.describe(amount="Amount of damage taken")
    async def hp_damage(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1]):
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
        await interaction.response.send_message(view=view)

    @hp.command(name="max", description="Open the Manage Max HP submenu (Level Up Potential brackets or custom adjust)")
    async def hp_max(self, interaction: discord.Interaction):
        active_char = await self._ensure_active_char(interaction)
        if not active_char:
            return

        view = await ManageMaxHPView.build(self.bot, interaction, self.db_manager, active_char)
        await interaction.response.send_message(view=view)

    @app_commands.command(name="help", description="Guide and reference for Sentiment TTRPG commands and mechanics")
    async def help_command(self, interaction: discord.Interaction):
        # Page 1: Character Management
        page1 = discord.ui.Container(
            discord.ui.TextDisplay(content="## 📜 **Sentiment Guide: Characters & Setup**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=
                "**`/set_attributes`**\n"
                "• Create a new character (automatically starts at **10 / 10 HP**) or open the character setup menu.\n"
                "• Add, edit, or delete attributes and set their levels (+0 to +9).\n"
                "• Give attributes custom titles (e.g. Red *'Passion'*, Blue *'Focus'*).\n"
                "• Switch active characters or delete characters.\n\n"
                "**`/change_active_character`**\n"
                "• Quickly switch which character you are currently playing.\n\n"
                "**`/character_card`**\n"
                "• View your character sheet: **Current / Max HP**, active Swing, attributes & bonuses, locked dice, and wounded dice.\n"
                "• Includes a dropdown to switch characters and the **❤️ Manage Max HP** button."
            ),
            accent_color=discord.Color.random()
        )

        # Page 2: Rolls
        page2 = discord.ui.Container(
            discord.ui.TextDisplay(content="## 🎲 **Sentiment Guide: Core Rolls**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=
                "**`/roll_to_dye`**\n"
                "• Reactive / defensive roll when things happen to your character (dodging, resisting magic, enduring distress).\n"
                "• Rolls a d6 for each unwounded and unlocked attribute.\n"
                "• If a Swing is active, the swing die is not rerolled—its saved value and bonus are added.\n"
                "• Use **Set Swing** on the roll message to pick a new active Swing, or **Apply Support Die** to roll a shared die.\n\n"
                "**`/roll_to_do`**\n"
                "• Proactive roll to impact the world (attacks, skill checks, social actions).\n"
                "• With a Swing: rolls **1d20 + Swing** (die value + attribute bonus). Rolling a 20 on the d20 is a **Critical** (doubles damage/effect)!\n"
                "• Without a Swing: rolls **1d20 + 1d6 Wild** with no attribute bonus.\n\n"
                "**`/roll_to_recover`**\n"
                "• Used during a Rest or after sustaining a Wound to unlock all locked dice and automatically recover HP:\n"
                "  - **At `0 HP`**: Your roll total becomes your new Current HP (capped at Max HP).\n"
                "  - **Above `0 HP`**: Your roll total is added to your Current HP (capped at Max HP).\n"
                "  - **No unwounded dice left**: Restores **+1 HP**."
            ),
            accent_color=discord.Color.random()
        )

        # Page 3: Health (HP), Damage & Leveling Up
        page3 = discord.ui.Container(
            discord.ui.TextDisplay(content="## ❤️ **Sentiment Guide: Health (HP) & Leveling**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=
                "**`/hp damage <amount>`**\n"
                "• Subtracts damage from your active character's Current HP (cannot drop below `0`).\n"
                "• **Hitting `0 HP` (Wound):** Displays a reminder to run **`/wound_die`** and **`/roll_to_recover`**, or choose to **Leave the Scene** (fleeing/passing out to avoid further damage in the current Scene/Conflict).\n"
                "• **All Dice Wounded + `0 HP`:** Displays a **Death / Leave the Scene** alert.\n\n"
                "**`/hp heal <amount>`**\n"
                "• Restores Current HP for other healing effects without changing your Max HP (capped at Max HP).\n\n"
                "**`/hp max` & `❤️ Manage Max HP` Button (on `/character_card`)**\n"
                "• Opens the Max HP submenu to increase/decrease Max HP (increasing Max HP also increases Current HP by the same amount).\n"
                "• **Spend Potential (Level-Up Brackets):**\n"
                "  - `10–19 Max HP`: **+5 HP** flat or roll **1d6 + 1**\n"
                "  - `20–39 Max HP`: **+3 HP** flat or roll **1d6**\n"
                "  - `40–59 Max HP`: **+2 HP** flat or roll **1d6 - 1**\n"
                "  - `60+ Max HP`: **+1 HP** flat\n"
                "• **Custom Adjust / Set:** Add/subtract any amount (`+5`, `-3`) or set an exact Max HP (great for NPCs or custom buffs)."
            ),
            accent_color=discord.Color.random()
        )

        # Page 4: Dice States & Support
        page4 = discord.ui.Container(
            discord.ui.TextDisplay(content="## 🔒 **Sentiment Guide: Dice States & Support**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=
                "**`/wound_die` & `/unwound_die`**\n"
                "• Wound an attribute die when hitting `0 HP` or pushing your character to the limit.\n"
                "• Wounding removes that die from rolls until healed and **automatically unlocks all locked dice**.\n"
                "• Use `/unwound_die` when wounds heal between sessions or from treatment.\n\n"
                "**`/lock_die` & `/unlock_die`**\n"
                "• Lock an unwounded die to use abilities (Sprint, Push, Block, Tag a Prop). Locking your Swing drops it.\n"
                "• Locked dice unlock at the start of your turn, end of a Scene, or when you `/roll_to_recover`.\n\n"
                "**`/drop_swing`**\n"
                "• Drop your active Swing to become colorless.\n\n"
                "**`/support`**\n"
                "• Pass an available attribute die to an ally (`+1d6` button on their next roll). Returns to you **locked** after use."
            ),
            accent_color=discord.Color.random()
        )

        # Page 5: GM & Situational Rules
        page5 = discord.ui.Container(
            discord.ui.TextDisplay(content="## ⚖️ **Sentiment Guide: GM & Combat Reference**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=
                "**`/set_gm`**\n"
                "• Set or transfer the designated Game Master for the server.\n"
                "• The GM can mark/unmark characters as **NPCs** in `/set_attributes` (appends `(NPC)` to their display name).\n\n"
                "**Combat & Clashing**\n"
                "• If you Roll to Do against an opponent dyed the same color as your Swing, a **Clash** occurs!\n"
                "• Both sides Roll to Do. If the attacker wins, damage is doubled; if the defender wins, they immediately get a free reprise action!\n\n"
                "**Conflict Flow**\n"
                "• Each turn in a Conflict gives 1 Action and 1 Move. You can lock dice to Sprint for extra moves."
            ),
            accent_color=discord.Color.random()
        )

        paginator = ButtonPaginator.create_standard_paginator(
            [page1, page2, page3, page4, page5],
            author_id=interaction.user.id,
            timeout=300.0
        )
        await paginator.start(interaction)