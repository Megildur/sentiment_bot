"""Roll messages (/roll_to_dye, /roll_to_do, /roll_to_recover) and their buttons.

A roll's dice are read back from its own text (RollText.parse_roll), so a press
works the same before and after a restart.
"""
import logging
import random
from typing import List, NamedTuple, Optional

import discord

from Source.Utils import Theme
from Source.Utils.Notice import notify
from Source.Utils.Permissions import server_of
from Source.Utils.Views import disable_message_controls, message_text
from .Characters import refresh_later
from .ColorRoles import assign_swing_color_role
from .Common import DiceItem, DiceModal, dice_db, edit_in_place, lasting_view, owner_of, row, separator, spawn, sync_color_role_later
from .Constants import color_emoji, swing_accent
from .RollText import (
    HEADINGS, VIEW_TYPES, Die, RollState, SupportRoll, do_body, dye_body, parse_roll, recover_body, with_swing,
)

log = logging.getLogger(__name__)


def _roll_view(kind: str, body: str, accent: Optional[discord.Colour], buttons: List[discord.ui.Item]) -> discord.ui.LayoutView:
    items: List[discord.ui.Item] = [discord.ui.TextDisplay(HEADINGS[kind]), separator(), discord.ui.TextDisplay(body)]
    if buttons:
        items += [separator(large=True), row(*buttons)]
    return lasting_view(*items, accent=accent)


def _swing_of(dice: List[Die]) -> Optional[tuple]:
    return next(((d.color, d.roll) for d in dice if d.is_swing), None)


def dye_view(display_name: str, dice: List[Die], support: List[SupportRoll], support_waiting: bool) -> discord.ui.LayoutView:
    buttons: List[discord.ui.Item] = [SetSwingButton()]
    if support_waiting:
        buttons.append(ApplySupportDieButton())
    return _roll_view("dye", dye_body(display_name, dice, support), swing_accent(_swing_of(dice)), buttons)


def do_view(display_name: str, d20: int, wild: int, swing: Optional[tuple], support: List[SupportRoll], support_waiting: bool) -> discord.ui.LayoutView:
    buttons: List[discord.ui.Item] = [ApplySupportDieButton()] if support_waiting else []
    return _roll_view("do", do_body(display_name, d20, wild, swing, support), swing_accent(swing), buttons)


def recover_view(display_name: str, dice: List[Die], hp: tuple) -> discord.ui.LayoutView:
    buttons: List[discord.ui.Item] = [SetSwingButton()] if dice else []
    return _roll_view("recover", recover_body(display_name, dice, hp), swing_accent(_swing_of(dice)), buttons)


class RollPress(NamedTuple):
    owner: int
    char_name: str
    roll: RollState


async def roll_press(interaction: discord.Interaction) -> Optional[RollPress]:
    """Read the pressed roll, or explain why it can't change and return None.

    A roll only changes while its character is still the player's active one;
    otherwise its buttons are greyed out.
    """
    db = dice_db(interaction)
    message = interaction.message
    owner = await owner_of(interaction)
    roll = parse_roll(message_text(message))
    tracked = await db.get_tracked_view(message.id)
    roll_char = (tracked[2] if tracked else "") or roll.char_name
    active = await db.get_selected_char(owner)
    if roll_char and active and roll_char != active:
        await notify(interaction, "Not the active character", f"This roll is for **{roll_char}**, but the active character is now **{active}**.", Theme.ACCENT)
        try:
            await disable_message_controls(message)
        except discord.HTTPException:
            log.debug("Could not grey out an old roll", exc_info=True)
        await db.untrack_active_view(message.id)
        return None
    char_name = roll_char or active
    if not roll.kind or not char_name:
        await notify(interaction, "Can't read this roll", "Sentiment couldn't read this roll. Roll again to use its buttons.")
        return None
    await db.track_active_view(owner, interaction.channel_id, message.id, VIEW_TYPES[roll.kind], char_name)
    return RollPress(owner, char_name, roll)


class SetSwingModal(DiceModal, title="Choose your Swing"):
    def __init__(self, press: RollPress, choices: List[Die]) -> None:
        super().__init__()
        self.press = press
        self.choices = choices
        options = [
            discord.SelectOption(label=f"{d.color} (rolled {d.roll}, bonus +{d.bonus or 0})", value=d.color, emoji=color_emoji(d.color))
            for d in choices
        ]
        self.color = discord.ui.Select(options=options, min_values=1, max_values=1, placeholder="Pick the Attribute to become your Swing")
        self.add_item(discord.ui.Label(text="Swing Attribute", component=self.color))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        owner, char_name, _ = self.press
        color = self.color.values[0]
        die = next(d for d in self.choices if d.color == color)
        db = dice_db(interaction)
        await db.set_swing(owner, char_name, color, die.roll)

        # Read the message again: the GM may have applied a support die since the form opened.
        roll = parse_roll(message_text(interaction.message))
        display_name = roll.display_name or char_name
        dice = with_swing(self.choices, color)
        if roll.kind == "recover":
            if roll.hp:
                hp = roll.hp
            else:
                current_hp, max_hp = await db.get_hp(owner, char_name)
                hp = (current_hp, current_hp, max_hp)
            view = recover_view(display_name, dice, hp)
        else:
            waiting = await db.get_pending_support_dice(owner, char_name)
            view = dye_view(display_name, dice, roll.support, bool(waiting))
        await edit_in_place(interaction, view)

        guild = server_of(interaction)
        if guild is not None:
            spawn(interaction, assign_swing_color_role(guild, owner, db, color))
        refresh_later(interaction, owner, char_name)


class SetSwingButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"set_swing_btn"):
    gm_allowed = True
    denied_text = "Only the player who rolled, or the GM, can change this roll."

    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Set Swing", style=discord.ButtonStyle.primary, custom_id="set_swing_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        press = await roll_press(interaction)
        if press is None:
            return
        if press.roll.kind not in ("dye", "recover"):
            await notify(interaction, "No Swing here", "Only Roll to Dye and Roll to Recover set a Swing.", Theme.ACCENT)
            return
        # A Roll to Dye line shows the bonus only for the swing die; the rest come from the character.
        bonuses = dict(await dice_db(interaction).get_character_attributes(press.owner, press.char_name))
        choices = [Die(d.color, d.name, d.roll, d.bonus if d.bonus is not None else bonuses.get(d.color, 0)) for d in press.roll.dice]
        if not choices:
            await notify(interaction, "No dice", "This roll has no dice to pick a Swing from.", Theme.ACCENT)
            return
        await interaction.response.send_modal(SetSwingModal(press, choices))


class ApplySupportDieButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"apply_support_btn"):
    gm_allowed = True
    denied_text = "Only the player who rolled, or the GM, can change this roll."

    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Apply Support die (+1d6)", style=discord.ButtonStyle.success, custom_id="apply_support_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        press = await roll_press(interaction)
        if press is None:
            return
        owner, char_name, roll = press
        if roll.kind not in ("dye", "do"):
            await notify(interaction, "No Support here", "Support dice go on Roll to Dye and Roll to Do.", Theme.ACCENT)
            return
        db = dice_db(interaction)
        waiting = await db.get_pending_support_dice(owner, char_name)
        if not waiting:
            await notify(interaction, "No Support dice", f"No one has sent **{char_name}** a Support die.", Theme.ACCENT)
            return

        await interaction.response.defer()
        lent = waiting[0]
        await db.consume_support_die(lent["share_user_id"], lent["share_char_name"], owner, char_name, lent["attribute"])
        support = roll.support + [SupportRoll(lent["attribute"], lent["share_char_name"], random.randint(1, 6), lent["share_user_id"])]
        display_name = roll.display_name or char_name
        if roll.kind == "dye":
            view = dye_view(display_name, roll.dice, support, len(waiting) > 1)
        else:
            view = do_view(display_name, roll.d20, roll.wild, roll.swing, support, len(waiting) > 1)
        await edit_in_place(interaction, view)
        # The die goes back locked; if it was the lender's swing, they lose that color role.
        sync_color_role_later(interaction, lent["share_user_id"])


ITEMS = (SetSwingButton, ApplySupportDieButton)
