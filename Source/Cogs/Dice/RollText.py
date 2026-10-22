"""Roll messages as text: drawing them, and reading them back when a button is pressed.

A roll's dice live only in its message, so Set swing and Apply support die read
them back from the text with parse_roll. Change a line format only together with
its pattern here, and keep the old format readable: messages already posted in
Discord still use it. scratch/test_rolls.py checks both directions and the
formats older versions posted.
"""
import re
from dataclasses import dataclass, field, replace
from typing import List, Optional, Tuple

from .Constants import COLOR_ORDER, color_emoji

HEADINGS = {
    "dye": "## 🎲 Roll to Dye",
    "do": "## 🎯 Roll to Do",
    "recover": "## 💚 Roll to Recover",
}

# The view_type each roll is tracked under in active_character_views (stored data; never rename).
VIEW_TYPES = {"dye": "RollToDyeView", "do": "RollToDoView", "recover": "RollToRecoverView"}


@dataclass
class Die:
    color: str
    name: str
    roll: int
    bonus: Optional[int] = None  # None when the line doesn't show it (a Roll to Dye die that isn't the swing)
    is_swing: bool = False


@dataclass
class SupportRoll:
    color: str
    from_char: str
    roll: int
    from_user_id: int = 0


@dataclass
class RollState:
    kind: str = ""  # "dye", "do" or "recover"; "" when the text isn't a roll
    display_name: str = ""
    dice: List[Die] = field(default_factory=list)
    support: List[SupportRoll] = field(default_factory=list)
    d20: int = 0
    wild: int = 0
    swing: Optional[Tuple[str, str, int, int]] = None  # Roll to Do: (color, name, die value, bonus)
    hp: Optional[Tuple[int, int, int]] = None  # Roll to Recover: (old, new, max)

    @property
    def char_name(self) -> str:
        return self.display_name.replace(" (NPC)", "").strip()


def _support_lines(support: List[SupportRoll], plus: str) -> List[str]:
    return [
        f"• 🤝 Support Die ({color_emoji(s.color)} **{s.color}** from *{s.from_char}*): **{plus}{s.roll}**"
        for s in support
    ]


def _support_notes(support: List[SupportRoll]) -> List[str]:
    if not support:
        return []
    return [""] + [f"-# Support die from *{s.from_char}* used and returned locked." for s in support]


def dye_total(dice: List[Die], support: List[SupportRoll]) -> int:
    # Only the swing die adds its bonus.
    return sum(d.roll + ((d.bonus or 0) if d.is_swing else 0) for d in dice) + sum(s.roll for s in support)


def dye_body(display_name: str, dice: List[Die], support: List[SupportRoll]) -> str:
    lines = [f"**Character:** *{display_name}*", "", "### Rolled dice"]
    for d in dice:
        line = f"• {color_emoji(d.color)} **{d.color}** (*{d.name}*): **{d.roll}**"
        if d.is_swing:
            line += f" (+{d.bonus or 0} Bonus) ⭐ **[SWING]**"
        lines.append(line)
    lines += _support_lines(support, "")
    lines += ["", f"### Total: {dye_total(dice, support)}"]
    return "\n".join(lines + _support_notes(support))


def do_total(d20: int, wild: int, swing: Optional[Tuple[str, str, int, int]], support: List[SupportRoll]) -> int:
    base = d20 + (swing[2] + swing[3] if swing else wild)
    return base + sum(s.roll for s in support)


def do_body(display_name: str, d20: int, wild: int, swing: Optional[Tuple[str, str, int, int]], support: List[SupportRoll]) -> str:
    critical = " · **Critical**" if d20 == 20 else ""
    if swing:
        color, name, value, bonus = swing
        lines = [
            f"*{display_name}* rolled for {color_emoji(color)} **{color}** (*{name}*)",
            "",
            f"• **d20 Die Roll:** **{d20}**{critical}",
            f"• **Active Swing:** **{value}** (+{bonus} Attribute Bonus = **{value + bonus}**)",
        ]
    else:
        lines = [
            f"*{display_name}* rolled to do (Wild / Colorless)",
            "",
            f"• **d20 Die Roll:** **{d20}**{critical}",
            f"• **1d6 Wild Roll:** **+{wild}**",
        ]
    lines += _support_lines(support, "+")
    lines += ["", f"### Total: {do_total(d20, wild, swing, support)}"]
    return "\n".join(lines + _support_notes(support))


def recover_body(display_name: str, dice: List[Die], hp: Tuple[int, int, int]) -> str:
    old_hp, new_hp, max_hp = hp
    lines = [f"**Character:** *{display_name}*", "All Locked dice are Unlocked.", "", "### Recovery roll"]
    total = sum(d.roll + (d.bonus or 0) for d in dice)
    for d in dice:
        bonus = d.bonus or 0
        mark = " ⭐ **[NEW SWING]**" if d.is_swing else ""
        lines.append(f"• {color_emoji(d.color)} **{d.color}** (*{d.name}*): Die **{d.roll}** + Bonus **+{bonus}** = **{d.roll + bonus}**{mark}")
    if not dice:
        lines.append("• *Every Attribute is Wounded.*")
    lines += ["", f"### HP updated: `{old_hp} / {max_hp}` ➔ `{new_hp} / {max_hp} HP`"]
    if not dice:
        lines.append("-# With every Attribute Wounded, you get 1 HP back.")
    elif old_hp <= 0:
        lines.append(f"-# At 0 HP, the roll total ({total}) becomes your HP, up to your Max HP.")
    else:
        lines.append(f"-# The roll total ({total}) is added to your HP, up to your Max HP.")
    return "\n".join(lines)


# Reading a roll back. Each pattern also accepts what older versions posted.

_KIND = re.compile(r"Roll to (Recover|Dye|Do)\b")
_CHARACTER = re.compile(r"\*\*Character:\*\*\s*\*([^*]+)\*")
_DO_CHARACTER = re.compile(r"^\*([^*]+)\*\s+rolled (?:for|to do)", re.M)
_DIE = re.compile(
    r"^•\s+[^\n*]*\*\*([A-Za-z]+)\*\*\s*\(\*([^*]*)\*\):\s*"
    r"(?:Die\s*\*\*(\d+)\*\*\s*\+\s*Bonus\s*\*\*([+-]?\d+)\*\*|\*\*(\d+)\*\*(?:\s*\(\+([+-]?\d+)\s+Bonus\))?)"
    r"([^\n]*)$",
    re.M,
)
_SUPPORT = re.compile(
    r"^•\s*🤝[^\n]*?(?:\((?:[^\n*]*?\*\*([A-Za-z]+)\*\*\s+)?from\s+\*([^*]+)\*\)|\(\*([^*]+)\*\))\s*:\s*(?:Die\s*)?\*\*\+?(\d+)\*\*",
    re.M,
)
_D20 = re.compile(r"d20 Die Roll:\*\*\s*\*\*(\d+)\*\*")
_WILD = re.compile(r"1d6 Wild Roll:\*\*\s*\*\*\+?(\d+)\*\*")
_DO_SWING = re.compile(r"rolled for \S+ \*\*([A-Za-z]+)\*\* \(\*([^*]*)\*\)")
_DO_SWING_VALUES = re.compile(r"Active Swing:\*\*\s*\*\*(\d+)\*\*\s*\(\+?(-?\d+)\s+Attribute Bonus")
_HP = re.compile(r"HP updated:\s*`(\d+)\s*/\s*(\d+)`\s*➔\s*`(\d+)\s*/\s*(\d+)\s*HP`", re.I)


def parse_roll(text: str) -> RollState:
    kind_match = _KIND.search(text)
    if not kind_match:
        return RollState()
    state = RollState(kind={"Recover": "recover", "Dye": "dye", "Do": "do"}[kind_match.group(1)])

    name = _DO_CHARACTER.search(text) if state.kind == "do" else _CHARACTER.search(text)
    state.display_name = name.group(1).strip() if name else ""

    for m in _DIE.finditer(text):
        color = m.group(1).capitalize()
        if color not in COLOR_ORDER:
            continue
        if m.group(3) is not None:
            roll, bonus = int(m.group(3)), int(m.group(4))
        else:
            roll = int(m.group(5))
            bonus = int(m.group(6)) if m.group(6) is not None else None
        rest = m.group(7)
        state.dice.append(Die(color, m.group(2).strip() or "None", roll, bonus, "⭐" in rest or "SWING" in rest))

    for m in _SUPPORT.finditer(text):
        from_char = (m.group(2) or m.group(3) or "").strip()
        state.support.append(SupportRoll((m.group(1) or "Support").capitalize(), from_char, int(m.group(4))))

    if state.kind == "do":
        d20 = _D20.search(text)
        wild = _WILD.search(text)
        swing = _DO_SWING.search(text)
        values = _DO_SWING_VALUES.search(text)
        state.d20 = int(d20.group(1)) if d20 else 1
        state.wild = int(wild.group(1)) if wild else 0
        if swing and values:
            state.swing = (swing.group(1), swing.group(2), int(values.group(1)), int(values.group(2)))

    if state.kind == "recover":
        hp = _HP.search(text)
        if hp:
            state.hp = (int(hp.group(1)), int(hp.group(3)), int(hp.group(2)))
    return state


def with_swing(dice: List[Die], color: str) -> List[Die]:
    """The same dice with `color` marked as the swing."""
    return [replace(d, is_swing=d.color == color) for d in dice]
