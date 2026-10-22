"""Permission checks shared by every command, panel and form.

Sentiment's own permissions (never read guild.me or permissions_for yourself;
scratch/test_permissions.py fails if you do):
- `server_of(interaction)` for the real, cached server. `interaction.guild` can be a
  stand-in whose `me` has no roles, which made role checks fail before v1.0.1.
- `missing_server_permissions(guild, ...)` for server-wide ones like Manage Roles.
- `role_problem(guild, role)` before giving out or saving a role.

The member's permissions:
- `member_has(member, ...)` in a panel's or button's check.
- `require_member_permissions(interaction, ...)` at the top of a staff command.
"""
from typing import Dict, List, Optional

import discord

from Source.Utils.Notice import notice_view, send_ephemeral

PERMISSION_LABELS: Dict[str, str] = {
    "administrator": "Administrator",
    "manage_guild": "Manage Server",
    "manage_roles": "Manage Roles",
    "manage_channels": "Manage Channels",
    "send_messages": "Send Messages",
    "read_message_history": "Read Message History",
    "view_channel": "View Channel",
}


def label(perm: str) -> str:
    return PERMISSION_LABELS.get(perm, perm.replace("_", " ").title())


def server_of(interaction: discord.Interaction) -> Optional[discord.Guild]:
    """The cached server the interaction came from, or None in DMs and servers Sentiment isn't in."""
    if interaction.guild_id is None:
        return None
    return interaction.client.get_guild(interaction.guild_id)


def missing_server_permissions(guild: Optional[discord.Guild], *perms: str) -> List[str]:
    """Names of server-wide permissions Sentiment lacks, like Manage Roles."""
    have = getattr(getattr(guild, "me", None), "guild_permissions", None)
    if have is None:
        return [label(p) for p in perms]
    if have.administrator:
        return []
    return [label(p) for p in perms if not getattr(have, p, False)]


def role_problem(guild: Optional[discord.Guild], role: Optional[discord.Role]) -> Optional[str]:
    """Why Sentiment can't give `role` to members, or None when it can."""
    if guild is None or role is None:
        return "That role doesn't exist any more."
    if role.is_default() or role.managed:
        return f"{role.mention} is managed by Discord or another app, so no one can give it out."
    missing = missing_server_permissions(guild, "manage_roles")
    if missing:
        return "Sentiment needs **Manage Roles**."
    if guild.me.top_role <= role:
        return f"Move Sentiment's role above {role.mention} in Server Settings > Roles."
    return None


def member_has(member: Optional[discord.abc.User], *perms: str, any_of: bool = False) -> bool:
    """Whether a server member has these permissions server-wide (Administrator has them all)."""
    have = getattr(member, "guild_permissions", None)
    if have is None:
        return False
    if have.administrator:
        return True
    found = [bool(getattr(have, perm, False)) for perm in perms]
    return any(found) if any_of else all(found)


async def require_member_permissions(
    interaction: discord.Interaction,
    *perms: str,
    any_of: bool = False,
    or_also: str = "",
    to: str = "change these settings",
) -> bool:
    """For staff commands: True if the member may run it, else a private notice and False.

    `to` finishes the sentence "You need Manage Server to ...". `or_also` names another
    way in that the caller already ruled out, such as "be the GM".
    """
    if member_has(interaction.user, *perms, any_of=any_of):
        return True
    names = (" or " if any_of else " and ").join(f"**{label(perm)}**" for perm in perms)
    if or_also:
        names += f", or to {or_also},"
    await send_ephemeral(interaction, notice_view("Permission needed", f"You need {names} to {to}."))
    return False
