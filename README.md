# 🎲 Sentiment

<p align="center">
  <a href="https://discord.com/oauth2/authorize?client_id=1547381359968784405&permissions=268815424&scope=bot+applications.commands&integration_type=0">
    <img src="https://img.shields.io/badge/Invite%20Bot-Discord%20App-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Invite Bot" />
  </a>
  &nbsp;
  <a href="https://discord.gg/Hr595Zk2tr">
    <img src="https://img.shields.io/badge/Support%20Server-Join%20Community-57F287?style=for-the-badge&logo=discord&logoColor=white" alt="Support Server" />
  </a>
  &nbsp;
  <a href="https://github.com/Megildur/sentiment_bot/releases/tag/v1.2.0">
    <img src="https://img.shields.io/badge/Release-v1.2.0-blue?style=for-the-badge" alt="Release v1.2.0" />
  </a>
</p>

A Discord companion for the **Sentiment** tabletop roleplaying game (rulebook 0.9). It keeps your characters,
rolls the game's three rolls (Roll to Dye, Roll to Do and Roll to Recover), tracks HP, Wounded and Locked dice,
Support dice and the GM's NPCs, and colors each player's name with their Swing.

---

## Links

| Link | What it's for | URL |
| :--- | :--- | :--- |
| **Invite Sentiment** | Add the bot to your server | [Add to server](https://discord.com/oauth2/authorize?client_id=1547381359968784405&permissions=268815424&scope=bot+applications.commands&integration_type=0) |
| **Support server** | Help, bug reports and ideas | [Join the server](https://discord.gg/Hr595Zk2tr) |
| **GitHub** | Source code and release notes | [Megildur/sentiment_bot](https://github.com/Megildur/sentiment_bot) |

---

## Features

- **Characters.** Several characters per player, each with Attributes in any of the 10 colors, a title for each
  (Red *Passion*, Blue *Focus*) and a bonus (its Attribute Level) from +0 to +9. New characters start at 10 / 10 HP.
  `/set_attributes` sets them up, `/character_card` shows the sheet, and `/change_active_character` switches.
- **The three rolls.**
  - `/roll_to_dye` rolls every Attribute die that isn't Wounded, Locked or sent as Support. Your Swing die keeps its
    saved result and adds its bonus. **Set Swing** picks a new Swing from the roll.
  - `/roll_to_do` rolls 1d20 plus your Swing, or 1d20 plus a Wild 1d6 while you're colorless. A 20 is a Critical.
  - `/roll_to_recover` Unlocks every die and rolls your Unwounded dice plus their bonuses. The total is your new HP,
    after a Rest or a Wound alike, as in the rulebook. It can also set a Swing.
  - `/roll_wild` rolls a single 1d6.
- **HP and leveling.** `/hp damage` and `/hp heal`, with the 0 HP steps from the rulebook (Roll to Recover, then
  Wound an Attribute, or Leave the Scene). `/hp max` spends Potential on Max HP using the rulebook's brackets, or
  sets any Max HP.
- **Dice states and Support.** `/lock_die` and `/unlock_die` (Locking your Swing die Ignites it), `/wound_die` and
  `/unwound_die` (a Wound Unlocks every die), `/drop_swing`, and `/support` to send an ally a die they can add to
  their next roll; it comes back to you Locked.
- **GM tools.** Each server has its own Game Master, chosen with `/set_gm`. The GM can mark characters as NPCs and
  use any player's rolls and character panels in that server.
- **Swing color roles.** A player's name in chat takes their Swing's color. Setting a Swing gives the role; dropping
  it (`/drop_swing`, Locking or Wounding the Swing die, switching characters) removes it. `/color_roles` sets up the
  10 roles and syncs players.
- **Buttons that last.** Every button and menu keeps working after the bot restarts, and only the player it belongs
  to (or the GM, where it makes sense) can press it.

### The 10 colors

| Color | Hex | Color | Hex |
| :--- | :--- | :--- | :--- |
| 🔴 Red | `#E74C3C` | 🟠 Orange | `#E67E22` |
| 🟡 Yellow | `#F1C40F` | 🔘 Grey | `#979C9F` |
| 🟢 Green | `#2ECC71` | ⚫ Black | `#2D2D2D` |
| 🔵 Blue | `#3498DB` | ⚪ White | `#F5F5F5` |
| 🟣 Purple | `#9B59B6` | 💎 Clear | `#1ABC9C` |

---

## Setting up color roles

Discord colors a member's name with their **highest role that has a color**, so the order of roles matters.

1. Open **Server Settings > Roles**.
2. Give Sentiment a role with **Manage Roles**, above every color role.
3. Put the 10 color roles directly under Sentiment's role.
4. Keep other colored roles below the color roles, or give them no color.
5. Run `/color_roles` and press **Set up roles**. It finds or creates the 10 roles and syncs every player.

**Sync my role** fixes one player whose Swing was set before the roles existed; **Sync all players** does everyone.
Setting up roles, picking a role for a color and syncing everyone need **Manage Roles** or being the server's GM.

```
Server role order
┌──────────────────────────────────────────────┐
│ [Sentiment's role]   (has Manage Roles)      │ ◄── top
│ ───────────────────────────────────────────  │
│ 🔴 Red              (#E74C3C)                │ ◄── swing color roles
│ 🟡 Yellow           (#F1C40F)                │
│ 🟢 Green            (#2ECC71)                │
│ 🔵 Blue             (#3498DB)                │
│ 🟣 Purple           (#9B59B6)                │
│ 🟠 Orange           (#E67E22)                │
│ 🔘 Grey             (#979C9F)                │
│ ⚫ Black            (#2D2D2D)                │
│ ⚪ White            (#F5F5F5)                │
│ 💎 Clear            (#1ABC9C)                │
│ ───────────────────────────────────────────  │
│ [Member role]       (no color)               │
│ @everyone                                    │ ◄── bottom
└──────────────────────────────────────────────┘
```

---

## Commands

| Command | Who | What it does |
| :--- | :--- | :--- |
| `/help` | Everyone | A six-page guide to the commands and the game's rules. |
| `/set_attributes` | Everyone | Create a character, or set up your active character's Attributes, titles and bonuses. |
| `/change_active_character <name>` | Everyone | Switch the character you're playing. |
| `/character_card` | Everyone | Your character sheet: HP, Swing, Attributes, Locked and Wounded dice. |
| `/roll_to_dye` | Everyone | Roll every available Attribute die. Has **Set Swing** and **Apply Support die**. |
| `/roll_to_do` | Everyone | Roll 1d20 plus your Swing, or 1d20 plus a Wild 1d6. |
| `/roll_to_recover` | Everyone | Unlock every die and roll your Unwounded dice; the total is your new HP. Has **Set Swing**. |
| `/roll_wild` | Everyone | Roll a single 1d6. |
| `/hp damage <amount>` | Everyone | Take damage. At 0 HP it lists the Wound steps. |
| `/hp heal <amount>` | Everyone | Heal, up to Max HP. |
| `/hp max` | Everyone | Spend Potential on Max HP, or set it. |
| `/lock_die` / `/unlock_die` | Everyone | Lock a die (to Sprint, Tag a Prop or Ignite your Swing), or Unlock one. |
| `/wound_die` / `/unwound_die` | Everyone | Wound an Attribute (Unlocks every die), or heal one. |
| `/drop_swing` | Everyone | Drop your Swing and become colorless. Removes your color role. |
| `/support <user>` | Everyone | Send an ally a die for their next roll. It comes back to you Locked. |
| `/color_roles` | Everyone; setup needs Manage Roles or GM | Set up and sync the swing color roles. |
| `/set_gm <user>` | Manage Server, or the server's current GM | Choose this server's Game Master. |

---

## Running your own copy

### You need
- Python 3.10 or newer
- A [Discord application](https://discord.com/developers/applications) with the **Server Members** and
  **Message Content** intents turned on

### Install

1. Clone the repository:
   ```bash
   git clone https://github.com/Megildur/sentiment_bot.git
   cd sentiment_bot
   ```
2. Make a virtual environment and install the dependencies:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Create `.env` in the root folder:
   ```env
   # The bot's token
   API_TOKEN=your_bot_token_here

   # Support server invite, shown under error messages
   BOT_SERVER=https://discord.gg/Hr595Zk2tr

   # Comma-separated server IDs where /owner and !b quicksync work
   ALLOWED_GUILDS=123456789012345678,987654321098765432
   ```
4. Start it: `.\start.ps1` on Windows (it pulls the latest version, updates dependencies and starts the bot), or
   `python Main.py`.
5. Invite it with the scopes `bot` and `applications.commands` and these permissions (integer `268815424`):
   Manage Roles, View Channels, Send Messages, Embed Links, Attach Files, Read Message History, Use External Emojis
   and Add Reactions:
   ```text
   https://discord.com/oauth2/authorize?client_id=1547381359968784405&permissions=268815424&scope=bot+applications.commands&integration_type=0
   ```
6. Sync the slash commands from a server in `ALLOWED_GUILDS` with `!b quicksync`, or `/owner sync sync_type:Guild`.

Read [AGENTS.md](AGENTS.md) before changing the code: it has the project's rules and a summary of the game rules
the bot follows.

---

## Project layout

```
sentiment/
├── Main.py                     # Starts the bot and loads the extensions
├── start.ps1                   # Pulls the latest version, sets up the venv and starts the bot
├── requirements.txt            # discord.py, aiosqlite, python-dotenv
├── AGENTS.md                   # Rules for changing the code, and the game rules summary
├── Data/Dice.db                # SQLite database (not in git)
└── Source/
    ├── Errors.py               # Last-resort error notices
    ├── OwnerCommands.py        # /owner sync, ext and cogs
    ├── Quicksync.py            # !b quicksync
    ├── Status.py               # Rotating status
    ├── Utils/                  # Shared helpers: notices, permissions, pings, colors, lasting buttons
    └── Cogs/Dice/
        ├── Dice.py             # The slash commands
        ├── Database.py         # Every read and write of the database
        ├── Characters.py       # Setup panel, character card, Max HP panel and their forms
        ├── Rolls.py            # Roll messages and their buttons
        ├── RollText.py         # Roll text, written and read back
        ├── DieStates.py        # Wound, Lock and Support forms
        ├── GM.py               # /set_gm
        ├── ColorRoles.py       # Giving and removing swing color roles
        ├── ColorRolesPanel.py  # /color_roles
        ├── HelpPages.py        # /help
        ├── Common.py           # What the panels, rolls and forms share
        └── Constants.py        # The 10 colors and the HP brackets
```

---

## Support

Questions, bugs or ideas: [join the support server](https://discord.gg/Hr595Zk2tr).
