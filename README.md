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
  <a href="https://github.com/Megildur/sentiment_bot/releases/tag/v1.0.1">
    <img src="https://img.shields.io/badge/Release-v1.0.1-blue?style=for-the-badge" alt="Release v1.0.1" />
  </a>
</p>

A dedicated Discord companion bot for the **Sentiment Tabletop Roleplaying Game (TTRPG)**. The bot manages character creation, dynamic attribute dice, core roll mechanics (*Roll to Dye*, *Roll to Do*, *Roll to Recover*), health and leveling brackets, dice states (*Wounded*, *Locked*, *Support*), Game Master NPC tagging, and **Dynamic Swing Color Roles** that change chat username colors to match player swings in real time.

---

## 🔗 Quick Links & Invites

| Link | Description | URL |
| :--- | :--- | :--- |
| 🤖 **Invite Sentiment Bot** | Add the bot directly to your Discord server | [**Add Bot to Server**](https://discord.com/oauth2/authorize?client_id=1547381359968784405&permissions=268815424&scope=bot+applications.commands&integration_type=0) |
| 💬 **Discord Support Server** | Get help, report bugs, and suggest features | [**Join Community Server**](https://discord.gg/Hr595Zk2tr) |
| 📦 **GitHub Repository** | View source code and release notes | [**Megildur/sentiment_bot**](https://github.com/Megildur/sentiment_bot) |

---

## ✨ Key Features

- **🎨 Dynamic Swing Color Roles & Chat Name Colors (v1.0.1)**:
  - **Dynamic Name Color:** When a player chooses an active Swing, the bot automatically grants the matching Discord color role, immediately changing their chat and member list username color to match their Swing's accent color!
  - **10 Accent Colors Supported:**
    - 🔴 **Red** (`#E74C3C`)
    - 🟡 **Yellow** (`#F1C40F`)
    - 🟢 **Green** (`#2ECC71`)
    - 🔵 **Blue** (`#3498DB`)
    - 🟣 **Purple** (`#9B59B6`)
    - 🟠 **Orange** (`#E67E22`)
    - 🔘 **Grey** (`#979C9F`)
    - ⚫ **Black** (`#2D2D2D`)
    - ⚪ **White** (`#F5F5F5`)
    - 💎 **Clear** (`#1ABC9C`)
  - **Automatic Grant & Removal:** Setting a Swing via `/roll_to_dye` or `/roll_to_recover` gives the role; dropping a swing (`/drop_swing`, locking/wounding the die, or switching characters) immediately removes the role to return to normal server colors.
  - **Auto-Search & Auto-Creation:** Searches for existing roles by name or automatically creates them with their exact accent colors if they don't exist yet.
  - **Interactive Management Menu (`/color_roles`)**: View mappings, customize with Discord's native `RoleSelect`, run 1-click **⚡ Auto-Setup Roles**, **🔄 Sync My Role**, or **👥 Sync All Players** across the campaign.
- **🎭 Character & Attribute System (`/set_attributes`, `/character_card`)**:
  - Support for multiple characters per user with autocomplete switching (`/change_active_character`).
  - Configure attribute levels (+0 to +9) and custom titles (e.g. Red *"Passion"*, Blue *"Focus"*).
  - Interactive `/character_card` displaying HP, active Swing, attributes, locked dice, and wounded dice.
- **🎲 Core Sentiment Rolls**:
  - **`/roll_to_dye`**: Defensive roll rolling 1d6 for all unwounded, unlocked attributes while preserving active Swing. Includes interactive **Set Swing** and **Apply Support Die** buttons.
  - **`/roll_to_do`**: Proactive action roll. Rolls **1d20 + Swing** (die + bonus) with Criticals on natural 20s, or **1d20 + 1d6 Wild** if colorless.
  - **`/roll_to_recover`**: Rest roll that automatically restores HP according to official Sentiment recovery rules, unlocks all dice, and allows setting a new Swing.
  - **`/roll_wild`**: Roll a standalone 1d6 die.
- **❤️ Health (HP) & Leveling Brackets (`/hp`)**:
  - Per-character Current and Max HP tracking (defaults to 10/10 HP).
  - Damage (`/hp damage`) with 0 HP Wounded reminders and Death / Leave Scene alerts.
  - Healing (`/hp heal`) up to Max HP.
  - Manage Max HP submenu (`/hp max` or character card button) with PDF Page 18 Potential level-up brackets (flat increase or 1d6 roll) and custom adjustments.
- **🔒 Dice States & Support System**:
  - **Locking & Unlocking (`/lock_die`, `/unlock_die`)**: Lock dice for Sprinting, Pushing, or Blocking. Locking your active swing die automatically drops it.
  - **Wounding & Healing (`/wound_die`, `/unwound_die`)**: Wounding an attribute die automatically unlocks all locked dice.
  - **Support Die (`/support`)**: Share an attribute die with an ally. When consumed in their roll, it returns to the donor locked.
- **⚖️ Game Master (GM) & Combat Tools**:
  - Set server Game Master (`/set_gm`).
  - GM can mark characters as NPCs (`(NPC)`).
  - Clashing rules when opponents have matching swing colors.

---

## ⚙️ Important: Discord Role Hierarchy Setup & Syncing

For Discord to display a player's username in their Swing's color, Discord's role hierarchy rules must be followed:

> ⚠️ **Discord Hierarchy Rule:** A member's username color in chat and the member list is determined strictly by their **highest role that has a color assigned**.

### How to Configure Roles in Your Server:
1. Open **Server Settings ➔ Roles**.
2. **Position the Bot's Role Above Color Roles:** Ensure the bot has a role (e.g. `@Sentiment Bot` or `@Botzilla test`) positioned higher than all color roles, with the **Manage Roles** permission enabled.
3. **Move Color Roles to the Top:** Drag all 10 Color Roles (Red, Yellow, Green, etc.) directly below the bot's role.
4. **Keep Other Colored Roles Lower:** Ensure members do not have other roles placed above the color roles that also have a custom color set (e.g. general member roles should have "Default" color, or be placed below the color roles).

### 🔄 Automatic Syncing & Dropping of Color Roles
- **Automatic Grant:** Whenever you choose or change a Swing via `/roll_to_dye` or `/roll_to_recover`, your matching Discord color role is granted automatically!
- **Automatic Removal:** Whenever you drop your Swing (`/drop_swing`, locking/wounding your swing die, or switching characters), all color roles are stripped automatically so your name color reverts to normal.
- **Sync Buttons (`/color_roles`):**
  - **`⚡ Auto-Setup Roles`**: Automatically scans/creates all 10 color roles and immediately syncs all active players across the server.
  - **`🔄 Sync My Role`**: Optional manual refresh if you had a swing chosen before roles were configured.
  - **`👥 Sync All Players`**: One-click bulk sync for GMs/Admins.

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

## 📋 Slash Commands Reference

| Command | Scope | Description |
| :--- | :--- | :--- |
| `/help` | Everyone | Comprehensive 6-page interactive paginator covering character setup, core rolls, health, dice states, color roles, and combat rules. |
| `/set_attributes` | Everyone | Create a character (starts at 10/10 HP) or configure attributes, bonus values (+0 to +9), and custom titles. |
| `/change_active_character <name>` | Everyone | Quickly switch which character you are actively playing with autocomplete. |
| `/character_card` | Everyone | View full character sheet: Current/Max HP, active Swing, attributes, locked dice, and wounded dice. |
| `/roll_to_dye` | Everyone | Defensive/reactive roll. Rolls 1d6 for all unwounded, unlocked attributes. Includes **Set Swing** and **Apply Support Die** buttons. |
| `/roll_to_do` | Everyone | Proactive roll (attacks, skill checks). Rolls **1d20 + Swing** (die + bonus) or **1d20 + 1d6 Wild** if colorless. |
| `/roll_to_recover` | Everyone | Rest & recovery roll. Automatically unlocks locked dice, recovers HP according to Sentiment rules, and includes **Set Swing**. |
| `/roll_wild` | Everyone | Roll a standalone 1d6 die. |
| `/hp damage <amount>` | Everyone | Deduct HP from your active character. Hitting 0 HP prompts a Wound alert; all dice wounded at 0 HP triggers Death/Leave Scene alert. |
| `/hp heal <amount>` | Everyone | Restores HP up to your character's Max HP. |
| `/hp max` | Everyone | Opens the Max HP submenu: spend Potential to increase Max HP using Sentiment PDF Page 18 brackets or set custom Max HP. |
| `/drop_swing` | Everyone | Drop active Swing to become colorless. Automatically removes your swing color role. |
| `/lock_die` | Everyone | Lock an available attribute die (for Sprinting, Pushing, Blocking). Locking your active swing die drops it. |
| `/unlock_die` | Everyone | Manually unlock a locked attribute die. |
| `/wound_die` | Everyone | Wound an attribute die when sustaining severe trauma. Automatically unlocks all locked dice. |
| `/unwound_die` | Everyone | Heal a wounded die after medical treatment or between sessions. |
| `/support <user>` | Everyone | Pass an attribute die to an ally. When applied in their roll, it returns to you locked. |
| `/color_roles` | Everyone / Admins | Open the interactive configuration menu to view, customize, auto-create, or sync Swing Color Roles. |
| `/set_gm <user>` | Admins / GM | Designate or transfer the Game Master for the server. The GM can tag characters as NPCs (`(NPC)`). |

---

## 🚀 Setup & Self-Hosting

### Prerequisites
- Python 3.10+ (Tested up to Python 3.14)
- A registered [Discord Bot Application](https://discord.com/developers/applications) with:
  - **Message Content Intent** enabled
  - **Server Members Intent** enabled

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Megildur/sentiment_bot.git
   cd sentiment_bot
   ```

2. **Set up a virtual environment**:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   # Discord Bot Application Token
   API_TOKEN=your_bot_token_here

   # Support server invite link
   BOT_SERVER=https://discord.gg/Hr595Zk2tr

   # Comma-separated Discord guild IDs authorized for owner/admin commands
   ALLOWED_GUILDS=123456789012345678,987654321098765432
   ```

5. **Run the bot**:
   On Windows PowerShell:
   ```powershell
   .\start.ps1
   ```
   Or directly with Python:
   ```bash
   python Main.py
   ```

6. **Add Bot to Server**:
   - In the [Discord Developer Portal](https://discord.com/developers/applications), navigate to **OAuth2** -> **URL Generator**:
     - **Scopes**:
       - `bot`
       - `applications.commands`
     - **Bot Permissions** (Permission Integer: `268815424`):
       - `Manage Roles`
       - `View Channels`
       - `Send Messages`
       - `Embed Links`
       - `Attach Files`
       - `Read Message History`
       - `Use External Emojis`
       - `Add Reactions`
   - Use the generated invite URL to add the bot to your server:
     ```text
     https://discord.com/oauth2/authorize?client_id=1547381359968784405&permissions=268815424&scope=bot+applications.commands&integration_type=0
     ```

7. **Sync Slash Commands**:
   - In any server listed in your `ALLOWED_GUILDS`, run the quicksync command:
     ```text
     !b quicksync
     ```
   - Or run the slash command:
     ```text
     /owner sync sync_type:Guild
     ```

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

## 🛡️ Support & Community

Need assistance, found an issue, or want to suggest new features?
- **Join our Discord**: [https://discord.gg/Hr595Zk2tr](https://discord.gg/Hr595Zk2tr)
- **Invite Sentiment Bot**: [https://discord.com/oauth2/authorize?client_id=1547381359968784405&permissions=268815424&scope=bot+applications.commands&integration_type=0](https://discord.com/oauth2/authorize?client_id=1547381359968784405&permissions=268815424&scope=bot+applications.commands&integration_type=0)
