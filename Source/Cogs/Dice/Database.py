import os
import discord
import aiosqlite
import asyncio
from typing import Optional, List, Tuple
from .Views import DatabaseFailView, DatabaseSuccessView, SetValuesModal, AttributeSetView

class DiceDatabase():
    def __init__(self, bot):
        self.db_path = "Data/Dice.db"
        self.db = None
        self.db_lock = asyncio.Lock()
        self.bot = bot

    async def connect(self):
        dir_name = os.path.dirname(self.db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        self.db = await aiosqlite.connect(self.db_path)
        await self.db.execute("PRAGMA journal_mode=WAL;")
        await self.db.execute("PRAGMA synchronous=NORMAL;")
        await self.db.commit()
        await self.initialize_database()

    async def close(self):
        if self.db:
            await self.db.close()

    async def initialize_database(self):
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS attributes (
                user_id INTEGER,
                char_name TEXT,
                attribute TEXT,
                attribute_value INTEGER,
                PRIMARY KEY (user_id, attribute, char_name)
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS attributes_names (
                user_id INTEGER,
                char_name TEXT,
                attribute TEXT,
                attribute_name TEXT,
                PRIMARY KEY (user_id, attribute, char_name)
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS support_die (
                share_support_user_id INTEGER,
                recieve_support_user_id INTEGER,
                share_support_char_name TEXT,
                recieve_support_char_name TEXT,
                attribute TEXT,
                attribute_name TEXT,
                PRIMARY KEY (share_support_user_id, recieve_support_user_id, share_support_char_name, recieve_support_char_name, attribute)
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS selected_char (
                user_id INTEGER PRIMARY KEY,
                char_name TEXT
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS gm (
                value INTEGER PRIMARY KEY CHECK (value = 1),
                user_id INTEGER 
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS npc (
                value INTEGER CHECK (value = 1),
                char_name TEXT,
                PRIMARY KEY (value, char_name)
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS swing (
                user_id INTEGER,
                char_name TEXT,
                swing TEXT,
                swing_value INTEGER,
                PRIMARY KEY (user_id, char_name)
                )
            ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS wounded (
                user_id INTEGER,
                char_name TEXT,
                wounded TEXT,
                PRIMARY KEY (user_id, char_name, wounded)
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS locked (
                user_id INTEGER,
                char_name TEXT,
                locked TEXT,
                PRIMARY KEY (user_id, char_name, locked)
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS hp (
                user_id INTEGER,
                char_name TEXT,
                current_hp INTEGER DEFAULT 10,
                max_hp INTEGER DEFAULT 10,
                PRIMARY KEY (user_id, char_name)
            )
        ''')
        await self.db.execute('''
            INSERT OR IGNORE INTO hp (user_id, char_name, current_hp, max_hp)
            SELECT DISTINCT user_id, char_name, 10, 10 FROM attributes
        ''')
        await self.db.commit()

    async def set_gm_check(self, interaction, user_id: int):
        async with self.db_lock:
            
            cursor = await self.db.execute("SELECT user_id FROM gm WHERE value = 1")
            result = await cursor.fetchone()

        if result is not None:
            gm = result[0]
            body = f"**<@{result[0]}>** is already set as gm, would you like to change the gm to <@{user_id}>?"
            footer = "-# press the button to change the gm"
            view = DatabaseFailView(self.bot, body, footer, db_manager=self, change=user_id)
            await interaction.response.send_message(view=view)
        else:
            await self.set_gm(interaction, user_id)

    async def set_gm(self, interaction, user_id: int):
        async with self.db_lock:
            await self.db.execute(
                "INSERT OR REPLACE INTO gm (value, user_id) VALUES (1, ?)", 
                (user_id,)
            )
            await self.db.commit()
        body = f"**<@{user_id}>** is now set as the gm!"
        view = DatabaseSuccessView(self.bot, body, user_id)
        await interaction.response.send_message(view=view)

    async def check_attributes(self, bot, interaction: discord.Interaction, char_name: str):
        async with self.db_lock:
            cursor = await self.db.execute(
                "SELECT attribute, attribute_value FROM attributes WHERE user_id = ? AND char_name = ?",
                (interaction.user.id, char_name)
            )
            result = await cursor.fetchall()
        return result

    async def set_attributes(self, interaction: discord.Interaction, char_name: str, attributes: list):
        async with self.db_lock:
            data = [(interaction.user.id, char_name, color, bonus) for color, bonus in attributes]
            
            if data:
                await self.db.executemany(
                    "INSERT OR REPLACE INTO attributes (user_id, char_name, attribute, attribute_value) VALUES (?, ?, ?, ?)",
                    data
                )
            await self.db.execute(
                "INSERT OR IGNORE INTO hp (user_id, char_name, current_hp, max_hp) VALUES (?, ?, 10, 10)",
                (interaction.user.id, char_name)
            )
            await self.db.commit()

    async def edit_attribute(self, interaction: discord.Interaction, char_name: str, old_color: str, new_color: str, new_bonus: int):
        async with self.db_lock:
            if old_color != new_color:
                await self.db.execute(
                    "DELETE FROM attributes WHERE user_id = ? AND char_name = ? AND attribute = ?",
                    (interaction.user.id, char_name, old_color)
                )
            
                await self.db.execute(
                    "INSERT OR REPLACE INTO attributes (user_id, char_name, attribute, attribute_value) VALUES (?, ?, ?, ?)",
                    (interaction.user.id, char_name, new_color, new_bonus)
                )
            else:
                await self.db.execute(
                    "UPDATE attributes SET attribute_value = ? WHERE user_id = ? AND char_name = ? AND attribute = ?",
                    (new_bonus, interaction.user.id, char_name, old_color)
                )
                
            await self.db.commit()

    async def add_attribute(self, interaction: discord.Interaction, char_name: str, color: str, bonus: int):
        async with self.db_lock:
            await self.db.execute(
                "INSERT OR REPLACE INTO attributes (user_id, char_name, attribute, attribute_value) VALUES (?, ?, ?, ?)",
                (interaction.user.id, char_name, color, bonus)
            )
            await self.db.commit()

    async def delete_attribute(self, interaction: discord.Interaction, char_name: str, color: str):
        async with self.db_lock:
            await self.db.execute(
                "DELETE FROM attributes WHERE user_id = ? AND char_name = ? AND attribute = ?",
                (interaction.user.id, char_name, color)
            )
            await self.db.commit()

    async def get_selected_char(self, user_id: int):
        async with self.db_lock:
            cursor = await self.db.execute("SELECT char_name FROM selected_char WHERE user_id = ?", (user_id,))
            res = await cursor.fetchone()
            return res[0] if res else None

    async def set_selected_char(self, user_id: int, char_name: str):
        async with self.db_lock:
            await self.db.execute(
                "INSERT OR REPLACE INTO selected_char (user_id, char_name) VALUES (?, ?)", 
                (user_id, char_name)
            )
            await self.db.commit()

    async def get_all_characters(self, user_id: int):
        async with self.db_lock:
            cursor = await self.db.execute("SELECT DISTINCT char_name FROM attributes WHERE user_id = ?", (user_id,))
            res = await cursor.fetchall()
            return [r[0] for r in res] if res else []

    async def completely_delete_character(self, user_id: int, char_name: str):
        async with self.db_lock:
            await self.db.execute("DELETE FROM attributes WHERE user_id = ? AND char_name = ?", (user_id, char_name))
            await self.db.execute("DELETE FROM attributes_names WHERE user_id = ? AND char_name = ?", (user_id, char_name))
            await self.db.execute("DELETE FROM selected_char WHERE user_id = ? AND char_name = ?", (user_id, char_name))
            await self.db.execute("DELETE FROM swing WHERE user_id = ? AND char_name = ?", (user_id, char_name))
            await self.db.execute("DELETE FROM wounded WHERE user_id = ? AND char_name = ?", (user_id, char_name))
            await self.db.execute("DELETE FROM locked WHERE user_id = ? AND char_name = ?", (user_id, char_name))
            await self.db.execute("DELETE FROM hp WHERE user_id = ? AND char_name = ?", (user_id, char_name))
            await self.db.execute(
                "DELETE FROM support_die WHERE (share_support_user_id = ? AND share_support_char_name = ?) OR (recieve_support_user_id = ? AND recieve_support_char_name = ?)",
                (user_id, char_name, user_id, char_name)
            )
            clean_name = char_name.replace(" (NPC)", "").strip()
            await self.db.execute("DELETE FROM npc WHERE char_name = ? OR char_name = ?", (char_name, clean_name))
            await self.db.commit()

    async def set_attribute_name(self, interaction: discord.Interaction, char_name: str, attribute: str, name: str):
        async with self.db_lock:
            await self.db.execute(
                "INSERT OR REPLACE INTO attributes_names (user_id, char_name, attribute, attribute_name) VALUES (?, ?, ?, ?)",
                (interaction.user.id, char_name, attribute, name)
            )
            await self.db.commit()

    async def get_attribute_names(self, user_id: int, char_name: str) -> dict:
        async with self.db_lock:
            cursor = await self.db.execute(
                "SELECT attribute, attribute_name FROM attributes_names WHERE user_id = ? AND char_name = ?",
                (user_id, char_name)
            )
            result = await cursor.fetchall()
            
            return {row[0]: row[1] for row in result} if result else {}

    # --- GM & NPC Helpers ---
    async def get_gm(self) -> Optional[int]:
        async with self.db_lock:
            cursor = await self.db.execute("SELECT user_id FROM gm WHERE value = 1")
            res = await cursor.fetchone()
            return res[0] if res else None

    async def is_gm(self, user_id: int) -> bool:
        gm_id = await self.get_gm()
        return gm_id == user_id

    async def is_npc(self, char_name: str) -> bool:
        if not char_name:
            return False
        clean_name = char_name.replace(" (NPC)", "").strip()
        async with self.db_lock:
            cursor = await self.db.execute("SELECT 1 FROM npc WHERE value = 1 AND (char_name = ? OR char_name = ?)", (char_name, clean_name))
            res = await cursor.fetchone()
            return res is not None

    async def toggle_npc(self, char_name: str) -> bool:
        clean_name = char_name.replace(" (NPC)", "").strip()
        is_currently_npc = await self.is_npc(clean_name)
        async with self.db_lock:
            if is_currently_npc:
                await self.db.execute("DELETE FROM npc WHERE char_name = ? OR char_name = ?", (clean_name, f"{clean_name} (NPC)"))
                await self.db.commit()
                return False
            else:
                await self.db.execute("INSERT OR REPLACE INTO npc (value, char_name) VALUES (1, ?)", (clean_name,))
                await self.db.commit()
                return True

    async def get_char_display_name(self, char_name: str) -> str:
        if not char_name:
            return ""
        clean_name = char_name.replace(" (NPC)", "").strip()
        if await self.is_npc(clean_name):
            return f"{clean_name} (NPC)"
        return clean_name

    # --- Attributes ---
    async def get_character_attributes(self, user_id: int, char_name: str) -> list[tuple[str, int]]:
        async with self.db_lock:
            cursor = await self.db.execute(
                "SELECT attribute, attribute_value FROM attributes WHERE user_id = ? AND char_name = ?",
                (user_id, char_name)
            )
            return await cursor.fetchall()

    # --- Swing ---
    async def get_swing(self, user_id: int, char_name: str) -> Optional[tuple[str, int]]:
        async with self.db_lock:
            cursor = await self.db.execute(
                "SELECT swing, swing_value FROM swing WHERE user_id = ? AND char_name = ?",
                (user_id, char_name)
            )
            res = await cursor.fetchone()
            return (res[0], res[1]) if res else None

    async def set_swing(self, user_id: int, char_name: str, attribute: str, swing_value: int):
        async with self.db_lock:
            await self.db.execute(
                "INSERT OR REPLACE INTO swing (user_id, char_name, swing, swing_value) VALUES (?, ?, ?, ?)",
                (user_id, char_name, attribute, swing_value)
            )
            await self.db.commit()

    async def drop_swing(self, user_id: int, char_name: str) -> bool:
        async with self.db_lock:
            cursor = await self.db.execute(
                "DELETE FROM swing WHERE user_id = ? AND char_name = ?",
                (user_id, char_name)
            )
            await self.db.commit()
            return cursor.rowcount > 0

    # --- Wounded ---
    async def get_wounded(self, user_id: int, char_name: str) -> list[str]:
        async with self.db_lock:
            cursor = await self.db.execute(
                "SELECT wounded FROM wounded WHERE user_id = ? AND char_name = ?",
                (user_id, char_name)
            )
            rows = await cursor.fetchall()
            return [r[0] for r in rows] if rows else []

    async def wound_die(self, user_id: int, char_name: str, attribute: str):
        async with self.db_lock:
            # 1. Unlock all locked dice (Sentiment rule: When you are Wounded, immediately Unlock all dice)
            await self.db.execute("DELETE FROM locked WHERE user_id = ? AND char_name = ?", (user_id, char_name))
            # 2. If the wounded die was swing, drop swing
            await self.db.execute("DELETE FROM swing WHERE user_id = ? AND char_name = ? AND swing = ?", (user_id, char_name, attribute))
            # 3. Add to wounded table
            await self.db.execute(
                "INSERT OR REPLACE INTO wounded (user_id, char_name, wounded) VALUES (?, ?, ?)",
                (user_id, char_name, attribute)
            )
            await self.db.commit()

    async def unwound_die(self, user_id: int, char_name: str, attribute: str) -> bool:
        async with self.db_lock:
            cursor = await self.db.execute(
                "DELETE FROM wounded WHERE user_id = ? AND char_name = ? AND wounded = ?",
                (user_id, char_name, attribute)
            )
            await self.db.commit()
            return cursor.rowcount > 0

    # --- Locked ---
    async def get_locked(self, user_id: int, char_name: str) -> list[str]:
        async with self.db_lock:
            cursor = await self.db.execute(
                "SELECT locked FROM locked WHERE user_id = ? AND char_name = ?",
                (user_id, char_name)
            )
            rows = await cursor.fetchall()
            return [r[0] for r in rows] if rows else []

    async def lock_die(self, user_id: int, char_name: str, attribute: str):
        async with self.db_lock:
            # If the die being locked is your swing it is removed "dropped" as your swing
            await self.db.execute("DELETE FROM swing WHERE user_id = ? AND char_name = ? AND swing = ?", (user_id, char_name, attribute))
            await self.db.execute(
                "INSERT OR REPLACE INTO locked (user_id, char_name, locked) VALUES (?, ?, ?)",
                (user_id, char_name, attribute)
            )
            await self.db.commit()

    async def unlock_die(self, user_id: int, char_name: str, attribute: str) -> bool:
        async with self.db_lock:
            cursor = await self.db.execute(
                "DELETE FROM locked WHERE user_id = ? AND char_name = ? AND locked = ?",
                (user_id, char_name, attribute)
            )
            await self.db.commit()
            return cursor.rowcount > 0

    async def unlock_all_dice(self, user_id: int, char_name: str):
        async with self.db_lock:
            await self.db.execute(
                "DELETE FROM locked WHERE user_id = ? AND char_name = ?",
                (user_id, char_name)
            )
            await self.db.commit()

    # --- Support Die ---
    async def add_support_die(self, share_user_id: int, share_char: str, recv_user_id: int, recv_char: str, attribute: str, attribute_name: str):
        async with self.db_lock:
            await self.db.execute(
                "INSERT OR REPLACE INTO support_die (share_support_user_id, recieve_support_user_id, share_support_char_name, recieve_support_char_name, attribute, attribute_name) VALUES (?, ?, ?, ?, ?, ?)",
                (share_user_id, recv_user_id, share_char, recv_char, attribute, attribute_name)
            )
            await self.db.commit()

    async def get_pending_support_dice(self, recv_user_id: int, recv_char: str) -> list[dict]:
        async with self.db_lock:
            cursor = await self.db.execute(
                "SELECT share_support_user_id, share_support_char_name, attribute, attribute_name FROM support_die WHERE recieve_support_user_id = ? AND recieve_support_char_name = ?",
                (recv_user_id, recv_char)
            )
            rows = await cursor.fetchall()
            return [
                {
                    "share_user_id": r[0],
                    "share_char_name": r[1],
                    "attribute": r[2],
                    "attribute_name": r[3]
                }
                for r in rows
            ]

    async def get_active_shared_out_dice(self, share_user_id: int, share_char: str) -> list[str]:
        async with self.db_lock:
            cursor = await self.db.execute(
                "SELECT attribute FROM support_die WHERE share_support_user_id = ? AND share_support_char_name = ?",
                (share_user_id, share_char)
            )
            rows = await cursor.fetchall()
            return [r[0] for r in rows] if rows else []

    async def consume_support_die(self, share_user_id: int, share_char: str, recv_user_id: int, recv_char: str, attribute: str):
        async with self.db_lock:
            # 1. Remove from support_die
            await self.db.execute(
                "DELETE FROM support_die WHERE share_support_user_id = ? AND recieve_support_user_id = ? AND share_support_char_name = ? AND recieve_support_char_name = ? AND attribute = ?",
                (share_user_id, recv_user_id, share_char, recv_char, attribute)
            )
            # 2. Return to donor locked! (insert into locked)
            await self.db.execute(
                "INSERT OR REPLACE INTO locked (user_id, char_name, locked) VALUES (?, ?, ?)",
                (share_user_id, share_char, attribute)
            )
            # 3. If it was donor's swing, drop swing
            await self.db.execute(
                "DELETE FROM swing WHERE user_id = ? AND char_name = ? AND swing = ?",
                (share_user_id, share_char, attribute)
            )
            await self.db.commit()

    # --- HP Helpers ---
    async def get_hp(self, user_id: int, char_name: str) -> Tuple[int, int]:
        async with self.db_lock:
            cursor = await self.db.execute(
                "SELECT current_hp, max_hp FROM hp WHERE user_id = ? AND char_name = ?",
                (user_id, char_name)
            )
            row = await cursor.fetchone()
            if row is not None:
                return int(row[0]), int(row[1])
            await self.db.execute(
                "INSERT OR IGNORE INTO hp (user_id, char_name, current_hp, max_hp) VALUES (?, ?, 10, 10)",
                (user_id, char_name)
            )
            await self.db.commit()
            return 10, 10

    async def set_hp(self, user_id: int, char_name: str, current_hp: int, max_hp: int) -> Tuple[int, int]:
        max_hp = max(1, int(max_hp))
        current_hp = max(0, min(int(current_hp), max_hp))
        async with self.db_lock:
            await self.db.execute(
                "INSERT OR REPLACE INTO hp (user_id, char_name, current_hp, max_hp) VALUES (?, ?, ?, ?)",
                (user_id, char_name, current_hp, max_hp)
            )
            await self.db.commit()
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
        old_cur, old_max = await self.get_hp(user_id, char_name)
        new_max = max(1, old_max + int(delta))
        actual_delta = new_max - old_max
        if actual_delta > 0:
            new_cur = min(new_max, old_cur + actual_delta)
        else:
            new_cur = min(old_cur, new_max)
        await self.set_hp(user_id, char_name, new_cur, new_max)
        return old_cur, old_max, new_cur, new_max

    async def set_max_hp_value(self, user_id: int, char_name: str, target_max: int) -> Tuple[int, int, int, int]:
        old_cur, old_max = await self.get_hp(user_id, char_name)
        delta = max(1, int(target_max)) - old_max
        return await self.adjust_max_hp(user_id, char_name, delta)

    async def recover_hp(self, user_id: int, char_name: str, roll_total: int, has_unwounded_dice: bool) -> Tuple[int, int, int]:
        old_hp, max_hp = await self.get_hp(user_id, char_name)
        if not has_unwounded_dice:
            new_hp = min(max_hp, old_hp + 1)
        elif old_hp <= 0:
            new_hp = min(max_hp, max(0, int(roll_total)))
        else:
            new_hp = min(max_hp, old_hp + max(0, int(roll_total)))
        await self.set_hp(user_id, char_name, new_hp, max_hp)
        return old_hp, new_hp, max_hp

    @staticmethod
    def get_potential_hp_bracket(max_hp: int) -> dict:
        """Returns PDF Page 18 Potential HP increase bracket info based on current Max HP."""
        if max_hp < 20:
            return {
                "bracket": "10–19 (or <10)",
                "flat_gain": 5,
                "can_roll": True,
                "roll_label": "1d6 + 1",
                "roll_mod": 1
            }
        elif max_hp < 40:
            return {
                "bracket": "20–39",
                "flat_gain": 3,
                "can_roll": True,
                "roll_label": "1d6",
                "roll_mod": 0
            }
        elif max_hp < 60:
            return {
                "bracket": "40–59",
                "flat_gain": 2,
                "can_roll": True,
                "roll_label": "1d6 - 1",
                "roll_mod": -1
            }
        else:
            return {
                "bracket": "60+",
                "flat_gain": 1,
                "can_roll": False,
                "roll_label": "N/A (60+ Max HP)",
                "roll_mod": 0
            }


