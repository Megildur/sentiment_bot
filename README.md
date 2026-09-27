# 🎲 Sentiment TTRPG Discord Bot

[![Release](https://img.shields.io/badge/release-v1.0.0-blue.svg)](https://github.com/Megildur/sentiment_bot/releases/tag/v1.0.0)
[![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.7%2B-blueviolet.svg)](https://github.com/Rapptz/discord.py)
[![Database](https://img.shields.io/badge/database-SQLite%20(aiosqlite)-orange.svg)](https://sqlite.org/)

A dedicated Discord companion bot for the **Sentiment Tabletop Roleplaying Game (TTRPG)**. The bot manages character creation, dynamic attribute dice, core roll mechanics (*Roll to Dye*, *Roll to Do*, *Roll to Recover*), health and leveling brackets, dice states (*Wounded*, *Locked*, *Support*), Game Master NPC tagging, and **Dynamic Swing Color Roles** that change chat username colors to match player swings in real time.

---

## 🌟 What's New in v1.0.0: Swing Color Roles & Chat Name Colors

In the Sentiment TTRPG, your character's active **Swing** represents your current emotional alignment and color affinity. In **v1.0.0**, this comes alive in Discord!

* **🎨 Chat Username Color Changes:** When you set a Swing, the bot automatically grants you the corresponding Discord color role. Your username in chat and the server member list dynamically changes to match your Swing's exact accent color!
* **10 Accent Colors Supported:**
  * 🔴 **Red** (`#E74C3C`)
  * 🟡 **Yellow** (`#F1C40F`)
  * 🟢 **Green** (`#2ECC71`)
  * 🔵 **Blue** (`#3498DB`)
  * 🟣 **Purple** (`#9B59B6`)
  * 🟠 **Orange** (`#E67E22`)
  * 🔘 **Grey** (`#979C9F`)
  * ⚫ **Black** (`#2D2D2D`)
  * ⚪ **White** (`#F5F5F5`)
  * 💎 **Clear** (`#1ABC9C`)
* **Automatic Role Assignment & Removal:**
  * Setting a Swing via `/roll_to_dye` or `/roll_to_recover` gives you the matching role and strips any previous color roles.
  * Dropping your Swing (`/drop_swing`), locking or wounding your active swing die, or switching characters automatically removes the color role so you return to your normal server name color.
* **Auto-Search & Auto-Creation:** If the color roles already exist on your server (by name), the bot automatically finds and links them. If they do not exist, the bot creates them automatically with the exact accent colors.
* **Interactive `/color_roles` Menu:** Server administrators and GMs can view current role bindings, customize roles with Discord's native `RoleSelect` menu, trigger 1-click **⚡ Auto-Setup All Roles**, run **🔄 Sync My Role**, or run **👥 Sync All Players** to update all server members.

---

## ⚙️ Important: Discord Role Hierarchy Setup

For Discord to display your username in your Swing's color, Discord's role hierarchy rules must be followed:

> ⚠️ **Discord Hierarchy Rule:** A member's username color in chat and the member list is determined strictly by their **highest role that has a color assigned**.

### How to Configure Roles in Your Server:
1. Open **Server Settings ➔ Roles**.
2. **Move the Bot's Role to the Top:** Ensure the bot has a custom role (e.g. `Sentiment Bot`) positioned higher than the color roles with the **Manage Roles** permission enabled.
3. **Move Color Roles to the Top:** Drag all 10 Color Roles (Red, Yellow, Green, etc.) directly below the bot's role.
4. **Keep Other Colored Roles Lower:** Ensure members do not have other roles placed above the color roles that also have a custom color set (e.g. general member roles should have "Default" color, or be placed below the color roles).
5. **Note on Server Owners:** Discord's internal security policy strictly prevents any bot from modifying the roles of the **Server Owner**. To test automatic role changes in action, test with another server member or a secondary account!

```
Server Role Hierarchy Example:
┌──────────────────────────────────────────────┐
│ [Bot Role]          (Has "Manage Roles")     │ ◄── Top
│ ───────────────────────────────────────────  │
│ 🔴 Red              (#E74C3C)                │ ◄── Swing Color Roles
│ 🟡 Yellow           (#F1C40F)                │     (Must be highest
│ 🟢 Green            (#2ECC71)                │      colored roles for
│ 🔵 Blue             (#3498DB)                │      members)
│ 🟣 Purple           (#9B59B6)                │
│ 🟠 Orange           (#E67E22)                │
│ 🔘 Grey             (#979C9F)                │
│ ⚫ Black            (#2D2D2D)                │
│ ⚪ White            (#F5F5F5)                │
│ 💎 Clear            (#1ABC9C)                │
│ ───────────────────────────────────────────  │
│ [Member Role]       (Default / No Color)     │
│ @everyone                                    │ ◄── Bottom
└──────────────────────────────────────────────┘
```

---

## 📖 Command Reference

### Character Management
| Command | Description |
| :--- | :--- |
| `/set_attributes` | Create a new character (starts at 10/10 HP) or configure attributes, bonus values (+0 to +9), and custom titles. |
| `/change_active_character <name>` | Quickly switch which character you are actively playing. |
| `/character_card` | View your full character sheet: Current/Max HP, active Swing, attributes, locked dice, and wounded dice. |

### Core Rolls
| Command | Description |
| :--- | :--- |
| `/roll_to_dye` | Defensive/reactive roll. Rolls 1d6 for all unwounded, unlocked attributes. Preserves active Swing die. Includes buttons to **Set Swing** and **Apply Support Die**. |
| `/roll_to_do` | Proactive roll (attacks, skill checks). Rolls **1d20 + Swing** (die value + bonus). Rolling 20 on the d20 is a Critical. Rolls **1d20 + 1d6 Wild** if colorless. |
| `/roll_to_recover` | Rest & recovery roll. Automatically unlocks all locked dice, recovers HP according to Sentiment rules, and includes a **Set Swing** button. |
| `/roll_wild` | Roll a standalone 1d6 die. |

### Health (HP) & Leveling
| Command | Description |
| :--- | :--- |
| `/hp damage <amount>` | Deduct HP from your active character. Hitting `0 HP` triggers a Wound & Recovery prompt; hitting `0 HP` with all dice wounded triggers a Death / Leave Scene alert. |
| `/hp heal <amount>` | Restores HP up to your character's Max HP. |
| `/hp max` | Opens the Max HP submenu: spend Potential to increase Max HP using Sentiment PDF Page 18 brackets (flat or rolled 1d6) or set custom Max HP. |

### Dice States & Support
| Command | Description |
| :--- | :--- |
| `/drop_swing` | Drop your active Swing to become colorless. Automatically removes your swing color role. |
| `/lock_die` | Lock an available attribute die (for Sprinting, Pushing, Blocking). Locking your active swing die drops it. |
| `/unlock_die` | Manually unlock a locked attribute die. |
| `/wound_die` | Wound an attribute die when sustaining severe trauma. Automatically unlocks all locked dice. |
| `/unwound_die` | Heal a wounded die after medical treatment or between sessions. |
| `/support <user>` | Pass an attribute die to an ally. When applied in their roll, it returns to you locked. |

### Server & GM Administration
| Command | Description |
| :--- | :--- |
| `/color_roles` | Open the interactive configuration menu to view, customize, auto-create, or sync Swing Color Roles. |
| `/set_gm <user>` | Designate or transfer the Game Master for the server. The GM can tag characters as NPCs (`(NPC)`). |
| `/help` | Comprehensive 6-page interactive paginator covering character setup, core rolls, health, dice states, color roles, and combat reference. |

---

## 🚀 Setup & Installation

### Prerequisites
* **Python 3.10+** (Tested up to Python 3.14)
* **Discord Bot Token** with the following Privileged Gateway Intents enabled in the [Discord Developer Portal](https://discord.com/developers/applications):
  * **Server Members Intent**
  * **Message Content Intent**

### 1. Clone the Repository
```bash
git clone https://github.com/Megildur/sentiment_bot.git
cd sentiment_bot
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory:
```env
API_TOKEN=your_discord_bot_token_here
ALLOWED_GUILDS=123456789012345678,987654321098765432
```
* `API_TOKEN`: Your Discord Bot token.
* `ALLOWED_GUILDS`: Comma-separated list of server IDs where owner sync commands are permitted.

### 3. Install Dependencies
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Run the Bot
On Windows PowerShell:
```powershell
.\start.ps1
```
Or directly with Python:
```bash
python Main.py
```

### 5. Sync Slash Commands
To register all slash commands with Discord:
* Use the owner prefix command in Discord: `!b quicksync`
* Or use `/owner sync Global` (or `/owner sync Guild`) from an authorized server.

---

## 📁 Architecture & Project Structure

```
sentiment/
├── Main.py                     # Bot initialization, extension loader, startup
├── start.ps1                   # Automated startup script with venv management
├── requirements.txt            # Python dependencies (discord.py, aiosqlite, python-dotenv)
├── README.md                   # Project documentation
├── Data/
│   └── Dice.db                 # SQLite database (WAL mode enabled)
└── Source/
    ├── Errors.py               # Global error handling and user notification views
    ├── OwnerCommands.py        # Owner administration and command syncing
    ├── Quicksync.py            # Quick prefix-based sync command (!b quicksync)
    ├── Status.py               # Bot status rotation
    ├── Utils/
    │   └── Paginator.py        # LayoutView paginator with dynamic page controls
    └── Cogs/
        └── Dice/
            ├── __init__.py     # Cog registration
            ├── Constants.py    # Color emojis, accent colors, and color lists
            ├── Database.py     # Database schema, queries, HP and character helpers
            ├── ColorRoles.py   # Color role auto-detection, creation, assignment & UI view
            ├── Dice.py         # Slash command handlers and /help paginator
            └── Views.py        # Discord UI components, modals, and roll layouts
```

---

## 📄 License
This project is developed for the Sentiment TTRPG community. Check with the repository maintainer for licensing details.
