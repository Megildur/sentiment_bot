"""Names that must never change: tables and columns, commands and options, and custom_ids.

Renaming any of them breaks existing data, every server's commands, or buttons on
messages already posted. Add to these lists; never edit or remove an entry.

    venv\\Scripts\\python.exe scratch\\test_fixed_names.py
"""
import asyncio
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fakes import Harness, check, finish  # noqa: E402

TABLES = {
    "attributes": ["user_id", "char_name", "attribute", "attribute_value"],
    "attributes_names": ["user_id", "char_name", "attribute", "attribute_name"],
    "support_die": ["share_support_user_id", "recieve_support_user_id", "share_support_char_name", "recieve_support_char_name", "attribute", "attribute_name"],
    "selected_char": ["user_id", "char_name"],
    "gm": ["value", "user_id"],
    "npc": ["value", "char_name"],
    "swing": ["user_id", "char_name", "swing", "swing_value"],
    "wounded": ["user_id", "char_name", "wounded"],
    "locked": ["user_id", "char_name", "locked"],
    "hp": ["user_id", "char_name", "current_hp", "max_hp"],
    "guild_color_roles": ["guild_id", "color", "role_id"],
    "active_character_views": ["user_id", "channel_id", "message_id", "view_type", "char_name"],
}

# Command: its options, in order.
COMMANDS = {
    "roll_to_dye": [], "roll_to_do": [], "roll_to_recover": [], "roll_wild": [],
    "set_gm": ["user"], "set_attributes": [], "change_active_character": ["characters"],
    "character_card": [], "wound_die": [], "unwound_die": [], "lock_die": [], "unlock_die": [],
    "drop_swing": [], "support": ["user"], "color_roles": [], "help": [],
    "hp heal": ["amount"], "hp damage": ["amount"], "hp max": [],
}

CUSTOM_IDS = [
    "create_new_char", "change_char_select", "edit_attribute_select", "name_atrs_btn", "add_atrs_btn",
    "delete_atrs_btn", "toggle_npc_btn", "delete_char_select", "close_menu_button", "cancel_delete_char_btn",
    "confirm_delete_char_btn", "new_active_char_select", "change_card_char_select", "manage_max_hp_btn",
    "back_to_card_btn", "pot_flat_hp_btn", "pot_roll_hp_btn", "custom_adj_max_hp_btn", "set_swing_btn",
    "apply_support_btn", "confirm_dm", "color_select_comp", "role_select_comp", "auto_setup_color_roles_btn",
    "sync_my_swing_role_btn", "sync_all_players_btn", "reset_color_role_btn", "paginator_prev", "paginator_next",
    "paginator_indicator",
]

VIEW_TYPES = ["AttributeSetView", "CharacterCardView", "ManageMaxHPView", "CreateCharacterView", "NoCharactersLeftView",
              "RollToDyeView", "RollToDoView", "RollToRecoverView"]


async def main() -> None:
    h = await Harness().start()
    try:
        path = h.cog.db.db_path
        conn = sqlite3.connect(path)
        for table, columns in TABLES.items():
            found = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
            check(found == columns, f"table {table} columns {found}")
        conn.close()

        found = {}
        for command in h.cog.get_app_commands():
            for sub in getattr(command, "commands", None) or [command]:
                name = sub.qualified_name
                found[name] = [p.name for p in sub.parameters]
        check(found == COMMANDS, f"commands or options changed: {found}")

        for custom_id in CUSTOM_IDS:
            owners = [c.__name__ for c in h.bot.dynamic_items if c.__discord_ui_compiled_template__.fullmatch(custom_id)]
            check(len(owners) == 1, f"{custom_id} handled by {owners}")

        from Source.Cogs.Dice import Characters, RollText
        stored = list(Characters.PANELS) + list(RollText.VIEW_TYPES.values())
        check(sorted(stored) == sorted(VIEW_TYPES), f"tracked view types changed: {stored}")
    finally:
        await h.cog.cog_unload()
    finish()


asyncio.run(main())
