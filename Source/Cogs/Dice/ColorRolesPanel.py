"""/color_roles: the public panel for a server's swing color roles.

Anyone can sync their own role from it. Setting roles up, picking or resetting
a color's role, and syncing everyone take Manage Roles, or being the GM.
The color being edited is read from the message's color menu, so two servers'
panels never mix.
"""
from typing import Dict, List, Optional

import discord

from Source.Utils import Theme
from Source.Utils.Notice import notify
from Source.Utils.Permissions import member_has, missing_server_permissions, role_problem, server_of
from Source.Utils.Views import LastingItem, find_component
from .ColorRoles import (
    assign_swing_color_role, auto_setup_all_color_roles, recolor, remove_swing_color_roles, role_named, sync_all_server_members,
)
from .Common import dice_db, edit_in_place, lasting_view, row, section, separator
from .Constants import COLOR_DISCORD_COLORS, COLOR_ORDER, color_emoji

STAFF_ONLY = "You need **Manage Roles**, or to be the GM, to change color roles."


def _hex(color: str) -> str:
    return f"#{COLOR_DISCORD_COLORS[color].value:06X}"


def _role_line(guild: discord.Guild, color: str, role: Optional[discord.Role]) -> str:
    line = f"{color_emoji(color)} **{color}** (`{_hex(color)}`): "
    if role is None:
        return line + "*made on first use*"
    problem = role_problem(guild, role)
    return line + role.mention + (" ⚠️ above Sentiment's role" if problem and guild.me.top_role <= role else "")


async def color_roles_panel(guild: discord.Guild, db, selected: str = "Red", note: Optional[str] = None) -> discord.ui.LayoutView:
    mapped = await db.get_guild_color_roles(guild.id)
    roles: Dict[str, Optional[discord.Role]] = {
        c: (guild.get_role(mapped[c]) if c in mapped else None) or role_named(guild, c) for c in COLOR_ORDER
    }

    if missing_server_permissions(guild, "manage_roles"):
        status = "**Sentiment can't give roles yet:** it needs **Manage Roles**."
    elif guild.me.top_role.is_default():
        status = "**Sentiment can't give roles yet:** give Sentiment a role with **Manage Roles**, above the color roles."
    else:
        status = f"**Sentiment's role:** {guild.me.top_role.mention}, with Manage Roles."
    selected_role = roles.get(selected)

    items: List[discord.ui.Item] = [
        discord.ui.TextDisplay(
            "## 🎨 Swing color roles\n"
            "Each player gets the role for their active character's Swing, so their name shows that color."
        ),
        separator(),
        discord.ui.TextDisplay("\n".join(_role_line(guild, c, roles[c]) for c in COLOR_ORDER)),
        separator(),
        discord.ui.TextDisplay(
            f"{status}\n"
            "-# Discord colors a name with the member's highest colored role. Keep these roles at the top, "
            "just under Sentiment's role, and other colored roles below them."
        ),
        separator(large=True),
        section("**Set up roles:** finds or creates all 10, then syncs every player.", AutoSetupButton()),
        section("**Sync my role:** matches your role to your active character's Swing.", SyncMyRoleButton()),
        section("**Sync all players:** updates everyone in this server.", SyncAllPlayersButton()),
        separator(large=True),
        discord.ui.TextDisplay("**Change one color's role**"),
        row(ColorSelect(selected)),
        row(RoleSelect(selected)),
        section(
            f"**{selected}:** {selected_role.mention if selected_role else 'none yet'}\n"
            "-# Reset to let Sentiment find a role by name, or make one.",
            ResetRoleButton(),
        ),
    ]
    if note:
        items.append(discord.ui.TextDisplay(f"-# {note}"))
    return lasting_view(*items, accent=COLOR_DISCORD_COLORS.get(selected, Theme.INFO))


def selected_color(message: Optional[discord.Message]) -> str:
    """The color the panel's color menu shows, read from the message itself."""
    menu = find_component(message, "color_select_comp")
    picked = next((o.value for o in getattr(menu, "options", []) if o.default), None)
    return picked if picked in COLOR_ORDER else "Red"


async def redraw(interaction: discord.Interaction, guild: discord.Guild, selected: str, note: Optional[str] = None) -> None:
    await edit_in_place(interaction, await color_roles_panel(guild, dice_db(interaction), selected, note))


class ColorRolesItem(LastingItem):
    """Staff controls on the panel. Buttons only work in the server the panel is in."""

    owner_only = False
    staff_only = True

    async def allowed(self, interaction: discord.Interaction) -> bool:
        if not self.staff_only:
            return True
        return member_has(interaction.user, "manage_roles") or await dice_db(interaction).is_gm(interaction.user.id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if server_of(interaction) is None:
            await notify(interaction, "Server only", "Color roles work in a server Sentiment is in.")
            return False
        if await self.allowed(interaction):
            return True
        await notify(interaction, "Permission needed", STAFF_ONLY)
        return False


class ColorSelect(ColorRolesItem, discord.ui.DynamicItem[discord.ui.Select], template=r"color_select_comp"):
    staff_only = False

    def __init__(self, selected: str) -> None:
        options = [
            discord.SelectOption(label=c, value=c, emoji=color_emoji(c), default=c == selected, description=f"Change the role for {c}")
            for c in COLOR_ORDER
        ]
        super().__init__(discord.ui.Select(custom_id="color_select_comp", placeholder="Pick a color", options=options, min_values=1, max_values=1))

    async def run(self, interaction: discord.Interaction) -> None:
        await redraw(interaction, server_of(interaction), self.item.values[0])


class RoleSelect(ColorRolesItem, discord.ui.DynamicItem[discord.ui.RoleSelect], template=r"role_select_comp"):
    def __init__(self, selected: str) -> None:
        super().__init__(discord.ui.RoleSelect(custom_id="role_select_comp", placeholder=f"Pick a server role for {selected}", min_values=1, max_values=1))

    async def run(self, interaction: discord.Interaction) -> None:
        guild = server_of(interaction)
        color = selected_color(interaction.message)
        role = guild.get_role(self.item.values[0].id)
        problem = role_problem(guild, role)
        if problem:
            await notify(interaction, "Can't use that role", f"{problem} Pick another role for {color}, or fix this first.")
            return
        await interaction.response.defer()
        await dice_db(interaction).set_guild_color_role(guild.id, color, role.id)
        await recolor(guild, role, color)
        await redraw(interaction, guild, color, f"{color} now uses {role.mention}.")


class AutoSetupButton(ColorRolesItem, discord.ui.DynamicItem[discord.ui.Button], template=r"auto_setup_color_roles_btn"):
    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Set up roles", style=discord.ButtonStyle.success, custom_id="auto_setup_color_roles_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        guild = server_of(interaction)
        if missing_server_permissions(guild, "manage_roles"):
            await notify(interaction, "Sentiment needs Manage Roles", "Give Sentiment's role **Manage Roles** in Server Settings > Roles, then try again.")
            return
        await interaction.response.defer()
        db = dice_db(interaction)
        roles = await auto_setup_all_color_roles(guild, db)
        stats = await sync_all_server_members(guild, db)
        missing = [c for c, r in roles.items() if r is None]
        note = f"Set up {len(roles) - len(missing)} of 10 roles and synced {stats['synced']} players."
        if missing:
            note += f" Couldn't make: {', '.join(missing)}."
        await redraw(interaction, guild, selected_color(interaction.message), note)


class SyncMyRoleButton(ColorRolesItem, discord.ui.DynamicItem[discord.ui.Button], template=r"sync_my_swing_role_btn"):
    staff_only = False

    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Sync my role", style=discord.ButtonStyle.primary, custom_id="sync_my_swing_role_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        guild = server_of(interaction)
        db = dice_db(interaction)
        user_id = interaction.user.id
        char_name = await db.get_selected_char(user_id)
        if not char_name:
            await notify(interaction, "No character", "Create a character with `/set_attributes` first.", Theme.ACCENT)
            return
        await interaction.response.defer(ephemeral=True)
        swing = await db.get_swing(user_id, char_name)
        if not swing:
            await remove_swing_color_roles(guild, user_id, db)
            await notify(interaction, "No Swing", f"**{char_name}** has no Swing, so your color roles were removed.", Theme.BRAND)
            return
        result = await assign_swing_color_role(guild, user_id, db, swing[0])
        if result["success"]:
            await notify(interaction, "Role synced", f"You have {result['role'].mention} for **{char_name}**'s {color_emoji(swing[0])} {swing[0]} Swing.", Theme.BRAND)
        else:
            await notify(interaction, "Couldn't sync your role", result["problem"] or "Discord refused the change.")


class SyncAllPlayersButton(ColorRolesItem, discord.ui.DynamicItem[discord.ui.Button], template=r"sync_all_players_btn"):
    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Sync all players", style=discord.ButtonStyle.primary, custom_id="sync_all_players_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        guild = server_of(interaction)
        if missing_server_permissions(guild, "manage_roles"):
            await notify(interaction, "Sentiment needs Manage Roles", "Give Sentiment's role **Manage Roles** in Server Settings > Roles, then try again.")
            return
        await interaction.response.defer(ephemeral=True)
        stats = await sync_all_server_members(guild, dice_db(interaction))
        await notify(
            interaction, "Players synced",
            f"Gave **{stats['synced']}** players their Swing's role, and cleared roles for **{stats['colorless']}** without a Swing.",
            Theme.BRAND,
        )


class ResetRoleButton(ColorRolesItem, discord.ui.DynamicItem[discord.ui.Button], template=r"reset_color_role_btn"):
    def __init__(self) -> None:
        super().__init__(discord.ui.Button(label="Reset", style=discord.ButtonStyle.secondary, custom_id="reset_color_role_btn"))

    async def run(self, interaction: discord.Interaction) -> None:
        guild = server_of(interaction)
        color = selected_color(interaction.message)
        await interaction.response.defer()
        await dice_db(interaction).delete_guild_color_role(guild.id, color)
        await redraw(interaction, guild, color, f"{color} is reset. Sentiment looks for a role named {color}, or makes one on first use.")


ITEMS = (ColorSelect, RoleSelect, AutoSetupButton, SyncMyRoleButton, SyncAllPlayersButton, ResetRoleButton)
