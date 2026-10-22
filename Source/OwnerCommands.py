"""/owner: syncing commands and reloading extensions, only in the servers listed in ALLOWED_GUILDS."""
import logging
import os
from typing import List, Literal

import discord
from discord import app_commands
from discord.ext import commands

from Source.Utils import Theme

log = logging.getLogger(__name__)

ALLOWED_GUILDS = [
    discord.Object(id=int(g.strip()))
    for g in os.getenv("ALLOWED_GUILDS", "").split(",")
    if g.strip().isdigit()
]


def get_all_extensions() -> List[str]:
    """Every loadable extension under Source. Utils is helpers, not extensions."""
    extensions = []
    for root, dirs, files in os.walk("Source"):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "Utils", "utils")]
        if "__init__.py" in files:
            extensions.append(root.replace(os.sep, "."))
            dirs.clear()
        else:
            extensions.extend(os.path.join(root, f[:-3]).replace(os.sep, ".") for f in files if f.endswith(".py"))
    return extensions


def _result_view(title: str, body: str, color: discord.Colour) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(discord.ui.TextDisplay(f"### {title}"), discord.ui.TextDisplay(body), accent_colour=color))
    return view


def _names(names: List[str]) -> str:
    text = ", ".join(f"`{n}`" for n in names)
    return text if len(text) <= 1500 else text[:1500].rsplit(",", 1)[0] + ", ..."


@app_commands.guilds(*ALLOWED_GUILDS)
@app_commands.default_permissions(administrator=True)
class OwnerCog(commands.GroupCog, group_name="owner"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="sync", description="Sync the bot's commands with Discord")
    async def sync(self, interaction: discord.Interaction, sync_type: Literal["Global", "Guild"]) -> None:
        await interaction.response.defer(ephemeral=False)
        await interaction.followup.send(view=_result_view(f"Syncing ({sync_type})", "This can take a few moments.", Theme.ACCENT))
        try:
            if sync_type == "Global":
                synced = [c.name for c in await self.bot.tree.sync(guild=None)]
                where = "globally"
            else:
                synced = []
                for guild in ALLOWED_GUILDS:
                    synced += [c.name for c in await self.bot.tree.sync(guild=guild)]
                where = f"to {len(ALLOWED_GUILDS)} allowed servers"
        except Exception:
            log.exception("Command sync (%s) failed", sync_type)
            await interaction.edit_original_response(view=_result_view("Sync failed", f"Couldn't sync commands {sync_type.lower()}. The error is in the log.", Theme.ERROR))
            return
        names = sorted(set(synced))
        body = f"Synced **{len(synced)}** commands {where}.\n\n{_names(names) if names else 'No commands to sync.'}"
        await interaction.edit_original_response(view=_result_view("Sync complete", body, Theme.BRAND))
        log.info("Synced %d commands %s: %s", len(synced), where, ", ".join(names))

    @app_commands.command(name="sync_clear", description="Remove all commands from the local tree (sync afterwards to apply)")
    async def sync_clear(self, interaction: discord.Interaction, clear_type: Literal["Global", "Guild"]) -> None:
        await interaction.response.defer(ephemeral=False)
        if clear_type == "Global":
            count = len(self.bot.tree.get_commands(guild=None))
            self.bot.tree.clear_commands(guild=None)
            where = "the global tree"
        else:
            count = len(self.bot.tree.get_commands(guild=interaction.guild))
            self.bot.tree.clear_commands(guild=interaction.guild)
            where = f"**{interaction.guild.name}**'s tree"
        body = f"Removed **{count}** commands from {where}. Discord keeps showing them until the next `/owner sync`."
        await interaction.followup.send(view=_result_view("Commands cleared", body, Theme.ACCENT))
        log.info("Cleared %d commands from %s", count, where.replace("**", ""))

    @app_commands.command(name="ext", description="Load, unload or reload an extension")
    async def ext(self, interaction: discord.Interaction, action: Literal["load", "unload", "reload"], extension: str) -> None:
        await interaction.response.defer(ephemeral=False)
        error = None
        try:
            if action == "load":
                await self.bot.load_extension(extension)
            elif action == "unload":
                await self.bot.unload_extension(extension)
            else:
                await self.bot.reload_extension(extension)
        except commands.ExtensionAlreadyLoaded:
            error = "It's already loaded."
        except commands.ExtensionNotLoaded:
            error = "It isn't loaded."
        except commands.ExtensionNotFound:
            error = "No extension has that name."
        except commands.ExtensionFailed as e:
            log.error("Extension %s failed during %s", extension, action, exc_info=e.original)
            error = f"It failed while loading (`{type(e.original).__name__}`). The traceback is in the log."
        except Exception as e:
            log.exception("Unexpected error during %s of %s", action, extension)
            error = f"Unexpected error (`{type(e).__name__}`). The traceback is in the log."

        if error:
            view = _result_view(f"Couldn't {action} `{extension}`", error, Theme.ERROR)
        else:
            view = _result_view(f"Extension {action}ed", f"`{extension}`", Theme.ACCENT if action == "unload" else Theme.BRAND)
        await interaction.followup.send(view=view)

    @ext.autocomplete("extension")
    async def ext_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return [app_commands.Choice(name=e, value=e) for e in get_all_extensions() if current.lower() in e.lower()][:25]

    @app_commands.command(name="cogs", description="Load or reload every extension under Source")
    async def cogs(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=False)
        groups = {"Reloaded": [], "Loaded": [], "Not found": [], "Failed": []}
        extensions = get_all_extensions()
        for ext in extensions:
            try:
                await self.bot.reload_extension(ext)
                groups["Reloaded"].append(ext)
            except commands.ExtensionNotLoaded:
                try:
                    await self.bot.load_extension(ext)
                    groups["Loaded"].append(ext)
                except commands.ExtensionNotFound:
                    groups["Not found"].append(ext)
                except commands.ExtensionFailed as e:
                    log.error("Extension %s failed to load", ext, exc_info=e.original)
                    groups["Failed"].append(ext)
            except commands.ExtensionNotFound:
                groups["Not found"].append(ext)
            except commands.ExtensionFailed as e:
                log.error("Extension %s failed to reload", ext, exc_info=e.original)
                groups["Failed"].append(ext)

        items: List[discord.ui.Item] = [discord.ui.TextDisplay("### Extensions")]
        for label, names in groups.items():
            if names:
                items.append(discord.ui.TextDisplay(f"**{label}:** {_names(names)}"))
        items.append(discord.ui.TextDisplay(f"-# {len(extensions)} extensions processed. Failures are in the log."))
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(*items, accent_colour=Theme.ERROR if groups["Failed"] else Theme.BRAND))
        await interaction.followup.send(view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OwnerCog(bot))
