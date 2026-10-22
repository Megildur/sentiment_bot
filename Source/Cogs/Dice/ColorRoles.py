"""Swing color roles: a player's name shows their active character's swing color.

Every function takes the real, cached server (`Permissions.server_of(interaction)`),
not `interaction.guild`, whose stand-in `me` has no roles.
"""
import logging
from typing import Any, Dict, List, Optional, Set

import discord

from Source.Utils.Permissions import missing_server_permissions, role_problem
from .Constants import COLOR_DISCORD_COLORS, COLOR_ORDER

log = logging.getLogger(__name__)


def role_named(guild: discord.Guild, color: str) -> Optional[discord.Role]:
    return next((r for r in guild.roles if r.name.strip().lower() == color.lower()), None)


async def get_guild_member(guild: discord.Guild, user_id: int) -> Optional[discord.Member]:
    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except discord.HTTPException:
            return None
    return member


async def recolor(guild: discord.Guild, role: discord.Role, color: str) -> None:
    """Give a color role its swing's exact color, when Sentiment is allowed to edit it."""
    desired = COLOR_DISCORD_COLORS.get(color)
    if desired is None or role.color.value == desired.value or role_problem(guild, role):
        return
    try:
        await role.edit(colour=desired, reason=f"Sentiment color role for {color}")
    except discord.HTTPException:
        log.warning("Could not recolor role %s in server %s", role.id, guild.id, exc_info=True)


async def color_role(guild: discord.Guild, db, color: str, mapped: Optional[Dict[str, int]] = None) -> Optional[discord.Role]:
    """The role for a color: the one the server picked, else one named after it, else a new one."""
    if mapped is None:
        mapped = await db.get_guild_color_roles(guild.id)
    role_id = mapped.get(color)
    if role_id:
        role = guild.get_role(role_id)
        if role is not None:
            return role
        # The picked role was deleted; forget it and look again.
        await db.delete_guild_color_role(guild.id, color)

    role = role_named(guild, color)
    if role is not None:
        await recolor(guild, role, color)
        await db.set_guild_color_role(guild.id, color, role.id)
        return role

    if missing_server_permissions(guild, "manage_roles"):
        return None
    try:
        role = await guild.create_role(
            name=color,
            colour=COLOR_DISCORD_COLORS.get(color, discord.Colour.default()),
            reason=f"Sentiment swing color role for {color}",
        )
    except discord.HTTPException:
        log.warning("Could not create the %s role in server %s", color, guild.id, exc_info=True)
        return None
    await db.set_guild_color_role(guild.id, color, role.id)
    return role


async def all_color_roles(guild: discord.Guild, db) -> Set[discord.Role]:
    """Every role that stands for a swing color: the picked ones and any named after a color."""
    roles = {guild.get_role(role_id) for role_id in (await db.get_guild_color_roles(guild.id)).values()}
    names = {c.lower() for c in COLOR_ORDER}
    roles.update(r for r in guild.roles if r.name.strip().lower() in names)
    roles.discard(None)
    return roles


async def assign_swing_color_role(guild: discord.Guild, user_id: int, db, color: str) -> Dict[str, Any]:
    """Give a member the role for `color` and take away the other color roles.

    Returns {"success", "role", "problem"}: `problem` says in plain words why it failed.
    """
    result: Dict[str, Any] = {"success": False, "role": None, "problem": None}
    member = await get_guild_member(guild, user_id)
    if member is None:
        result["problem"] = "That member isn't in this server."
        return result
    if missing_server_permissions(guild, "manage_roles"):
        result["problem"] = "Sentiment needs **Manage Roles**."
        return result

    target = await color_role(guild, db, color)
    if target is None:
        result["problem"] = f"Sentiment couldn't find or create a **{color}** role."
        return result
    result["role"] = target
    problem = role_problem(guild, target)
    if problem:
        result["problem"] = problem
        return result

    others = await all_color_roles(guild, db)
    stale = [r for r in member.roles if r in others and r != target and not role_problem(guild, r)]
    if stale:
        try:
            await member.remove_roles(*stale, reason="Sentiment swing color changed")
        except discord.HTTPException:
            log.warning("Could not remove old color roles from %s", member.id, exc_info=True)

    if target in member.roles:
        result["success"] = True
        return result
    try:
        await member.add_roles(target, reason=f"Sentiment swing set to {color}")
        result["success"] = True
    except discord.HTTPException:
        log.warning("Could not give %s the %s role", member.id, color, exc_info=True)
        result["problem"] = f"Discord refused to give {target.mention}. Check that Sentiment's role is above it."
    return result


async def remove_swing_color_roles(guild: discord.Guild, user_id: int, db) -> List[discord.Role]:
    """Take every color role away from a member. Returns the roles they had."""
    member = await get_guild_member(guild, user_id)
    if member is None:
        return []
    color_roles = await all_color_roles(guild, db)
    had = [r for r in member.roles if r in color_roles]
    removable = [r for r in had if not role_problem(guild, r)]
    if removable:
        try:
            await member.remove_roles(*removable, reason="Sentiment swing dropped")
        except discord.HTTPException:
            log.warning("Could not remove color roles from %s", member.id, exc_info=True)
    return had


async def sync_member_swing_color_role(guild: discord.Guild, user_id: int, db) -> Dict[str, Any]:
    """Match a member's color role to their active character's swing (none without a swing)."""
    active_char = await db.get_selected_char(user_id)
    swing = await db.get_swing(user_id, active_char) if active_char else None
    if swing and swing[0]:
        return await assign_swing_color_role(guild, user_id, db, swing[0])
    await remove_swing_color_roles(guild, user_id, db)
    return {"success": True, "role": None, "problem": None}


async def auto_setup_all_color_roles(guild: discord.Guild, db) -> Dict[str, Optional[discord.Role]]:
    mapped = await db.get_guild_color_roles(guild.id)
    return {color: await color_role(guild, db, color, mapped) for color in COLOR_ORDER}


async def sync_all_server_members(guild: discord.Guild, db) -> Dict[str, int]:
    """Sync every player in this server. Members come from the cache: with the members
    intent it holds the whole server, so players elsewhere cost no API calls."""
    stats = {"synced": 0, "colorless": 0}
    for user_id, char_name in await db.get_selected_chars():
        if guild.get_member(user_id) is None:
            continue
        swing = await db.get_swing(user_id, char_name)
        if swing and swing[0]:
            result = await assign_swing_color_role(guild, user_id, db, swing[0])
            if result["success"]:
                stats["synced"] += 1
        else:
            await remove_swing_color_roles(guild, user_id, db)
            stats["colorless"] += 1
    return stats
