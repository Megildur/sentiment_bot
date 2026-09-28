from __future__ import annotations
from typing import List, Optional, Any, Sequence, Union
import re

import discord
from discord.abc import Messageable


class ButtonPaginator(discord.ui.LayoutView):
    
    def __init__(
        self,
        pages: Optional[Sequence[discord.ui.Container]] = None,
        *,
        author_id: Optional[int] = None,
        timeout: Optional[float] = None,
        loop: bool = False,
        custom_buttons: Optional[List[discord.ui.Button]] = None,
    ) -> None:
        super().__init__(timeout=timeout)
        self.message: Optional[Union[discord.Message, discord.WebhookMessage]] = None
        self.author_id: Optional[int] = author_id
        self.current_page: int = 0
        self.pages = list(pages) if pages is not None else []
        self.max_pages = len(self.pages)
        self.loop: bool = loop
        self.custom_buttons = custom_buttons or []

        self.prev_btn = self._create_previous_button()
        self.indicator_btn = self._create_page_indicator()
        self.next_btn = self._create_next_button()

    def _create_previous_button(self) -> discord.ui.Button:
        button = discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary, custom_id="paginator_prev")
        button.callback = self._previous_callback
        return button

    def _create_next_button(self) -> discord.ui.Button:
        button = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary, custom_id="paginator_next")
        button.callback = self._next_callback
        return button

    def _create_page_indicator(self) -> discord.ui.Button:
        button = discord.ui.Button(style=discord.ButtonStyle.primary, disabled=True, custom_id="paginator_indicator")
        button.callback = self._indicator_callback
        return button

    @staticmethod
    def _find_component_by_custom_id(items: Sequence[Any], custom_id: str) -> Optional[Any]:
        for item in items:
            if getattr(item, "custom_id", None) == custom_id or (isinstance(item, dict) and item.get("custom_id") == custom_id):
                return item
            children = getattr(item, "children", None)
            if children is None and isinstance(item, dict):
                children = item.get("components")
            if children:
                found = ButtonPaginator._find_component_by_custom_id(children, custom_id)
                if found:
                    return found
        return None

    def _sync_page_from_message(self, message: Optional[discord.Message]) -> None:
        if not self.pages:
            from Source.Cogs.Dice.HelpPages import get_help_pages
            self.pages = get_help_pages()
            self.max_pages = len(self.pages)
        if not message:
            return
        btn = self._find_component_by_custom_id(getattr(message, "components", []), "paginator_indicator")
        if btn:
            label = getattr(btn, "label", None) or (btn.get("label") if isinstance(btn, dict) else None)
            if label:
                match = re.search(r"Page\s+(\d+)/(\d+)", label)
                if match:
                    self.current_page = max(0, min(int(match.group(1)) - 1, self.max_pages - 1))

    def _render(self) -> None:
        self.clear_items()

        if not self.pages:
            from Source.Cogs.Dice.HelpPages import get_help_pages
            self.pages = get_help_pages()
            self.max_pages = len(self.pages)

        if not self.pages:
            return

        self.current_page = max(0, min(self.current_page, self.max_pages - 1))
        container = self.pages[self.current_page]

        items_to_remove = [
            child for child in container.children 
            if getattr(child, "_is_paginator_injected", False)
        ]
        
        for item in items_to_remove:
            try:
                container.remove_item(item)
            except AttributeError:
                container.children.remove(item)

        if self.max_pages > 1 or self.custom_buttons:
            self.update_buttons()
            
            sep = discord.ui.Separator(spacing=discord.SeparatorSpacing.large)
            sep._is_paginator_injected = True
            self._safe_add_to_container(container, sep)
            if self.max_pages > 1:
                page_row = discord.ui.ActionRow(self.prev_btn, self.indicator_btn, self.next_btn)
                page_row._is_paginator_injected = True
                self._safe_add_to_container(container, page_row)

            if self.custom_buttons:
                custom_row = discord.ui.ActionRow(*self.custom_buttons)
                custom_row._is_paginator_injected = True
                self._safe_add_to_container(container, custom_row)
                
        self.add_item(container)

    def _safe_add_to_container(self, container: discord.ui.Container, item: discord.ui.Item) -> None:
        try:
            container.add_item(item)
        except AttributeError:
            container.children.append(item)

    def update_buttons(self) -> None:
        self.prev_btn.disabled = not self.loop and self.current_page == 0
        self.next_btn.disabled = not self.loop and self.current_page == self.max_pages - 1
        self.indicator_btn.label = f"Page {self.current_page + 1}/{self.max_pages}"

    async def _previous_callback(self, interaction: discord.Interaction) -> None:
        self._sync_page_from_message(interaction.message)
        if self.loop:
            self.current_page = self.max_pages - 1 if self.current_page <= 0 else self.current_page - 1
        else:
            if self.current_page > 0:
                self.current_page -= 1
        await self.update_page(interaction)

    async def _next_callback(self, interaction: discord.Interaction) -> None:
        self._sync_page_from_message(interaction.message)
        if self.loop:
            self.current_page = 0 if self.current_page >= self.max_pages - 1 else self.current_page + 1
        else:
            if self.current_page < self.max_pages - 1:
                self.current_page += 1
        await self.update_page(interaction)

    async def _indicator_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.author_id:
            return True

        if self.author_id != interaction.user.id:
            await interaction.response.send_message("You cannot interact with this menu.", ephemeral=True)
            return False

        return True

    async def update_page(self, interaction: discord.Interaction) -> None:
        self._render()
        await interaction.response.edit_message(view=self)

    async def start(
        self, obj: Union[discord.Interaction, Messageable], **send_kwargs: Any
    ) -> Optional[Union[discord.Message, discord.WebhookMessage]]:
        self._render()
        
        if isinstance(obj, discord.Interaction):
            if obj.response.is_done():
                self.message = await obj.followup.send(view=self, **send_kwargs)
            else:
                await obj.response.send_message(view=self, **send_kwargs)
                self.message = await obj.original_response()
        elif isinstance(obj, Messageable):
            self.message = await obj.send(view=self, **send_kwargs)
        else:
            raise TypeError(f"Expected Interaction or Messageable, got {obj.__class__.__name__}")

        return self.message

    def stop(self) -> None:
        self.message = None
        super().stop()

    @classmethod
    def create_standard_paginator(
        cls,
        pages: Sequence[discord.ui.Container],
        *,
        author_id: Optional[int] = None,
        timeout: Optional[float] = None,
        loop: bool = False,
    ) -> "ButtonPaginator":
        return cls(
            pages,
            author_id=author_id,
            timeout=timeout,
            loop=loop
        )

    @classmethod
    def create_persistent_paginator(cls) -> "ButtonPaginator":
        from Source.Cogs.Dice.HelpPages import get_help_pages
        paginator = cls(
            get_help_pages(),
            author_id=None,
            timeout=None
        )
        paginator._render()
        return paginator