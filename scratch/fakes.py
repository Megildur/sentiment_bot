"""Stand-ins for Discord so the Dice cog can run offline against a temporary database.

Messages hold real discord.py Component objects built from the views Sentiment
sends, and presses go through discord.py's own DynamicItem dispatch, so a test
press takes the same path as one in Discord, before or after a restart.
"""
import asyncio
import itertools
import logging
import os
import sys
import tempfile
from types import SimpleNamespace
from typing import Any, List, Optional

sys.path.insert(0, os.getcwd())
import discord
from discord.components import _component_factory
from discord.ui.view import ViewStore

from Source.Utils.Views import find_component, message_text

_ids = itertools.count(1000)
FAILS: List[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        print("FAIL " + msg)
        FAILS.append(msg)


class ErrorLog(logging.Handler):
    """Fails the run on any logged error: discord.py logs a failed press instead of raising."""

    def __init__(self) -> None:
        super().__init__(logging.ERROR)

    def emit(self, record: logging.LogRecord) -> None:
        FAILS.append(f"logged error: {record.getMessage()}")
        print("FAIL logged error:", record.getMessage())
        if record.exc_info:
            import traceback
            traceback.print_exception(*record.exc_info)


logging.getLogger().addHandler(ErrorLog())


class FakeRole:
    def __init__(self, name: str, position: int, color: int = 0, default: bool = False, managed: bool = False) -> None:
        self.id = next(_ids)
        self.name = name
        self.position = position
        self.color = discord.Colour(color)
        self.managed = managed
        self._default = default
        self.mention = f"<@&{self.id}>"

    def is_default(self) -> bool:
        return self._default

    async def edit(self, colour: discord.Colour = None, **kw: Any) -> None:
        self.color = colour

    def __le__(self, other: "FakeRole") -> bool:
        return self.position <= other.position

    def __lt__(self, other: "FakeRole") -> bool:
        return self.position < other.position

    def __hash__(self) -> int:
        return self.id


class FakeMember:
    def __init__(self, user_id: int, roles: List[FakeRole], perms: discord.Permissions) -> None:
        self.id = user_id
        self.roles = roles
        self.guild_permissions = perms
        self.display_name = f"user{user_id}"
        self.mention = f"<@{user_id}>"

    @property
    def top_role(self) -> FakeRole:
        return max(self.roles, key=lambda r: r.position)

    async def add_roles(self, *roles: FakeRole, **kw: Any) -> None:
        self.roles += [r for r in roles if r not in self.roles]

    async def remove_roles(self, *roles: FakeRole, **kw: Any) -> None:
        self.roles = [r for r in self.roles if r not in roles]


class FakeGuild:
    def __init__(self, bot_id: int, bot_perms: discord.Permissions) -> None:
        self.id = next(_ids)
        self.everyone = FakeRole("@everyone", 0, default=True)
        self.bot_role = FakeRole("Sentiment", 20)
        self.roles = [self.everyone, self.bot_role]
        self.me = FakeMember(bot_id, [self.everyone, self.bot_role], bot_perms)
        self.members = {bot_id: self.me}

    def get_role(self, role_id: int) -> Optional[FakeRole]:
        return next((r for r in self.roles if r.id == role_id), None)

    def get_member(self, user_id: int) -> Optional[FakeMember]:
        return self.members.get(user_id)

    async def fetch_member(self, user_id: int) -> FakeMember:
        member = self.members.get(user_id)
        if member is None:
            raise discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "Unknown Member")
        return member

    async def create_role(self, name: str, colour: discord.Colour, **kw: Any) -> FakeRole:
        role = FakeRole(name, 10, colour.value)
        self.roles.append(role)
        return role

    def add_member(self, user_id: int, perms: discord.Permissions = discord.Permissions.none()) -> FakeMember:
        member = FakeMember(user_id, [self.everyone], perms)
        self.members[user_id] = member
        return member


class FakeMessage:
    def __init__(self, harness: "Harness", view: discord.ui.LayoutView, owner_id: Optional[int], ephemeral: bool, allowed_mentions: Any) -> None:
        self.harness = harness
        self.id = next(_ids)
        self.channel = harness.channel
        self.flags = SimpleNamespace(components_v2=True, ephemeral=ephemeral)
        self.interaction_metadata = SimpleNamespace(user=SimpleNamespace(id=owner_id)) if owner_id else None
        self.ephemeral = ephemeral
        self.allowed_mentions = allowed_mentions
        self.deleted = False
        self.components: List[Any] = []
        self.set_view(view)
        harness.messages[self.id] = self

    def set_view(self, view: Optional[discord.ui.LayoutView]) -> None:
        if view is None:
            return
        self.harness.check_view(view, ephemeral=self.ephemeral)
        self.components = [_component_factory(d) for d in view.to_components()]

    async def edit(self, view: Optional[discord.ui.LayoutView] = None, **kw: Any) -> "FakeMessage":
        self.set_view(view)
        return self

    async def delete(self) -> None:
        self.deleted = True

    @property
    def text(self) -> str:
        return message_text(self)

    def control(self, custom_id: str) -> Any:
        return find_component(self, custom_id)


class FakeChannel:
    def __init__(self, harness: "Harness") -> None:
        self.harness = harness
        self.id = next(_ids)

    async def fetch_message(self, message_id: int) -> FakeMessage:
        message = self.harness.messages.get(message_id)
        if message is None or message.deleted:
            raise discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "Unknown Message")
        return message


class FakeResponse:
    def __init__(self, interaction: "FakeInteraction") -> None:
        self.i = interaction
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def defer(self, ephemeral: bool = False, thinking: bool = False) -> None:
        self._done = True
        self.i.deferred_ephemeral = ephemeral

    async def send_message(self, view: Any = None, ephemeral: bool = False, allowed_mentions: Any = None, **kw: Any) -> None:
        self._done = True
        self.i.original = self.i.harness.post(view, self.i.user.id, ephemeral, allowed_mentions)
        self.i.sent.append(self.i.original)

    async def edit_message(self, view: Any = None, **kw: Any) -> None:
        self._done = True
        self.i.message.set_view(view)

    async def send_modal(self, modal: discord.ui.Modal) -> None:
        self._done = True
        self.i.modal = modal


class FakeFollowup:
    def __init__(self, interaction: "FakeInteraction") -> None:
        self.i = interaction

    async def send(self, view: Any = None, ephemeral: bool = False, allowed_mentions: Any = None, **kw: Any) -> FakeMessage:
        i = self.i
        # After a public defer of a slash command, the first follow-up becomes the
        # "thinking" message: it can't be private, and it doesn't ping.
        if i.message is None and i.original is None and not i.deferred_ephemeral:
            ephemeral = False
        message = i.harness.post(view, i.user.id, ephemeral, allowed_mentions)
        if i.original is None and i.message is None:
            i.original = message
        i.sent.append(message)
        return message


class FakeInteraction:
    def __init__(self, harness: "Harness", user: FakeMember, message: Optional[FakeMessage] = None, data: Optional[dict] = None) -> None:
        self.harness = harness
        self.client = harness.bot
        self.user = user
        self.message = message
        self.data = data or {}
        self.guild_id = harness.guild.id if harness.in_guild else None
        self.channel_id = harness.channel.id
        self.response = FakeResponse(self)
        self.followup = FakeFollowup(self)
        self.original: Optional[FakeMessage] = None
        self.deferred_ephemeral = False
        self.sent: List[FakeMessage] = []
        self.modal: Optional[discord.ui.Modal] = None

    async def edit_original_response(self, view: Any = None, **kw: Any) -> None:
        (self.message or self.original).set_view(view)

    async def original_response(self) -> FakeMessage:
        return self.original

    async def delete_original_response(self) -> None:
        if self.original:
            self.original.deleted = True

    def notices(self) -> List[str]:
        """The headings of private replies this interaction sent."""
        return [m.text.split("\n")[0].lstrip("# ").strip() for m in self.sent if m.ephemeral]


class FakeBot:
    def __init__(self, harness: "Harness") -> None:
        self.harness = harness
        self.cogs: dict = {}
        self.dynamic_items: List[type] = []
        self.user = SimpleNamespace(id=1)
        self.users: List[Any] = []

    def get_cog(self, name: str) -> Any:
        return self.cogs.get(name)

    def get_guild(self, guild_id: int) -> Optional[FakeGuild]:
        return self.harness.guild if guild_id == self.harness.guild.id else None

    def get_user(self, user_id: int) -> Any:
        return SimpleNamespace(id=user_id, display_name=f"user{user_id}")

    def get_channel(self, channel_id: int) -> Optional[FakeChannel]:
        return self.harness.channel if channel_id == self.harness.channel.id else None

    async def fetch_channel(self, channel_id: int) -> FakeChannel:
        return self.harness.channel

    def add_dynamic_items(self, *items: type) -> None:
        self.dynamic_items += items

    def remove_dynamic_items(self, *items: type) -> None:
        self.dynamic_items = [i for i in self.dynamic_items if i not in items]


class Harness:
    """One bot process. `restart()` throws away everything in memory but the database."""

    def __init__(self, db_dir: Optional[str] = None) -> None:
        self.db_dir = db_dir or tempfile.mkdtemp(prefix="sentiment_test_")
        self.messages: dict = {}
        self.channel = FakeChannel(self)
        self.guild = FakeGuild(1, discord.Permissions(manage_roles=True))
        self.in_guild = True
        self.bot = FakeBot(self)
        self.cog = None
        self.modal: Optional[discord.ui.Modal] = None

    async def start(self) -> "Harness":
        from Source.Cogs.Dice.Dice import Dice

        self.cog = Dice(self.bot)
        self.cog.db.db_path = os.path.join(self.db_dir, "Dice.db")
        self.bot.cogs["Dice"] = self.cog
        await self.cog.cog_load()
        return self

    @property
    def db(self):
        return self.cog.db

    async def restart(self) -> "Harness":
        await self.idle()
        await self.cog.cog_unload()
        self.bot.dynamic_items = []
        await self.start()
        return self

    async def idle(self) -> None:
        """Wait for background work, such as refreshing a player's other messages."""
        while self.cog and len(self.cog.background):
            await asyncio.gather(*list(self.cog.background._tasks), return_exceptions=True)

    def check_view(self, view: discord.ui.LayoutView, ephemeral: bool) -> None:
        if view.is_finished():
            return  # a greyed-out copy, stopped so discord.py doesn't keep it
        dynamic = [i for i in view.walk_children() if isinstance(i, discord.ui.DynamicItem)]
        static = [i for i in view.walk_children() if i.is_dispatchable() and not isinstance(i, discord.ui.DynamicItem)]
        check(not static, f"view {type(view).__name__} has controls discord.py would keep in memory: {[getattr(i, 'custom_id', '?') for i in static]}")
        if dynamic:
            check(view.timeout is None, "a view with DynamicItems has a timeout")
            check(not ephemeral, "DynamicItems sent in a private reply (discord.py would time them out)")
        text = message_text(view)
        check(len(text) <= 4000, f"message text is {len(text)} characters")

    def post(self, view: Any, owner_id: int, ephemeral: bool, allowed_mentions: Any) -> FakeMessage:
        return FakeMessage(self, view, owner_id, ephemeral, allowed_mentions)

    def interaction(self, user: FakeMember, message: Optional[FakeMessage] = None, data: Optional[dict] = None) -> FakeInteraction:
        return FakeInteraction(self, user, message, data)

    async def command(self, name: str, user: FakeMember, *args: Any) -> FakeInteraction:
        """Run a slash command's callback, like Discord would."""
        interaction = self.interaction(user)
        command = getattr(self.cog, name)
        await asyncio.create_task(command.callback(self.cog, interaction, *args))
        self.modal = interaction.modal
        await self.idle()
        return interaction

    async def press(self, message: FakeMessage, custom_id: str, user: FakeMember, values: Optional[list] = None) -> FakeInteraction:
        """Press a control through discord.py's DynamicItem dispatch."""
        component = message.control(custom_id)
        check(component is not None, f"no control {custom_id} on the message")
        matches = [c for c in self.bot.dynamic_items if c.__discord_ui_compiled_template__.fullmatch(custom_id)]
        check(len(matches) == 1, f"{custom_id} matches {len(matches)} registered classes")
        interaction = self.interaction(user, message, {"custom_id": custom_id, "component_type": component.type.value, "values": values or []})
        if component is None or len(matches) != 1:
            return interaction
        factory = matches[0]
        match = factory.__discord_ui_compiled_template__.fullmatch(custom_id)
        # Its own task, like discord.py, so select picks don't leak between presses.
        await asyncio.create_task(ViewStore.schedule_dynamic_item_call(None, component.type.value, factory, interaction, custom_id, match))
        self.modal = interaction.modal
        await self.idle()
        return interaction

    async def submit(self, source: FakeInteraction, user: Optional[FakeMember] = None, **fields: Any) -> FakeInteraction:
        """Fill in the form `source` opened and send it."""
        modal = source.modal
        check(modal is not None, "no form was opened")
        interaction = self.interaction(user or source.user, source.message)
        if modal is None:
            return interaction
        for name, value in fields.items():
            item = getattr(modal, name)
            if isinstance(item, discord.ui.TextInput):
                item._value = value
            elif isinstance(item, (discord.ui.CheckboxGroup, discord.ui.Select)):
                item._values = value
            elif isinstance(item, list):
                for radio, v in zip(item, value):
                    radio._value = v
            else:
                item._value = value
        await asyncio.create_task(modal.on_submit(interaction))
        await self.idle()
        return interaction


def member(harness: Harness, user_id: int, **perms: bool) -> FakeMember:
    return harness.guild.add_member(user_id, discord.Permissions(**perms))


def finish() -> None:
    if FAILS:
        print(f"\n{len(FAILS)} failure(s)")
        sys.exit(1)
    print("OK")
