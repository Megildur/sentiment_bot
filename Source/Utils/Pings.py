"""Pinging people from Components v2 messages.

Discord notifies a mention only when a message is created; edits never ping.
So a ping belongs in a new message, never in an edit (and that includes the
first follow-up after a "thinking" defer, which edits the loading message).
In a v2 message the mention also gets its own text line above the container,
so every client treats it as a ping even when the container names the person too.
"""
from typing import Iterable, List, Optional

import discord


def _unique(ids: Iterable[Optional[int]]) -> List[int]:
    return [i for i in dict.fromkeys(ids) if i]


def ping_line(users: Iterable[Optional[int]] = (), roles: Iterable[Optional[int]] = ()) -> Optional[discord.ui.TextDisplay]:
    """The mentions on their own line, or None when there's nobody to ping."""
    mentions = [f"<@{u}>" for u in _unique(users)] + [f"<@&{r}>" for r in _unique(roles)]
    return discord.ui.TextDisplay(" ".join(mentions)) if mentions else None


def with_ping(
    view: discord.ui.LayoutView,
    users: Iterable[Optional[int]] = (),
    roles: Iterable[Optional[int]] = (),
) -> discord.ui.LayoutView:
    """Put the ping line above everything already in the view. Returns the view."""
    line = ping_line(users, roles)
    if line is None:
        return view
    children = list(view.children)
    view.clear_items()
    view.add_item(line)
    for child in children:
        view.add_item(child)
    return view


def ping_mentions(users: Iterable[Optional[int]] = (), roles: Iterable[Optional[int]] = ()) -> discord.AllowedMentions:
    """Allowed mentions that ping exactly these people and roles, and nobody else."""
    return discord.AllowedMentions(
        everyone=False,
        replied_user=False,
        users=[discord.Object(id=u) for u in _unique(users)],
        roles=[discord.Object(id=r) for r in _unique(roles)],
    )
