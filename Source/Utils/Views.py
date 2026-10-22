"""Buttons and menus on messages that keep working forever, across restarts.

Every control on a lasting message is a DynamicItem whose template is its exact
custom_id. discord.py builds a fresh item from the message for every press, so:
- nothing is kept in memory per message (a view with timeout=None used to stay
  in memory until the next restart, for every message ever sent);
- a press after a restart runs the same code as one before it;
- two messages never share state. A view registered with bot.add_view is one
  object for every message, and Sentiment's used to carry one player's roll or
  server into the next press.

Three rules keep them registered (discord.py drops a DynamicItem class for every
message when a view holding one times out or is stopped):
- never send them in a private reply (discord.py gives those a 15-minute timeout);
- never give their view a timeout or call stop() on it;
- build a fresh view for every send or edit, never edit with one already sent.

The state a press needs comes from the message (who ran the command, its text,
the options picked) and the database, never from memory.
"""
import logging
from typing import Any, ClassVar, Optional

import discord

from Source.Utils.Notice import notify

log = logging.getLogger(__name__)


def message_invoker_id(message: Optional[discord.Message]) -> Optional[int]:
    """Who ran the command (or sent the form) that posted this message.

    Discord keeps this on the message, so a press can check it after a restart.
    """
    user = getattr(getattr(message, "interaction_metadata", None), "user", None)
    return user.id if user else None


def message_text(message: Any) -> str:
    """All the text in a message or view, top to bottom, one block per line."""
    texts = []

    def walk(item: Any) -> None:
        content = getattr(item, "content", None)
        if isinstance(content, str) and content:
            texts.append(content)
        for child in getattr(item, "children", None) or ():
            walk(child)
        accessory = getattr(item, "accessory", None)
        if accessory is not None:
            walk(accessory)

    for component in getattr(message, "components", None) or getattr(message, "children", None) or ():
        walk(component)
    return "\n".join(texts)


def find_component(message: Any, custom_id: str) -> Any:
    """The component with this custom_id in a message or view, or None."""
    def walk(items: Any) -> Any:
        for item in items or ():
            if getattr(item, "custom_id", None) == custom_id:
                return item
            found = walk(getattr(item, "children", None))
            if found is None and getattr(item, "accessory", None) is not None:
                found = walk([item.accessory])
            if found is not None:
                return found
        return None

    return walk(getattr(message, "components", None) or getattr(message, "children", None))


async def disable_message_controls(message: discord.Message) -> None:
    """Grey out every button and menu on a message, such as a roll for a character no longer active."""
    view = discord.ui.LayoutView.from_message(message, timeout=None)
    for item in view.walk_children():
        # Link buttons never expire on Discord's side, so leave them usable.
        if hasattr(item, "disabled") and not getattr(item, "url", None):
            item.disabled = True
    # Stopped before sending, so discord.py doesn't keep this copy in memory.
    view.stop()
    await message.edit(view=view)


class LastingItem:
    """Shared behavior for every control on a lasting message.

    Subclass it together with discord.ui.DynamicItem, with the exact custom_id as
    the template, and register the class with bot.add_dynamic_items in cog_load:

        class Close(LastingItem, discord.ui.DynamicItem[discord.ui.Button], template=r"close_menu_button"):
            def __init__(self):
                super().__init__(discord.ui.Button(label="Close menu", custom_id="close_menu_button"))

            async def run(self, interaction): ...

    Who may press: everyone when `owner_only` is False, otherwise the person who
    ran the command (override `allowed` to let others in). Errors become a private
    notice; discord.py would otherwise drop them and Discord would say
    "This interaction failed".
    """

    owner_only: ClassVar[bool] = True
    denied_title: ClassVar[str] = "Not your menu"
    denied_text: ClassVar[str] = "Only the person who opened this can use it."

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Item, match: Any) -> Any:
        # Wrap the control discord.py rebuilt from the message, options and picks included.
        self = cls.__new__(cls)
        discord.ui.DynamicItem.__init__(self, item)
        return self

    async def allowed(self, interaction: discord.Interaction) -> bool:
        if not self.owner_only:
            return True
        owner = message_invoker_id(interaction.message)
        return owner is None or owner == interaction.user.id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        try:
            if await self.allowed(interaction):
                return True
        except Exception:
            log.exception("Checking who may press %s failed", type(self).__name__)
            await notify(interaction, "Something went wrong", "That didn't go through. Try again in a moment.")
            return False
        await notify(interaction, self.denied_title, self.denied_text)
        return False

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            await self.run(interaction)
        except Exception:
            log.exception("%s failed", type(self).__name__)
            await notify(interaction, "Something went wrong", "That didn't go through. Try again in a moment.")

    async def run(self, interaction: discord.Interaction) -> None:
        raise NotImplementedError
