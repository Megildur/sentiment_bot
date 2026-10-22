"""Every read and write of Sentiment's data: SQLite at Data/Dice.db through aiosqlite.

Nothing else touches the database file or `self.db`. Table and column names are
fixed (including the misspelled `recieve_support_*` columns): existing servers'
data lives in them, so new data goes in new columns or tables only.
"""
import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import aiosqlite

from .Constants import sort_by_color


@dataclass
class CharacterState:
    """One character as every roll, card and die command sees it."""
    char_name: str
    display_name: str
    attributes: List[Tuple[str, int]]
    names: Dict[str, str]
    swing: Optional[Tuple[str, int]]
    wounded: List[str]
    locked: List[str]
    shared_out: List[str] = field(default_factory=list)

    def bonus(self, color: str) -> int:
        return next((b for c, b in self.attributes if c == color), 0)

    def name(self, color: str) -> str:
        return self.names.get(color, "None")

    def usable(self, *, locked: bool = True, shared_out: bool = True) -> List[Tuple[str, int]]:
        """Attribute dice that aren't wounded, and by default not locked or lent to an ally."""
        skip = set(self.wounded)
        if locked:
            skip.update(self.locked)
        if shared_out:
            skip.update(self.shared_out)
        return [(c, b) for c, b in self.attributes if c not in skip]


def _clean(char_name: str) -> str:
    return char_name.replace(" (NPC)", "").strip()


class DiceDatabase:
    def __init__(self) -> None:
        self.db_path = "Data/Dice.db"
        self.db: Optional[aiosqlite.Connection] = None
        self.db_lock = asyncio.Lock()

    async def connect(self) -> None:
        # A local file: opening it and creating tables takes milliseconds, so this
        # is the one place cog_load may touch storage.
        dir_name = os.path.dirname(self.db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        self.db = await aiosqlite.connect(self.db_path)
        await self.db.execute("PRAGMA journal_mode=WAL;")
        await self.db.execute("PRAGMA synchronous=NORMAL;")
        await self.db.commit()
        await self.initialize_database()

    async def close(self) -> None:
        if self.db:
            await self.db.close()

    async def initialize_database(self) -> None:
        await self.db.execute("CREATE TABLE IF NOT EXISTS attributes (user_id INTEGER, char_name TEXT, attribute TEXT, attribute_value INTEGER, PRIMARY KEY (user_id, attribute, char_name))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS attributes_names (user_id INTEGER, char_name TEXT, attribute TEXT, attribute_name TEXT, PRIMARY KEY (user_id, attribute, char_name))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS support_die (share_support_user_id INTEGER, recieve_support_user_id INTEGER, share_support_char_name TEXT, recieve_support_char_name TEXT, attribute TEXT, attribute_name TEXT, PRIMARY KEY (share_support_user_id, recieve_support_user_id, share_support_char_name, recieve_support_char_name, attribute))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS selected_char (user_id INTEGER PRIMARY KEY, char_name TEXT)")
        # Sentiment used to have one GM for every server; that row is kept, and only read once
        # to give that GM the servers they share with Sentiment (see Dice._move_gm_to_servers).
        await self.db.execute("CREATE TABLE IF NOT EXISTS gm (value INTEGER PRIMARY KEY CHECK (value = 1), user_id INTEGER)")
        await self.db.execute("CREATE TABLE IF NOT EXISTS guild_gm (guild_id INTEGER PRIMARY KEY, user_id INTEGER)")
        await self.db.execute("CREATE TABLE IF NOT EXISTS npc (value INTEGER CHECK (value = 1), char_name TEXT, PRIMARY KEY (value, char_name))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS swing (user_id INTEGER, char_name TEXT, swing TEXT, swing_value INTEGER, PRIMARY KEY (user_id, char_name))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS wounded (user_id INTEGER, char_name TEXT, wounded TEXT, PRIMARY KEY (user_id, char_name, wounded))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS locked (user_id INTEGER, char_name TEXT, locked TEXT, PRIMARY KEY (user_id, char_name, locked))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS hp (user_id INTEGER, char_name TEXT, current_hp INTEGER DEFAULT 10, max_hp INTEGER DEFAULT 10, PRIMARY KEY (user_id, char_name))")
        # Characters made before HP existed start at 10 / 10.
        await self.db.execute("INSERT OR IGNORE INTO hp (user_id, char_name, current_hp, max_hp) SELECT DISTINCT user_id, char_name, 10, 10 FROM attributes")
        await self.db.execute("CREATE TABLE IF NOT EXISTS guild_color_roles (guild_id INTEGER, color TEXT, role_id INTEGER, PRIMARY KEY (guild_id, color))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS active_character_views (user_id INTEGER, channel_id INTEGER, message_id INTEGER PRIMARY KEY, view_type TEXT, char_name TEXT DEFAULT '')")
        try:
            # Databases from before v1.0.4 lack this column.
            await self.db.execute("ALTER TABLE active_character_views ADD COLUMN char_name TEXT DEFAULT ''")
        except aiosqlite.OperationalError:
            pass
        await self.db.commit()

    async def _one(self, sql: str, args: Sequence[Any] = ()) -> Optional[tuple]:
        async with self.db_lock:
            cursor = await self.db.execute(sql, args)
            return await cursor.fetchone()

    async def _all(self, sql: str, args: Sequence[Any] = ()) -> List[tuple]:
        async with self.db_lock:
            cursor = await self.db.execute(sql, args)
            return list(await cursor.fetchall())

    async def _write(self, *statements: Tuple[str, Sequence[Any]]) -> int:
        """Run the statements as one commit. Returns the last one's row count."""
        async with self.db_lock:
            rowcount = 0
            for sql, args in statements:
                cursor = await self.db.execute(sql, args)
                rowcount = cursor.rowcount
            await self.db.commit()
            return rowcount

    # Each server's GM. Outside a server (guild_id None) there is no GM.

    async def get_gm(self, guild_id: Optional[int]) -> Optional[int]:
        if guild_id is None:
            return None
        row = await self._one("SELECT user_id FROM guild_gm WHERE guild_id = ?", (guild_id,))
        return row[0] if row else None

    async def set_gm(self, guild_id: int, user_id: int) -> None:
        await self._write(("INSERT OR REPLACE INTO guild_gm (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id)))

    async def is_gm(self, guild_id: Optional[int], user_id: int) -> bool:
        return guild_id is not None and await self.get_gm(guild_id) == user_id

    async def get_legacy_gm(self) -> Optional[int]:
        """The one GM for every server from before GMs were per server, if there was one."""
        row = await self._one("SELECT user_id FROM gm WHERE value = 1")
        return row[0] if row else None

    async def has_server_gms(self) -> bool:
        return await self._one("SELECT 1 FROM guild_gm LIMIT 1") is not None

    # Characters and attributes

    async def set_attributes(self, user_id: int, char_name: str, attributes: List[Tuple[str, int]]) -> None:
        statements = [
            ("INSERT OR REPLACE INTO attributes (user_id, char_name, attribute, attribute_value) VALUES (?, ?, ?, ?)",
             (user_id, char_name, color, bonus))
            for color, bonus in attributes
        ]
        statements.append(("INSERT OR IGNORE INTO hp (user_id, char_name, current_hp, max_hp) VALUES (?, ?, 10, 10)", (user_id, char_name)))
        await self._write(*statements)

    async def edit_attribute(self, user_id: int, char_name: str, old_color: str, new_color: str, new_bonus: int) -> None:
        if old_color != new_color:
            await self._write(
                ("DELETE FROM attributes WHERE user_id = ? AND char_name = ? AND attribute = ?", (user_id, char_name, old_color)),
                ("INSERT OR REPLACE INTO attributes (user_id, char_name, attribute, attribute_value) VALUES (?, ?, ?, ?)",
                 (user_id, char_name, new_color, new_bonus)),
            )
        else:
            await self._write(("UPDATE attributes SET attribute_value = ? WHERE user_id = ? AND char_name = ? AND attribute = ?",
                               (new_bonus, user_id, char_name, old_color)))

    async def add_attribute(self, user_id: int, char_name: str, color: str, bonus: int) -> None:
        await self._write(("INSERT OR REPLACE INTO attributes (user_id, char_name, attribute, attribute_value) VALUES (?, ?, ?, ?)",
                           (user_id, char_name, color, bonus)))

    async def delete_attribute(self, user_id: int, char_name: str, color: str) -> None:
        await self._write(("DELETE FROM attributes WHERE user_id = ? AND char_name = ? AND attribute = ?", (user_id, char_name, color)))

    async def get_character_attributes(self, user_id: int, char_name: str) -> List[Tuple[str, int]]:
        return await self._all("SELECT attribute, attribute_value FROM attributes WHERE user_id = ? AND char_name = ?", (user_id, char_name))

    async def set_attribute_name(self, user_id: int, char_name: str, attribute: str, name: str) -> None:
        await self._write(("INSERT OR REPLACE INTO attributes_names (user_id, char_name, attribute, attribute_name) VALUES (?, ?, ?, ?)",
                           (user_id, char_name, attribute, name)))

    async def get_attribute_names(self, user_id: int, char_name: str) -> Dict[str, str]:
        rows = await self._all("SELECT attribute, attribute_name FROM attributes_names WHERE user_id = ? AND char_name = ?", (user_id, char_name))
        return {color: name for color, name in rows}

    async def get_selected_char(self, user_id: int) -> Optional[str]:
        row = await self._one("SELECT char_name FROM selected_char WHERE user_id = ?", (user_id,))
        return row[0] if row else None

    async def set_selected_char(self, user_id: int, char_name: str) -> None:
        await self._write(("INSERT OR REPLACE INTO selected_char (user_id, char_name) VALUES (?, ?)", (user_id, char_name)))

    async def get_selected_chars(self) -> List[Tuple[int, str]]:
        """Every player's active character, for syncing a whole server's color roles."""
        return await self._all("SELECT user_id, char_name FROM selected_char")

    async def get_all_characters(self, user_id: int) -> List[str]:
        rows = await self._all("SELECT DISTINCT char_name FROM attributes WHERE user_id = ?", (user_id,))
        return [r[0] for r in rows]

    async def completely_delete_character(self, user_id: int, char_name: str) -> None:
        clean_name = _clean(char_name)
        await self._write(
            ("DELETE FROM attributes WHERE user_id = ? AND char_name = ?", (user_id, char_name)),
            ("DELETE FROM attributes_names WHERE user_id = ? AND char_name = ?", (user_id, char_name)),
            ("DELETE FROM selected_char WHERE user_id = ? AND char_name = ?", (user_id, char_name)),
            ("DELETE FROM swing WHERE user_id = ? AND char_name = ?", (user_id, char_name)),
            ("DELETE FROM wounded WHERE user_id = ? AND char_name = ?", (user_id, char_name)),
            ("DELETE FROM locked WHERE user_id = ? AND char_name = ?", (user_id, char_name)),
            ("DELETE FROM hp WHERE user_id = ? AND char_name = ?", (user_id, char_name)),
            ("DELETE FROM support_die WHERE (share_support_user_id = ? AND share_support_char_name = ?) OR (recieve_support_user_id = ? AND recieve_support_char_name = ?)",
             (user_id, char_name, user_id, char_name)),
            ("DELETE FROM npc WHERE char_name = ? OR char_name = ?", (char_name, clean_name)),
        )

    async def get_character_state(self, user_id: int, char_name: str) -> CharacterState:
        attributes = sort_by_color(await self.get_character_attributes(user_id, char_name))
        return CharacterState(
            char_name=char_name,
            display_name=await self.get_char_display_name(char_name),
            attributes=attributes,
            names=await self.get_attribute_names(user_id, char_name),
            swing=await self.get_swing(user_id, char_name),
            wounded=await self.get_wounded(user_id, char_name),
            locked=await self.get_locked(user_id, char_name),
            shared_out=await self.get_active_shared_out_dice(user_id, char_name),
        )

    # NPCs (marked by the GM; kept by character name)

    async def is_npc(self, char_name: str) -> bool:
        if not char_name:
            return False
        clean_name = _clean(char_name)
        row = await self._one("SELECT 1 FROM npc WHERE value = 1 AND (char_name = ? OR char_name = ?)", (char_name, clean_name))
        return row is not None

    async def toggle_npc(self, char_name: str) -> bool:
        clean_name = _clean(char_name)
        if await self.is_npc(clean_name):
            await self._write(("DELETE FROM npc WHERE char_name = ? OR char_name = ?", (clean_name, f"{clean_name} (NPC)")))
            return False
        await self._write(("INSERT OR REPLACE INTO npc (value, char_name) VALUES (1, ?)", (clean_name,)))
        return True

    async def get_char_display_name(self, char_name: str) -> str:
        if not char_name:
            return ""
        clean_name = _clean(char_name)
        return f"{clean_name} (NPC)" if await self.is_npc(clean_name) else clean_name

    # Swing, wounded and locked dice

    async def get_swing(self, user_id: int, char_name: str) -> Optional[Tuple[str, int]]:
        row = await self._one("SELECT swing, swing_value FROM swing WHERE user_id = ? AND char_name = ?", (user_id, char_name))
        return (row[0], row[1]) if row else None

    async def set_swing(self, user_id: int, char_name: str, attribute: str, swing_value: int) -> None:
        await self._write(("INSERT OR REPLACE INTO swing (user_id, char_name, swing, swing_value) VALUES (?, ?, ?, ?)",
                           (user_id, char_name, attribute, swing_value)))

    async def drop_swing(self, user_id: int, char_name: str) -> bool:
        return await self._write(("DELETE FROM swing WHERE user_id = ? AND char_name = ?", (user_id, char_name))) > 0

    async def get_wounded(self, user_id: int, char_name: str) -> List[str]:
        rows = await self._all("SELECT wounded FROM wounded WHERE user_id = ? AND char_name = ?", (user_id, char_name))
        return [r[0] for r in rows]

    async def wound_die(self, user_id: int, char_name: str, attribute: str) -> None:
        # A wound unlocks every die, and a wounded swing die stops being the swing.
        await self._write(
            ("DELETE FROM locked WHERE user_id = ? AND char_name = ?", (user_id, char_name)),
            ("DELETE FROM swing WHERE user_id = ? AND char_name = ? AND swing = ?", (user_id, char_name, attribute)),
            ("INSERT OR REPLACE INTO wounded (user_id, char_name, wounded) VALUES (?, ?, ?)", (user_id, char_name, attribute)),
        )

    async def unwound_die(self, user_id: int, char_name: str, attribute: str) -> bool:
        return await self._write(("DELETE FROM wounded WHERE user_id = ? AND char_name = ? AND wounded = ?", (user_id, char_name, attribute))) > 0

    async def get_locked(self, user_id: int, char_name: str) -> List[str]:
        rows = await self._all("SELECT locked FROM locked WHERE user_id = ? AND char_name = ?", (user_id, char_name))
        return [r[0] for r in rows]

    async def lock_die(self, user_id: int, char_name: str, attribute: str) -> None:
        # Locking the swing die drops the swing.
        await self._write(
            ("DELETE FROM swing WHERE user_id = ? AND char_name = ? AND swing = ?", (user_id, char_name, attribute)),
            ("INSERT OR REPLACE INTO locked (user_id, char_name, locked) VALUES (?, ?, ?)", (user_id, char_name, attribute)),
        )

    async def unlock_die(self, user_id: int, char_name: str, attribute: str) -> bool:
        return await self._write(("DELETE FROM locked WHERE user_id = ? AND char_name = ? AND locked = ?", (user_id, char_name, attribute))) > 0

    async def unlock_all_dice(self, user_id: int, char_name: str) -> None:
        await self._write(("DELETE FROM locked WHERE user_id = ? AND char_name = ?", (user_id, char_name)))

    # Support dice lent between players

    async def add_support_die(self, share_user_id: int, share_char: str, recv_user_id: int, recv_char: str, attribute: str, attribute_name: str) -> None:
        await self._write(("INSERT OR REPLACE INTO support_die (share_support_user_id, recieve_support_user_id, share_support_char_name, recieve_support_char_name, attribute, attribute_name) VALUES (?, ?, ?, ?, ?, ?)",
                           (share_user_id, recv_user_id, share_char, recv_char, attribute, attribute_name)))

    async def get_pending_support_dice(self, recv_user_id: int, recv_char: str) -> List[dict]:
        rows = await self._all("SELECT share_support_user_id, share_support_char_name, attribute, attribute_name FROM support_die WHERE recieve_support_user_id = ? AND recieve_support_char_name = ?",
                               (recv_user_id, recv_char))
        return [{"share_user_id": r[0], "share_char_name": r[1], "attribute": r[2], "attribute_name": r[3]} for r in rows]

    async def get_active_shared_out_dice(self, share_user_id: int, share_char: str) -> List[str]:
        rows = await self._all("SELECT attribute FROM support_die WHERE share_support_user_id = ? AND share_support_char_name = ?", (share_user_id, share_char))
        return [r[0] for r in rows]

    async def consume_support_die(self, share_user_id: int, share_char: str, recv_user_id: int, recv_char: str, attribute: str) -> None:
        # A used support die goes back to its owner locked, and stops being their swing.
        await self._write(
            ("DELETE FROM support_die WHERE share_support_user_id = ? AND recieve_support_user_id = ? AND share_support_char_name = ? AND recieve_support_char_name = ? AND attribute = ?",
             (share_user_id, recv_user_id, share_char, recv_char, attribute)),
            ("INSERT OR REPLACE INTO locked (user_id, char_name, locked) VALUES (?, ?, ?)", (share_user_id, share_char, attribute)),
            ("DELETE FROM swing WHERE user_id = ? AND char_name = ? AND swing = ?", (share_user_id, share_char, attribute)),
        )

    # HP

    async def get_hp(self, user_id: int, char_name: str) -> Tuple[int, int]:
        row = await self._one("SELECT current_hp, max_hp FROM hp WHERE user_id = ? AND char_name = ?", (user_id, char_name))
        if row is not None:
            return int(row[0]), int(row[1])
        await self._write(("INSERT OR IGNORE INTO hp (user_id, char_name, current_hp, max_hp) VALUES (?, ?, 10, 10)", (user_id, char_name)))
        return 10, 10

    async def set_hp(self, user_id: int, char_name: str, current_hp: int, max_hp: int) -> Tuple[int, int]:
        max_hp = max(1, int(max_hp))
        current_hp = max(0, min(int(current_hp), max_hp))
        await self._write(("INSERT OR REPLACE INTO hp (user_id, char_name, current_hp, max_hp) VALUES (?, ?, ?, ?)",
                           (user_id, char_name, current_hp, max_hp)))
        return current_hp, max_hp

    async def heal_hp(self, user_id: int, char_name: str, amount: int) -> Tuple[int, int, int]:
        old_hp, max_hp = await self.get_hp(user_id, char_name)
        new_hp = min(max_hp, max(0, old_hp + max(0, int(amount))))
        await self.set_hp(user_id, char_name, new_hp, max_hp)
        return old_hp, new_hp, max_hp

    async def damage_hp(self, user_id: int, char_name: str, amount: int) -> Tuple[int, int, int]:
        old_hp, max_hp = await self.get_hp(user_id, char_name)
        new_hp = max(0, old_hp - max(0, int(amount)))
        await self.set_hp(user_id, char_name, new_hp, max_hp)
        return old_hp, new_hp, max_hp

    async def adjust_max_hp(self, user_id: int, char_name: str, delta: int) -> Tuple[int, int, int, int]:
        # Raising max HP raises current HP by the same amount; lowering it only caps current HP.
        old_cur, old_max = await self.get_hp(user_id, char_name)
        new_max = max(1, old_max + int(delta))
        actual_delta = new_max - old_max
        new_cur = min(new_max, old_cur + actual_delta) if actual_delta > 0 else min(old_cur, new_max)
        await self.set_hp(user_id, char_name, new_cur, new_max)
        return old_cur, old_max, new_cur, new_max

    async def set_max_hp_value(self, user_id: int, char_name: str, target_max: int) -> Tuple[int, int, int, int]:
        _, old_max = await self.get_hp(user_id, char_name)
        return await self.adjust_max_hp(user_id, char_name, max(1, int(target_max)) - old_max)

    async def recover_hp(self, user_id: int, char_name: str, roll_total: int, has_unwounded_dice: bool) -> Tuple[int, int, int]:
        # At 0 HP the roll sets HP; above 0 it adds to it; with every die wounded you get 1 HP.
        old_hp, max_hp = await self.get_hp(user_id, char_name)
        if not has_unwounded_dice:
            new_hp = min(max_hp, old_hp + 1)
        elif old_hp <= 0:
            new_hp = min(max_hp, max(0, int(roll_total)))
        else:
            new_hp = min(max_hp, old_hp + max(0, int(roll_total)))
        await self.set_hp(user_id, char_name, new_hp, max_hp)
        return old_hp, new_hp, max_hp

    # Color roles each server picked

    async def get_guild_color_roles(self, guild_id: int) -> Dict[str, int]:
        rows = await self._all("SELECT color, role_id FROM guild_color_roles WHERE guild_id = ?", (guild_id,))
        return {color: role_id for color, role_id in rows}

    async def set_guild_color_role(self, guild_id: int, color: str, role_id: int) -> None:
        await self._write(("INSERT OR REPLACE INTO guild_color_roles (guild_id, color, role_id) VALUES (?, ?, ?)", (guild_id, color, role_id)))

    async def delete_guild_color_role(self, guild_id: int, color: str) -> None:
        await self._write(("DELETE FROM guild_color_roles WHERE guild_id = ? AND color = ?", (guild_id, color)))

    # Messages that show a player's character, refreshed when it changes

    async def track_active_view(self, user_id: int, channel_id: int, message_id: int, view_type: str, char_name: str = "") -> None:
        await self._write(("INSERT OR REPLACE INTO active_character_views (user_id, channel_id, message_id, view_type, char_name) VALUES (?, ?, ?, ?, ?)",
                           (user_id, channel_id, message_id, view_type, char_name)))

    async def untrack_active_view(self, message_id: int) -> None:
        await self._write(("DELETE FROM active_character_views WHERE message_id = ?", (message_id,)))

    async def get_user_active_views(self, user_id: int) -> List[Tuple[int, int, str, str]]:
        rows = await self._all("SELECT channel_id, message_id, view_type, char_name FROM active_character_views WHERE user_id = ?", (user_id,))
        return [(r[0], r[1], r[2], r[3] or "") for r in rows]

    async def get_tracked_view(self, message_id: int) -> Optional[Tuple[int, str, str]]:
        """(user_id, view_type, char_name) for a tracked message, or None."""
        row = await self._one("SELECT user_id, view_type, char_name FROM active_character_views WHERE message_id = ?", (message_id,))
        return (row[0], row[1], row[2] or "") if row else None
