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
            CREATE TABLE IF NOT EXISTS stats (
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
            await self.db.execute("DELETE FROM selected_char WHERE user_id = ? AND char_name = ?", (user_id, char_name))
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

