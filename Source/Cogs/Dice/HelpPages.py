"""/help: the guide to Sentiment's commands and rules, one page at a time.

Anyone can turn the pages, and they keep working after a restart: the page
number is read from the message's "Page X/Y" label. What the pages say about
the game follows the rulebook summary in AGENTS.md.
"""
import re
from typing import List, Tuple

import discord

from Source.Utils import Theme
from Source.Utils.Views import LastingItem, find_component
from .Common import lasting_view, row, separator

PAGES: List[Tuple[str, str]] = [
    (
        "## 📜 Characters",
        "A new character has three Attributes (three differently colored d6), **10 HP** and **6 Speed**. "
        "Each Attribute has a title you choose, like Red *Passion* or Blue *Focus*, and a bonus "
        "(its Attribute Level) from +0 to +9.\n\n"
        "**`/set_attributes`**\n"
        "• Create a character, or open your active character's setup.\n"
        "• Add, edit, title or delete Attributes. Switch your active character, or delete one.\n\n"
        "**`/change_active_character`**\n"
        "• Switch which character you're playing. Every roll and command uses your active character.\n\n"
        "**`/character_card`**\n"
        "• Your character sheet: HP, Swing, Attributes, Locked and Wounded dice.\n"
        "• Switch characters from it, or open **Manage Max HP**.",
    ),
    (
        "## 🎲 Core rolls",
        "**`/roll_to_dye`**: when something happens to you\n"
        "• Rolls every Attribute die that isn't Wounded, Locked or sent as Support. Beat what triggered it to succeed.\n"
        "• **Set Swing** makes one rolled die your Swing: its result plus its bonus. While it's your Swing you're "
        "Dyed its Color, and it isn't rerolled: later Rolls to Dye add its saved result plus its bonus.\n"
        "• Rolling to Dye just to see where your character's head is (a Roll to Reflect) works the same way.\n\n"
        "**`/roll_to_do`**: when you act on the world\n"
        "• **1d20 + your Swing**. With no Swing, **1d20 + 1d6**: a Wild roll, Dyed no Color.\n"
        "• Beat the target's Roll to Dye; a tie goes to the one who Rolled to Dye. A hit deals damage equal to your "
        "Swing (or the d6 when Wild).\n"
        "• A 20 on the d20 is a **Critical**: damage, or the effect, doubles.\n\n"
        "**`/roll_to_recover`**: after a Rest, or when you take a Wound\n"
        "• Unlocks all your dice, then rolls your Unwounded dice and adds all their bonuses.\n"
        "• At 0 HP the total becomes your HP; above 0 it's added to your HP. Either way it stops at Max HP.\n"
        "• With every Attribute Wounded, you get 1 HP back. You may set a new Swing from this roll.",
    ),
    (
        "## ❤️ HP and leveling",
        "**`/hp damage <amount>`** and **`/hp heal <amount>`**\n"
        "• Take damage down to 0, or heal up to Max HP.\n\n"
        "**At 0 HP you take a Wound**\n"
        "1. Run **`/roll_to_recover`**: it Unlocks all your dice and sets your new HP.\n"
        "2. Run **`/wound_die`** to Wound one Attribute. It sits out until it heals.\n"
        "• When you're Wounded you may also **Leave the Scene** (flee or pass out): you take no more damage in this Scene or Conflict.\n"
        "• At 0 HP with every Attribute Wounded, your character dies.\n\n"
        "**`/hp max`**, or **Manage Max HP** on `/character_card`\n"
        "You gain a Level at creation and after each session, and each Level gives 1 Potential. Spend Potential on Max HP:\n"
        "  - `10–19` Max HP (or less): **+5**, or roll **1d6 + 1**\n"
        "  - `20–39`: **+3**, or roll **1d6**\n"
        "  - `40–59`: **+2**, or roll **1d6 - 1**\n"
        "  - `60+`: **+1**, no roll\n"
        "• Raising Max HP raises current HP by the same amount. **Change Max HP** sets any value, for NPCs or buffs.",
    ),
    (
        "## 🔒 Dice states and Support",
        "**`/lock_die`** and **`/unlock_die`**\n"
        "• Lock any Attribute die to **Sprint** (move your Speed again) or **Tag a Prop** (use the scenery, usually +1d6).\n"
        "• Lock your Swing die to **Ignite** it: the Swing is spent, for a **Push** (+1d6 to a roll), a **Block** "
        "(take 1d6 less damage) or a **Multiply** (up to two more targets, rolled Wild).\n"
        "• Locked dice come back at the end of the Scene, at the start of your Turn in a Conflict, or with `/roll_to_recover`.\n\n"
        "**`/wound_die`** and **`/unwound_die`**\n"
        "• A Wound takes an Attribute out of play and Unlocks every Locked die. Any Attribute can be Wounded, even a Locked one.\n"
        "• Wounds heal between sessions, or when your GM says so.\n\n"
        "**`/drop_swing`**\n"
        "• Drop your Swing and become colorless. Your Swing color role is removed.\n\n"
        "**`/support`**\n"
        "• Send an ally one of your dice. They're Dyed its Color too, and get **Apply Support die (+1d6)** on their next roll. "
        "The die comes back to you Locked.",
    ),
    (
        "## 🎨 Swing color roles",
        "Your name in chat and the member list takes your active character's Swing color. All 10 colors work.\n\n"
        "**When it changes**\n"
        "• Setting a Swing in `/roll_to_dye` or `/roll_to_recover` gives you that color's role.\n"
        "• Losing your Swing (`/drop_swing`, Locking or Wounding the Swing die, or switching characters) removes it.\n\n"
        "**`/color_roles`**\n"
        "• **Set up roles** finds or creates the 10 color roles with their exact colors, then syncs every player.\n"
        "• **Sync my role** matches your role to your Swing, for a Swing set before the roles existed.\n"
        "• **Sync all players** updates everyone in the server at once.\n"
        "• The menus there pick your own role for any color.\n\n"
        "**Role order**\n"
        "• Discord colors a name with the member's **highest role that has a color**.\n"
        "• In Server Settings > Roles, put the color roles at the top, just under Sentiment's role.\n"
        "• Sentiment's role must be above every color role and have **Manage Roles**.\n"
        "• Keep other colored roles below the color roles, or their color shows instead.",
    ),
    (
        "## ⚖️ GM, Scenes and Conflicts",
        "**`/set_gm`**\n"
        "• Choose the GM. Members with Manage Server, and the current GM, can do this.\n"
        "• The GM can mark characters as **NPCs** in `/set_attributes`, and use any player's rolls and character panels.\n\n"
        "**Target numbers** (beat it to succeed)\n"
        "Very Easy 5 · Easy 10 · Normal 15 · Hard 20 · Very Hard 25 · Extreme 30\n\n"
        "**Clash**\n"
        "• Rolling to Do at someone Dyed your Color is a Clash: they Roll to Do instead of to Dye. If the attacker wins, "
        "damage doubles; if the defender wins, they act at once.\n\n"
        "**Conflicts**\n"
        "• Everyone Rolls to Dye for Initiative. Each Turn has 1 Action and 1 Move; Lock dice to Sprint for more Moves.\n"
        "• At the end of each Act, everyone Keeps their Swing or Rerolls it with a new Roll to Dye.",
    ),
]

_PAGE = re.compile(r"Page\s+(\d+)/\d+")


def help_view(page: int = 0) -> discord.ui.LayoutView:
    page = max(0, min(page, len(PAGES) - 1))
    heading, body = PAGES[page]
    last = len(PAGES) - 1
    indicator = discord.ui.Button(label=f"Page {page + 1}/{len(PAGES)}", style=discord.ButtonStyle.primary, disabled=True, custom_id="paginator_indicator")
    return lasting_view(
        discord.ui.TextDisplay(heading),
        separator(),
        discord.ui.TextDisplay(body),
        separator(large=True),
        row(HelpPageButton("prev", page == 0), HelpPageButton.wrap(indicator), HelpPageButton("next", page == last)),
        accent=Theme.INFO,
    )


class HelpPageButton(LastingItem, discord.ui.DynamicItem[discord.ui.Button], template=r"paginator_(prev|next|indicator)"):
    owner_only = False

    def __init__(self, step: str, disabled: bool) -> None:
        label, emoji = ("Previous", "◀️") if step == "prev" else ("Next", "▶️")
        super().__init__(discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, disabled=disabled, custom_id=f"paginator_{step}"))

    @classmethod
    def wrap(cls, button: discord.ui.Button) -> "HelpPageButton":
        # The page label is a disabled button; it's wrapped too, so the message holds
        # no control discord.py would keep in memory.
        self = cls.__new__(cls)
        discord.ui.DynamicItem.__init__(self, button)
        return self

    async def run(self, interaction: discord.Interaction) -> None:
        indicator = find_component(interaction.message, "paginator_indicator")
        match = _PAGE.search(getattr(indicator, "label", None) or "")
        current = int(match.group(1)) - 1 if match else 0
        step = {"paginator_prev": -1, "paginator_next": 1}.get(self.custom_id, 0)
        await interaction.response.edit_message(view=help_view(current + step))


ITEMS = (HelpPageButton,)
