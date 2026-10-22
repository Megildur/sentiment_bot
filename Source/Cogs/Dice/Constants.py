"""The ten Sentiment colors and the game's HP rules."""
from typing import Iterable, List, Optional, Sequence, Tuple, TypeVar

import discord

COLOR_ORDER = ["Red", "Yellow", "Green", "Blue", "Purple", "Orange", "Grey", "Black", "White", "Clear"]

COLOR_EMOJIS = {
    "Red": "🔴",
    "Yellow": "🟡",
    "Green": "🟢",
    "Blue": "🔵",
    "Purple": "🟣",
    "Orange": "🟠",
    "Grey": "<:grey_circle:1551035782993551415>",
    "Black": "⚫",
    "White": "⚪",
    "Clear": "💎"
}

# Form options can't show custom emoji, so Grey gets a stock one there.
MODAL_COLOR_EMOJIS = dict(COLOR_EMOJIS, Grey="🔘")

COLOR_DISCORD_COLORS = {
    "Red": discord.Color.red(),
    "Yellow": discord.Color.gold(),
    "Green": discord.Color.green(),
    "Blue": discord.Color.blue(),
    "Purple": discord.Color.purple(),
    "Orange": discord.Color.orange(),
    "Grey": discord.Color.light_grey(),
    "Black": discord.Color.from_rgb(45, 45, 45),
    "White": discord.Color.from_rgb(245, 245, 245),
    "Clear": discord.Color.teal()
}

Row = TypeVar("Row", bound=Sequence)


def color_emoji(color: str) -> str:
    return COLOR_EMOJIS.get(color, "⚪")


def sort_by_color(rows: Iterable[Row]) -> List[Row]:
    """Rows whose first value is a color, in the game's color order."""
    return sorted(rows, key=lambda row: COLOR_ORDER.index(row[0]) if row[0] in COLOR_ORDER else len(COLOR_ORDER))


def swing_accent(swing: Optional[Tuple]) -> Optional[discord.Colour]:
    """The accent for anything about a character: its swing's color, or none while colorless."""
    if swing and swing[0] in COLOR_DISCORD_COLORS:
        return COLOR_DISCORD_COLORS[swing[0]]
    return None


def hp_bracket(max_hp: int) -> dict:
    """What spending 1 Potential gives at this max HP (the level-up brackets)."""
    if max_hp < 20:
        return {"bracket": "10–19 (or <10)", "flat_gain": 5, "can_roll": True, "roll_label": "1d6 + 1", "roll_mod": 1}
    if max_hp < 40:
        return {"bracket": "20–39", "flat_gain": 3, "can_roll": True, "roll_label": "1d6", "roll_mod": 0}
    if max_hp < 60:
        return {"bracket": "40–59", "flat_gain": 2, "can_roll": True, "roll_label": "1d6 - 1", "roll_mod": -1}
    return {"bracket": "60+", "flat_gain": 1, "can_roll": False, "roll_label": "N/A (60+ Max HP)", "roll_mod": 0}
