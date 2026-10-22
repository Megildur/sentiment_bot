"""Character panels: /set_attributes, /character_card and /hp max, and the forms they open.

Every button and menu here is a DiceItem (see Source/Utils/Views.py): it works on
the player the message belongs to and their active character, read fresh from
the database on every press.
"""
import logging
import random
import re
from typing import List, Optional, Tuple

import discord

from Source.Utils import Theme
from Source.Utils.Notice import notify
from Source.Utils.Views import disable_message_controls, message_text
from .Common import (
    DiceItem, DiceModal, dice_db, edit_in_place, lasting_view, owner_of, row, section, separator,
    spawn, sync_color_role_later,
)
from .Constants import COLOR_ORDER, MODAL_COLOR_EMOJIS, color_emoji, hp_bracket, swing_accent
from .RollText import parse_roll

log = logging.getLogger(__name__)

# How each panel is tracked in active_character_views (stored data; never rename).
ATTRIBUTES = "AttributeSetView"
CARD = "CharacterCardView"
MAX_HP = "ManageMaxHPView"
CREATE = "CreateCharacterView"
NO_CHARACTERS = "NoCharactersLeftView"
PANELS = (ATTRIBUTES, CARD, MAX_HP, CREATE, NO_CHARACTERS)

PLAYER_OR_GM = "Only the player this belongs to, or the GM, can use it."


def _char_options(chars: List[str], active: Optional[str] = None) -> Tuple[List[discord.SelectOption], bool]:
    options = [discord.SelectOption(label=c[:100], value=c[:100], default=c == active) for c in chars[:25]]
    if not options:
        return [discord.SelectOption(label="No characters yet", value="_none_")], True
    return options, False


def _attribute_line(color: str, name: str, bonus: int) -> str:
    return f"• {color_emoji(color)} **{color}** (*{name}*): +{bonus}"


# Who and which character a press is about


async def active_character(interaction: discord.Interaction, user_id: int) -> Optional[str]:
    """The player's active character, fixing the choice when it points at a deleted one."""
    db = dice_db(interaction)
    active = await db.get_selected_char(user_id)
    chars = await db.get_all_characters(user_id)
    if not chars:
        if active:
            # Clears what's left of a character whose last attribute was deleted.
            await db.completely_delete_character(user_id, active)
        return None
    if active not in chars:
        active = chars[0]
        await db.set_selected_char(user_id, active)
        refresh_later(interaction, user_id, active)
    return active


# Panels


async def attribute_panel(
    client: discord.Client, db, guild_id: Optional[int], user_id: int, char_name: str, note: Optional[str] = None,
) -> discord.ui.LayoutView:
    state = await db.get_character_state(user_id, char_name)
    chars = await db.get_all_characters(user_id)
    user = client.get_user(user_id)
    player = user.display_name if user else "Player"

    heading = f"## 🎭 Character setup\n**Active character:** *{state.display_name}*\n-# {player}'s active character. Every roll and command uses it."
    if note:
        heading += f"\n{note}"
    attributes = "\n".join(_attribute_line(c, state.name(c), b) for c, b in state.attributes) or "-# No Attributes yet."

    items: List[discord.ui.Item] = [
        discord.ui.TextDisplay(heading),
        separator(),
        discord.ui.TextDisplay(f"**Attributes**\n{attributes}"),
        row(EditAttributeSelect(state.attributes)),
        section("**Add an Attribute.**\n-# Up to 10 colors.", AddAttributeButton()),
        section("**Name an Attribute.**\n-# Give a color its title, like Red *Passion*.", NameAttributeButton()),
        section("**Delete an Attribute.**", DeleteAttributeButton()),
        separator(large=True),
        discord.ui.TextDisplay("**Switch active character**"),
        row(ChangeCharSelect(chars, char_name)),
        section("**New character.**\n-# Starts at 10 / 10 HP.", CreateCharacterButton()),
    ]
    if await db.is_gm(guild_id, user_id):
        is_npc = await db.is_npc(char_name)
        items.append(section(f"**NPC:** {'Yes' if is_npc else 'No'}\n-# Only this server's GM sees this.", ToggleNPCButton(is_npc)))
    items += [
        separator(large=True),
        discord.ui.TextDisplay("**Delete a character**"),
        row(DeleteCharSelect(chars)),
        section("-# Done here?", CloseMenuButton()),
    ]
    return lasting_view(*items, accent=swing_accent(state.swing))


def create_character_view() -> discord.ui.LayoutView:
    return lasting_view(
        discord.ui.TextDisplay(
            "## 🎭 Create a character\n"
            "You don't have a character yet. Press **Create character**, enter a name and check up to three colors "
            "(most characters start with three Attributes), then pick each one's bonus in the same order, top to bottom. "
            "New characters start at 10 / 10 HP."
        ),
        separator(large=True),
        row(CreateCharacterButton(), CloseMenuButton()),
        accent=Theme.BRAND,
    )


def no_characters_view(deleted_char: Optional[str] = None) -> discord.ui.LayoutView:
    deleted = f"**{deleted_char}** was deleted. " if deleted_char else ""
    return lasting_view(
        discord.ui.TextDisplay(f"## No characters left\n{deleted}Create a new character to keep playing."),
        separator(large=True),
        row(CreateCharacterButton(), CloseMenuButton()),
        accent=Theme.MUTED,
    )


def confirm_delete_view(char_name: str) -> discord.ui.LayoutView:
    # ConfirmDeleteButton reads the name back from "delete **name**".
    return lasting_view(
        discord.ui.TextDisplay(
            f"## Delete {char_name}?\n"
            f"This will permanently delete **{char_name}**: its Attributes, Swing, HP and dice. It can't be undone."
        ),
        separator(large=True),
        row(CancelDeleteButton(), ConfirmDeleteButton()),
        accent=Theme.ERROR,
    )


def pick_active_view(chars: List[str], deleted_char: str) -> discord.ui.LayoutView:
    return lasting_view(
        discord.ui.TextDisplay(f"## Pick your active character\n**{deleted_char}** was deleted. Pick which character to play now."),
        separator(large=True),
        row(NewActiveCharSelect(chars)),
        accent=Theme.BRAND,
    )


def hp_status(current_hp: int, max_hp: int, all_wounded: bool) -> str:
    status = f"`{current_hp} / {max_hp}`"
    if current_hp > 0:
        return status
    if all_wounded:
        return status + " · Every Attribute is Wounded: by the rules, your character dies."
    return status + " · You take a Wound: run `/roll_to_recover`, then `/wound_die`."


async def character_card(db, user_id: int, char_name: str) -> discord.ui.LayoutView:
    state = await db.get_character_state(user_id, char_name)
    current_hp, max_hp = await db.get_hp(user_id, char_name)
    chars = await db.get_all_characters(user_id)

    if state.swing:
        color, value = state.swing
        bonus = state.bonus(color)
        swing_text = f"{color_emoji(color)} **{color}** (*{state.name(color)}*): die **{value}** + bonus **{bonus}** = **{value + bonus}**"
    else:
        swing_text = "None"

    attribute_lines = []
    for color, bonus in state.attributes:
        tags = [t for t, on in (("Swing", state.swing and state.swing[0] == color), ("Locked", color in state.locked), ("Wounded", color in state.wounded)) if on]
        attribute_lines.append(_attribute_line(color, state.name(color), bonus) + "".join(f" · *{t}*" for t in tags))

    def dice_list(colors: List[str]) -> str:
        return ", ".join(f"{color_emoji(c)} **{c}**" for c in colors) or "None"

    all_wounded = bool(state.attributes) and len(state.wounded) >= len(state.attributes)
    return lasting_view(
        discord.ui.TextDisplay(
            "## 📜 Character card\n"
            f"**Player:** <@{user_id}>\n"
            f"**Character:** *{state.display_name}*\n"
            f"**HP:** {hp_status(current_hp, max_hp, all_wounded)}"
        ),
        separator(),
        discord.ui.TextDisplay(
            f"**Swing:** {swing_text}\n\n"
            f"**Attributes**\n" + ("\n".join(attribute_lines) or "-# No Attributes yet.") + "\n\n"
            f"**Locked:** {dice_list(state.locked)}\n"
            f"**Wounded:** {dice_list(state.wounded)}"
        ),
        separator(large=True),
        discord.ui.TextDisplay("**Switch active character**"),
        row(ChangeCardCharSelect(chars, char_name)),
        separator(large=True),
        row(ManageMaxHPButton(), CloseMenuButton()),
        accent=swing_accent(state.swing),
    )


async def max_hp_panel(db, user_id: int, char_name: str, note: Optional[str] = None) -> discord.ui.LayoutView:
    current_hp, max_hp = await db.get_hp(user_id, char_name)
    display_name = await db.get_char_display_name(char_name)
    swing = await db.get_swing(user_id, char_name)
    bracket = hp_bracket(max_hp)

    heading = f"## ❤️ Max HP\n**Character:** *{display_name}*\n**HP:** `{current_hp} / {max_hp}`"
    if note:
        heading += f"\n\n{note}"
    roll_text = f"**Or roll for it:** {bracket['roll_label']} Max HP." if bracket["can_roll"] else "**Or roll for it:** not at 60+ Max HP."
    return lasting_view(
        discord.ui.TextDisplay(heading),
        discord.ui.TextDisplay("-# Spending 1 Potential raises Max HP, and current HP goes up by the same amount."),
        separator(),
        section(f"**Spend Potential:** +{bracket['flat_gain']} Max HP.\n-# Your bracket: {bracket['bracket']} Max HP.", FlatHPButton(bracket)),
        section(roll_text, RollHPButton(bracket)),
        section("**Custom:** add, subtract or set an exact Max HP.", CustomMaxHPButton()),
        discord.ui.TextDisplay("-# Brackets: 10–19 Max HP: +5 or 1d6 + 1 · 20–39: +3 or 1d6 · 40–59: +2 or 1d6 - 1 · 60+: +1"),
        separator(large=True),
        row(BackToCardButton(), CloseMenuButton()),
        accent=swing_accent(swing),
    )


def hp_result_view(
    display_name: str, action: str, amount: int, old_hp: int, new_hp: int, max_hp: int,
    total_attrs: int = 0, wounded_count: int = 0, swing: Optional[tuple] = None,
) -> discord.ui.LayoutView:
    if action == "heal":
        lines = [
            "## 💚 Healed",
            f"**Character:** *{display_name}*",
            f"Healed **{new_hp - old_hp}** HP (from {amount}).",
            f"**HP:** `{old_hp} / {max_hp}` ➔ `{new_hp} / {max_hp}`",
        ]
        if new_hp == max_hp:
            lines.append("-# At Max HP.")
    else:
        lines = [
            "## 💥 Damage taken",
            f"**Character:** *{display_name}*",
            f"Lost **{old_hp - new_hp}** HP (from {amount}).",
            f"**HP:** `{old_hp} / {max_hp}` ➔ `{new_hp} / {max_hp}`",
        ]
        if new_hp == 0 and total_attrs > 0 and wounded_count >= total_attrs:
            lines += [
                "",
                "### 0 HP with every Attribute Wounded",
                "By the rules, your character dies. What death means depends on your campaign, so check with your GM.",
            ]
        elif new_hp == 0:
            lines += [
                "",
                "### 0 HP: you take a Wound",
                "1. Run `/roll_to_recover`. It Unlocks all your dice and rolls them for your new HP.",
                "2. Run `/wound_die` to Wound one Attribute.",
                "-# You may also Leave the Scene (flee or pass out). You still take the Wound and Roll to Recover, "
                "but take no more damage in this Scene or Conflict.",
            ]
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(discord.ui.TextDisplay("\n".join(lines)), accent_colour=swing_accent(swing)))
    return view


# Keeping a player's other messages in step


async def _fetch_message(client: discord.Client, channel_id: int, message_id: int) -> Optional[discord.Message]:
    channel = client.get_channel(channel_id)
    if channel is None:
        channel = await client.fetch_channel(channel_id)
    return await channel.fetch_message(message_id)


async def _panel_for(
    client: discord.Client, db, guild_id: Optional[int], view_type: str, user_id: int, char_name: str,
) -> Tuple[discord.ui.LayoutView, str, str]:
    if not char_name:
        if view_type == CREATE:
            return create_character_view(), CREATE, ""
        return no_characters_view(), NO_CHARACTERS, ""
    if view_type == CARD:
        return await character_card(db, user_id, char_name), CARD, char_name
    if view_type == MAX_HP:
        return await max_hp_panel(db, user_id, char_name), MAX_HP, char_name
    return await attribute_panel(client, db, guild_id, user_id, char_name), ATTRIBUTES, char_name


async def refresh_tracked_messages(client: discord.Client, db, user_id: int, char_name: str, exclude_message_id: Optional[int] = None) -> None:
    """Redraw a player's panels and cards for `char_name`, and grey out rolls for any other character.

    Rolls for `char_name` itself are skipped before fetching anything, so a player's
    hundredth roll doesn't cost a hundred API calls on every HP change.
    """
    for channel_id, message_id, view_type, tracked_char in await db.get_user_active_views(user_id):
        if message_id == exclude_message_id:
            continue
        is_panel = view_type in PANELS
        if not is_panel and char_name and tracked_char == char_name:
            continue
        try:
            message = await _fetch_message(client, channel_id, message_id)
            if is_panel:
                guild_id = message.guild.id if message.guild else None
                view, new_type, new_char = await _panel_for(client, db, guild_id, view_type, user_id, char_name)
                await message.edit(view=view, allowed_mentions=discord.AllowedMentions.none())
                await db.track_active_view(user_id, channel_id, message_id, new_type, new_char)
                continue
            roll_char = tracked_char or parse_roll(message_text(message)).char_name
            if char_name and roll_char == char_name:
                continue
            await disable_message_controls(message)
            await db.untrack_active_view(message_id)
        except discord.NotFound:
            await db.untrack_active_view(message_id)
        except discord.HTTPException:
            log.debug("Could not refresh message %s", message_id, exc_info=True)
        except Exception:
            log.exception("Refreshing message %s failed", message_id)


def refresh_later(interaction: discord.Interaction, user_id: int, char_name: str, exclude_message_id: Optional[int] = None) -> None:
    spawn(interaction, refresh_tracked_messages(interaction.client, dice_db(interaction), user_id, char_name, exclude_message_id))


async def show(interaction: discord.Interaction, view: discord.ui.LayoutView, view_type: str, user_id: int, char_name: str, *, changed: bool) -> None:
    """Replace the pressed message with `view`, and when the character changed, redraw the player's other messages."""
    await edit_in_place(interaction, view)
    if interaction.message is None:
        return
    await dice_db(interaction).track_active_view(user_id, interaction.channel_id, interaction.message.id, view_type, char_name)
    if changed:
        refresh_later(interaction, user_id, char_name, exclude_message_id=interaction.message.id)


async def show_attributes(interaction: discord.Interaction, user_id: int, char_name: Optional[str], note: Optional[str] = None, *, changed: bool = True) -> None:
    if not char_name:
        await show(interaction, no_characters_view(), NO_CHARACTERS, user_id, "", changed=changed)
        return
    view = await attribute_panel(interaction.client, dice_db(interaction), interaction.guild_id, user_id, char_name, note)
    await show(interaction, view, ATTRIBUTES, user_id, char_name, changed=changed)


async def owner_and_character(interaction: discord.Interaction) -> Tuple[int, Optional[str]]:
    owner = await owner_of(interaction)
    return owner, await active_character(interaction, owner)


# Forms


def _color_checkboxes(colors: List[str], default: Optional[str] = None) -> List[discord.CheckboxGroupOption]:
    return [discord.CheckboxGroupOption(label=f"{MODAL_COLOR_EMOJIS.get(c, '⚪')} {c}", value=c, default=c == default) for c in colors]


def _bonus_options(default: Optional[int] = None) -> List[discord.RadioGroupOption]:
    return [discord.RadioGroupOption(label=f"Bonus: +{i}", value=str(i), default=i == default) for i in range(10)]


def _attribute_select(attributes: List[Tuple[str, int]], placeholder: str) -> discord.ui.Select:
    options = [discord.SelectOption(label=f"{c} (+{b})", value=c, emoji=color_emoji(c)) for c, b in attributes]
    return discord.ui.Select(options=options, min_values=1, max_values=1, placeholder=placeholder)


class CreateCharacterModal(DiceModal, title="Create a character"):
    def __init__(self) -> None:
        super().__init__()
        self.name_input = discord.ui.TextInput(label="Character name", placeholder="Enter a name", max_length=50, required=True)
        self.add_item(self.name_input)
        self.colors = discord.ui.CheckboxGroup(options=_color_checkboxes(COLOR_ORDER), min_values=1, max_values=3)
        self.add_item(discord.ui.Label(text="Colors (up to 3)", component=self.colors))
        self.bonuses = []
        for place in ("1st", "2nd", "3rd"):
            bonus = discord.ui.RadioGroup(options=_bonus_options(), required=False)
            self.bonuses.append(bonus)
            self.add_item(discord.ui.Label(text=f"Bonus for the {place} checked color", component=bonus))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        char_name = self.name_input.value.strip()
        if not char_name:
            await notify(interaction, "Name needed", "Give your character a name.")
            return
        # Each bonus belongs to the color in the same place; a skipped one is +0.
        attributes = [(color, int(bonus.value or 0)) for color, bonus in zip(self.colors.values, self.bonuses)]
        db = dice_db(interaction)
        user_id = interaction.user.id
        await db.set_attributes(user_id, char_name, attributes)
        await db.set_selected_char(user_id, char_name)
        sync_color_role_later(interaction, user_id)

        if interaction.message is not None and interaction.message.flags.ephemeral:
            view = await attribute_panel(interaction.client, db, interaction.guild_id, user_id, char_name, "-# Character created.")
            await interaction.response.send_message(view=view)
            return
        await show_attributes(interaction, user_id, char_name, "-# Character created.")


class EditAttributeModal(DiceModal, title="Edit an Attribute"):
    def __init__(self, user_id: int, char_name: str, old_color: str, old_bonus: int) -> None:
        super().__init__()
        self.user_id, self.char_name, self.old_color = user_id, char_name, old_color
        self.color = discord.ui.CheckboxGroup(options=_color_checkboxes(COLOR_ORDER, old_color), min_values=1, max_values=1)
        self.add_item(discord.ui.Label(text=f"Editing {old_color}", component=self.color))
        self.bonus = discord.ui.RadioGroup(options=_bonus_options(old_bonus))
        self.add_item(discord.ui.Label(text="New bonus", component=self.bonus))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await dice_db(interaction).edit_attribute(self.user_id, self.char_name, self.old_color, self.color.values[0], int(self.bonus.value))
        await show_attributes(interaction, self.user_id, self.char_name)


class AddAttributeModal(DiceModal, title="Add an Attribute"):
    def __init__(self, user_id: int, char_name: str, current_colors: List[str]) -> None:
        super().__init__()
        self.user_id, self.char_name = user_id, char_name
        self.color = discord.ui.CheckboxGroup(options=_color_checkboxes([c for c in COLOR_ORDER if c not in current_colors]), min_values=1, max_values=1)
        self.add_item(discord.ui.Label(text="Color to add", component=self.color))
        self.bonus = discord.ui.RadioGroup(options=_bonus_options(0))
        self.add_item(discord.ui.Label(text="Bonus", component=self.bonus))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await dice_db(interaction).add_attribute(self.user_id, self.char_name, self.color.values[0], int(self.bonus.value))
        await show_attributes(interaction, self.user_id, self.char_name)


class DeleteAttributeModal(DiceModal, title="Delete an Attribute"):
    def __init__(self, user_id: int, char_name: str, attributes: List[Tuple[str, int]]) -> None:
        super().__init__()
        self.user_id, self.char_name = user_id, char_name
        self.color = _attribute_select(attributes, "Pick an Attribute to delete")
        self.add_item(discord.ui.Label(text="Attribute to delete", component=self.color))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        db = dice_db(interaction)
        await db.delete_attribute(self.user_id, self.char_name, self.color.values[0])
        if not await db.get_all_characters(self.user_id):
            await db.completely_delete_character(self.user_id, self.char_name)
            sync_color_role_later(interaction, self.user_id)
            await show(interaction, no_characters_view(self.char_name), NO_CHARACTERS, self.user_id, "", changed=True)
            return
        await show_attributes(interaction, self.user_id, self.char_name)


class NameAttributeModal(DiceModal, title="Name an Attribute"):
    def __init__(self, user_id: int, char_name: str, attributes: List[Tuple[str, int]]) -> None:
        super().__init__()
        self.user_id, self.char_name = user_id, char_name
        self.color = _attribute_select(attributes, "Pick an Attribute to name")
        self.add_item(discord.ui.Label(text="Attribute to name", component=self.color))
        self.name_input = discord.ui.TextInput(label="Attribute title", placeholder="For example Strength or Honor", max_length=50, required=True)
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await dice_db(interaction).set_attribute_name(self.user_id, self.char_name, self.color.values[0], self.name_input.value)
        await show_attributes(interaction, self.user_id, self.char_name)


class CustomMaxHPModal(DiceModal):
    def __init__(self, user_id: int, char_name: str, current_max: int) -> None:
        super().__init__(title=f"Max HP: {char_name}"[:45])
        self.user_id, self.char_name = user_id, char_name
        self.delta_input = discord.ui.TextInput(
            label="Add or subtract (for example +5 or -3)", placeholder="Leave blank to set an exact Max HP", required=False, max_length=10,
        )
        self.exact_input = discord.ui.TextInput(
            label=f"Or set an exact Max HP (now {current_max})", placeholder="For example 15", required=False, max_length=10,
        )
        self.add_item(self.delta_input)
        self.add_item(self.exact_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        delta_raw, exact_raw = self.delta_input.value.strip(), self.exact_input.value.strip()
        if not delta_raw and not exact_raw:
            await notify(interaction, "Nothing to change", "Enter an amount to add or subtract, or an exact Max HP.")
            return
        try:
            value = int(exact_raw or delta_raw)
        except ValueError:
            await notify(interaction, "Not a number", "Enter a whole number, like `+5`, `-2` or `20`.")
            return
        db = dice_db(interaction)
        if exact_raw:
            if value < 1:
                await notify(interaction, "Too low", "Max HP must be at least 1.")
                return
            old_cur, old_max, new_cur, new_max = await db.set_max_hp_value(self.user_id, self.char_name, value)
            label = f"**Max HP set to {new_max}.**"
        else:
            old_cur, old_max, new_cur, new_max = await db.adjust_max_hp(self.user_id, self.char_name, value)
            label = f"**Max HP changed by {new_max - old_max:+d}.**"
        note = f"{label} HP `{old_cur} / {old_max}` ➔ `{new_cur} / {new_max}`."
        view = await max_hp_panel(db, self.user_id, self.char_name, note)
        await show(interaction, view, MAX_HP, self.user_id, self.char_name, changed=True)


# Buttons and menus. custom_id strings are fixed: messages already posted use them.


class CreateCharacterButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"create_new_char"):
    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Create character", style=discord.ButtonStyle.success, custom_id="create_new_char"))

    async def run(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(CreateCharacterModal())


class CloseMenuButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"close_menu_button"):
    gm_allowed = True
    denied_text = PLAYER_OR_GM

    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Close menu", style=discord.ButtonStyle.secondary, custom_id="close_menu_button"))

    async def run(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await dice_db(interaction).untrack_active_view(interaction.message.id)
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            log.debug("Could not delete a closed menu", exc_info=True)


class ChangeCharSelect(DiceItem, discord.ui.DynamicItem[discord.ui.Select], template=r"change_char_select"):
    gm_allowed = True
    denied_text = PLAYER_OR_GM
    custom = "change_char_select"
    view_type = ATTRIBUTES

    def __init__(self, chars: List[str], active: str) -> None:
        options, disabled = _char_options(chars, active)
        super().__init__(discord.ui.Select(
            custom_id=self.custom, placeholder="Switch active character", options=options, disabled=disabled, min_values=1, max_values=1,
        ))

    async def run(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        db = dice_db(interaction)
        owner = await owner_of(interaction)
        new_active = self.item.values[0]
        if new_active not in await db.get_all_characters(owner):
            await notify(interaction, "Character not found", "That character was deleted. Pick another one.")
            return
        await db.set_selected_char(owner, new_active)
        sync_color_role_later(interaction, owner)
        if self.view_type == CARD:
            await show(interaction, await character_card(db, owner, new_active), CARD, owner, new_active, changed=True)
        else:
            await show_attributes(interaction, owner, new_active)


class ChangeCardCharSelect(ChangeCharSelect, template=r"change_card_char_select"):
    custom = "change_card_char_select"
    view_type = CARD


class NewActiveCharSelect(ChangeCharSelect, template=r"new_active_char_select"):
    # Shown right after the player deleted their active character; only they pick the next one.
    gm_allowed = False
    denied_text = "Only the person who opened this can use it."
    custom = "new_active_char_select"

    def __init__(self, chars: List[str]) -> None:
        options, disabled = _char_options(chars)
        discord.ui.DynamicItem.__init__(self, discord.ui.Select(
            custom_id=self.custom, placeholder="Pick your active character", options=options, disabled=disabled, min_values=1, max_values=1,
        ))


class EditAttributeSelect(DiceItem, discord.ui.DynamicItem[discord.ui.Select], template=r"edit_attribute_select"):
    gm_allowed = True
    denied_text = PLAYER_OR_GM

    def __init__(self, attributes: List[Tuple[str, int]]) -> None:
        options = [
            discord.SelectOption(label=f"Edit {c}", description=f"Bonus now: +{b}", value=c, emoji=color_emoji(c))
            for c, b in attributes
        ]
        disabled = not options
        options = options or [discord.SelectOption(label="No Attributes yet", value="_none_")]
        super().__init__(discord.ui.Select(
            custom_id="edit_attribute_select", placeholder="Edit an Attribute", options=options, disabled=disabled, min_values=1, max_values=1,
        ))

    async def run(self, interaction: discord.Interaction) -> None:
        owner, char_name = await owner_and_character(interaction)
        if not char_name:
            await notify(interaction, "No character", "This player has no characters left.")
            return
        color = self.item.values[0]
        attributes = dict(await dice_db(interaction).get_character_attributes(owner, char_name))
        if color not in attributes:
            await notify(interaction, "Attribute not found", f"**{char_name}** has no {color} Attribute any more.")
            return
        await interaction.response.send_modal(EditAttributeModal(owner, char_name, color, attributes[color]))


class AddAttributeButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"add_atrs_btn"):
    gm_allowed = True
    denied_text = PLAYER_OR_GM

    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Add Attribute", style=discord.ButtonStyle.primary, custom_id="add_atrs_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        owner, char_name = await owner_and_character(interaction)
        if not char_name:
            await notify(interaction, "No character", "This player has no characters left.")
            return
        colors = [c for c, _ in await dice_db(interaction).get_character_attributes(owner, char_name)]
        if len(colors) >= len(COLOR_ORDER):
            await notify(interaction, "All colors used", f"**{char_name}** already has all 10 Attributes.", Theme.ACCENT)
            return
        await interaction.response.send_modal(AddAttributeModal(owner, char_name, colors))


class NameAttributeButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"name_atrs_btn"):
    gm_allowed = True
    denied_text = PLAYER_OR_GM

    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Name Attribute", style=discord.ButtonStyle.secondary, custom_id="name_atrs_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        owner, char_name = await owner_and_character(interaction)
        attributes = await dice_db(interaction).get_character_attributes(owner, char_name) if char_name else []
        if not attributes:
            await notify(interaction, "No Attributes", "Add an Attribute before naming one.", Theme.ACCENT)
            return
        await interaction.response.send_modal(NameAttributeModal(owner, char_name, attributes))


class DeleteAttributeButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"delete_atrs_btn"):
    gm_allowed = True
    denied_text = PLAYER_OR_GM

    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Delete Attribute", style=discord.ButtonStyle.danger, custom_id="delete_atrs_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        owner, char_name = await owner_and_character(interaction)
        attributes = await dice_db(interaction).get_character_attributes(owner, char_name) if char_name else []
        if not attributes:
            await notify(interaction, "No Attributes", "There are no Attributes to delete.", Theme.ACCENT)
            return
        await interaction.response.send_modal(DeleteAttributeModal(owner, char_name, attributes))


class ToggleNPCButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"toggle_npc_btn"):
    denied_title = "GM only"
    denied_text = "Only this server's GM can mark a character as an NPC."

    def __init__(self, is_npc: bool) -> None:
        super().__init__(discord.ui.Button(
            label="Unmark NPC" if is_npc else "Mark as NPC",
            style=discord.ButtonStyle.danger if is_npc else discord.ButtonStyle.secondary,
            custom_id="toggle_npc_btn",
        ))

    async def allowed(self, interaction: discord.Interaction) -> bool:
        return await dice_db(interaction).is_gm(interaction.guild_id, interaction.user.id)

    async def run(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        owner, char_name = await owner_and_character(interaction)
        if char_name:
            await dice_db(interaction).toggle_npc(char_name)
        await show_attributes(interaction, owner, char_name)


class DeleteCharSelect(DiceItem, discord.ui.DynamicItem[discord.ui.Select], template=r"delete_char_select"):
    gm_allowed = True
    denied_text = PLAYER_OR_GM

    def __init__(self, chars: List[str]) -> None:
        options, disabled = _char_options(chars)
        super().__init__(discord.ui.Select(
            custom_id="delete_char_select", placeholder="Delete a character permanently", options=options, disabled=disabled, min_values=1, max_values=1,
        ))

    async def run(self, interaction: discord.Interaction) -> None:
        await edit_in_place(interaction, confirm_delete_view(self.item.values[0]))


_DELETE_TARGET = re.compile(r"delete \*\*([^*]+)\*\*", re.I)


class CancelDeleteButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"cancel_delete_char_btn"):
    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="cancel_delete_char_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        owner, char_name = await owner_and_character(interaction)
        await show_attributes(interaction, owner, char_name, changed=False)


class ConfirmDeleteButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"confirm_delete_char_btn"):
    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Delete character", style=discord.ButtonStyle.danger, custom_id="confirm_delete_char_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        match = _DELETE_TARGET.search(message_text(interaction.message))
        if not match:
            await notify(interaction, "Couldn't delete", "Sentiment couldn't tell which character to delete. Pick it again from `/set_attributes`.")
            return
        char_name = match.group(1).strip()
        db = dice_db(interaction)
        owner = await owner_of(interaction)
        await db.completely_delete_character(owner, char_name)
        sync_color_role_later(interaction, owner)

        chars = await db.get_all_characters(owner)
        active = await db.get_selected_char(owner)
        if not chars:
            await show(interaction, no_characters_view(char_name), NO_CHARACTERS, owner, "", changed=True)
        elif active not in chars:
            await edit_in_place(interaction, pick_active_view(chars, char_name))
        else:
            await show_attributes(interaction, owner, active)


class ManageMaxHPButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"manage_max_hp_btn"):
    gm_allowed = True
    denied_text = PLAYER_OR_GM

    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Manage Max HP", style=discord.ButtonStyle.primary, emoji="❤️", custom_id="manage_max_hp_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        owner, char_name = await owner_and_character(interaction)
        if not char_name:
            await show(interaction, no_characters_view(), NO_CHARACTERS, owner, "", changed=False)
            return
        await show(interaction, await max_hp_panel(dice_db(interaction), owner, char_name), MAX_HP, owner, char_name, changed=False)


class BackToCardButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"back_to_card_btn"):
    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Back to character card", style=discord.ButtonStyle.secondary, custom_id="back_to_card_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        owner, char_name = await owner_and_character(interaction)
        if not char_name:
            await show(interaction, no_characters_view(), NO_CHARACTERS, owner, "", changed=False)
            return
        await show(interaction, await character_card(dice_db(interaction), owner, char_name), CARD, owner, char_name, changed=False)


class FlatHPButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"pot_flat_hp_btn"):
    def __init__(self, bracket: dict) -> None:
        super().__init__(discord.ui.Button(label=f"Add {bracket['flat_gain']} Max HP", style=discord.ButtonStyle.success, custom_id="pot_flat_hp_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        owner, char_name = await owner_and_character(interaction)
        if not char_name:
            await notify(interaction, "No character", "You have no characters left.")
            return
        db = dice_db(interaction)
        _, max_hp = await db.get_hp(owner, char_name)
        gain = hp_bracket(max_hp)["flat_gain"]
        old_cur, old_max, new_cur, new_max = await db.adjust_max_hp(owner, char_name, gain)
        note = f"**Spent 1 Potential: +{gain} Max HP.** HP `{old_cur} / {old_max}` ➔ `{new_cur} / {new_max}`."
        await show(interaction, await max_hp_panel(db, owner, char_name, note), MAX_HP, owner, char_name, changed=True)


class RollHPButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"pot_roll_hp_btn"):
    def __init__(self, bracket: dict) -> None:
        can_roll = bracket["can_roll"]
        super().__init__(discord.ui.Button(
            label=f"Roll {bracket['roll_label']}" if can_roll else "No roll at 60+",
            style=discord.ButtonStyle.primary, emoji="🎲", disabled=not can_roll, custom_id="pot_roll_hp_btn",
        ))

    async def run(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        owner, char_name = await owner_and_character(interaction)
        if not char_name:
            await notify(interaction, "No character", "You have no characters left.")
            return
        db = dice_db(interaction)
        _, max_hp = await db.get_hp(owner, char_name)
        bracket = hp_bracket(max_hp)
        if not bracket["can_roll"]:
            await notify(interaction, "No roll at 60+", "At 60 or more Max HP, Potential only buys +1 Max HP.", Theme.ACCENT)
            return
        die = random.randint(1, 6)
        mod = bracket["roll_mod"]
        gained = max(0, die + mod)
        old_cur, old_max, new_cur, new_max = await db.adjust_max_hp(owner, char_name, gained)
        mod_text = f" {'+' if mod > 0 else '-'} {abs(mod)}" if mod else ""
        note = (
            f"**Spent 1 Potential: rolled 1d6 ({die}){mod_text} = +{gained} Max HP.** "
            f"HP `{old_cur} / {old_max}` ➔ `{new_cur} / {new_max}`."
        )
        await show(interaction, await max_hp_panel(db, owner, char_name, note), MAX_HP, owner, char_name, changed=True)


class CustomMaxHPButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"custom_adj_max_hp_btn"):
    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Change Max HP", style=discord.ButtonStyle.secondary, custom_id="custom_adj_max_hp_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        owner, char_name = await owner_and_character(interaction)
        if not char_name:
            await notify(interaction, "No character", "You have no characters left.")
            return
        _, max_hp = await dice_db(interaction).get_hp(owner, char_name)
        await interaction.response.send_modal(CustomMaxHPModal(owner, char_name, max_hp))


ITEMS = (
    CreateCharacterButton, CloseMenuButton, ChangeCharSelect, ChangeCardCharSelect, NewActiveCharSelect,
    EditAttributeSelect, AddAttributeButton, NameAttributeButton, DeleteAttributeButton, ToggleNPCButton,
    DeleteCharSelect, CancelDeleteButton, ConfirmDeleteButton, ManageMaxHPButton, BackToCardButton,
    FlatHPButton, RollHPButton, CustomMaxHPButton,
)
