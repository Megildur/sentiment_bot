import discord
from .Constants import COLOR_EMOJIS

MODAL_COLOR_EMOJIS = COLOR_EMOJIS.copy()
MODAL_COLOR_EMOJIS["Grey"] = "🔘"

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
        
        result = [(c, b) for c, b in attributes]
        
        all_chars = await self.db_manager.get_all_characters(interaction.user.id)
        
        view = AttributeSetView(self.bot, interaction, self.db_manager, char_name=char_name, result=result, all_chars=all_chars, is_new=True)
        
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
        
        return cls(
            bot=bot, 
            interaction=interaction, 
            db_manager=db_manager, 
            char_name=char_name, 
            result=result, 
            all_chars=all_chars, 
            attribute_names=attribute_names, 
            is_new=is_new
        )

    def __init__(self, bot, interaction, db_manager, char_name: str, result: list, all_chars: list, attribute_names: dict = None, is_new: bool = False):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = interaction.user.id
        self.char_name = char_name

        attribute_names = attribute_names or {}

        title = "## **✅ Attributes and bonuses are set!**" if is_new else "## **⚠️ Attributes and bonuses are already set!**"
        
        color_choices = ["Red", "Yellow", "Green", "Blue", "Purple", "Orange", "Grey", "Black", "White", "Clear"]
        
        results = sorted(result, key=lambda row: color_choices.index(row[0]) if row[0] in color_choices else 99)
        
        body_lines = [f"### 📊 {interaction.user.display_name}'s Attribute Breakdown \n**Character Name:** *{self.char_name}*"]
        for i, row in enumerate(results, start=1):
            color = row[0]
            bonus = row[1]
            
            custom_name = attribute_names.get(color)
            display_name = f"{color} (**Attribute Name:** *{custom_name}*)" if custom_name else color
            
            body_lines.append(f"• **Slot {i}:** {COLOR_EMOJIS.get(color, '⚪')} {display_name} ➔ **Bonus:** +{bonus}")
        
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
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            discord.ui.TextDisplay(content="Select a character here to delete it!"),
            discord.ui.ActionRow(DeleteCharSelect(self.bot, db_manager, all_chars, active_char=self.char_name)),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            discord.ui.Section(
                discord.ui.TextDisplay("Press this button to close this menu"),
                accessory=CloseMenuButton()
            ),
            accent_color=discord.Color.random()
        )
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
            
        super().__init__(placeholder="Select an attribute to edit...", min_values=1, max_values=1, options=options)

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
        
        super().__init__(placeholder="Switch active character...", min_values=1, max_values=1, options=options)

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
        super().__init__(placeholder="Delete a character permanently...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        char_to_delete = self.values[0]
        view = ConfirmDeleteCharView(self.bot, self.db_manager, char_to_delete, self.active_char)
        await interaction.response.edit_message(view=view)

class CancelDeleteButton(discord.ui.Button):
    def __init__(self, bot, db_manager, active_char: str):
        super().__init__(label="Cancel", style=discord.ButtonStyle.secondary)
        self.bot = bot
        self.db_manager = db_manager
        self.active_char = active_char

    async def callback(self, interaction: discord.Interaction):
        view = await AttributeSetView.build(self.bot, interaction, self.db_manager, char_name=self.active_char)
        await interaction.response.edit_message(content=None, view=view)

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
        
        if self.char_to_delete == self.active_char:
            if not all_chars:
                await interaction.response.edit_message(
                    content="⚠️ You have no characters left. Use `/set_attributes` to create a new one.", 
                    view=None
                )
            else:
                view = SelectNewActiveCharView(self.bot, self.db_manager, all_chars, deleted_char=self.char_to_delete)
                await interaction.response.edit_message(content=None, view=view)
        else:
            view = await AttributeSetView.build(self.bot, interaction, self.db_manager, char_name=self.active_char)
            await interaction.response.edit_message(content=None, view=view)

class ConfirmDeleteCharView(discord.ui.LayoutView):
    def __init__(self, bot, db_manager, char_to_delete: str, active_char: str):
        super().__init__(timeout=300)
        
        container = discord.ui.Container(
            discord.ui.TextDisplay(content=f"## **⚠️ Delete {char_to_delete}?**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(content=f"Are you sure you want to permanently delete **{char_to_delete}**? This action cannot be undone."),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            
            discord.ui.ActionRow(
                CancelDeleteButton(bot, db_manager, active_char),
                ConfirmDeleteButton(bot, db_manager, char_to_delete, active_char)
            )
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
        await interaction.response.edit_message(content=None, view=view)

class SelectNewActiveCharView(discord.ui.LayoutView):
    def __init__(self, bot, db_manager, all_chars: list, deleted_char: str = None):
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
            )
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
        
        result = await self.db_manager.check_attributes(self.bot, interaction, self.char_name)
        all_chars = await self.db_manager.get_all_characters(interaction.user.id)
        attribute_names = await self.db_manager.get_attribute_names(interaction.user.id, self.char_name)
        
        view = AttributeSetView(self.bot, interaction, self.db_manager, char_name=self.char_name, result=result, all_chars=all_chars, attribute_names=attribute_names, is_new=True)
        
        try:
            await interaction.response.edit_message(view=view)
        except discord.HTTPException:
            await interaction.response.send_message(view=view)
