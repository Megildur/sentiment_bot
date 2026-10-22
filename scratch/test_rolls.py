"""Roll text: what Sentiment draws reads back the same, and so do rolls older versions posted.

Set Swing and Apply Support die read a roll's dice from its message, so a format
change that breaks reading would break every roll already in Discord.

    venv\\Scripts\\python.exe scratch\\test_rolls.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fakes import check, finish  # noqa: E402

from Source.Cogs.Dice.RollText import (  # noqa: E402
    HEADINGS, Die, SupportRoll, do_body, dye_body, parse_roll, recover_body,
)


def roundtrip() -> None:
    dice = [Die("Red", "Passion", 5, 3, True), Die("Blue", "None", 3), Die("Grey", "Old *Grey*".replace("*", ""), 6)]
    support = [SupportRoll("Blue", "Corin", 4)]
    state = parse_roll(HEADINGS["dye"] + "\n" + dye_body("Aria (NPC)", dice, support))
    check(state.kind == "dye" and state.display_name == "Aria (NPC)" and state.char_name == "Aria", f"dye name: {state.display_name}")
    check([(d.color, d.name, d.roll, d.is_swing) for d in state.dice] == [(d.color, d.name, d.roll, d.is_swing) for d in dice], f"dye dice: {state.dice}")
    check(state.dice[0].bonus == 3 and state.dice[1].bonus is None, "only the Swing die shows its bonus")
    check([(s.color, s.from_char, s.roll) for s in state.support] == [("Blue", "Corin", 4)], f"dye support: {state.support}")
    check("### Total: 21" in dye_body("Aria", dice, support), "dye total: 5 + 3 + 3 + 6 + 4")

    swing = ("Red", "Passion", 5, 3)
    state = parse_roll(HEADINGS["do"] + "\n" + do_body("Aria", 20, 0, swing, support))
    check(state.kind == "do" and state.d20 == 20 and state.swing == swing and state.display_name == "Aria", f"do: {state}")
    check(len(state.support) == 1 and state.support[0].roll == 4, "do support")
    state = parse_roll(HEADINGS["do"] + "\n" + do_body("Aria", 7, 2, None, []))
    check(state.swing is None and state.wild == 2 and state.d20 == 7, f"wild do: {state}")

    rec = [Die("Red", "Passion", 2, 3, True), Die("Grey", "None", 6, 0)]
    state = parse_roll(HEADINGS["recover"] + "\n" + recover_body("Aria", rec, (0, 10, 10)))
    check(state.kind == "recover" and state.hp == (0, 10, 10), f"recover hp: {state.hp}")
    check([(d.color, d.roll, d.bonus, d.is_swing) for d in state.dice] == [("Red", 2, 3, True), ("Grey", 6, 0, False)], f"recover dice: {state.dice}")


# Copied from what v1.0.5 posted.
OLD_DYE = (
    "## 🎲 **Roll to Dye**\n"
    "**Character:** *Aria*\n\n"
    "### 🎲 Rolled Attribute Dice\n"
    "• 🔴 **Red** (*Passion*): **5** (+3 Bonus) ⭐ **[SWING]**\n"
    "• 🔵 **Blue** (*None*): **3**\n"
    "• 🤝 Support Die (🔵 **Blue** from *Corin*): **4**\n"
    "\n### 📊 **Total Roll: 15**\n"
    "\n-# Support die from *Corin* used and returned locked."
)
OLD_DO = (
    "## 🎯 **Roll to Do**\n"
    "*Aria* rolled for 🔴 **Red** (*Passion*)\n\n"
    "• **d20 Die Roll:** **20** 💥 **CRITICAL HIT!**\n"
    "• **Active Swing:** **5** (+3 Attribute Bonus = **8**)\n"
    "• 🤝 Support Die (🔵 **Blue** from *Corin*): **+4**\n"
    "\n### 📊 **Total Roll: 32**"
)
OLDER_WILD = (
    "## 🎯 **Roll to Do**\n"
    "*Aria* rolled to do (Wild / Colorless)\n\n"
    "• **d20 Die Roll:** **11**\n"
    "• **1d6 Wild Roll:** **4**\n"
)
OLD_RECOVER = (
    "## 💚 **Roll to Recover**\n"
    "**Character:** *Aria*\n\n"
    "🔓 *All previously locked dice have been unlocked!*\n\n"
    "### 💚 Recovery Roll Breakdown\n"
    "• 🔴 **Red** (*Passion*): Die **2** + Bonus **+3** = **5** ⭐ **[NEW SWING]**\n"
    "• <:grey_circle:1551035782993551415> **Grey** (*None*): Die **6** + Bonus **+0** = **6**\n"
    "\n### ❤️ **HP Updated: `0 / 10` ➔ `10 / 10 HP`**\n"
    "• **Recovering from 0 HP:** Roll total (**11**) sets your new Current HP (`0` ➔ `10 / 10`)"
)


def old_formats() -> None:
    state = parse_roll(OLD_DYE)
    check(state.kind == "dye" and state.display_name == "Aria", "old dye name")
    check([(d.color, d.roll, d.bonus, d.is_swing) for d in state.dice] == [("Red", 5, 3, True), ("Blue", 3, None, False)], f"old dye dice: {state.dice}")
    check([(s.color, s.from_char, s.roll) for s in state.support] == [("Blue", "Corin", 4)], f"old dye support keeps its color: {state.support}")

    state = parse_roll(OLD_DO)
    check(state.kind == "do" and state.d20 == 20 and state.swing == ("Red", "Passion", 5, 3), f"old do: {state}")
    check(state.support and state.support[0].roll == 4, "old do support")

    state = parse_roll(OLDER_WILD)
    check(state.kind == "do" and state.wild == 4 and state.swing is None, f"older wild do: {state}")

    state = parse_roll(OLD_RECOVER)
    check(state.kind == "recover" and state.hp == (0, 10, 10), f"old recover hp: {state.hp}")
    check([(d.color, d.roll, d.bonus, d.is_swing) for d in state.dice] == [("Red", 2, 3, True), ("Grey", 6, 0, False)], f"old recover dice: {state.dice}")

    check(parse_roll("## 📜 Character card\n**Character:** *Aria*").kind == "", "a card isn't a roll")


roundtrip()
old_formats()
finish()
