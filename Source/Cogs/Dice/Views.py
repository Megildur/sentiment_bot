import discord
import random
from typing import Optional
from .Constants import COLOR_EMOJIS

MODAL_COLOR_EMOJIS = COLOR_EMOJIS.copy()
MODAL_COLOR_EMOJIS["Grey"] = "🔘"

COLOR_DISCORD_COLORS = {
    "Red": discord.Color.red(),
    "Yellow": discord.Color.gold(),
    "Green": discord.Color.green(),
    "Blue": discord.Color.blue(),
    "Purple": discord.Color.purple(),
    "Orange": discord.Color.orange(),
    "Grey": discord.Color.light_grey(),
    "Black": discord.Color.from_rgb(45, 45, 45),
    "White": discord.Color.from_rgb(245, 245, 245),
    "Clear": discord.Color.teal()
}

def get_swing_accent_color(swing: Optional[tuple] = None) -> discord.Color:
    if swing and swing[0] in COLOR_DISCORD_COLORS:
        return COLOR_DISCORD_COLORS[swing[0]]
    return discord.Color.random()

class AddGMButton(discord.ui.Button):
    def __init__(self, bot, user_id, db_manager):
        super().__init__(
            label="confirm",
            style=discord.ButtonStyle.success,
            custom_id="confirm_dm"
        )
        self.bot = bot
        self.user_id = user_id
        self.db_manager = db_manager

    async def callback(self, interaction: discord.Interaction):
        await self.db_manager.set_gm(interaction, self.user_id)

class DatabaseFailView(discord.ui.LayoutView):
    def __init__(self, bot, body, footer_text, db_manager = None, **kwargs):
        super().__init__(timeout=300)
        self.kwargs = kwargs
        self.bot=bot

        container = discord.ui.Container(
            discord.ui.TextDisplay(content="## **⚠️ WARNING**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=body),
            accent_color=discord.Color.yellow()
        )

        if "change" in self.kwargs:
            footer = discord.ui.TextDisplay(content=footer_text)
            new_gm_id = self.kwargs.get("change") 
            button = AddGMButton(self.bot, new_gm_id, db_manager)
            container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
            container.add_item(discord.ui.Section(
                footer,
                accessory=button
            ))

        else:
            footer = discord.ui.TextDisplay(content=f"footer")
            container.add_item(footer)

        self.add_item(container)

class DatabaseSuccessView(discord.ui.LayoutView):
    def __init__(self, bot, body, user_id, **kwargs):
        super().__init__(timeout=300)
        self.bot = bot
        self.kwargs = kwargs

        container = discord.ui.Container(
            discord.ui.TextDisplay(content="## **✅ SUCCESS**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=body),
            accent_color=discord.Color.green()
        )

        self.add_item(container)

class SetValuesModal(discord.ui.Modal, title="Set Attributes and Bonuses"):
    def __init__(self, bot, db_manager):
        super().__init__()
        self.bot = bot
        self.db_manager = db_manager
        
        self.char_name_input = discord.ui.TextInput(
            label="Character Name",
            placeholder="Enter character name here...",
            max_length=50,
            required=True
        )
        self.add_item(self.char_name_input)
        
        color_choices = ["Red", "Yellow", "Green", "Blue", "Purple", "Orange", "Grey", "Black", "White", "Clear"]
        
        color_opts = []
        for c in color_choices:
            color_opts.append(discord.CheckboxGroupOption(
                label=f"{MODAL_COLOR_EMOJIS.get(c, '⚪')} {c}", 
                value=c
            ))
            
        self.colors = discord.ui.CheckboxGroup(
            options=color_opts,
            max_values=3,
            min_values=1
        )
        self.add_item(discord.ui.Label(text="Select Colors", component=self.colors))
        
        def create_radio_options():
            opts = []
            for i in range(10): 
                val = str(i)
                opts.append(discord.RadioGroupOption(label=f"Bonus: +{val}", value=val))
            return opts

        self.attribute1 = discord.ui.RadioGroup(options=create_radio_options(), required=False)
        self.add_item(discord.ui.Label(text="Bonus for 1st checked color", component=self.attribute1))
        
        self.attribute2 = discord.ui.RadioGroup(options=create_radio_options(), required=False)
        self.add_item(discord.ui.Label(text="Bonus for 2nd checked color", component=self.attribute2))
        
        self.attribute3 = discord.ui.RadioGroup(options=create_radio_options(), required=False)
        self.add_item(discord.ui.Label(text="Bonus for 3rd checked color", component=self.attribute3))

    async def on_submit(self, interaction: discord.Interaction):
        char_name = self.char_name_input.value
        selected_colors = self.colors.values
        
        raw_bonuses = [self.attribute1.value, self.attribute2.value, self.attribute3.value]
        bonuses = [int(b) for b in raw_bonuses if b is not None]
        
        while len(bonuses) < len(selected_colors):
            bonuses.append(0)
            
        attributes = list(zip(selected_colors, bonuses))
        
        await self.db_manager.set_attributes(interaction, char_name, attributes)
        await self.db_manager.set_selected_char(interaction.user.id, char_name)
        
        view = await AttributeSetView.build(self.bot, interaction, self.db_manager, char_name=char_name, is_new=True)
        
        is_ephemeral = interaction.message.flags.ephemeral if interaction.message else False

        if is_ephemeral:
            await interaction.response.send_message(view=view)
        else:
            try:
                await interaction.response.edit_message(view=view)
            except discord.HTTPException:
                await interaction.response.send_message(view=view)
                
class AttributeSetView(discord.ui.LayoutView):

    @classmethod
    async def build(cls, bot, interaction: discord.Interaction, db_manager, char_name: str, is_new: bool = False):
        result = await db_manager.check_attributes(bot, interaction, char_name)
        all_chars = await db_manager.get_all_characters(interaction.user.id)
        attribute_names = await db_manager.get_attribute_names(interaction.user.id, char_name)
        is_gm = await db_manager.is_gm(interaction.user.id)
        is_npc = await db_manager.is_npc(char_name)
        display_name = await db_manager.get_char_display_name(char_name)
        swing = await db_manager.get_swing(interaction.user.id, char_name)
        
        return cls(
            bot=bot, 
            interaction=interaction, 
            db_manager=db_manager, 
            char_name=char_name, 
            result=result, 
            all_chars=all_chars, 
            attribute_names=attribute_names, 
            is_new=is_new,
            is_gm=is_gm,
            is_npc=is_npc,
            display_name=display_name,
            swing=swing
        )

    def __init__(self, bot, interaction, db_manager, char_name: str, result: list, all_chars: list, attribute_names: dict = None, is_new: bool = False, is_gm: bool = False, is_npc: bool = False, display_name: str = None, swing: tuple = None):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = interaction.user.id
        self.char_name = char_name
        self.is_gm = is_gm
        self.is_npc = is_npc
        self.display_name = display_name or char_name

        attribute_names = attribute_names or {}

        title = "## **✅ Attributes and bonuses are set!**" if is_new else "## **⚠️ Attributes and bonuses are already set!**"
        
        color_choices = ["Red", "Yellow", "Green", "Blue", "Purple", "Orange", "Grey", "Black", "White", "Clear"]
        
        results = sorted(result, key=lambda row: color_choices.index(row[0]) if row[0] in color_choices else 99)
        
        body_lines = [f"### 📊 {interaction.user.display_name}'s Attribute Breakdown \n**Character Name:** *{self.display_name}*"]
        for i, row in enumerate(results, start=1):
            color = row[0]
            bonus = row[1]
            
            custom_name = attribute_names.get(color)
            display_name_attr = f"{color} (**Attribute Name:** *{custom_name}*)" if custom_name else color
            
            body_lines.append(f"• **Slot {i}:** {COLOR_EMOJIS.get(color, '⚪')} {display_name_attr} ➔ **Bonus:** +{bonus}")
        
        body = "\n".join(body_lines)
        
        footer = "-# If any of these are wrong or need to be updated please select it in this dropdown to update it"
        footer2 = "Press this button to add another attribute and set its bonus"
        footer3 = "Press this button to remove an attribute and its bonus"
        
        container = discord.ui.Container(
            discord.ui.TextDisplay(content=title),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=body),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            discord.ui.TextDisplay(content="Use this select to change the character you are editing and make it your selected character!\n"),
            discord.ui.ActionRow(ChangeCharSelect(self.bot, db_manager, all_chars, active_char=self.char_name)),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large, visible=False),
            discord.ui.TextDisplay(content=
                                  "**NOTE:** The character selected and shown here will be the one modified when using all other commands and rolls.\n"
                                   "**IT IS YOUR ACTIVE CHARACTER**\n"
                                   "You can also change your active character before using another command or roll using the `/change_active_character` command."
            ),
            discord.ui.Separator(visible=False),
            discord.ui.Section(
                discord.ui.TextDisplay(content="-# Need to make a new character? Press this button!"),
                accessory=CreateCharButton(self.bot, db_manager)
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            discord.ui.TextDisplay(content=footer),
            discord.ui.ActionRow(
                EditAttributeSelect(self.bot, db_manager, char_name=self.char_name, result=results)
            ),
            discord.ui.Separator(visible=False),
            discord.ui.Section(
                discord.ui.TextDisplay(content="Do you want to name an attribute for this character?"),
                accessory=NameAtrsButton(self.bot, db_manager, char_name=self.char_name)
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            discord.ui.Section(
                discord.ui.TextDisplay(content=footer2),
                accessory=AddAtrsButton(self.bot, db_manager, char_name=self.char_name)
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large, visible=False),
            discord.ui.Section(
                discord.ui.TextDisplay(content=footer3),
                accessory=DeleteAtrsButton(self.bot, db_manager, char_name=self.char_name)
            ),
        )

        if self.is_gm:
            container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large, visible=False))
            container.add_item(discord.ui.Section(
                discord.ui.TextDisplay(content="-# GM Option: Mark or unmark this character as an NPC"),
                accessory=ToggleNPCButton(self.bot, db_manager, char_name=self.char_name, is_npc=self.is_npc)
            ))

        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(discord.ui.TextDisplay(content="Select a character here to delete it!"))
        container.add_item(discord.ui.ActionRow(DeleteCharSelect(self.bot, db_manager, all_chars, active_char=self.char_name)))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(discord.ui.Section(
            discord.ui.TextDisplay("Press this button to close this menu"),
            accessory=CloseMenuButton()
        ))
        container.accent_color = get_swing_accent_color(swing)

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        
        await interaction.response.send_message(
            "❌ This menu is not for you.", 
            ephemeral=True
        )
        return False

class EditAttributeSelect(discord.ui.Select):
    def __init__(self, bot, db_manager, char_name: str, result: list):
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name
        self.result_dict = {row[0]: str(row[1]) for row in result}
        
        options = [
            discord.SelectOption(label=f"Edit {color}", description=f"Current bonus: +{bonus}", value=color, emoji=COLOR_EMOJIS.get(color, "⚪"))
            for color, bonus in self.result_dict.items()
        ]
        disabled = False
        if not options:
            options = [discord.SelectOption(label="No attributes available", value="_none_")]
            disabled = True
            
        super().__init__(placeholder="Select an attribute to edit...", min_values=1, max_values=1, options=options, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        selected_color = self.values[0]
        modal = EditSingleAttributeModal(self.bot, self.db_manager, self.char_name, selected_color, self.result_dict[selected_color])
        await interaction.response.send_modal(modal)

class EditSingleAttributeModal(discord.ui.Modal, title="Edit Attribute"):
    def __init__(self, bot, db_manager, char_name: str, old_color: str, old_bonus: str):
        super().__init__()
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name
        self.old_color = old_color
        
        color_opts = [discord.CheckboxGroupOption(label=f"{MODAL_COLOR_EMOJIS.get(c, '⚪')} {c}", value=c, default=(c == old_color)) for c in ["Red", "Yellow", "Green", "Blue", "Purple", "Orange", "Grey", "Black", "White", "Clear"]]
        self.color_select = discord.ui.CheckboxGroup(options=color_opts, max_values=1, min_values=1)
        self.add_item(discord.ui.Label(text=f"Editing: {old_color}", component=self.color_select))
        
        bonus_opts = [discord.RadioGroupOption(label=f"Bonus: +{i}", value=str(i), default=(str(i) == old_bonus)) for i in range(10)]
        self.bonus_select = discord.ui.RadioGroup(options=bonus_opts)
        self.add_item(discord.ui.Label(text="Select new bonus", component=self.bonus_select))

    async def on_submit(self, interaction: discord.Interaction):
        await self.db_manager.edit_attribute(interaction, self.char_name, self.old_color, self.color_select.values[0], int(self.bonus_select.value))
        
        view = await AttributeSetView.build(self.bot, interaction, self.db_manager, self.char_name)
        
        try:
            await interaction.response.edit_message(view=view)
        except discord.HTTPException:
            await interaction.response.send_message(view=view)

class AddAtrsButton(discord.ui.Button):
    def __init__(self, bot, db_manager, char_name: str):
        super().__init__(label="Add Attribute", style=discord.ButtonStyle.primary)
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name

    async def callback(self, interaction: discord.Interaction):
        result = await self.db_manager.check_attributes(self.bot, interaction, self.char_name)
        current_colors = [row[0] for row in result] if result else []
        
        if len(current_colors) >= 10:
            await interaction.response.send_message("❌ This character already has all available attributes!", ephemeral=True)
            return
            
        await interaction.response.send_modal(AddSingleAttributeModal(self.bot, self.db_manager, self.char_name, current_colors))

class AddSingleAttributeModal(discord.ui.Modal, title="Add New Attribute"):
    def __init__(self, bot, db_manager, char_name: str, current_colors: list):
        super().__init__()
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name
        
        all_colors = ["Red", "Yellow", "Green", "Blue", "Purple", "Orange", "Grey", "Black", "White", "Clear"]
        available = [c for c in all_colors if c not in current_colors]
        
        self.color_select = discord.ui.CheckboxGroup(options=[discord.CheckboxGroupOption(label=f"{MODAL_COLOR_EMOJIS.get(c, '⚪')} {c}", value=c) for c in available], max_values=1, min_values=1)
        self.add_item(discord.ui.Label(text="Select a color to add", component=self.color_select))
        
        self.bonus_select = discord.ui.RadioGroup(options=[discord.RadioGroupOption(label=f"Bonus: +{i}", value=str(i), default=(str(i) == "0")) for i in range(10)])
        self.add_item(discord.ui.Label(text="Select bonus", component=self.bonus_select))

    async def on_submit(self, interaction: discord.Interaction):
        await self.db_manager.add_attribute(interaction, self.char_name, self.color_select.values[0], int(self.bonus_select.value))
        
        view = await AttributeSetView.build(self.bot, interaction, self.db_manager, self.char_name)

        try:
            await interaction.response.edit_message(view=view)
        except discord.HTTPException:
            await interaction.response.send_message(view=view)

class DeleteAtrsButton(discord.ui.Button):
    def __init__(self, bot, db_manager, char_name: str):
        super().__init__(label="Delete Attribute", style=discord.ButtonStyle.danger)
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name

    async def callback(self, interaction: discord.Interaction):
        result = await self.db_manager.check_attributes(self.bot, interaction, self.char_name)
        
        if not result:
            await interaction.response.send_message("❌ This character has no attributes to delete!", ephemeral=True)
            return
            
        await interaction.response.send_modal(DeleteSingleAttributeModal(self.bot, self.db_manager, self.char_name, result))

class DeleteSingleAttributeModal(discord.ui.Modal, title="Delete Attribute"):
    def __init__(self, bot, db_manager, char_name: str, current_attributes: list):
        super().__init__()
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name
        
        options = [discord.SelectOption(label=f"{row[0]} (+{row[1]})", value=row[0], emoji=COLOR_EMOJIS.get(row[0], "⚪")) for row in current_attributes]
        self.color_select = discord.ui.Select(options=options, min_values=1, max_values=1, placeholder="Select an attribute to delete...")
        self.add_item(discord.ui.Label(text="Attribute to Delete", component=self.color_select))

    async def on_submit(self, interaction: discord.Interaction):
        await self.db_manager.delete_attribute(interaction, self.char_name, self.color_select.values[0])
        
        all_chars = await self.db_manager.get_all_characters(interaction.user.id)
        if not all_chars:
            await self.db_manager.completely_delete_character(interaction.user.id, self.char_name)
            view = NoCharactersLeftView(self.bot, self.db_manager, deleted_char=self.char_name)
        else:
            view = await AttributeSetView.build(self.bot, interaction, self.db_manager, self.char_name, is_new=True)

        try:
            await interaction.response.edit_message(view=view)
        except discord.HTTPException:
            await interaction.response.send_message(view=view)

class CreateCharButton(discord.ui.Button):
    def __init__(self, bot, db_manager):
        super().__init__(label="Create New Character", style=discord.ButtonStyle.success, custom_id="create_new_char")
        self.bot = bot
        self.db_manager = db_manager

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SetValuesModal(self.bot, self.db_manager))

class ChangeCharSelect(discord.ui.Select):
    def __init__(self, bot, db_manager, all_chars: list, active_char: str):
        self.bot = bot
        self.db_manager = db_manager
        
        options = [
            discord.SelectOption(label=c, value=c, default=(c == active_char))
            for c in all_chars[:25]
        ]
        disabled = False
        if not options:
            options = [discord.SelectOption(label="No characters available", value="_none_")]
            disabled = True
        
        super().__init__(placeholder="Switch active character...", min_values=1, max_values=1, options=options, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        new_active = self.values[0]
        await self.db_manager.set_selected_char(interaction.user.id, new_active)

        view = await AttributeSetView.build(self.bot, interaction, self.db_manager, char_name=new_active)
        await interaction.response.edit_message(view=view)

class DeleteCharSelect(discord.ui.Select):
    def __init__(self, bot, db_manager, all_chars: list, active_char: str):
        self.bot = bot
        self.db_manager = db_manager
        self.active_char = active_char
        
        options = [discord.SelectOption(label=c, value=c) for c in all_chars[:25]]
        disabled = False
        if not options:
            options = [discord.SelectOption(label="No characters available", value="_none_")]
            disabled = True
        super().__init__(placeholder="Delete a character permanently...", min_values=1, max_values=1, options=options, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        char_to_delete = self.values[0]
        swing = await self.db_manager.get_swing(interaction.user.id, char_to_delete)
        view = ConfirmDeleteCharView(self.bot, self.db_manager, char_to_delete, self.active_char, swing=swing)
        await interaction.response.edit_message(view=view)

class NoCharactersLeftView(discord.ui.LayoutView):
    def __init__(self, bot, db_manager, deleted_char: str = None):
        super().__init__(timeout=300)
        deleted_msg = f"**{deleted_char}** was permanently deleted.\n\n" if deleted_char else ""
        container = discord.ui.Container(
            discord.ui.TextDisplay(content="## **⚠️ No Characters Remaining**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                content=f"{deleted_msg}You have no characters left. Use `/set_attributes` or press the button below to create a new character!"
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            discord.ui.ActionRow(
                CreateCharButton(bot, db_manager),
                CloseMenuButton()
            ),
            accent_color=discord.Color.random()
        )
        self.add_item(container)

class CancelDeleteButton(discord.ui.Button):
    def __init__(self, bot, db_manager, active_char: str):
        super().__init__(label="Cancel", style=discord.ButtonStyle.secondary)
        self.bot = bot
        self.db_manager = db_manager
        self.active_char = active_char

    async def callback(self, interaction: discord.Interaction):
        all_chars = await self.db_manager.get_all_characters(interaction.user.id)
        if not all_chars:
            view = NoCharactersLeftView(self.bot, self.db_manager)
            await interaction.response.edit_message(view=view)
            return

        target_char = self.active_char if self.active_char in all_chars else all_chars[0]
        view = await AttributeSetView.build(self.bot, interaction, self.db_manager, char_name=target_char)
        await interaction.response.edit_message(view=view)

class ConfirmDeleteButton(discord.ui.Button):
    def __init__(self, bot, db_manager, char_to_delete: str, active_char: str):
        super().__init__(label="Confirm Delete", style=discord.ButtonStyle.danger)
        self.bot = bot
        self.db_manager = db_manager
        self.char_to_delete = char_to_delete
        self.active_char = active_char

    async def callback(self, interaction: discord.Interaction):
        await self.db_manager.completely_delete_character(interaction.user.id, self.char_to_delete)
        all_chars = await self.db_manager.get_all_characters(interaction.user.id)
        
        if not all_chars:
            view = NoCharactersLeftView(self.bot, self.db_manager, deleted_char=self.char_to_delete)
            await interaction.response.edit_message(view=view)
        elif self.char_to_delete == self.active_char or self.active_char not in all_chars:
            view = SelectNewActiveCharView(self.bot, self.db_manager, all_chars, deleted_char=self.char_to_delete)
            await interaction.response.edit_message(view=view)
        else:
            view = await AttributeSetView.build(self.bot, interaction, self.db_manager, char_name=self.active_char)
            await interaction.response.edit_message(view=view)

class ConfirmDeleteCharView(discord.ui.LayoutView):
    def __init__(self, bot, db_manager, char_to_delete: str, active_char: str, swing: tuple = None):
        super().__init__(timeout=300)
        
        container = discord.ui.Container(
            discord.ui.TextDisplay(content=f"## **⚠️ Delete {char_to_delete}?**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=f"Are you sure you want to permanently delete **{char_to_delete}**? This action cannot be undone."),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            
            discord.ui.ActionRow(
                CancelDeleteButton(bot, db_manager, active_char),
                ConfirmDeleteButton(bot, db_manager, char_to_delete, active_char)
            ),
            accent_color=get_swing_accent_color(swing)
        )
        self.add_item(container)

class NewActiveCharSelect(discord.ui.Select):
    def __init__(self, bot, db_manager, all_chars: list):
        self.bot = bot
        self.db_manager = db_manager
        options = [discord.SelectOption(label=c, value=c) for c in all_chars[:25]]
        super().__init__(placeholder="Select new active character...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        new_active = self.values[0]
        await self.db_manager.set_selected_char(interaction.user.id, new_active)
        
        view = await AttributeSetView.build(self.bot, interaction, self.db_manager, char_name=new_active)
        await interaction.response.edit_message(view=view)

class SelectNewActiveCharView(discord.ui.LayoutView):
    def __init__(self, bot, db_manager, all_chars: list, deleted_char: str = None, swing: tuple = None):
        super().__init__(timeout=300)
        
        title = "## **Select New Character**"
        
        if deleted_char:
            body = f"**{deleted_char}** was successfully deleted.\nPlease select a new active character from the dropdown below."
        else:
            body = "Please select a new active character."
            
        container = discord.ui.Container(
            discord.ui.TextDisplay(content=title),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=body),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            discord.ui.ActionRow(
                NewActiveCharSelect(bot, db_manager, all_chars)
            ),
            accent_color=get_swing_accent_color(swing)
        )
        self.add_item(container)

class CloseMenuButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Close Menu",
            style=discord.ButtonStyle.secondary,
            custom_id="close_menu_button"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.message.delete()

class NameAtrsButton(discord.ui.Button):
    def __init__(self, bot, db_manager, char_name: str):
        super().__init__(label="Name Attribute", style=discord.ButtonStyle.secondary)
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name

    async def callback(self, interaction: discord.Interaction):
        result = await self.db_manager.check_attributes(self.bot, interaction, self.char_name)
        
        if not result:
            await interaction.response.send_message("❌ This character has no attributes to name!", ephemeral=True)
            return
            
        await interaction.response.send_modal(NameAttributeModal(self.bot, self.db_manager, self.char_name, result))

class NameAttributeModal(discord.ui.Modal, title="Name Attribute"):
    def __init__(self, bot, db_manager, char_name: str, current_attributes: list):
        super().__init__()
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name
        
        options = [
            discord.SelectOption(label=f"{row[0]} (+{row[1]})", value=row[0], emoji=COLOR_EMOJIS.get(row[0], "⚪"))
            for row in current_attributes
        ]
        self.color_select = discord.ui.Select(
            options=options, min_values=1, max_values=1, placeholder="Select an attribute to name..."
        )
        self.add_item(discord.ui.Label(text="Attribute to Name", component=self.color_select))

        self.name_input = discord.ui.TextInput(
            label="Attribute Name",
            placeholder="e.g., Strength, Honor...",
            max_length=50,
            required=True
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        selected_color = self.color_select.values[0]
        custom_name = self.name_input.value
        
        await self.db_manager.set_attribute_name(interaction, self.char_name, selected_color, custom_name)
        
        view = await AttributeSetView.build(self.bot, interaction, self.db_manager, char_name=self.char_name, is_new=True)
        
        try:
            await interaction.response.edit_message(view=view)
        except discord.HTTPException:
            await interaction.response.send_message(view=view)


class ToggleNPCButton(discord.ui.Button):
    def __init__(self, bot, db_manager, char_name: str, is_npc: bool = False):
        label = "Unmark NPC" if is_npc else "Mark as NPC"
        style = discord.ButtonStyle.danger if is_npc else discord.ButtonStyle.secondary
        super().__init__(label=label, style=style, custom_id="toggle_npc_btn")
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name

    async def callback(self, interaction: discord.Interaction):
        if not await self.db_manager.is_gm(interaction.user.id):
            await interaction.response.send_message("❌ Only the designated GM can mark or unmark a character as an NPC.", ephemeral=True)
            return
        await self.db_manager.toggle_npc(self.char_name)
        view = await AttributeSetView.build(self.bot, interaction, self.db_manager, char_name=self.char_name)
        try:
            await interaction.response.edit_message(view=view)
        except discord.HTTPException:
            await interaction.response.send_message(view=view)


class NoticeView(discord.ui.LayoutView):
    def __init__(self, title: str, body: str, color: Optional[discord.Color] = None):
        super().__init__(timeout=300)
        container = discord.ui.Container(
            discord.ui.TextDisplay(content=f"## {title}"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=body),
            accent_color=color if color is not None else discord.Color.random()
        )
        self.add_item(container)


class ChangeCardCharSelect(discord.ui.Select):
    def __init__(self, bot, db_manager, all_chars: list, active_char: str):
        self.bot = bot
        self.db_manager = db_manager
        options = [
            discord.SelectOption(label=c, value=c, default=(c == active_char))
            for c in all_chars[:25]
        ]
        disabled = False
        if not options:
            options = [discord.SelectOption(label="No characters available", value="_none_")]
            disabled = True
        super().__init__(placeholder="Switch active character...", min_values=1, max_values=1, options=options, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        new_active = self.values[0]
        await self.db_manager.set_selected_char(interaction.user.id, new_active)
        view = await CharacterCardView.build(self.bot, interaction, self.db_manager, char_name=new_active)
        await interaction.response.edit_message(view=view)


class ManageMaxHPButton(discord.ui.Button):
    def __init__(self, bot, db_manager, char_name: str):
        super().__init__(label="Manage Max HP", style=discord.ButtonStyle.primary, emoji="❤️", custom_id="manage_max_hp_btn")
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name

    async def callback(self, interaction: discord.Interaction):
        view = await ManageMaxHPView.build(self.bot, interaction, self.db_manager, self.char_name)
        await interaction.response.edit_message(view=view)


class BackToCharacterCardButton(discord.ui.Button):
    def __init__(self, bot, db_manager, char_name: str):
        super().__init__(label="Back to Character Card", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="back_to_card_btn")
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name

    async def callback(self, interaction: discord.Interaction):
        view = await CharacterCardView.build(self.bot, interaction, self.db_manager, self.char_name)
        await interaction.response.edit_message(view=view)


class PotentialFlatHPButton(discord.ui.Button):
    def __init__(self, parent_view, flat_gain: int):
        super().__init__(
            label=f"Level Up: +{flat_gain} Max HP (Flat)",
            style=discord.ButtonStyle.success,
            emoji="✨",
            custom_id="pot_flat_hp_btn"
        )
        self.parent_view = parent_view
        self.flat_gain = flat_gain

    async def callback(self, interaction: discord.Interaction):
        old_cur, old_max, new_cur, new_max = await self.parent_view.db_manager.adjust_max_hp(
            self.parent_view.user_id, self.parent_view.char_name, self.flat_gain
        )
        status_msg = (
            f"✨ **Spent 1 Potential (Default Option):**\n"
            f"• Max HP increased by **+{self.flat_gain}** (`{old_max}` ➔ `{new_max}`)\n"
            f"• Current HP increased (`{old_cur}/{old_max}` ➔ `{new_cur}/{new_max}`)"
        )
        view = await ManageMaxHPView.build(
            self.parent_view.bot, interaction, self.parent_view.db_manager, self.parent_view.char_name, status_note=status_msg
        )
        await interaction.response.edit_message(view=view)


class PotentialRollHPButton(discord.ui.Button):
    def __init__(self, parent_view, bracket_info: dict):
        can_roll = bracket_info["can_roll"]
        label = f"Level Up: Roll {bracket_info['roll_label']}" if can_roll else "Roll Unavailable (60+ Max HP)"
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            emoji="🎲",
            disabled=not can_roll,
            custom_id="pot_roll_hp_btn"
        )
        self.parent_view = parent_view
        self.bracket_info = bracket_info

    async def callback(self, interaction: discord.Interaction):
        d6_val = random.randint(1, 6)
        mod = self.bracket_info["roll_mod"]
        gained = max(0, d6_val + mod)
        old_cur, old_max, new_cur, new_max = await self.parent_view.db_manager.adjust_max_hp(
            self.parent_view.user_id, self.parent_view.char_name, gained
        )
        mod_str = f" + {mod}" if mod > 0 else (f" - {abs(mod)}" if mod < 0 else "")
        status_msg = (
            f"🎲 **Spent 1 Potential (Randomized {self.bracket_info['roll_label']}):**\n"
            f"• Rolled **1d6 ({d6_val}){mod_str} = +{gained} Max HP**\n"
            f"• HP Updated: `{old_cur}/{old_max}` ➔ `{new_cur}/{new_max}`"
        )
        view = await ManageMaxHPView.build(
            self.parent_view.bot, interaction, self.parent_view.db_manager, self.parent_view.char_name, status_note=status_msg
        )
        await interaction.response.edit_message(view=view)


class CustomMaxHPModal(discord.ui.Modal):
    def __init__(self, bot, db_manager, char_name: str, current_max: int):
        super().__init__(title=f"Adjust Max HP: {char_name[:25]}")
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name

        self.delta_input = discord.ui.TextInput(
            label="Increase or Decrease Max HP (e.g. +5 or -3)",
            placeholder="Enter +amount to add or -amount to subtract (leave blank if setting exact)",
            required=False,
            max_length=10
        )
        self.exact_input = discord.ui.TextInput(
            label=f"OR Set Exact Max HP (Current: {current_max})",
            placeholder="Enter exact new Max HP (e.g. 15, 25)",
            required=False,
            max_length=10
        )
        self.add_item(self.delta_input)
        self.add_item(self.exact_input)

    async def on_submit(self, interaction: discord.Interaction):
        delta_raw = self.delta_input.value.strip()
        exact_raw = self.exact_input.value.strip()

        if not delta_raw and not exact_raw:
            await interaction.response.send_message("❌ Please provide either an amount to add/subtract or an exact Max HP value.", ephemeral=True)
            return

        try:
            if exact_raw:
                target_val = int(exact_raw)
                if target_val < 1:
                    await interaction.response.send_message("❌ Max HP must be at least 1.", ephemeral=True)
                    return
                old_cur, old_max, new_cur, new_max = await self.db_manager.set_max_hp_value(
                    interaction.user.id, self.char_name, target_val
                )
                diff = new_max - old_max
                diff_str = f"+{diff}" if diff >= 0 else f"{diff}"
                status_msg = (
                    f"⚙️ **Max HP Set to {new_max} ({diff_str}):**\n"
                    f"• HP Updated: `{old_cur}/{old_max}` ➔ `{new_cur}/{new_max}`"
                )
            else:
                delta_val = int(delta_raw)
                old_cur, old_max, new_cur, new_max = await self.db_manager.adjust_max_hp(
                    interaction.user.id, self.char_name, delta_val
                )
                diff = new_max - old_max
                diff_str = f"+{diff}" if diff >= 0 else f"{diff}"
                status_msg = (
                    f"⚙️ **Max HP Adjusted ({diff_str}):**\n"
                    f"• HP Updated: `{old_cur}/{old_max}` ➔ `{new_cur}/{new_max}`"
                )
        except ValueError:
            await interaction.response.send_message("❌ Invalid number entered. Please enter an integer (like `+5`, `-2`, or `20`).", ephemeral=True)
            return

        view = await ManageMaxHPView.build(
            self.bot, interaction, self.db_manager, self.char_name, status_note=status_msg
        )
        await interaction.response.edit_message(view=view)


class CustomAdjustMaxHPButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(
            label="Custom Increase / Decrease / Set",
            style=discord.ButtonStyle.secondary,
            emoji="⚙️",
            custom_id="custom_adj_max_hp_btn"
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        modal = CustomMaxHPModal(
            self.parent_view.bot,
            self.parent_view.db_manager,
            self.parent_view.char_name,
            self.parent_view.max_hp
        )
        await interaction.response.send_modal(modal)


class ManageMaxHPView(discord.ui.LayoutView):
    @classmethod
    async def build(cls, bot, interaction: discord.Interaction, db_manager, char_name: str, status_note: Optional[str] = None):
        current_hp, max_hp = await db_manager.get_hp(interaction.user.id, char_name)
        display_name = await db_manager.get_char_display_name(char_name)
        bracket_info = db_manager.get_potential_hp_bracket(max_hp)
        swing = await db_manager.get_swing(interaction.user.id, char_name)
        return cls(
            bot=bot,
            user_id=interaction.user.id,
            db_manager=db_manager,
            char_name=char_name,
            display_name=display_name,
            current_hp=current_hp,
            max_hp=max_hp,
            bracket_info=bracket_info,
            status_note=status_note,
            swing=swing
        )

    def __init__(self, bot, user_id: int, db_manager, char_name: str, display_name: str, current_hp: int, max_hp: int, bracket_info: dict, status_note: Optional[str] = None, swing: Optional[tuple] = None):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.db_manager = db_manager
        self.char_name = char_name
        self.display_name = display_name
        self.current_hp = current_hp
        self.max_hp = max_hp
        self.bracket_info = bracket_info

        lines = [
            f"**Character:** *{display_name}*",
            f"### ❤️ Current Health: `{current_hp} / {max_hp} HP`\n"
        ]
        if status_note:
            lines.append(f"{status_note}\n")

        lines.append(
            "### 📈 Sentiment Level-Up Brackets (Per 1 Potential Spent)\n"
            "• **10–19 Max HP:** `+5 HP` (Default) or `1d6 + 1` (Rolled)\n"
            "• **20–39 Max HP:** `+3 HP` (Default) or `1d6` (Rolled)\n"
            "• **40–59 Max HP:** `+2 HP` (Default) or `1d6 - 1` (Rolled)\n"
            "• **60+ Max HP:** `+1 HP` (Default only)\n\n"
            f"👉 **Your Active Bracket ({bracket_info['bracket']} Max HP):** "
            f"**+{bracket_info['flat_gain']} HP** flat or **{bracket_info['roll_label']}** rolled.\n"
            "-# Note: Increasing Max HP also increases Current HP by the same amount."
        )

        container = discord.ui.Container(
            discord.ui.TextDisplay(content="## ❤️ **Manage Max HP**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content="\n".join(lines)),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            discord.ui.ActionRow(
                PotentialFlatHPButton(self, bracket_info["flat_gain"]),
                PotentialRollHPButton(self, bracket_info),
                CustomAdjustMaxHPButton(self)
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            discord.ui.ActionRow(
                BackToCharacterCardButton(self.bot, self.db_manager, self.char_name),
                CloseMenuButton()
            ),
            accent_color=get_swing_accent_color(swing)
        )
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("❌ This HP menu is not for you.", ephemeral=True)
        return False


class HPActionResultView(discord.ui.LayoutView):
    def __init__(self, display_name: str, action_type: str, amount: int, old_hp: int, new_hp: int, max_hp: int, total_attrs: int = 3, wounded_count: int = 0, swing: Optional[tuple] = None):
        super().__init__(timeout=300)
        if action_type == "heal":
            title = "💚 **Character Healed**"
            actual_healed = new_hp - old_hp
            lines = [
                f"**Character:** *{display_name}*",
                f"**Healing Applied:** `+{amount} HP` (*Restored {actual_healed} HP*)",
                f"### ❤️ HP: `{old_hp} / {max_hp}` ➔ **`{new_hp} / {max_hp}`**"
            ]
            if new_hp == max_hp:
                lines.append("-# Character is at Maximum HP!")
        else:
            title = "💥 **Damage Sustained**"
            actual_dmg = old_hp - new_hp
            lines = [
                f"**Character:** *{display_name}*",
                f"**Damage Taken:** `-{amount} HP` (*Lost {actual_dmg} HP*)",
                f"### ❤️ HP: `{old_hp} / {max_hp}` ➔ **`{new_hp} / {max_hp}`**"
            ]
            if new_hp == 0:
                if total_attrs > 0 and wounded_count >= total_attrs:
                    lines.append(
                        "\n### 💀 **0 HP & ALL ATTRIBUTES WOUNDED — DEATH / LEAVE THE SCENE!**\n"
                        "• All of your character's Attributes are already **Wounded** and your HP has reached **0**.\n"
                        "• Per Sentiment rules, your character either **dies** or must choose to **Leave the Scene** (fleeing or passing out so you can no longer sustain further damage in this Scene/Conflict)."
                    )
                else:
                    lines.append(
                        "\n### ⚠️ **0 HP REACHED — SUSTAINED A WOUND!**\n"
                        "• Hitting **0 HP** causes your character to sustain a **Wound**!\n"
                        "• **Next Steps:**\n"
                        "  1. Run **`/wound_die`** to choose an Attribute die to Wound *(automatically unlocks all locked dice)*.\n"
                        "  2. Run **`/roll_to_recover`** to roll your unwounded dice and determine your new Current HP!\n"
                        "• 🛡️ **Leave the Scene Option:** Whenever you become Wounded in a Scene or Conflict, you may also choose to **Leave the Scene** (fleeing or passing out). You still Wound a die and Roll to Recover as normal, but cannot sustain further damage from this Scene or Conflict."
                    )

        container = discord.ui.Container(
            discord.ui.TextDisplay(content=title),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content="\n".join(lines)),
            accent_color=get_swing_accent_color(swing)
        )
        self.add_item(container)


class CharacterCardView(discord.ui.LayoutView):
    @classmethod
    async def build(cls, bot, interaction: discord.Interaction, db_manager, char_name: str):
        attributes = await db_manager.get_character_attributes(interaction.user.id, char_name)
        attribute_names = await db_manager.get_attribute_names(interaction.user.id, char_name)
        swing = await db_manager.get_swing(interaction.user.id, char_name)
        wounded = await db_manager.get_wounded(interaction.user.id, char_name)
        locked = await db_manager.get_locked(interaction.user.id, char_name)
        all_chars = await db_manager.get_all_characters(interaction.user.id)
        display_name = await db_manager.get_char_display_name(char_name)
        current_hp, max_hp = await db_manager.get_hp(interaction.user.id, char_name)

        return cls(
            bot=bot,
            interaction=interaction,
            db_manager=db_manager,
            char_name=char_name,
            display_name=display_name,
            attributes=attributes,
            attribute_names=attribute_names,
            swing=swing,
            wounded=wounded,
            locked=locked,
            all_chars=all_chars,
            current_hp=current_hp,
            max_hp=max_hp
        )

    def __init__(self, bot, interaction, db_manager, char_name: str, display_name: str, attributes: list, attribute_names: dict, swing: tuple, wounded: list, locked: list, all_chars: list, current_hp: int = 10, max_hp: int = 10):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = interaction.user.id
        self.char_name = char_name

        accent_color = discord.Color.random()
        if swing and swing[0] in COLOR_DISCORD_COLORS:
            accent_color = COLOR_DISCORD_COLORS[swing[0]]

        color_choices = ["Red", "Yellow", "Green", "Blue", "Purple", "Orange", "Grey", "Black", "White", "Clear"]
        sorted_attrs = sorted(attributes, key=lambda row: color_choices.index(row[0]) if row[0] in color_choices else 99)

        attr_lines = []
        if sorted_attrs:
            for color, bonus in sorted_attrs:
                custom_name = attribute_names.get(color, "None")
                tags = []
                if swing and swing[0] == color:
                    tags.append(f"⭐ **SWING** (Die: {swing[1]})")
                if color in locked:
                    tags.append("🔒 **LOCKED**")
                if color in wounded:
                    tags.append("🩸 **WOUNDED**")
                
                status_str = f" [{', '.join(tags)}]" if tags else ""
                emoji = COLOR_EMOJIS.get(color, "⚪")
                attr_lines.append(f"• {emoji} **{color}** (*{custom_name}*) ➔ **Bonus:** +{bonus}{status_str}")
        else:
            attr_lines.append("• *No attributes set*")

        attrs_text = "\n".join(attr_lines)

        if swing:
            swing_color, swing_val = swing
            custom_name = attribute_names.get(swing_color, "None")
            swing_bonus = next((b for c, b in attributes if c == swing_color), 0)
            swing_text = f"{COLOR_EMOJIS.get(swing_color, '⚪')} **{swing_color}** (*{custom_name}*) | Die Value: **{swing_val}** (+{swing_bonus} bonus = **{swing_val + swing_bonus}**)"
        else:
            swing_text = "None"

        if locked:
            locked_text = ", ".join(f"{COLOR_EMOJIS.get(c, '⚪')} **{c}**" for c in locked)
        else:
            locked_text = "None"

        if wounded:
            wounded_text = ", ".join(f"{COLOR_EMOJIS.get(c, '⚪')} **{c}**" for c in wounded)
        else:
            wounded_text = "None"

        if current_hp == 0:
            if sorted_attrs and len(wounded) >= len(sorted_attrs):
                hp_status = f"💀 **`{current_hp} / {max_hp} HP`** *(0 HP & All Dice Wounded — Death / Leave the Scene!)*"
            else:
                hp_status = f"⚠️ **`{current_hp} / {max_hp} HP`** *(0 HP — Wounded! Use `/wound_die` & `/roll_to_recover`)*"
        else:
            hp_status = f"❤️ **`{current_hp} / {max_hp} HP`**"

        body = (
            f"**Player:** <@{interaction.user.id}>\n"
            f"**Character:** *{display_name}*\n"
            f"**Health (HP):** {hp_status}\n\n"
            f"### 🎯 Active Swing\n{swing_text}\n\n"
            f"### 📊 Attributes & Bonuses\n{attrs_text}\n\n"
            f"### 🔒 Locked Dice\n{locked_text}\n\n"
            f"### 🩸 Wounded Dice\n{wounded_text}"
        )

        container = discord.ui.Container(
            discord.ui.TextDisplay(content="## 📜 **Character Card**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=body),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            discord.ui.TextDisplay(content="Switch active character:"),
            discord.ui.ActionRow(ChangeCardCharSelect(self.bot, db_manager, all_chars, active_char=self.char_name)),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            discord.ui.ActionRow(
                ManageMaxHPButton(self.bot, db_manager, self.char_name),
                CloseMenuButton()
            ),
            accent_color=accent_color
        )
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("❌ This character card is not for you.", ephemeral=True)
        return False


class WoundDieModal(discord.ui.Modal):
    def __init__(self, bot, db_manager, char_name: str, available_attrs: list, attr_names: dict):
        super().__init__(title=f"Wound Die: {char_name[:30]}")
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name

        options = [
            discord.SelectOption(
                label=f"{color} ({attr_names.get(color, 'None')})",
                value=color,
                emoji=COLOR_EMOJIS.get(color, "⚪")
            )
            for color, bonus in available_attrs
        ]
        self.color_select = discord.ui.Select(
            options=options,
            min_values=1,
            max_values=1,
            placeholder="Select attribute to wound..."
        )
        self.add_item(discord.ui.Label(text=f"Wounding die for {char_name}", component=self.color_select))

    async def on_submit(self, interaction: discord.Interaction):
        chosen_color = self.color_select.values[0]
        await self.db_manager.wound_die(interaction.user.id, self.char_name, chosen_color)
        view = await CharacterCardView.build(self.bot, interaction, self.db_manager, self.char_name)
        await interaction.response.send_message(view=view)


class UnwoundDieModal(discord.ui.Modal):
    def __init__(self, bot, db_manager, char_name: str, wounded_colors: list, attr_names: dict):
        super().__init__(title=f"Unwound Die: {char_name[:30]}")
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name

        options = [
            discord.SelectOption(
                label=f"Heal {color} ({attr_names.get(color, 'None')})",
                value=color,
                emoji=COLOR_EMOJIS.get(color, "⚪")
            )
            for color in wounded_colors
        ]
        self.color_select = discord.ui.Select(
            options=options,
            min_values=1,
            max_values=1,
            placeholder="Select attribute to heal/unwound..."
        )
        self.add_item(discord.ui.Label(text=f"Healing die for {char_name}", component=self.color_select))

    async def on_submit(self, interaction: discord.Interaction):
        chosen_color = self.color_select.values[0]
        await self.db_manager.unwound_die(interaction.user.id, self.char_name, chosen_color)
        view = await CharacterCardView.build(self.bot, interaction, self.db_manager, self.char_name)
        await interaction.response.send_message(view=view)


class LockDieModal(discord.ui.Modal):
    def __init__(self, bot, db_manager, char_name: str, lockable_attrs: list, attr_names: dict):
        super().__init__(title=f"Lock Die: {char_name[:30]}")
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name

        options = [
            discord.SelectOption(
                label=f"{color} ({attr_names.get(color, 'None')})",
                value=color,
                emoji=COLOR_EMOJIS.get(color, "⚪")
            )
            for color, bonus in lockable_attrs
        ]
        self.color_select = discord.ui.Select(
            options=options,
            min_values=1,
            max_values=1,
            placeholder="Select attribute to lock..."
        )
        self.add_item(discord.ui.Label(text=f"Locking die for {char_name}", component=self.color_select))

    async def on_submit(self, interaction: discord.Interaction):
        chosen_color = self.color_select.values[0]
        await self.db_manager.lock_die(interaction.user.id, self.char_name, chosen_color)
        view = await CharacterCardView.build(self.bot, interaction, self.db_manager, self.char_name)
        await interaction.response.send_message(view=view)


class UnlockDieModal(discord.ui.Modal):
    def __init__(self, bot, db_manager, char_name: str, locked_colors: list, attr_names: dict):
        super().__init__(title=f"Unlock Die: {char_name[:30]}")
        self.bot = bot
        self.db_manager = db_manager
        self.char_name = char_name

        options = [
            discord.SelectOption(
                label=f"Unlock {color} ({attr_names.get(color, 'None')})",
                value=color,
                emoji=COLOR_EMOJIS.get(color, "⚪")
            )
            for color in locked_colors
        ]
        self.color_select = discord.ui.Select(
            options=options,
            min_values=1,
            max_values=1,
            placeholder="Select attribute to unlock..."
        )
        self.add_item(discord.ui.Label(text=f"Unlocking die for {char_name}", component=self.color_select))

    async def on_submit(self, interaction: discord.Interaction):
        chosen_color = self.color_select.values[0]
        await self.db_manager.unlock_die(interaction.user.id, self.char_name, chosen_color)
        view = await CharacterCardView.build(self.bot, interaction, self.db_manager, self.char_name)
        await interaction.response.send_message(view=view)


class SupportDieModal(discord.ui.Modal):
    def __init__(self, bot, db_manager, sender_char: str, target_user: discord.User | discord.Member, target_char: str, available_attrs: list, attr_names: dict):
        super().__init__(title="Send Support Die")
        self.bot = bot
        self.db_manager = db_manager
        self.sender_char = sender_char
        self.target_user = target_user
        self.target_char = target_char
        self.attr_names = attr_names

        options = [
            discord.SelectOption(
                label=f"{color} ({attr_names.get(color, 'None')})",
                value=color,
                emoji=COLOR_EMOJIS.get(color, "⚪")
            )
            for color, bonus in available_attrs
        ]
        self.color_select = discord.ui.Select(
            options=options,
            min_values=1,
            max_values=1,
            placeholder="Select attribute to share as support..."
        )
        self.add_item(discord.ui.Label(text=f"Send support to {target_user.display_name} ({target_char})", component=self.color_select))

    async def on_submit(self, interaction: discord.Interaction):
        chosen_color = self.color_select.values[0]
        attr_name = self.attr_names.get(chosen_color, "None")
        await self.db_manager.add_support_die(
            share_user_id=interaction.user.id,
            share_char=self.sender_char,
            recv_user_id=self.target_user.id,
            recv_char=self.target_char,
            attribute=chosen_color,
            attribute_name=attr_name
        )
        sender_display = await self.db_manager.get_char_display_name(self.sender_char)
        target_display = await self.db_manager.get_char_display_name(self.target_char)
        swing = await self.db_manager.get_swing(interaction.user.id, self.sender_char)
        emoji = COLOR_EMOJIS.get(chosen_color, "⚪")

        view = discord.ui.LayoutView()
        container = discord.ui.Container(
            discord.ui.TextDisplay(content="## 🤝 **Support Die Sent!**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                content=f"**<@{interaction.user.id}>** (*{sender_display}*) sent their {emoji} **{chosen_color}** (*{attr_name}*) die to support **<@{self.target_user.id}>** (*{target_display}*)!\n\n"
                        f"• An extra +1d6 is now available on {target_display}'s next Roll to Dye or Roll to Do.\n"
                        f"• When used, the die will automatically return to {sender_display} **locked**."
            ),
            accent_color=get_swing_accent_color(swing)
        )
        view.add_item(container)
        await interaction.response.send_message(view=view)


class SetSwingModal(discord.ui.Modal):
    def __init__(self, roll_view, available_dice: list):
        super().__init__(title="Choose Your Swing Attribute")
        self.roll_view = roll_view

        options = [
            discord.SelectOption(
                label=f"{d['color']} (Rolled: {d['roll']}, Bonus: +{d['bonus']})",
                value=d['color'],
                emoji=COLOR_EMOJIS.get(d['color'], "⚪")
            )
            for d in available_dice
        ]
        self.color_select = discord.ui.Select(
            options=options,
            min_values=1,
            max_values=1,
            placeholder="Select an attribute to make your Swing..."
        )
        self.add_item(discord.ui.Label(text="Select Swing Attribute", component=self.color_select))

    async def on_submit(self, interaction: discord.Interaction):
        chosen_color = self.color_select.values[0]
        await self.roll_view.update_swing(chosen_color, interaction)


class SetSwingButton(discord.ui.Button):
    def __init__(self, roll_view):
        super().__init__(label="Set Swing", style=discord.ButtonStyle.primary, custom_id="set_swing_btn")
        self.roll_view = roll_view

    async def callback(self, interaction: discord.Interaction):
        modal = SetSwingModal(self.roll_view, self.roll_view.get_swing_choices())
        await interaction.response.send_modal(modal)


class ApplySupportDieButton(discord.ui.Button):
    def __init__(self, roll_view):
        super().__init__(label="Apply Support Die (+1d6)", style=discord.ButtonStyle.success, custom_id="apply_support_btn")
        self.roll_view = roll_view

    async def callback(self, interaction: discord.Interaction):
        await self.roll_view.apply_support_die(interaction)


class RollToDyeView(discord.ui.LayoutView):
    def __init__(self, bot, user_id: int, char_name: str, display_name: str, rolled_dice: list, swing_info: tuple, pending_support: list, db_manager):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.char_name = char_name
        self.display_name = display_name
        self.rolled_dice = rolled_dice  # list of dicts: {'color', 'name', 'roll', 'bonus', 'is_swing'}
        self.swing_info = swing_info    # (swing_color, swing_val, swing_bonus) or None
        self.pending_support = pending_support  # list of dicts from support_die
        self.support_rolls = []         # applied support dice
        self.db_manager = db_manager
        self.render_view()

    def get_swing_choices(self) -> list:
        return self.rolled_dice

    def render_view(self):
        self.clear_items()

        # Recalculate total
        total = 0
        dice_lines = []
        for d in self.rolled_dice:
            emoji = COLOR_EMOJIS.get(d['color'], "⚪")
            custom_name = d.get('name', 'None')
            if d.get('is_swing'):
                subtotal = d['roll'] + d['bonus']
                total += subtotal
                dice_lines.append(f"• {emoji} **{d['color']}** (*{custom_name}*): **{d['roll']}** (+{d['bonus']} Bonus) ⭐ **[SWING]**")
            else:
                total += d['roll']
                dice_lines.append(f"• {emoji} **{d['color']}** (*{custom_name}*): **{d['roll']}**")

        for s in self.support_rolls:
            total += s['roll']
            emoji = COLOR_EMOJIS.get(s['color'], "⚪")
            dice_lines.append(f"• 🤝 Support Die ({emoji} **{s['color']}** from *{s['from_char']}*): **{s['roll']}**")

        body_lines = [
            f"**Character:** *{self.display_name}*\n",
            "### 🎲 Rolled Attribute Dice",
            "\n".join(dice_lines),
            f"\n### 📊 **Total Roll: {total}**"
        ]

        if self.support_rolls:
            notes = [f"-# Support die from *{s['from_char']}* used and returned locked." for s in self.support_rolls]
            body_lines.append("\n" + "\n".join(notes))

        accent_color = discord.Color.random()
        if self.swing_info and self.swing_info[0] in COLOR_DISCORD_COLORS:
            accent_color = COLOR_DISCORD_COLORS[self.swing_info[0]]

        container = discord.ui.Container(
            discord.ui.TextDisplay(content=f"## 🎲 **Roll to Dye**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content="\n".join(body_lines)),
            accent_color=accent_color
        )

        action_buttons = [SetSwingButton(self)]
        if self.pending_support:
            action_buttons.append(ApplySupportDieButton(self))

        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(discord.ui.ActionRow(*action_buttons))
        self.add_item(container)

    async def update_swing(self, chosen_color: str, interaction: discord.Interaction):
        matching_die = next((d for d in self.rolled_dice if d['color'] == chosen_color), None)
        if not matching_die:
            await interaction.response.send_message("❌ Selected attribute not found in roll.", ephemeral=True)
            return

        await self.db_manager.set_swing(self.user_id, self.char_name, chosen_color, matching_die['roll'])
        self.swing_info = (chosen_color, matching_die['roll'], matching_die['bonus'])

        for d in self.rolled_dice:
            d['is_swing'] = (d['color'] == chosen_color)

        self.render_view()
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            await interaction.response.send_message(view=self)

    async def apply_support_die(self, interaction: discord.Interaction):
        if not self.pending_support:
            await interaction.response.send_message("❌ No support dice available to apply.", ephemeral=True)
            return

        item = self.pending_support.pop(0)
        roll_val = random.randint(1, 6)
        self.support_rolls.append({
            "color": item["attribute"],
            "name": item["attribute_name"],
            "from_char": item["share_char_name"],
            "from_user_id": item["share_user_id"],
            "roll": roll_val
        })

        await self.db_manager.consume_support_die(
            share_user_id=item["share_user_id"],
            share_char=item["share_char_name"],
            recv_user_id=self.user_id,
            recv_char=self.char_name,
            attribute=item["attribute"]
        )

        self.render_view()
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            await interaction.response.send_message(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("❌ This roll is not yours to modify.", ephemeral=True)
        return False


class RollToDoView(discord.ui.LayoutView):
    def __init__(self, bot, user_id: int, char_name: str, display_name: str, swing_info: tuple, d20_roll: int, d6_wild: int, pending_support: list, db_manager):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.char_name = char_name
        self.display_name = display_name
        self.swing_info = swing_info  # (color, custom_name, swing_val, bonus) or None
        self.d20_roll = d20_roll
        self.d6_wild = d6_wild
        self.pending_support = pending_support
        self.support_rolls = []
        self.db_manager = db_manager
        self.render_view()

    def render_view(self):
        self.clear_items()

        crit_text = " 💥 **CRITICAL HIT!**" if self.d20_roll == 20 else ""
        if self.swing_info:
            color, custom_name, swing_val, bonus = self.swing_info
            emoji = COLOR_EMOJIS.get(color, "⚪")
            swing_total = swing_val + bonus
            base_total = self.d20_roll + swing_total
            total = base_total + sum(s['roll'] for s in self.support_rolls)

            lines = [
                f"*{self.display_name}* rolled for {emoji} **{color}** (*{custom_name}*)\n",
                f"• **d20 Die Roll:** **{self.d20_roll}**{crit_text}",
                f"• **Active Swing:** **{swing_val}** (+{bonus} Attribute Bonus = **{swing_total}**)"
            ]
            accent_color = COLOR_DISCORD_COLORS.get(color, discord.Color.random())
        else:
            base_total = self.d20_roll + self.d6_wild
            total = base_total + sum(s['roll'] for s in self.support_rolls)
            lines = [
                f"*{self.display_name}* rolled to do (Wild / Colorless)\n",
                f"• **d20 Die Roll:** **{self.d20_roll}**{crit_text}",
                f"• **1d6 Wild Roll:** **+{self.d6_wild}**"
            ]
            accent_color = discord.Color.random()

        for s in self.support_rolls:
            emoji = COLOR_EMOJIS.get(s['color'], "⚪")
            lines.append(f"• 🤝 Support Die ({emoji} **{s['color']}** from *{s['from_char']}*): **+{s['roll']}**")

        lines.append(f"\n### 📊 **Total Roll: {total}**")

        if self.support_rolls:
            notes = [f"-# Support die from *{s['from_char']}* used and returned locked." for s in self.support_rolls]
            lines.append("\n" + "\n".join(notes))

        container = discord.ui.Container(
            discord.ui.TextDisplay(content="## 🎯 **Roll to Do**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content="\n".join(lines)),
            accent_color=accent_color
        )

        if self.pending_support:
            container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
            container.add_item(discord.ui.ActionRow(ApplySupportDieButton(self)))

        self.add_item(container)

    async def apply_support_die(self, interaction: discord.Interaction):
        if not self.pending_support:
            await interaction.response.send_message("❌ No support dice available to apply.", ephemeral=True)
            return

        item = self.pending_support.pop(0)
        roll_val = random.randint(1, 6)
        self.support_rolls.append({
            "color": item["attribute"],
            "name": item["attribute_name"],
            "from_char": item["share_char_name"],
            "from_user_id": item["share_user_id"],
            "roll": roll_val
        })

        await self.db_manager.consume_support_die(
            share_user_id=item["share_user_id"],
            share_char=item["share_char_name"],
            recv_user_id=self.user_id,
            recv_char=self.char_name,
            attribute=item["attribute"]
        )

        self.render_view()
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            await interaction.response.send_message(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("❌ This roll is not yours to modify.", ephemeral=True)
        return False


class RollToRecoverView(discord.ui.LayoutView):
    def __init__(self, bot, user_id: int, char_name: str, display_name: str, rolled_dice: list, swing_info: tuple, db_manager, old_hp: int = 10, new_hp: int = 10, max_hp: int = 10):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.char_name = char_name
        self.display_name = display_name
        self.rolled_dice = rolled_dice  # list of dicts: {'color', 'name', 'roll', 'bonus'}
        self.swing_info = swing_info    # (swing_color, swing_val, swing_bonus) or None
        self.db_manager = db_manager
        self.old_hp = old_hp
        self.new_hp = new_hp
        self.max_hp = max_hp
        self.render_view()

    def get_swing_choices(self) -> list:
        return self.rolled_dice

    def render_view(self):
        self.clear_items()

        if self.rolled_dice:
            dice_lines = []
            total_roll = 0
            for d in self.rolled_dice:
                emoji = COLOR_EMOJIS.get(d['color'], "⚪")
                custom_name = d.get('name', 'None')
                subtotal = d['roll'] + d['bonus']
                total_roll += subtotal
                is_swing_mark = " ⭐ **[NEW SWING]**" if self.swing_info and self.swing_info[0] == d['color'] else ""
                dice_lines.append(f"• {emoji} **{d['color']}** (*{custom_name}*): Die **{d['roll']}** + Bonus **+{d['bonus']}** = **{subtotal}**{is_swing_mark}")
            dice_text = "\n".join(dice_lines)
        else:
            dice_text = "• *All attributes are wounded! Recovering base minimal +1 HP.*"
            total_roll = 1

        if not self.rolled_dice:
            recovery_rule_note = f"• **No Unwounded Dice Left:** Gained **+1 HP** (`{self.old_hp}` + `1` ➔ `{self.new_hp} / {self.max_hp}`)"
        elif self.old_hp <= 0:
            recovery_rule_note = f"• **Recovering from 0 HP:** Roll total (**{total_roll}**) sets your new Current HP (`0` ➔ `{self.new_hp} / {self.max_hp}`)"
        else:
            recovery_rule_note = f"• **Resting with Remaining HP (`{self.old_hp} HP`):** Roll total (**+{total_roll}**) added to Current HP (`{self.old_hp}` + `{total_roll}` ➔ `{self.new_hp} / {self.max_hp}`)"

        lines = [
            f"**Character:** *{self.display_name}*\n",
            "🔓 *All previously locked dice have been unlocked!*\n",
            "### 💚 Recovery Roll Breakdown",
            dice_text,
            f"\n### ❤️ **HP Updated: `{self.old_hp} / {self.max_hp}` ➔ `{self.new_hp} / {self.max_hp} HP`**",
            recovery_rule_note,
            "-# Note: Total current HP cannot exceed your character's Maximum HP."
        ]

        accent_color = get_swing_accent_color(self.swing_info)

        container = discord.ui.Container(
            discord.ui.TextDisplay(content="## 💚 **Roll to Recover**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content="\n".join(lines)),
            accent_color=accent_color
        )

        if self.rolled_dice:
            container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
            container.add_item(discord.ui.ActionRow(SetSwingButton(self)))

        self.add_item(container)

    async def update_swing(self, chosen_color: str, interaction: discord.Interaction):
        matching_die = next((d for d in self.rolled_dice if d['color'] == chosen_color), None)
        if not matching_die:
            await interaction.response.send_message("❌ Selected attribute not found in roll.", ephemeral=True)
            return

        await self.db_manager.set_swing(self.user_id, self.char_name, chosen_color, matching_die['roll'])
        self.swing_info = (chosen_color, matching_die['roll'], matching_die['bonus'])

        self.render_view()
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            await interaction.response.send_message(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("❌ This roll is not yours to modify.", ephemeral=True)
        return False

