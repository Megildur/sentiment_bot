import logging
import discord
from typing import Optional, List, Dict
from .Constants import COLOR_EMOJIS, COLOR_DISCORD_COLORS, COLOR_ORDER

logger = logging.getLogger("sentiment.color_roles")


def is_higher_than(higher_role: Optional[discord.Role], lower_role: Optional[discord.Role]) -> bool:
    """Safely checks if higher_role is strictly higher in the hierarchy than lower_role."""
    if not higher_role or not lower_role:
        return False
    return getattr(higher_role, "position", 0) > getattr(lower_role, "position", 0)


async def get_or_create_color_role(guild: discord.Guild, db_manager, color_name: str) -> Optional[discord.Role]:
    """
    Finds or creates a role for the specified Sentiment color.
    1. Checks database mapping for the guild.
    2. If not mapped or role was deleted, searches existing roles in the guild by name.
    3. If not found, creates the role with the matching accent color.
    """
    if not guild:
        return None

    # 1. Check DB mapping
    role_id = await db_manager.get_guild_color_role(guild.id, color_name)
    if role_id:
        role = guild.get_role(role_id)
        if role is not None:
            return role
        # Role was deleted in guild, clean up stale DB entry
        await db_manager.delete_guild_color_role(guild.id, color_name)

    desired_color = COLOR_DISCORD_COLORS.get(color_name)

    # 2. Search existing roles by name (case-insensitive)
    matching_role = next(
        (r for r in guild.roles if r.name.strip().lower() == color_name.lower()),
        None
    )

    if matching_role:
        # If matching role color differs and bot has permission to edit it, update to match accent color
        if desired_color and matching_role.color.value != desired_color.value:
            try:
                if guild.me.guild_permissions.manage_roles and is_higher_than(guild.me.top_role, matching_role):
                    await matching_role.edit(colour=desired_color, reason=f"Sentiment color role update for {color_name}")
            except Exception as e:
                logger.warning(f"Could not update color for existing role {matching_role.name}: {e}")

        await db_manager.set_guild_color_role(guild.id, color_name, matching_role.id)
        return matching_role

    # 3. Create role if not found
    if guild.me.guild_permissions.manage_roles:
        try:
            created_role = await guild.create_role(
                name=color_name,
                colour=desired_color or discord.Color.default(),
                reason=f"Sentiment Swing Color Role for {color_name}"
            )
            await db_manager.set_guild_color_role(guild.id, color_name, created_role.id)
            return created_role
        except Exception as e:
            logger.warning(f"Failed to create color role '{color_name}' in guild {guild.id}: {e}")
            return None
    else:
        logger.warning(f"Cannot create role '{color_name}' in guild {guild.id}: Bot missing Manage Roles permission")
        return None


async def get_all_guild_color_roles(guild: discord.Guild, db_manager) -> List[discord.Role]:
    """
    Returns a deduplicated list of all roles in the guild that represent any of the 10 Sentiment colors.
    Includes roles in the database and roles whose names match any of the color names.
    """
    if not guild:
        return []

    roles = set()
    # From DB
    db_roles = await db_manager.get_guild_color_roles(guild.id)
    for color, r_id in db_roles.items():
        role = guild.get_role(r_id)
        if role:
            roles.add(role)

    # From role names
    color_names_lower = {c.lower() for c in COLOR_ORDER}
    for r in guild.roles:
        if r.name.strip().lower() in color_names_lower:
            roles.add(r)

    return list(roles)


async def assign_swing_color_role(bot, guild: discord.Guild, member: discord.Member, db_manager, chosen_color: str) -> Optional[discord.Role]:
    """
    Assigns the color role matching chosen_color to the member, and strips any other color roles they hold.
    """
    if not guild or not member or not isinstance(member, discord.Member):
        return None

    target_role = await get_or_create_color_role(guild, db_manager, chosen_color)
    all_color_roles = await get_all_guild_color_roles(guild, db_manager)

    # Roles to remove: any color role the member currently holds except target_role
    roles_to_remove = [r for r in member.roles if r in all_color_roles and (not target_role or r.id != target_role.id)]

    can_manage = guild.me.guild_permissions.manage_roles and is_higher_than(guild.me.top_role, member.top_role)

    if can_manage and roles_to_remove:
        removable = [r for r in roles_to_remove if is_higher_than(guild.me.top_role, r)]
        if removable:
            try:
                await member.remove_roles(*removable, reason="Sentiment swing color changed")
            except Exception as e:
                logger.warning(f"Failed to remove old swing roles from {member}: {e}")

    if target_role and target_role not in member.roles:
        if can_manage and is_higher_than(guild.me.top_role, target_role):
            try:
                await member.add_roles(target_role, reason=f"Sentiment swing set to {chosen_color}")
            except Exception as e:
                logger.warning(f"Failed to add swing role {target_role.name} to {member}: {e}")

    return target_role


async def remove_swing_color_roles(bot, guild: discord.Guild, member: discord.Member, db_manager) -> List[discord.Role]:
    """
    Removes all Sentiment color roles currently held by the member.
    """
    if not guild or not member or not isinstance(member, discord.Member):
        return []

    all_color_roles = await get_all_guild_color_roles(guild, db_manager)
    roles_to_remove = [r for r in member.roles if r in all_color_roles]

    can_manage = guild.me.guild_permissions.manage_roles and is_higher_than(guild.me.top_role, member.top_role)

    if can_manage and roles_to_remove:
        removable = [r for r in roles_to_remove if is_higher_than(guild.me.top_role, r)]
        if removable:
            try:
                await member.remove_roles(*removable, reason="Sentiment swing dropped / removed")
            except Exception as e:
                logger.warning(f"Failed to remove swing roles from {member}: {e}")

    return roles_to_remove


async def sync_member_swing_color_role(bot, guild: discord.Guild, user_id: int, db_manager) -> None:
    """
    Syncs a member's swing color role to their active character's current swing state.
    """
    if not guild:
        return

    member = guild.get_member(user_id)
    if not member:
        try:
            member = await guild.fetch_member(user_id)
        except Exception:
            return

    if not member or not isinstance(member, discord.Member):
        return

    active_char = await db_manager.get_selected_char(user_id)
    if active_char:
        swing = await db_manager.get_swing(user_id, active_char)
        if swing and swing[0]:
            await assign_swing_color_role(bot, guild, member, db_manager, swing[0])
            return

    await remove_swing_color_roles(bot, guild, member, db_manager)


async def auto_setup_all_color_roles(guild: discord.Guild, db_manager) -> Dict[str, Optional[discord.Role]]:
    """
    Iterates through all 10 Sentiment colors, searching or creating each role and binding to DB.
    """
    mappings = {}
    for color in COLOR_ORDER:
        role = await get_or_create_color_role(guild, db_manager, color)
        mappings[color] = role
    return mappings


class ColorSelectComponent(discord.ui.Select):
    def __init__(self, selected_color: str):
        options = [
            discord.SelectOption(
                label=f"{color}",
                value=color,
                emoji=COLOR_EMOJIS.get(color, "⚪"),
                default=(color == selected_color),
                description=f"Configure role for {color}"
            )
            for color in COLOR_ORDER
        ]
        super().__init__(
            placeholder="Select a color to configure or assign...",
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
            placeholder=f"Select a server role for {selected_color}...",
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
        desired_color = COLOR_DISCORD_COLORS.get(color_name)
        if desired_color and selected_role.color.value != desired_color.value:
            if interaction.guild.me.guild_permissions.manage_roles and is_higher_than(interaction.guild.me.top_role, selected_role):
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
            label="Auto-Setup All Roles",
            style=discord.ButtonStyle.success,
            emoji="⚡",
            custom_id="auto_setup_color_roles_btn"
        )

    async def callback(self, interaction: discord.Interaction):
        if not await self.view.check_admin_permissions(interaction):
            return

        await interaction.response.defer()
        await auto_setup_all_color_roles(interaction.guild, self.view.db_manager)
        await self.view.refresh(
            interaction,
            is_followup=True,
            notice="✅ **Auto-Setup Complete!** All 10 color roles were verified or created with matching accent colors."
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
        await sync_member_swing_color_role(
            self.view.bot,
            interaction.guild,
            interaction.user.id,
            self.view.db_manager
        )
        active_char = await self.view.db_manager.get_selected_char(interaction.user.id)
        swing = await self.view.db_manager.get_swing(interaction.user.id, active_char) if active_char else None
        if swing:
            emoji = COLOR_EMOJIS.get(swing[0], "⚪")
            await interaction.response.send_message(
                f"✅ Synced your swing role to {emoji} **{swing[0]}** for character *{active_char}*!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "ℹ️ Your active character has no active swing. Removed all swing color roles.",
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
            notice=f"🧹 Reset custom mapping for **{color_name}**. The bot will search by role name or create on next swing."
        )


class ColorRolesConfigView(discord.ui.LayoutView):
    @classmethod
    async def build(cls, bot, guild: discord.Guild, db_manager, selected_color: str = "Red"):
        view = cls(bot=bot, guild=guild, db_manager=db_manager, selected_color=selected_color)
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

        db_roles = await self.db_manager.get_guild_color_roles(self.guild.id)
        has_manage_roles = self.guild.me.guild_permissions.manage_roles if self.guild else False
        bot_top_role = self.guild.me.top_role if self.guild else None

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
                warn = ""
                bot_pos = getattr(bot_top_role, 'position', 0) if bot_top_role else 0
                role_pos = getattr(role, 'position', 0)
                if bot_top_role and role_pos >= bot_pos:
                    warn = " ⚠️ *(Placed above bot!)*"
                role_status_lines.append(f"• {emoji} **{color}**: {role.mention} (`#{hex_color}`){warn}")
            else:
                role_status_lines.append(f"• {emoji} **{color}**: *Not mapped (Auto-created on use)* (`#{hex_color}`)")

        info_blocks = [
            "> ⚠️ **CRITICAL: Role Hierarchy Required for Chat Name Colors**\n"
            "> Discord sets a user's name color in chat and the member list by their **highest role with a color**.\n"
            "> \n"
            "> 1. Open **Server Settings ➔ Roles**.\n"
            "> 2. Drag all 10 Color Roles to the **top of your role hierarchy** (just below the bot's own role).\n"
            "> 3. Ensure the **Bot's role** is positioned **above** the color roles and has **Manage Roles** enabled.\n"
            "> 4. Ensure players do not have another role above these color roles that has a custom color."
        ]

        if not has_manage_roles:
            info_blocks.append(
                "> ❌ **CRITICAL: Bot is missing the 'Manage Roles' permission!**\n"
                "> The bot cannot assign, edit, or auto-create color roles until this permission is granted in Server Settings."
            )

        if notice:
            info_blocks.append(f"> {notice}")

        body_text = (
            "\n\n".join(info_blocks) +
            "\n\n### 📋 **Current Color Role Mappings**\n" +
            "\n".join(role_status_lines)
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
