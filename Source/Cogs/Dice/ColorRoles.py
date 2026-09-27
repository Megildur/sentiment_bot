import logging
import discord
from typing import Optional, List, Dict, Any
from .Constants import COLOR_EMOJIS, COLOR_DISCORD_COLORS, COLOR_ORDER

logger = logging.getLogger("sentiment.color_roles")


async def get_bot_member(bot, guild: discord.Guild) -> Optional[discord.Member]:
    """
    Retrieves the bot's actual Member object in the guild with full roles and permissions.
    Avoids discord.py's Interaction.guild.me fallback which defaults to roles=[] (@everyone only).
    """
    if not guild or not bot:
        return None

    actual_guild = bot.get_guild(guild.id) or guild
    bot_user_id = bot.user.id if bot.user else None

    if not bot_user_id:
        return actual_guild.me

    # Check if cached member has custom roles (more than @everyone)
    cached_member = actual_guild.get_member(bot_user_id)
    if cached_member and len(cached_member.roles) > 1:
        return cached_member

    # Fetch fresh member directly from Discord REST API to guarantee all roles are loaded
    try:
        fetched_member = await actual_guild.fetch_member(bot_user_id)
        if fetched_member:
            return fetched_member
    except Exception as e:
        logger.debug(f"Could not fetch bot member in guild {guild.id}: {e}")

    return cached_member or actual_guild.me or guild.me


async def get_guild_member(guild: discord.Guild, user_or_member: Any) -> Optional[discord.Member]:
    """
    Ensures we have a discord.Member instance in the guild even if a discord.User or ID was passed.
    """
    if isinstance(user_or_member, discord.Member):
        return user_or_member

    user_id = getattr(user_or_member, 'id', None)
    if not user_id:
        return None

    member = guild.get_member(user_id)
    if not member:
        try:
            member = await guild.fetch_member(user_id)
        except Exception:
            pass
    return member


def is_higher_than(higher_role: Optional[discord.Role], lower_role: Optional[discord.Role]) -> bool:
    """Safely checks if higher_role is strictly higher in the hierarchy than lower_role."""
    if not higher_role or not lower_role:
        return False
    return getattr(higher_role, "position", 0) > getattr(lower_role, "position", 0)


async def get_or_create_color_role(guild: discord.Guild, db_manager, color_name: str, bot=None) -> Optional[discord.Role]:
    """
    Finds or creates a role for the specified Sentiment color.
    1. Checks database mapping for the guild.
    2. If not mapped or role was deleted, searches existing roles in the guild by name.
    3. If not found, creates the role with the matching accent color.
    """
    if not guild:
        return None

    actual_guild = (bot.get_guild(guild.id) if bot else None) or guild

    # 1. Check DB mapping
    role_id = await db_manager.get_guild_color_role(actual_guild.id, color_name)
    if role_id:
        role = actual_guild.get_role(role_id)
        if role is not None:
            return role
        # Role was deleted in guild, clean up stale DB entry
        await db_manager.delete_guild_color_role(actual_guild.id, color_name)

    desired_color = COLOR_DISCORD_COLORS.get(color_name)

    # 2. Search existing roles by name (case-insensitive)
    matching_role = next(
        (r for r in actual_guild.roles if r.name.strip().lower() == color_name.lower()),
        None
    )

    if matching_role:
        bot_member = await get_bot_member(bot, actual_guild) if bot else actual_guild.me
        if desired_color and matching_role.color.value != desired_color.value:
            if bot_member and bot_member.guild_permissions.manage_roles and is_higher_than(bot_member.top_role, matching_role):
                try:
                    await matching_role.edit(colour=desired_color, reason=f"Sentiment color role update for {color_name}")
                except Exception as e:
                    logger.warning(f"Could not update color for existing role {matching_role.name}: {e}")

        await db_manager.set_guild_color_role(actual_guild.id, color_name, matching_role.id)
        return matching_role

    # 3. Create role if not found
    bot_member = await get_bot_member(bot, actual_guild) if bot else actual_guild.me
    can_create = bot_member and (bot_member.guild_permissions.manage_roles or bot_member.guild_permissions.administrator)

    if can_create:
        try:
            created_role = await actual_guild.create_role(
                name=color_name,
                colour=desired_color or discord.Color.default(),
                reason=f"Sentiment Swing Color Role for {color_name}"
            )
            await db_manager.set_guild_color_role(actual_guild.id, color_name, created_role.id)
            return created_role
        except Exception as e:
            logger.warning(f"Failed to create color role '{color_name}' in guild {actual_guild.id}: {e}")
            return None
    else:
        logger.warning(f"Cannot create role '{color_name}' in guild {actual_guild.id}: Bot missing Manage Roles permission")
        return None


async def get_all_guild_color_roles(guild: discord.Guild, db_manager, bot=None) -> List[discord.Role]:
    """
    Returns a deduplicated list of all roles in the guild that represent any of the 10 Sentiment colors.
    Includes roles in the database and roles whose names match any of the color names.
    """
    if not guild:
        return []

    actual_guild = (bot.get_guild(guild.id) if bot else None) or guild
    roles = set()

    # From DB
    db_roles = await db_manager.get_guild_color_roles(actual_guild.id)
    for color, r_id in db_roles.items():
        role = actual_guild.get_role(r_id)
        if role:
            roles.add(role)

    # From role names
    color_names_lower = {c.lower() for c in COLOR_ORDER}
    for r in actual_guild.roles:
        if r.name.strip().lower() in color_names_lower:
            roles.add(r)

    return list(roles)


async def assign_swing_color_role(bot, guild: discord.Guild, user_or_member: Any, db_manager, chosen_color: str) -> Dict[str, Any]:
    """
    Assigns the color role matching chosen_color to the member, and strips any other color roles they hold.
    Returns a dictionary with execution status and details:
    {'success': bool, 'role': Optional[Role], 'is_owner': bool, 'error': Optional[str]}
    """
    result = {"success": False, "role": None, "is_owner": False, "error": None}

    if not guild:
        result["error"] = "no_guild"
        return result

    actual_guild = (bot.get_guild(guild.id) if bot else None) or guild
    member = await get_guild_member(actual_guild, user_or_member)
    if not member:
        result["error"] = "member_not_found"
        return result

    if member.id == actual_guild.owner_id:
        result["is_owner"] = True

    bot_member = await get_bot_member(bot, actual_guild)
    if not bot_member:
        result["error"] = "bot_member_not_found"
        return result

    target_role = await get_or_create_color_role(actual_guild, db_manager, chosen_color, bot=bot)
    if not target_role:
        result["error"] = "could_not_create_or_find_role"
        return result

    result["role"] = target_role
    all_color_roles = await get_all_guild_color_roles(actual_guild, db_manager, bot=bot)

    # Roles to remove: any color role the member currently holds except target_role
    roles_to_remove = [r for r in member.roles if r in all_color_roles and r.id != target_role.id]

    bot_top_pos = getattr(bot_member.top_role, 'position', 0)
    has_perm = bot_member.guild_permissions.manage_roles or bot_member.guild_permissions.administrator

    if not has_perm:
        result["error"] = "missing_manage_roles_permission"
        logger.warning(f"Bot missing manage_roles permission in {actual_guild.name}")
        return result

    if bot_top_pos <= target_role.position:
        result["error"] = "bot_role_lower_than_color_role"
        logger.warning(f"Bot top role {bot_member.top_role.name} (pos {bot_top_pos}) is not higher than color role {target_role.name} (pos {target_role.position})")
        return result

    # Remove old swing color roles
    if roles_to_remove:
        removable = [r for r in roles_to_remove if bot_top_pos > getattr(r, 'position', 0)]
        if removable:
            try:
                await member.remove_roles(*removable, reason="Sentiment swing color changed")
            except discord.Forbidden as e:
                logger.debug(f"Forbidden removing old roles from {member.display_name}: {e}")
            except Exception as e:
                logger.warning(f"Error removing old roles from {member.display_name}: {e}")

    # Add new swing color role
    if target_role not in member.roles:
        try:
            await member.add_roles(target_role, reason=f"Sentiment swing set to {chosen_color}")
            result["success"] = True
        except discord.Forbidden as e:
            if result["is_owner"]:
                result["error"] = "forbidden_server_owner"
                logger.info(f"Cannot assign role to Server Owner {member.display_name} due to Discord API restrictions.")
            else:
                result["error"] = "forbidden_hierarchy"
                logger.warning(f"Discord Forbidden assigning {target_role.name} to {member.display_name}: {e}")
        except Exception as e:
            result["error"] = str(e)
            logger.warning(f"Failed to add role {target_role.name} to {member.display_name}: {e}")
    else:
        result["success"] = True

    return result


async def remove_swing_color_roles(bot, guild: discord.Guild, user_or_member: Any, db_manager) -> List[discord.Role]:
    """
    Removes all Sentiment color roles currently held by the member.
    """
    if not guild:
        return []

    actual_guild = (bot.get_guild(guild.id) if bot else None) or guild
    member = await get_guild_member(actual_guild, user_or_member)
    if not member:
        return []

    bot_member = await get_bot_member(bot, actual_guild)
    all_color_roles = await get_all_guild_color_roles(actual_guild, db_manager, bot=bot)
    roles_to_remove = [r for r in member.roles if r in all_color_roles]

    if not bot_member:
        return []

    bot_top_pos = getattr(bot_member.top_role, 'position', 0)
    has_perm = bot_member.guild_permissions.manage_roles or bot_member.guild_permissions.administrator

    if has_perm and roles_to_remove:
        removable = [r for r in roles_to_remove if bot_top_pos > getattr(r, 'position', 0)]
        if removable:
            try:
                await member.remove_roles(*removable, reason="Sentiment swing dropped / removed")
            except discord.Forbidden:
                pass
            except Exception as e:
                logger.warning(f"Failed to remove swing roles from {member}: {e}")

    return roles_to_remove


async def sync_member_swing_color_role(bot, guild: discord.Guild, user_id: int, db_manager) -> Dict[str, Any]:
    """
    Syncs a member's swing color role to their active character's current swing state.
    """
    if not guild:
        return {"success": False, "error": "no_guild"}

    actual_guild = (bot.get_guild(guild.id) if bot else None) or guild
    member = await get_guild_member(actual_guild, user_id)
    if not member:
        return {"success": False, "error": "member_not_found"}

    active_char = await db_manager.get_selected_char(user_id)
    if active_char:
        swing = await db_manager.get_swing(user_id, active_char)
        if swing and swing[0]:
            return await assign_swing_color_role(bot, actual_guild, member, db_manager, swing[0])

    await remove_swing_color_roles(bot, actual_guild, member, db_manager)
    return {"success": True, "role": None, "is_owner": (member.id == actual_guild.owner_id), "error": None}


async def auto_setup_all_color_roles(guild: discord.Guild, db_manager, bot=None) -> Dict[str, Optional[discord.Role]]:
    """
    Iterates through all 10 Sentiment colors, searching or creating each role and binding to DB.
    """
    mappings = {}
    actual_guild = (bot.get_guild(guild.id) if bot else None) or guild
    for color in COLOR_ORDER:
        role = await get_or_create_color_role(actual_guild, db_manager, color, bot=bot)
        mappings[color] = role
    return mappings


async def sync_all_server_members(bot, guild: discord.Guild, db_manager) -> Dict[str, int]:
    """
    Syncs swing color roles for all players in the server who have an active character.
    Returns stats: {'synced': count, 'colorless': count, 'skipped_owner': count}
    """
    actual_guild = (bot.get_guild(guild.id) if bot else None) or guild
    stats = {"synced": 0, "colorless": 0, "skipped_owner": 0}

    # Query all users with selected characters
    async with db_manager.db_lock:
        cursor = await db_manager.db.execute("SELECT user_id, char_name FROM selected_char")
        rows = await cursor.fetchall()

    for user_id, char_name in rows:
        member = actual_guild.get_member(user_id)
        if not member:
            continue

        if member.id == actual_guild.owner_id:
            stats["skipped_owner"] += 1
            continue

        swing = await db_manager.get_swing(user_id, char_name)
        if swing and swing[0]:
            res = await assign_swing_color_role(bot, actual_guild, member, db_manager, swing[0])
            if res.get("success"):
                stats["synced"] += 1
        else:
            await remove_swing_color_roles(bot, actual_guild, member, db_manager)
            stats["colorless"] += 1

    return stats


class ColorSelectComponent(discord.ui.Select):
    def __init__(self, selected_color: str):
        options = [
            discord.SelectOption(
                label=f"{color}",
                value=color,
                emoji=COLOR_EMOJIS.get(color, "⚪"),
                default=(color == selected_color),
                description=f"Configure role binding for {color}"
            )
            for color in COLOR_ORDER
        ]
        super().__init__(
            placeholder="Select a color to configure or assign a role to...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_color = self.values[0]
        await self.view.refresh(interaction)


class RoleSelectComponent(discord.ui.RoleSelect):
    def __init__(self, selected_color: str):
        super().__init__(
            placeholder=f"Pick an existing server role for {selected_color}...",
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        if not await self.view.check_admin_permissions(interaction):
            return

        selected_role = self.values[0]
        color_name = self.view.selected_color

        await self.view.db_manager.set_guild_color_role(interaction.guild.id, color_name, selected_role.id)

        # Update role color to match accent color if needed and possible
        bot_member = await get_bot_member(self.view.bot, interaction.guild)
        desired_color = COLOR_DISCORD_COLORS.get(color_name)
        if desired_color and selected_role.color.value != desired_color.value:
            if bot_member and bot_member.guild_permissions.manage_roles and is_higher_than(bot_member.top_role, selected_role):
                try:
                    await selected_role.edit(colour=desired_color, reason=f"Sentiment color role update for {color_name}")
                except Exception as e:
                    logger.warning(f"Could not update role color for {selected_role.name}: {e}")

        await self.view.refresh(
            interaction,
            notice=f"✅ Mapped **{color_name}** to {selected_role.mention}!"
        )


class AutoSetupButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Auto-Setup Roles",
            style=discord.ButtonStyle.success,
            emoji="⚡",
            custom_id="auto_setup_color_roles_btn"
        )

    async def callback(self, interaction: discord.Interaction):
        if not await self.view.check_admin_permissions(interaction):
            return

        await interaction.response.defer()
        await auto_setup_all_color_roles(interaction.guild, self.view.db_manager, bot=self.view.bot)
        await self.view.refresh(
            interaction,
            is_followup=True,
            notice="✅ **Auto-Setup Complete!** All 10 color roles were verified or created with their exact accent colors."
        )


class SyncMyRoleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Sync My Role",
            style=discord.ButtonStyle.primary,
            emoji="🔄",
            custom_id="sync_my_swing_role_btn"
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ This action can only be used inside a server.", ephemeral=True)
            return

        actual_guild = self.view.bot.get_guild(interaction.guild.id) or interaction.guild
        is_owner = (actual_guild.owner_id == interaction.user.id)

        active_char = await self.view.db_manager.get_selected_char(interaction.user.id)
        if not active_char:
            await interaction.response.send_message(
                "❌ You do not have an active character selected! Use `/set_attributes` or `/change_active_character` first.",
                ephemeral=True
            )
            return

        swing = await self.view.db_manager.get_swing(interaction.user.id, active_char)
        if not swing:
            await remove_swing_color_roles(self.view.bot, actual_guild, interaction.user, self.view.db_manager)
            await interaction.response.send_message(
                f"ℹ️ Your active character *{active_char}* has no active Swing. Removed all swing color roles.",
                ephemeral=True
            )
            return

        chosen_color = swing[0]
        emoji = COLOR_EMOJIS.get(chosen_color, "⚪")

        sync_result = await assign_swing_color_role(
            self.view.bot,
            actual_guild,
            interaction.user,
            self.view.db_manager,
            chosen_color
        )

        if is_owner:
            await interaction.response.send_message(
                f"ℹ️ Your active character *{active_char}* is set to **{emoji} {chosen_color}** Swing.\n\n"
                f"> ⚠️ **Discord Server Owner Notice:**\n"
                f"> You are the **Server Owner** (`{interaction.user.display_name}`). Discord's internal security system strictly prevents any bot from modifying the roles of the Server Owner.\n"
                f"> **To test automatic swing color role assignment in action, have another player choose a swing, or test with a secondary account!**",
                ephemeral=True
            )
        elif sync_result.get("success"):
            target_role = sync_result.get("role")
            role_mention = target_role.mention if target_role else f"@{chosen_color}"
            await interaction.response.send_message(
                f"✅ Successfully synced! Granted {role_mention} for **{emoji} {chosen_color}** swing on *{active_char}*.",
                ephemeral=True
            )
        else:
            err = sync_result.get("error", "unknown")
            await interaction.response.send_message(
                f"⚠️ Could not assign role for **{chosen_color}** ({err}). Please verify the bot has **Manage Roles** permission and its role is above `{chosen_color}` in Server Settings ➔ Roles.",
                ephemeral=True
            )


class SyncAllPlayersButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Sync All Players",
            style=discord.ButtonStyle.primary,
            emoji="👥",
            custom_id="sync_all_players_btn"
        )

    async def callback(self, interaction: discord.Interaction):
        if not await self.view.check_admin_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        stats = await sync_all_server_members(self.view.bot, interaction.guild, self.view.db_manager)
        owner_note = f" (Skipped Server Owner due to Discord permissions policy)" if stats['skipped_owner'] > 0 else ""
        await interaction.followup.send(
            f"✅ **Player Sync Complete!**\n"
            f"• Updated **{stats['synced']}** player(s) with active swings.\n"
            f"• Cleared roles for **{stats['colorless']}** player(s) without swings.{owner_note}",
            ephemeral=True
        )


class ResetRoleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Reset Selected",
            style=discord.ButtonStyle.secondary,
            emoji="🧹",
            custom_id="reset_color_role_btn"
        )

    async def callback(self, interaction: discord.Interaction):
        if not await self.view.check_admin_permissions(interaction):
            return

        color_name = self.view.selected_color
        await self.view.db_manager.delete_guild_color_role(interaction.guild.id, color_name)
        await self.view.refresh(
            interaction,
            notice=f"🧹 Reset custom mapping for **{color_name}**. The bot will search by role name or auto-create on next swing."
        )


class ColorRolesConfigView(discord.ui.LayoutView):
    @classmethod
    async def build(cls, bot, guild: discord.Guild, db_manager, selected_color: str = "Red"):
        actual_guild = (bot.get_guild(guild.id) if (bot and guild) else None) or guild
        view = cls(bot=bot, guild=actual_guild, db_manager=db_manager, selected_color=selected_color)
        await view.render_view()
        return view

    def __init__(self, bot, guild: discord.Guild, db_manager, selected_color: str = "Red"):
        super().__init__(timeout=600)
        self.bot = bot
        self.guild = guild
        self.db_manager = db_manager
        self.selected_color = selected_color

    async def check_admin_permissions(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used inside a server.", ephemeral=True)
            return False

        is_admin = interaction.user.guild_permissions.manage_roles or interaction.user.guild_permissions.administrator
        is_gm = await self.db_manager.is_gm(interaction.user.id)
        if not (is_admin or is_gm):
            await interaction.response.send_message(
                "❌ You need the **Manage Roles** permission or to be the designated **GM** to modify server color roles.",
                ephemeral=True
            )
            return False
        return True

    async def render_view(self, notice: Optional[str] = None):
        self.clear_items()

        actual_guild = (self.bot.get_guild(self.guild.id) if (self.bot and self.guild) else None) or self.guild
        self.guild = actual_guild

        bot_member = await get_bot_member(self.bot, self.guild)
        has_manage_roles = bot_member.guild_permissions.manage_roles or bot_member.guild_permissions.administrator if bot_member else False
        bot_top_role = bot_member.top_role if bot_member else None
        has_custom_bot_role = bot_top_role is not None and bot_top_role.position > 0
        bot_pos = bot_top_role.position if has_custom_bot_role else 0

        db_roles = await self.db_manager.get_guild_color_roles(self.guild.id)

        role_status_lines = []
        for color in COLOR_ORDER:
            emoji = COLOR_EMOJIS.get(color, "⚪")
            hex_color = hex(COLOR_DISCORD_COLORS[color].value)[2:].upper().zfill(6)
            mapped_id = db_roles.get(color)
            role = self.guild.get_role(mapped_id) if (self.guild and mapped_id) else None

            if not role and self.guild:
                # Search by role name
                matching = next((r for r in self.guild.roles if r.name.strip().lower() == color.lower()), None)
                if matching:
                    role = matching

            if role:
                role_pos = getattr(role, 'position', 0)
                if has_custom_bot_role and role_pos >= bot_pos:
                    status = f"⚠️ *(Position: {role_pos} - Placed ABOVE bot! Drag bot role higher)*"
                elif has_custom_bot_role:
                    status = f"✅ *(Position: {role_pos})*"
                else:
                    status = f"*(Position: {role_pos})*"
                role_status_lines.append(f"• {emoji} **{color}**: {role.mention} (`#{hex_color}`) {status}")
            else:
                role_status_lines.append(f"• {emoji} **{color}**: *Not mapped (Auto-created on use)* (`#{hex_color}`)")

        info_blocks = [
            "> ⚠️ **CRITICAL: Role Hierarchy Setup for Chat Name Colors**\n"
            "> Discord sets a user's name color in chat and the member list by their **highest role with a color**.\n"
            "> \n"
            "> 1. Open **Server Settings ➔ Roles**.\n"
            "> 2. Drag all 10 Color Roles to the **top of your role hierarchy** (just below the bot's own role).\n"
            "> 3. Ensure the **Bot's role** is positioned **above** the color roles and has **Manage Roles** enabled.\n"
            "> 4. Ensure players do not have another role above these color roles that has a custom color set."
        ]

        if bot_member:
            if not has_manage_roles:
                info_blocks.append(
                    "> ❌ **CRITICAL: Bot is missing the 'Manage Roles' permission!**\n"
                    "> The bot cannot assign, edit, or auto-create color roles until this permission is granted in Server Settings."
                )
            elif not has_custom_bot_role:
                info_blocks.append(
                    "> ❌ **CRITICAL: Bot has no custom role assigned in Server Settings!**\n"
                    "> The bot currently only has the default `@everyone` role. Please go to **Server Settings ➔ Roles**, create or assign a role to the bot (e.g. 'Sentiment Bot'), enable **Manage Roles**, and move it above the color roles."
                )
            else:
                info_blocks.append(
                    f"> 🤖 **Bot Status:** Role: **@{bot_top_role.name}** (Position: `{bot_pos}`) | Manage Roles: **Active ✅**"
                )

        if notice:
            info_blocks.append(f"> {notice}")

        action_guide = (
            "### 🛠️ **Server Actions**\n"
            "• **⚡ Auto-Setup Roles:** Scans server for matching color roles or creates missing ones with their exact accent colors.\n"
            "• **🔄 Sync My Role:** Refreshes your own Discord role to match your active character's Swing.\n"
            "• **👥 Sync All Players:** Updates all campaign players in the server to match their active character's Swing.\n"
            "• **🧹 Reset Selected:** Clears the custom role mapping for the dropdown-selected color."
        )

        body_text = (
            "\n\n".join(info_blocks) +
            "\n\n### 📋 **Current Color Role Mappings**\n" +
            "\n".join(role_status_lines) +
            f"\n\n{action_guide}"
        )

        accent = COLOR_DISCORD_COLORS.get(self.selected_color, discord.Color.gold())

        container = discord.ui.Container(
            discord.ui.TextDisplay(content="## 🎨 **Sentiment Swing Color Roles Configuration**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=body_text),
            accent_color=accent
        )

        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(discord.ui.ActionRow(ColorSelectComponent(self.selected_color)))
        container.add_item(discord.ui.ActionRow(RoleSelectComponent(self.selected_color)))
        container.add_item(discord.ui.ActionRow(
            AutoSetupButton(),
            SyncMyRoleButton(),
            SyncAllPlayersButton(),
            ResetRoleButton()
        ))

        self.add_item(container)

    async def refresh(self, interaction: discord.Interaction, is_followup: bool = False, notice: Optional[str] = None):
        await self.render_view(notice=notice)
        if is_followup:
            await interaction.edit_original_response(view=self)
        else:
            try:
                await interaction.response.edit_message(view=self)
            except discord.InteractionResponded:
                await interaction.edit_original_response(view=self)
            except Exception:
                await interaction.followup.send(view=self)
