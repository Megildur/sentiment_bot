# Sentiment: rules for anyone (human or agent) changing this repo

Sentiment is a discord.py 2.7 bot for the Sentiment tabletop RPG (rulebook 0.9). All its data is
in SQLite at `Data/Dice.db`, read and written through `Source/Cogs/Dice/Database.py` with aiosqlite.
Run Python with `venv\Scripts\python.exe` from the repo root. Production runs on Wispbyte, which
pulls `main` when it starts; the owner edits `.env` there. Python files use LF line endings; never
convert a file's line endings in a commit that also changes code.

Adapted from Botzilla's AGENTS.md. Where the two differ, this file wins for this repo.

## Ground rules
- Improve what exists; don't rewrite from scratch. Smallest change that solves the problem.
- Reuse before writing. Never duplicate code, or write new code where a shared helper can be reused
  or extended. Look in the reuse table, `Source/Utils` and `Source/Cogs/Dice/Common.py` first.
- Never change these, because changing them breaks servers, posted messages or saved data:
  - slash command, group and option names, option types, choice values
  - `custom_id` strings (every one is listed in `scratch/test_fixed_names.py`)
  - table and column names or types, including the misspelled `recieve_support_*` columns
    (add columns or tables only, never drop data)
  - the `view_type` strings stored in `active_character_views` (`AttributeSetView`, `RollToDyeView`...)
  Descriptions, labels and wording may change.
- Store data only in SQLite through `DiceDatabase` (`cog.db`). Never JSON or other files, and never
  `db.db.execute` outside `Database.py`.
- Each server has its own GM (`guild_gm`); there is no GM in DMs. Every GM check passes the server:
  `db.is_gm(interaction.guild_id, user_id)`. The old `gm` table (one GM for every server) is only
  read once, by `Dice._move_gm_to_servers`, and never written.
- The database is the source of truth. Don't keep game state in memory: not per player, not per
  message. A press reads what it needs from the message and the database (see Lasting messages).
- `cog_load` may open the SQLite file and create tables (local, milliseconds). No Discord or other
  network calls there: extensions load one after another before Sentiment connects.
- No new dependencies unless the benefit is large; say why in one line.
- Flag anything that changes behavior (permissions, data writes, timing, who can press a button,
  game math).
- Check Sentiment's own permissions only with `Source/Utils/Permissions.py`. Never read
  `guild_permissions` or `permissions_for` yourself; `scratch/check_code_rules.py` fails if you do.
  Use `server_of(interaction)` for the server: `interaction.guild` can be a stand-in whose `me`
  has no roles.
- Never quietly do less because Sentiment lacks a permission. Refuse with what's missing, when the
  setting is changed or the button is pressed.
- Never print or commit secrets (`.env`, the token).
- Code must run on Python 3.10+: no `match`, no `X | Y` unions at runtime, no reused quotes inside
  f-strings (the host's Python isn't pinned; `scratch/check_code_rules.py` checks).
- Comments explain why, not what.

## Look and copy
- Components v2 only: `discord.ui.LayoutView` + `Container` / `TextDisplay` / `Section`. Never
  `discord.Embed`, and never plain `content=` replies. The one exception: the owner's `!b quicksync`.
- Colors: anything about a character (rolls, cards, HP, setup) uses its Swing's color from
  `Constants.swing_accent`, and no accent while it's colorless. Everything else uses
  `Source/Utils/Theme.py` by meaning: BRAND (normal/success), ACCENT (warnings, "not now"),
  INFO (help, settings), MUTED (ended or deleted), ERROR (errors, refusals, delete confirmations).
- Emoji only where they carry meaning: at most one per heading, color circles for dice colors,
  ⭐ for the Swing die and 🤝 for Support dice in roll lines.
- Sentence-case headings, except game terms, which keep the rulebook's capitals (see Game rules).
- Short, concrete sentences. No em dashes. No filler (seamless, supercharge, elevate, unlock as a
  verb of excitement, revolutionize, effortless, next-generation, powerful, ultimate, comprehensive).
  No invented stats. No exclamation marks in notices.
- Errors are private, plain-language, and never show raw exception text; details go to the log.
- Respect Discord limits: 4000 text characters and 40 components per message, 25 select options,
  80-character button labels, 45-character form titles and labels.

## Game rules (Sentiment 0.9)
The bot follows the Sentiment 0.9 rulebook. Whenever code, `/help`, the README or any message
describes a mechanic, it must match this section. If the rulebook changes, update this section
first, then the code, `HelpPages.py` and the README together.

### Terms
Use the rulebook's words with its capitals: Attribute, Attribute Level, Swing, Dyed, colorless, Wild,
Roll to Dye, Roll to Do, Roll to Recover, Roll to Reflect, Critical, Clash, Wound / Wounded,
Lock / Locked / Unlock, Ignite, Push, Block, Multiply, Sprint, Tag a Prop, Support, Rest, Scene,
Conflict, Act, Turn, Action, Move, Initiative, Leave the Scene, HP, Max HP, Speed, Potential, Level,
Gift, GM, NPC. Players see the Attribute Level as the "bonus"; keep that word, because roll lines
are read back with it (`Bonus` in `RollText.py`).

### Characters
- A new character has 3 Attributes (three differently colored d6), 10 HP and 6 Speed.
- Each Attribute has a color, a title the player picks (Red *Passion*), and an Attribute Level from
  +0 to +9. The ten colors are in `Constants.COLOR_ORDER`.

### Roll to Dye and the Swing
- Roll to Dye when something happens to you: roll every Attribute die you have. The result is their
  total plus applicable bonuses. Beat whatever triggered it to succeed.
- After a Roll to Dye you may pick one rolled die as your Swing. Its value is the die's result plus
  its Attribute Level. While it's your Swing you are Dyed its Color.
- The Swing die is set aside and not rerolled while it stays your Swing: later Rolls to Dye add its
  saved result plus its Attribute Level. Rulebook example: Red 5, Blue 3, Yellow 6, Yellow picked as
  Swing with Level 3: 5 + 3 + 6 + 3 = 17.
- Picking a new Swing drops the old one. One Swing at a time. You may Drop your Swing (become
  colorless) when Rolling to Dye, between rolls on your own Turn, or any time outside a Conflict.
- Roll to Reflect is a Roll to Dye made to see what your character is thinking; it can set a Swing.

### Roll to Do
- Roll to Do to act on the world: 1d20 plus your Swing. With no Swing, 1d20 plus 1d6: a Wild roll,
  Dyed no Color. Your Swing's Attribute must fit the action, or you drop it first.
- Succeed by beating the target's Roll to Dye; a tie goes to whoever Rolled to Dye.
- A harmful hit deals damage equal to your Swing (or the d6 when Wild).
- A 20 on the d20 is a Critical: damage doubles, or a non-attack's effect doubles in scope, scale or
  speed.
- Clash: Rolling to Do at a character Dyed your Color. The defender Rolls to Do instead of to Dye.
  Attacker wins: double damage (or a greater effect). Defender wins: they immediately reprise with
  an Action or Move of their choice.

### Igniting and Locking
- Ignite: needs a Swing. The Swing is spent and its die Locked. Effects: Push (+1d6 to a roll, before
  its effects resolve), Block (take 1d6 less damage, even after the roll), Multiply (up to two more
  targets, each a new Wild Roll to Do).
- Lock: any Attribute die, no Swing needed, as often as you like. Locking the Swing die drops the
  Swing. Effects: Sprint (move your Speed again), Tag a Prop (use the scenery, usually +1d6).
- Locked dice come back at the end of the Scene, or at the start of your next Turn in a Conflict.

### HP, Rest and Roll to Recover
- Characters start at 10 HP. Words can deal damage as well as weapons.
- Roll to Recover after a Rest or when Wounded: Unlock all dice, roll every Unwounded Attribute die
  and add all their Attribute Levels. The total is your new HP, never above Max HP. With no dice
  left, you get 1 HP back. It counts as a Roll to Dye, so it can set a new Swing.
- An interrupted Rest may let you roll only one or two dice (GM's call).

### Wounds, death and Leaving the Scene
- At 0 HP you take a Wound, in this order: Unlock all dice, Roll to Recover, then Wound one
  Attribute (its die is out of the game until it heals).
- Any Attribute can be Wounded, even a Locked one. Wounds heal between sessions unless the GM says
  otherwise. A player may take a Wound at any time (it Unlocks all dice), including to trigger an
  Ignite or Lock effect for free.
- With every Attribute Wounded and 0 HP, the character dies (what death means is up to the campaign).
- Whenever a character becomes Wounded, they may Leave the Scene: they still take the Wound and Roll
  to Recover, but take no more damage in that Scene or Conflict.

### Scenes and target numbers
- Beat the GM's target number: Very Easy 5 (1d6 + 1), Easy 10 (2d6 + 2), Normal 15 (3d6 + 3),
  Hard 20 (4d6 + 4), Very Hard 25 (5d6 + 5), Extreme 30 (6d6 + 6). Every 5 over can count as an
  extra success. All Locked dice return at the end of a Scene.
- Social: a successful Roll to Do can Restrict one of the target's Attributes from being their Swing
  (two on a Clash).

### Conflicts
- Everyone Rolls to Dye for Initiative; the highest picks who goes first. Each Act lasts until every
  character has had a Turn; the active player picks who goes next.
- A Turn is 1 Action (usually a Roll to Do, or a Roll to Reflect) and 1 Move (up to your Speed);
  Lock dice to Sprint for extra Moves. Locked dice Unlock at the start of your Turn.
- At the end of each Act, everyone Keeps their Swing or Rerolls it (drop it, Roll to Dye, pick a new
  one). Initiative then goes to the highest Roll to Dye among those who rerolled, else the highest
  Swing, then d20s.

### Support (still being tested in the rulebook)
- Pass an ally one of your Attribute dice: it leaves your pool, they're also Dyed its Color, they
  roll it as part of the supported action (usually one roll), and it comes back to you Locked.
- In a Conflict it uses your Action. Supporting out of turn means Igniting your Swing and skipping
  your next Turn. Supporting after the roll is an Ignite and can't make a Clash. An unused Support
  die can be reclaimed, Locked, at the start of an Act or Scene.

### Levelling up and Potential
- A character gains a Level at creation and after each session; each Level gives 1 Potential.
- Potential buys Max HP (`Constants.hp_bracket`): 10–19 (or under 10): +5 or 1d6 + 1; 20–39: +3 or
  1d6; 40–59: +2 or 1d6 - 1; 60+: +1, no roll.
- Raising an Attribute Level costs the new level in Potential (+0 to +1 costs 1, +1 to +2 costs 2...),
  up to +9. Potential also buys and levels Gifts, and 1 Potential plus a Level rerolls any roll once.

### Gifts
Gifts (up to six equipped, one per Type per roll, Levels, LINK, AFFINITY, Burning) are not in the
bot. Don't add Gift mechanics without the owner.

### Where the bot differs from the rulebook
These are known and left for the owner to decide. Don't "fix" them silently; don't add new ones.
Roll to Recover follows the rulebook exactly, for a Rest as well as a Wound (the owner decided this):
the total becomes your HP even when that's lower than before.
- Raising Max HP also raises current HP by the same amount.
- Roll to Recover also rolls dice lent out as Support.
- Players set Attribute Levels freely (0 to 9); the bot doesn't charge Potential or count Levels.
- NPC marks are by character name, so they cover every player's character with that name.
- Not tracked: Speed, Potential, Gifts, Scenes, Conflicts and Acts, Restrict, interrupted Rests,
  reclaiming Support dice. Ignite is a Lock of the Swing die with `/lock_die`.

## Menu layout
`/set_attributes` (`Characters.attribute_panel`) is the model; the character card, Max HP panel and
`/color_roles` follow it.
- Start with a `## ` heading (one emoji at most) and a line on what the panel is for.
- One setting or action per line: a `Section` with `**Name:** value` or `**Action.**` and a `-#` note,
  with its button as the accessory (`Common.section`). Never a block of text with a row of buttons
  under it; a pair of navigation buttons (Back, Close menu) in a row is fine.
- Separators between groups, and before navigation.
- Buttons say what they do ("Add Attribute", "Change Max HP", "Close menu").
- Anything that deletes data asks first: a confirm panel in ERROR color with a danger button and Cancel.
- Edits with several fields open a form (`Common.DiceModal`), so the panel stays short.

## Lasting messages (buttons that never expire)
Every button and menu Sentiment posts keeps working forever and after restarts. Read
`Source/Utils/Views.py` before touching one.
- Each control is a DynamicItem whose template is its exact `custom_id`, built on `LastingItem`
  (or `DiceItem`, which adds the GM override). Add the class to its module's `ITEMS`; `Dice.py`
  registers them all in `cog_load` (`LASTING_ITEMS`).
- Never use a view registered with `bot.add_view`, or static buttons, on these messages: one view
  object then serves every message, and state leaked between players and servers before v1.1.0.
- Never send them in a private reply, give their view a timeout, or call `stop()` on it: discord.py
  then unregisters the class for every message. Build a fresh view (`Common.lasting_view`) for every
  send or edit.
- A press gets everything from the message and the database: the owner from
  `Common.owner_of` (who ran the command), the active character from the database, a roll's dice
  from its text (`RollText.parse_roll`), the color being edited from the panel's own menu. Roll line
  formats are data: change one only together with its pattern, keep old formats readable, and run
  `scratch/test_rolls.py`.
- Who may press: the owner by default; `gm_allowed = True` on items the server's GM may use on any player's
  message (setup panels, cards, rolls); `owner_only = False` for anyone (help pages, Sync my role).
- Messages about a character are tracked in `active_character_views` (`Common.send_tracked`,
  `Characters.show`) so `refresh_later` can redraw them, and grey out rolls for a character that's
  no longer active, when the character changes.

## Pings
Discord pings a mention only when a message is created; edits never ping, and neither does the first
follow-up after a public `defer()`.
- **Who gets pinged:** the ally in the `/support` message (they have a die to use), and the new GM
  in the `/set_gm` announcement (unless they chose themselves).
- **Never ping:** rolls, character cards, setup panels, HP results, notices, `/color_roles`, `/help`,
  the GM change prompt, or anyone named in their own command. Send cards and prompts with
  `discord.AllowedMentions.none()`. The bot's default allows user pings, never roles or @everyone.
- The mention goes on its own line above the container with `Pings.with_ping(view, users=...)`, and
  is sent with `Pings.ping_mentions(...)` naming exactly who to ping.

## Reuse before writing
| Need | Use |
| :--- | :--- |
| A short notice, error or confirmation | `Notice.notify(interaction, title, body, color)`, or `notice_view` + `send_ephemeral`; after a public `defer()`, `send_deferred_error` keeps it private |
| Refusing a slash command | Check before `defer()` and answer with `send_ephemeral`, so the refusal is private (`Dice._refuse`, `Dice._state`) |
| Pinging someone | `Pings.with_ping` + `Pings.ping_mentions` (see Pings) |
| Work the reply doesn't wait for | `Common.spawn(interaction, coro)`, which keeps the task in `cog.background` and cancels it on unload |
| Sentiment's permissions | `Permissions.server_of`, `missing_server_permissions(guild, "manage_roles")`, `role_problem(guild, role)` |
| The member's permissions | `Permissions.member_has(member, ...)`, `require_member_permissions(interaction, ..., or_also=..., to=...)` |
| A button or menu on a posted message | `LastingItem` / `DiceItem` (see Lasting messages) |
| A view for such a message | `Common.lasting_view`, `section`, `row`, `separator` |
| Who a message belongs to | `Common.owner_of(interaction)` |
| A message's text or one of its controls | `Views.message_text`, `Views.find_component` |
| Greying out an old message | `Views.disable_message_controls(message)` |
| Replacing the pressed message | `Common.edit_in_place`; for character panels `Characters.show` / `show_attributes` |
| Posting a message about a character | `Common.send_tracked(...)`, then `Characters.refresh_later` if the character changed |
| The player's active character | `Characters.active_character(interaction, user_id)`; on a press, `owner_and_character(interaction)` |
| Everything about a character | `db.get_character_state(user_id, char)`: a `CharacterState` with `usable()`, `bonus()`, `name()` |
| Roll messages | `RollText` (`dye_body`, `do_body`, `recover_body`, `parse_roll`) and `Rolls.dye_view` / `do_view` / `recover_view` |
| Colors and HP rules | `Constants`: `COLOR_ORDER`, `color_emoji`, `sort_by_color`, `swing_accent`, `hp_bracket`; `Theme` |
| A form | `Common.DiceModal` (errors become a notice) |
| Color roles | `ColorRoles`: `assign_swing_color_role`, `remove_swing_color_roles`, `sync_member_swing_color_role`, `color_role` |

If two modules need the same logic, move it into `Source/Utils` or the Dice package instead of copying
it. Helper modules live inside a package or `Source/Utils`, never loose in `Source/Cogs` or `Source`:
`Main.py` loads every `Source/Cogs/*.py` as an extension, and `/owner cogs` loads every `Source/*.py`.

## Rewriting a module (and building a new one)
1. **Understand** it: what it does, its files, tables, and which messages and buttons it posts.
2. **Audit** it, naming files and lines: AI-copy tells (emoji clutter, em dashes, filler, embeds or
   plain-text replies), duplicated code a helper covers, oversized files, hard-coded colors, game
   text that disagrees with the Game rules section, state kept in memory, unclear errors, Discord limits.
3. **Clean up**: reuse and extend helpers first, follow every rule here, keep every fixed name, and
   flag behavior changes.
4. **Verify**: run every test in `scratch/` (see Tests).
5. **Report** by pass: what changed and why, behavior changes, open questions (list them at the end
   instead of stopping to ask), and manual steps (`.env` keys, `/owner sync`).

## When you add or change a command
1. Build it from the helpers above. Keep its name and options if it exists.
2. Staff-only work checks `Permissions.require_member_permissions` (Manage Server for the GM, Manage
   Roles for color roles) and the same check again on its buttons.
3. Describe it in `/help` (`HelpPages.py`) in the rulebook's terms, and in the README command table.
4. If it stores new data, add a column or table in `Database.initialize_database` and add the names
   to `scratch/test_fixed_names.py`.
5. Verify (see Tests). After deploy, new or renamed commands and description changes need `/owner sync`.

## Tests
All offline, against a temporary database; none of them log in to Discord. `scratch/` is local only
(gitignored, like Botzilla's), so the tests live in the owner's workspace and never reach the server.
- `venv\Scripts\python.exe scratch\test_press_everything.py`: runs every command and presses every
  button and form through discord.py's own dispatch, including after simulated restarts, and checks
  who may press, pings, and that no control is kept in memory or sent privately.
- `venv\Scripts\python.exe scratch\test_rolls.py`: roll text reads back, including older formats.
- `venv\Scripts\python.exe scratch\test_fixed_names.py`: tables, columns, commands, options and
  custom_ids are unchanged.
- `venv\Scripts\python.exe scratch\check_code_rules.py`: Python 3.10 f-strings, no `match`, no
  permission reads outside Permissions.py, no embeds or plain-text replies.
- `venv\Scripts\python.exe -m py_compile <changed files>`.

## Releases
Ask the owner before committing. When approved:
1. Commit on `main` in separate commits by topic, and `git push origin main`. Wispbyte pulls `main`
   on start, so never rewrite or force-push commits already pushed: fix forward with a new commit.
2. Update the version badge in the README (its link and text).
3. Tag the release commit `vX.Y.Z`, push the tag, and publish it with
   `gh release create vX.Y.Z -R Megildur/sentiment_bot --title "vX.Y.Z - <summary>" --notes-file <file>`.
   Notes start with `## What's Changed in vX.Y.Z` and follow Look and copy.

## Discord server announcements
- One announcement in a fenced code block, under Discord's 2,000-character limit.
- Layout: `# Sentiment v<version> is out`, then `## New` and `## Fixes` as needed, and an optional
  `-#` line for server owners (for example a permission a feature needs).
- A sentence or two per new feature. Sum fixes up in one line, naming only ones players noticed.
- Copy follows Look and copy, and game terms follow Game rules.
