"""Forms for /wound_die, /unwound_die, /lock_die, /unlock_die and /support."""
from typing import Dict, List, Tuple, Union

import discord

from Source.Utils.Pings import ping_mentions, with_ping
from .Characters import CARD, character_card, refresh_later
from .Common import DiceModal, dice_db, send_tracked, sync_color_role_later
from .Constants import color_emoji, swing_accent
from .Database import CharacterState

# action: (form title, option prefix, placeholder, database method, can it drop the swing?)
ACTIONS: Dict[str, Tuple[str, str, str, str, bool]] = {
    "wound": ("Wound an Attribute", "", "Pick the die to Wound", "wound_die", True),
    "unwound": ("Heal a Wounded die", "Heal ", "Pick the die to heal", "unwound_die", False),
    "lock": ("Lock a die", "", "Pick the die to Lock", "lock_die", True),
    "unlock": ("Unlock a die", "Unlock ", "Pick the die to Unlock", "unlock_die", False),
}


class DieStateModal(DiceModal):
    """Wound, heal, lock or unlock one die, then post the updated character card."""

    def __init__(self, action: str, state: CharacterState, colors: List[str]) -> None:
        title, prefix, placeholder, self.method, self.drops_swing = ACTIONS[action]
        super().__init__(title=f"{title}: {state.display_name}"[:45])
        self.char_name = state.char_name
        options = [
            discord.SelectOption(label=f"{prefix}{c} ({state.name(c)})"[:100], value=c, emoji=color_emoji(c))
            for c in colors
        ]
        self.color = discord.ui.Select(options=options, min_values=1, max_values=1, placeholder=placeholder)
        self.add_item(discord.ui.Label(text=f"Die for {state.display_name}"[:45], component=self.color))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        db = dice_db(interaction)
        user_id = interaction.user.id
        await getattr(db, self.method)(user_id, self.char_name, self.color.values[0])
        if self.drops_swing:
            sync_color_role_later(interaction, user_id)
        view = await character_card(db, user_id, self.char_name)
        message = await send_tracked(interaction, view, CARD, user_id, self.char_name, allowed_mentions=discord.AllowedMentions.none())
        refresh_later(interaction, user_id, self.char_name, exclude_message_id=message.id)


class SupportDieModal(DiceModal, title="Send a Support die"):
    def __init__(self, state: CharacterState, target: Union[discord.User, discord.Member], target_char: str, colors: List[str]) -> None:
        super().__init__()
        self.state = state
        self.target = target
        self.target_char = target_char
        options = [discord.SelectOption(label=f"{c} ({state.name(c)})"[:100], value=c, emoji=color_emoji(c)) for c in colors]
        self.color = discord.ui.Select(options=options, min_values=1, max_values=1, placeholder="Pick the die to send")
        self.add_item(discord.ui.Label(text=f"Support {target.display_name}"[:45], component=self.color))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        color = self.color.values[0]
        name = self.state.name(color)
        db = dice_db(interaction)
        await db.add_support_die(interaction.user.id, self.state.char_name, self.target.id, self.target_char, color, name)
        target_display = await db.get_char_display_name(self.target_char)
        sender_display = self.state.display_name

        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(
                "## 🤝 Support die sent\n"
                f"<@{interaction.user.id}> (*{sender_display}*) sent their {color_emoji(color)} **{color}** (*{name}*) die "
                f"to support <@{self.target.id}> (*{target_display}*).\n\n"
                f"• {target_display} gets an extra 1d6 on their next Roll to Dye or Roll to Do.\n"
                f"• Once it's used, the die goes back to {sender_display} Locked.\n"
                f"-# While they hold it, they're also Dyed {color}."
            ),
            accent_colour=swing_accent(self.state.swing),
        ))
        # The ally has a die to use, so they're pinged; the sender started it.
        await interaction.response.send_message(
            view=with_ping(view, users=[self.target.id]), allowed_mentions=ping_mentions(users=[self.target.id]),
        )
