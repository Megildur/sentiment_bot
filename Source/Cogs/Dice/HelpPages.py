from __future__ import annotations
import discord

def get_help_pages() -> list[discord.ui.Container]:
    page1 = discord.ui.Container(
        discord.ui.TextDisplay(content="## 📜 **Sentiment Guide: Characters & Setup**"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(content=
            "**`/set_attributes`**\n"
            "• Create a new character (automatically starts at **10 / 10 HP**) or open the character setup menu.\n"
            "• Add, edit, or delete attributes and set their levels (+0 to +9).\n"
            "• Give attributes custom titles (e.g. Red *'Passion'*, Blue *'Focus'*).\n"
            "• Switch active characters or delete characters.\n\n"
            "**`/change_active_character`**\n"
            "• Quickly switch which character you are currently playing.\n\n"
            "**`/character_card`**\n"
            "• View your character sheet: **Current / Max HP**, active Swing, attributes & bonuses, locked dice, and wounded dice.\n"
            "• Includes a dropdown to switch characters and the **❤️ Manage Max HP** button."
        ),
        accent_color=discord.Color.random()
    )

    page2 = discord.ui.Container(
        discord.ui.TextDisplay(content="## 🎲 **Sentiment Guide: Core Rolls**"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(content=
            "**`/roll_to_dye`**\n"
            "• Reactive / defensive roll when things happen to your character (dodging, resisting magic, enduring distress).\n"
            "• Rolls a d6 for each unwounded and unlocked attribute.\n"
            "• If a Swing is active, the swing die is not rerolled—its saved value and bonus are added.\n"
            "• Use **Set Swing** on the roll message to pick a new active Swing, or **Apply Support Die** to roll a shared die.\n\n"
            "**`/roll_to_do`**\n"
            "• Proactive roll to impact the world (attacks, skill checks, social actions).\n"
            "• With a Swing: rolls **1d20 + Swing** (die value + attribute bonus). Rolling a 20 on the d20 is a **Critical** (doubles damage/effect)!\n"
            "• Without a Swing: rolls **1d20 + 1d6 Wild** with no attribute bonus.\n\n"
            "**`/roll_to_recover`**\n"
            "• Used during a Rest or after sustaining a Wound to unlock all locked dice and automatically recover HP:\n"
            "  - **At `0 HP`**: Your roll total becomes your new Current HP (capped at Max HP).\n"
            "  - **Above `0 HP`**: Your roll total is added to your Current HP (capped at Max HP).\n"
            "  - **No unwounded dice left**: Restores **+1 HP**."
        ),
        accent_color=discord.Color.random()
    )

    page3 = discord.ui.Container(
        discord.ui.TextDisplay(content="## ❤️ **Sentiment Guide: Health (HP) & Leveling**"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(content=
            "**`/hp damage <amount>`**\n"
            "• Subtracts damage from your active character's Current HP (cannot drop below `0`).\n"
            "• **Hitting `0 HP` (Wound):** Displays a reminder to run **`/wound_die`** and **`/roll_to_recover`**, or choose to **Leave the Scene** (fleeing/passing out to avoid further damage in the current Scene/Conflict).\n"
            "• **All Dice Wounded + `0 HP`:** Displays a **Death / Leave the Scene** alert.\n\n"
            "**`/hp heal <amount>`**\n"
            "• Restores Current HP for other healing effects without changing your Max HP (capped at Max HP).\n\n"
            "**`/hp max` & `❤️ Manage Max HP` Button (on `/character_card`)**\n"
            "• Opens the Max HP submenu to increase/decrease Max HP (increasing Max HP also increases Current HP by the same amount).\n"
            "• **Spend Potential (Level-Up Brackets):**\n"
            "  - `10–19 Max HP`: **+5 HP** flat or roll **1d6 + 1**\n"
            "  - `20–39 Max HP`: **+3 HP** flat or roll **1d6**\n"
            "  - `40–59 Max HP`: **+2 HP** flat or roll **1d6 - 1**\n"
            "  - `60+ Max HP`: **+1 HP** flat\n"
            "• **Custom Adjust / Set:** Add/subtract any amount (`+5`, `-3`) or set an exact Max HP (great for NPCs or custom buffs)."
        ),
        accent_color=discord.Color.random()
    )

    page4 = discord.ui.Container(
        discord.ui.TextDisplay(content="## 🔒 **Sentiment Guide: Dice States & Support**"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(content=
            "**`/wound_die` & `/unwound_die`**\n"
            "• Wound an attribute die when hitting `0 HP` or pushing your character to the limit.\n"
            "• Wounding removes that die from rolls until healed and **automatically unlocks all locked dice**.\n"
            "• Use `/unwound_die` when wounds heal between sessions or from treatment.\n\n"
            "**`/lock_die` & `/unlock_die`**\n"
            "• Lock an unwounded die to use abilities (Sprint, Push, Block, Tag a Prop). Locking your Swing drops it.\n"
            "• Locked dice unlock at the start of your turn, end of a Scene, or when you `/roll_to_recover`.\n\n"
            "**`/drop_swing`**\n"
            "• Drop your active Swing to become colorless.\n"
            "• Automatically removes your swing color role so your chat name reverts to normal.\n\n"
            "**`/support`**\n"
            "• Pass an available attribute die to an ally (`+1d6` button on their next roll). Returns to you **locked** after use."
        ),
        accent_color=discord.Color.random()
    )

    page5 = discord.ui.Container(
        discord.ui.TextDisplay(content="## 🎨 **Sentiment Guide: Swing Color Roles & Name Colors**"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(content=
            "**Dynamic Swing Color Roles & Chat Name Colors**\n"
            "• Matches your username color in chat and the member list to your active character's Swing accent color (all 10 Sentiment colors supported).\n\n"
            "⚡ **Automatic Role Application & Dropping:**\n"
            "• **Automatic Grant:** Whenever you choose or change a Swing in `/roll_to_dye` or `/roll_to_recover`, your matching Discord color role is granted immediately!\n"
            "• **Automatic Removal:** Whenever you drop your Swing (`/drop_swing`, locking/wounding the swing die, or switching characters), all swing color roles are stripped immediately so your name reverts to normal!\n\n"
            "**`/color_roles` Command Actions**\n"
            "• **⚡ Auto-Setup Roles:** Scans server for matching color roles or creates missing ones with their exact accent colors, and immediately auto-syncs all active players!\n"
            "• **🔄 Sync My Role:** Manually refreshes your color role to match your active character's swing (useful if your swing was chosen before color roles were set up).\n"
            "• **👥 Sync All Players:** Bulk-syncs all campaign players in the server with their active character's Swing in one click!\n"
            "• **Role Picker:** Use dropdowns to customize or map custom roles for each color.\n\n"
            "⚠️ **Role Hierarchy Setup for Name Colors**\n"
            "• In Discord, your chat name color is determined by your **highest role that has a color**.\n"
            "• **Move all Color Roles to the top** of your server's role hierarchy (Server Settings ➔ Roles), positioned directly below the bot's role.\n"
            "• Ensure the **Bot's role** is higher than all color roles and has the **Manage Roles** permission enabled.\n"
            "• Ensure members do not have another colored role above the color roles, or Discord will display that role's color instead!"
        ),
        accent_color=discord.Color.gold()
    )

    page6 = discord.ui.Container(
        discord.ui.TextDisplay(content="## ⚖️ **Sentiment Guide: GM & Combat Reference**"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(content=
            "**`/set_gm`**\n"
            "• Set or transfer the designated Game Master for the server.\n"
            "• The GM can mark/unmark characters as **NPCs** in `/set_attributes` (appends `(NPC)` to their display name).\n\n"
            "**Combat & Clashing**\n"
            "• If you Roll to Do against an opponent dyed the same color as your Swing, a **Clash** occurs!\n"
            "• Both sides Roll to Do. If the attacker wins, damage is doubled; if the defender wins, they immediately get a free reprise action!\n\n"
            "**Conflict Flow**\n"
            "• Each turn in a Conflict gives 1 Action and 1 Move. You can lock dice to Sprint for extra moves."
        ),
        accent_color=discord.Color.random()
    )

    return [page1, page2, page3, page4, page5, page6]
