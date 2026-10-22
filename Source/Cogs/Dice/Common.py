"""What every Dice panel, roll and form shares: who owns a message, and how a press answers."""
import logging
from typing import TYPE_CHECKING, Any, ClassVar, Coroutine, Optional

import discord

from Source.Utils.Notice import notify
from Source.Utils.Permissions import server_of
from Source.Utils.Views import LastingItem, message_invoker_id
from .ColorRoles import sync_member_swing_color_role

if TYPE_CHECKING:
    from .Database import DiceDatabase

log = logging.getLogger(__name__)


def dice_db(interaction: discord.Interaction) -> "DiceDatabase":
    return interaction.client.get_cog("Dice").db


def spawn(interaction: discord.Interaction, coro: Coroutine[Any, Any, Any]) -> None:
    """Run work the reply doesn't wait for, such as giving a color role."""
    interaction.client.get_cog("Dice").background.spawn(coro)


async def owner_of(interaction: discord.Interaction) -> int:
    """The player a message belongs to: whoever ran the command that posted it."""
    owner = message_invoker_id(interaction.message)
    if owner:
        return owner
    if interaction.message is not None:
        tracked = await dice_db(interaction).get_tracked_view(interaction.message.id)
        if tracked:
            return tracked[0]
    return interaction.user.id


def sync_color_role_later(interaction: discord.Interaction, user_id: int) -> None:
    """Match a player's color role to their swing after the reply has gone out."""
    guild = server_of(interaction)
    if guild is not None:
        spawn(interaction, sync_member_swing_color_role(guild, user_id, dice_db(interaction)))


def lasting_view(*items: discord.ui.Item, accent: Optional[discord.Colour] = None) -> discord.ui.LayoutView:
    """One container in a view that never times out, as every message with DiceItems needs."""
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.Container(*items, accent_colour=accent))
    return view


def section(text: str, accessory: discord.ui.Item) -> discord.ui.Section:
    """One setting or action per line: its text, with the button that changes it beside it."""
    return discord.ui.Section(discord.ui.TextDisplay(text), accessory=accessory)


def row(*items: discord.ui.Item) -> discord.ui.ActionRow:
    return discord.ui.ActionRow(*items)


def separator(large: bool = False) -> discord.ui.Separator:
    return discord.ui.Separator(spacing=discord.SeparatorSpacing.large if large else discord.SeparatorSpacing.small)


async def edit_in_place(interaction: discord.Interaction, view: discord.ui.LayoutView) -> None:
    """Replace the message a button or form was used on."""
    if interaction.response.is_done():
        await interaction.edit_original_response(view=view)
    else:
        await interaction.response.edit_message(view=view)


async def send_tracked(
    interaction: discord.Interaction, view: discord.ui.LayoutView, view_type: str, user_id: int, char_name: str, **kwargs: Any,
) -> discord.Message:
    """Post a public message about a character and remember it, so it updates when the character changes."""
    if interaction.response.is_done():
        message = await interaction.followup.send(view=view, **kwargs)
    else:
        await interaction.response.send_message(view=view, **kwargs)
        message = await interaction.original_response()
    await dice_db(interaction).track_active_view(user_id, interaction.channel_id, message.id, view_type, char_name)
    return message


class DiceItem(LastingItem):
    """A control on a player's message. `gm_allowed` lets the server's GM use it on any player's message."""

    gm_allowed: ClassVar[bool] = False

    async def allowed(self, interaction: discord.Interaction) -> bool:
        if not self.owner_only or interaction.user.id == await owner_of(interaction):
            return True
        return self.gm_allowed and await dice_db(interaction).is_gm(interaction.guild_id, interaction.user.id)


class DiceModal(discord.ui.Modal):
    """A form. Errors become a private notice instead of Discord's "Something went wrong"."""

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log.error("Form %s failed", type(self).__name__, exc_info=error)
        await notify(interaction, "Something went wrong", "That didn't go through. Try again in a moment.")
