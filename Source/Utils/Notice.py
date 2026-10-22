"""Short notices: errors, refusals and confirmations, all in one style."""

import logging
from typing import Optional

import discord

from Source.Utils import Theme

log = logging.getLogger(__name__)


def notice_view(
    title: str,
    body: str,
    color: Optional[discord.Colour] = Theme.ERROR,
    footer: Optional[str] = None,
) -> discord.ui.LayoutView:
    # A level-3 heading keeps notices quieter than real panels, which use level 2.
    items = [
        discord.ui.TextDisplay(f"### {title}"),
        discord.ui.TextDisplay(body),
    ]
    if footer:
        items.append(discord.ui.TextDisplay(f"-# {footer}"))
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(*items, accent_colour=color))
    return view


async def send_ephemeral(interaction: discord.Interaction, view: discord.ui.LayoutView) -> bool:
    """Reply privately whether or not the interaction was already answered.

    Returns False when Discord refused, after logging it.
    """
    try:
        if interaction.response.is_done():
            await interaction.followup.send(view=view, ephemeral=True)
        else:
            await interaction.response.send_message(view=view, ephemeral=True)
        return True
    except discord.HTTPException:
        log.warning("Could not send a private notice", exc_info=True)
        return False


async def notify(
    interaction: discord.Interaction, title: str, body: str, color: Optional[discord.Colour] = Theme.ERROR,
) -> bool:
    """A notice_view sent privately: the usual way to say why something didn't work."""
    return await send_ephemeral(interaction, notice_view(title, body, color))


async def send_deferred_error(interaction: discord.Interaction, view: discord.ui.LayoutView) -> bool:
    """A private notice after a public defer() of a slash command.

    The first follow-up after a public defer replaces the "thinking" message and
    can't be private, so the error would be posted for everyone. Deleting the
    placeholder first lets the follow-up be private.
    """
    try:
        await interaction.delete_original_response()
    except discord.HTTPException:
        log.debug("Could not delete the deferred response", exc_info=True)
    return await send_ephemeral(interaction, view)
