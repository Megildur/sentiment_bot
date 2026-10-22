"""/set_gm: choosing the Game Master, who can mark NPCs and use any player's rolls and panels."""
import logging
import re
from typing import Union

import discord

from Source.Utils import Theme
from Source.Utils.Notice import notify
from Source.Utils.Permissions import member_has, require_member_permissions
from Source.Utils.Pings import ping_mentions, with_ping
from Source.Utils.Views import disable_message_controls, message_text
from .Common import DiceItem, dice_db, lasting_view, section

log = logging.getLogger(__name__)

# Reads the new GM back from the prompt; the first form is what older versions posted.
_NEW_GM = re.compile(r"(?:change the gm to|Make) <@!?(\d+)>", re.I)


async def may_choose_gm(interaction: discord.Interaction) -> bool:
    """Members with Manage Server, and the current GM, choose the GM. Says so to anyone else."""
    if member_has(interaction.user, "manage_guild") or await dice_db(interaction).is_gm(interaction.user.id):
        return True
    return await require_member_permissions(interaction, "manage_guild", or_also="be the GM", to="choose the GM")


async def announce_gm(interaction: discord.Interaction, new_gm: int) -> None:
    """Post that `new_gm` is the GM, pinging them unless they chose themselves."""
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(f"## ⚖️ New GM\n<@{new_gm}> is now the GM."),
        accent_colour=Theme.BRAND,
    ))
    ping = [new_gm] if new_gm != interaction.user.id else []
    await interaction.response.send_message(view=with_ping(view, users=ping), allowed_mentions=ping_mentions(users=ping))


async def set_gm(interaction: discord.Interaction, user: Union[discord.User, discord.Member]) -> None:
    if not await may_choose_gm(interaction):
        return
    db = dice_db(interaction)
    current = await db.get_gm()
    if current is not None and current != user.id:
        prompt = lasting_view(
            discord.ui.TextDisplay(f"## ⚖️ Change the GM?\n<@{current}> is the GM. Make <@{user.id}> the GM instead?"),
            section("-# Press to confirm.", ConfirmGMButton()),
            accent=Theme.ACCENT,
        )
        await interaction.response.send_message(view=prompt, allowed_mentions=discord.AllowedMentions.none())
        return
    await db.set_gm(user.id)
    await announce_gm(interaction, user.id)


class ConfirmGMButton(DiceItem, discord.ui.DynamicItem[discord.ui.Button], template=r"confirm_dm"):
    denied_text = "Only the person who ran `/set_gm` can confirm this."

    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Make GM", style=discord.ButtonStyle.success, custom_id="confirm_dm"))

    async def run(self, interaction: discord.Interaction) -> None:
        if not await may_choose_gm(interaction):
            return
        match = _NEW_GM.search(message_text(interaction.message))
        if not match:
            await notify(interaction, "Couldn't change the GM", "Sentiment couldn't tell who the new GM is. Run `/set_gm` again.")
            return
        new_gm = int(match.group(1))
        await dice_db(interaction).set_gm(new_gm)
        await announce_gm(interaction, new_gm)
        try:
            await disable_message_controls(interaction.message)
        except discord.HTTPException:
            log.debug("Could not grey out the GM prompt", exc_info=True)


ITEMS = (ConfirmGMButton,)
